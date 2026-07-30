"""The UIAutomationCore calls a provider is actually made of.

Hand-rolled vtables over stdlib ctypes: one global vtable per interface, one
shell struct per interface per widget, and an address-to-state map that turns
a COM `this` back into the blueprint that answers for it. Every GUID, id and
vtable order is transcribed from the Windows SDK headers, never from memory.
"""

from __future__ import annotations

import ctypes
import struct
from typing import TYPE_CHECKING, Any

from tk_uia._subclass import WindowSubclasses
from tk_uia.annotate import PropId
from tk_uia.provide import (
    Pattern,
    SelectionChange,
    ValueAnswers,
    the_selection_changes_between,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from tk_uia.provide import Blueprint

UiaRootObjectId = -25
_UiaAppendRuntimeId = 3

_ProviderOptions_ServerSideProvider = 0x2

_NavigateDirection_Parent = 0
_NavigateDirection_NextSibling = 1
_NavigateDirection_PreviousSibling = 2
_NavigateDirection_FirstChild = 3
_NavigateDirection_LastChild = 4

_UIA_ExpandCollapsePatternId = 10005
_UIA_ScrollItemPatternId = 10017

_ExpandCollapseState_Collapsed = 0
_ExpandCollapseState_Expanded = 1
_ExpandCollapseState_LeafNode = 3

_THE_EVENT_FOR_EACH_SELECTION_CHANGE = {
    SelectionChange.ADDED: 20010,  # UIA_SelectionItem_ElementAddedToSelectionEventId
    SelectionChange.REMOVED: 20011,  # ...ElementRemovedFromSelectionEventId
    SelectionChange.SELECTED: 20012,  # ...ElementSelectedEventId
}

_UIA_ControlTypePropertyId = 30003
_UIA_NamePropertyId = 30005
_UIA_IsKeyboardFocusablePropertyId = 30009
_UIA_IsEnabledPropertyId = 30010
_UIA_HelpTextPropertyId = 30013
_UIA_IsOffscreenPropertyId = 30022
_UIA_ValueValuePropertyId = 30045
_UIA_FullDescriptionPropertyId = 30159

# Anything absent is still written to MSAA and read back on demand, just never
# announced.
_THE_UIA_PROPERTY_FOR_EACH_PROP: Mapping[PropId, int] = {
    PropId.NAME: _UIA_NamePropertyId,
    PropId.VALUE: _UIA_ValueValuePropertyId,
}

_HRESULT = ctypes.c_long

_S_OK = 0
_E_NOINTERFACE = struct.unpack("i", struct.pack("I", 0x80004002))[0]
_E_FAIL = struct.unpack("i", struct.pack("I", 0x80004005))[0]
# COR_E_INVALIDOPERATION, which UIAutomationCoreApi.h names UIA_E_INVALIDOPERATION.
_UIA_E_INVALIDOPERATION = struct.unpack("i", struct.pack("I", 0x80131509))[0]

_VT_I4 = 3
_VT_BSTR = 8
_VT_BOOL = 11

_IID_IUnknown = "{00000000-0000-0000-C000-000000000046}"
_IID_IRawElementProviderSimple = "{D6DD68D1-86FD-4332-8666-9ABEDEA2D24C}"
_IID_IRawElementProviderFragment = "{F7063DA8-8359-439C-9297-BBC5299A7D87}"
_IID_IRawElementProviderFragmentRoot = "{620CE2A5-AB8F-40A9-86CB-DE3C75599B58}"
_IID_IInvokeProvider = "{54FCB24B-E18E-47A2-B4D3-ECCBE77599A2}"
_IID_IValueProvider = "{C7935180-6FB3-4201-B174-7DF73ADBF64A}"
_IID_IRangeValueProvider = "{36DC7AEF-33E6-4691-AFE1-2BE7274B3D33}"
_IID_ISelectionItemProvider = "{2ACAD808-B2D4-452D-A407-91FF1AD167B2}"
_IID_IToggleProvider = "{56D00BD0-C4F4-433C-A836-1A52A57E0892}"
_IID_IScrollItemProvider = "{2360C714-4BF1-4B26-BA65-9B21316127EB}"
_IID_IExpandCollapseProvider = "{D847D3A5-CAB0-4A98-8C32-ECB45C59AD24}"

# The two interfaces only a container with rows answers; a plain widget's
# structure is its window's, and offering these would claim otherwise.
_THE_KINDS_ONLY_A_CONTAINER_ANSWERS = ("fragment", "fragment_root")

_THE_SHELL_FOR_EACH_PATTERN = {
    Pattern.INVOKE: "invoke",
    Pattern.TOGGLE: "toggle",
    Pattern.VALUE: "value",
    Pattern.RANGE_VALUE: "range",
    Pattern.SELECTION_ITEM: "selection",
}

# A table because `Pattern(10099)` raises for an id no member carries.
_THE_PATTERN_WITH_EACH_ID: Mapping[int, Pattern] = {
    pattern.value: pattern for pattern in Pattern
}

_THE_SHELL_A_ROW_OFFERS_FOR_EACH_PATTERN_ID: Mapping[int, str] = {
    Pattern.SELECTION_ITEM.value: "selection",
    _UIA_ScrollItemPatternId: "scroll",
}


class _Variant(ctypes.Structure):
    _fields_ = (
        ("vt", ctypes.c_ushort),
        ("reserved1", ctypes.c_ushort),
        ("reserved2", ctypes.c_ushort),
        ("reserved3", ctypes.c_ushort),
        ("data", ctypes.c_ubyte * 16),
    )

    def hold_number(self, value: int) -> None:
        self.vt = _VT_I4
        ctypes.cast(self.data, ctypes.POINTER(ctypes.c_int))[0] = value

    def hold_truth(self, value: bool) -> None:
        self.vt = _VT_BOOL
        ctypes.cast(self.data, ctypes.POINTER(ctypes.c_short))[0] = -1 if value else 0

    def hold_words(self, value: str) -> None:
        self.vt = _VT_BSTR
        ctypes.cast(self.data, ctypes.POINTER(ctypes.c_void_p))[0] = (
            _oleaut32().SysAllocString(value)
        )


class _UiaRect(ctypes.Structure):
    _fields_ = (
        ("left", ctypes.c_double),
        ("top", ctypes.c_double),
        ("width", ctypes.c_double),
        ("height", ctypes.c_double),
    )


class _Shell(ctypes.Structure):
    """A COM object: its address is the interface pointer, its one field the vtable."""

    _fields_ = (("vtable", ctypes.c_void_p),)


class _Hosted:
    """One widget's provider state: the blueprint, its shells, and one refcount."""

    def __init__(self, hwnd: int, blueprint: Blueprint) -> None:
        self.hwnd = hwnd
        self.blueprint = blueprint
        self.refcount = 0
        self.shells: dict[str, _Shell] = {}
        self.rows: dict[str, _HostedRow] = {}
        # The selection as last announced, so only real changes raise events.
        self.selection_now: tuple[str, ...] = ()


class _HostedRow:
    """One row's COM identity: an element of its container's, with no window.

    Asked again for the same key, the container answers the same identity, so
    a client's runtime ids stay stable while the row does. `number` is the
    int a runtime id needs, minted once per key and never reused.
    """

    def __init__(self, container: _Hosted, key: str, number: int) -> None:
        self.container = container
        self.key = key
        self.number = number
        # The same lifetime pin as the container's: the registry owns the
        # memory until the container goes.
        self.refcount = 1
        self.shells: dict[str, _Shell] = {}


_BY_ADDRESS: dict[int, _Hosted] = {}
_BY_HWND: dict[int, _Hosted] = {}
_ROW_BY_ADDRESS: dict[int, _HostedRow] = {}


class ComProviderPlatform:
    """Where providers answer from: WM_GETOBJECT in, pattern calls back out."""

    def __init__(
        self, subclasses: WindowSubclasses, note_trouble: Callable[[str], None]
    ) -> None:
        self._subclasses = subclasses
        self._note = note_trouble

    def host(self, hwnd: int, blueprint: Blueprint) -> None:
        com = _the_com_layer()
        hosted = _Hosted(hwnd, blueprint)
        for kind, vtable in com.vtables.items():
            shell = _Shell(ctypes.cast(ctypes.pointer(vtable), ctypes.c_void_p))
            hosted.shells[kind] = shell
            _BY_ADDRESS[ctypes.addressof(shell)] = hosted
        _BY_HWND[hwnd] = hosted
        # The lifetime pin: UIA refcounts transiently on every walk, and the
        # shells must outlive every zero crossing until the widget goes.
        hosted.refcount += 1
        self._subclasses.put_in_the_path_of(hwnd, self._answer, self._handle_gone)

    def unhost(self, hwnd: int) -> None:
        self._let_go(hwnd)
        self._subclasses.step_out_of(hwnd)

    def announces(self, prop: PropId) -> bool:
        return prop in _THE_UIA_PROPERTY_FOR_EACH_PROP

    def announce_change(self, hwnd: int, prop: PropId, now: object) -> None:
        uia_property = _THE_UIA_PROPERTY_FOR_EACH_PROP.get(prop)
        if uia_property is None:
            return
        # Resolved at raise time: a widget unhosted since the change was posted
        # has nothing to announce and nobody to announce it as.
        hosted = _BY_HWND.get(hwnd)
        if hosted is None:
            return
        com = _the_com_layer()
        if not com.core.UiaClientsAreListening():
            return
        old = _Variant()
        new = _Variant()
        if isinstance(now, str):
            new.hold_words(now)
        elif isinstance(now, bool):
            new.hold_truth(now)
        elif isinstance(now, int):
            new.hold_number(now)
        try:
            com.core.UiaRaiseAutomationPropertyChangedEvent(
                ctypes.addressof(hosted.shells["simple"]), uia_property, old, new
            )
        finally:
            _oleaut32().VariantClear(ctypes.byref(new))

    def announce_selection(self, hwnd: int, now: tuple[str, ...]) -> None:
        hosted = _BY_HWND.get(hwnd)
        if hosted is None:
            return
        changes = the_selection_changes_between(hosted.selection_now, now)
        hosted.selection_now = now
        if not changes:
            return
        com = _the_com_layer()
        if not com.core.UiaClientsAreListening():
            return
        for change, key in changes:
            row = _the_row(hosted, key)
            com.core.UiaRaiseAutomationEvent(
                ctypes.addressof(row.shells["simple"]),
                _THE_EVENT_FOR_EACH_SELECTION_CHANGE[change],
            )

    def _answer(self, hwnd: int, wparam: int, lparam: int) -> int | None:
        asked_for = ctypes.c_long(lparam & 0xFFFFFFFF).value
        if asked_for != UiaRootObjectId:
            return None
        hosted = _BY_HWND.get(hwnd)
        if hosted is None:
            return None
        return _the_com_layer().core.UiaReturnRawElementProvider(
            hwnd, wparam, lparam, ctypes.addressof(hosted.shells["simple"])
        )

    def _handle_gone(self, hwnd: int) -> None:
        self._let_go(hwnd)

    def _let_go(self, hwnd: int) -> None:
        hosted = _BY_HWND.pop(hwnd, None)
        if hosted is None:
            return
        core = _the_com_layer().core
        core.UiaReturnRawElementProvider(hwnd, 0, 0, None)
        for row in hosted.rows.values():
            core.UiaDisconnectProvider(ctypes.addressof(row.shells["simple"]))
            for shell in row.shells.values():
                _ROW_BY_ADDRESS.pop(ctypes.addressof(shell), None)
        hosted.rows.clear()
        core.UiaDisconnectProvider(ctypes.addressof(hosted.shells["simple"]))
        hosted.refcount -= 1
        for shell in hosted.shells.values():
            _BY_ADDRESS.pop(ctypes.addressof(shell), None)


def _hosted_for(this: int) -> _Hosted:
    return _BY_ADDRESS[int(this)]


def _row_for(this: int) -> _HostedRow:
    return _ROW_BY_ADDRESS[int(this)]


def _the_row(container: _Hosted, key: str) -> _HostedRow:
    row = container.rows.get(key)
    if row is None:
        # Rows are never removed until the container goes, so the count is a
        # number no other key has worn.
        row = _HostedRow(container, key, number=len(container.rows) + 1)
        for kind, vtable in _the_com_layer().row_vtables.items():
            shell = _Shell(ctypes.cast(ctypes.pointer(vtable), ctypes.c_void_p))
            row.shells[kind] = shell
            _ROW_BY_ADDRESS[ctypes.addressof(shell)] = row
        container.rows[key] = row
    return row


def _the_value_said_for(hosted: _Hosted) -> str | None:
    return hosted.blueprint.value_the_application_said()


def _write_pointer(out: int, address: int | None) -> None:
    ctypes.cast(out, ctypes.POINTER(ctypes.c_void_p))[0] = address


def _write_int(out: int, value: int) -> None:
    ctypes.cast(out, ctypes.POINTER(ctypes.c_int))[0] = value


def _hand_out_a_row(container: _Hosted, key: str, out: int) -> None:
    row = _the_row(container, key)
    _write_pointer(out, ctypes.addressof(row.shells["fragment"]))
    row.refcount += 1


def _hand_out_another_row(row: _HostedRow, key: str | None, out: int) -> None:
    if key is not None:
        _hand_out_a_row(row.container, key, out)


def _a_runtime_id_appending(number: int) -> int:
    """A two-int SAFEARRAY: append-to-the-window's-id, then the row's number."""
    oleaut = _oleaut32()
    array = oleaut.SafeArrayCreateVector(_VT_I4, 0, 2)
    for position, value in enumerate((_UiaAppendRuntimeId, number)):
        oleaut.SafeArrayPutElement(
            array,
            ctypes.byref(ctypes.c_long(position)),
            ctypes.byref(ctypes.c_int(value)),
        )
    return array


class _ComLayer:
    """Everything built on first use: WINFUNCTYPE only exists on Windows."""

    def __init__(self) -> None:
        self.core = _load_uiautomationcore()
        self.iids = {
            _guid_bytes(_IID_IUnknown): "simple",  # identity: one pointer, always
            _guid_bytes(_IID_IRawElementProviderSimple): "simple",
            _guid_bytes(_IID_IRawElementProviderFragment): "fragment",
            _guid_bytes(_IID_IRawElementProviderFragmentRoot): "fragment_root",
            _guid_bytes(_IID_IInvokeProvider): "invoke",
            _guid_bytes(_IID_IToggleProvider): "toggle",
            _guid_bytes(_IID_IValueProvider): "value",
            _guid_bytes(_IID_IRangeValueProvider): "range",
            _guid_bytes(_IID_ISelectionItemProvider): "selection",
        }
        self.row_iids = {
            _guid_bytes(_IID_IUnknown): "simple",
            _guid_bytes(_IID_IRawElementProviderSimple): "simple",
            _guid_bytes(_IID_IRawElementProviderFragment): "fragment",
            _guid_bytes(_IID_ISelectionItemProvider): "selection",
            _guid_bytes(_IID_IScrollItemProvider): "scroll",
            _guid_bytes(_IID_IExpandCollapseProvider): "expand",
        }
        self.kept_alive: list[Any] = []
        self.vtables = self._the_vtables()
        self.row_vtables = self._the_row_vtables()

    def _the_vtables(self) -> dict[str, Any]:
        hresult = _HRESULT
        this = ctypes.c_void_p
        out = ctypes.c_void_p

        unknown = (
            self._slot(hresult, this, out, out)(self._query_interface),
            self._slot(ctypes.c_ulong, this)(self._add_reference),
            self._slot(ctypes.c_ulong, this)(self._release),
        )
        simple = (
            *unknown,
            self._slot(hresult, this, out)(self._provider_options),
            self._slot(hresult, this, ctypes.c_int, out)(self._pattern_provider),
            self._slot(hresult, this, ctypes.c_int, out)(self._property_value),
            self._slot(hresult, this, out)(self._host_provider),
        )
        invoke = (*unknown, self._slot(hresult, this)(self._invoke))
        toggle = (
            *unknown,
            self._slot(hresult, this)(self._toggle),
            self._slot(hresult, this, out)(self._toggle_state),
        )
        value = (
            *unknown,
            self._slot(hresult, this, ctypes.c_wchar_p)(self._set_value),
            self._slot(hresult, this, out)(self._value),
            self._slot(hresult, this, out)(self._value_read_only),
        )
        # Vtable order from UIAutomationCore.h: Value, IsReadOnly, Maximum,
        # Minimum, LargeChange, SmallChange.
        range_value = (
            *unknown,
            self._slot(hresult, this, ctypes.c_double)(self._set_range_value),
            self._slot(hresult, this, out)(self._range_value),
            self._slot(hresult, this, out)(self._range_read_only),
            self._slot(hresult, this, out)(self._range_maximum),
            self._slot(hresult, this, out)(self._range_minimum),
            self._slot(hresult, this, out)(self._range_large_change),
            self._slot(hresult, this, out)(self._range_small_change),
        )
        selection = (
            *unknown,
            self._slot(hresult, this)(self._select),
            self._slot(hresult, this)(self._add_to_selection),
            self._slot(hresult, this)(self._remove_from_selection),
            self._slot(hresult, this, out)(self._is_selected),
            self._slot(hresult, this, out)(self._selection_container),
        )
        # Vtable order from UIAutomationCore.h: Navigate, GetRuntimeId,
        # get_BoundingRectangle, GetEmbeddedFragmentRoots, SetFocus,
        # get_FragmentRoot.
        fragment = (
            *unknown,
            self._slot(hresult, this, ctypes.c_int, out)(self._navigate),
            self._slot(hresult, this, out)(self._runtime_id),
            self._slot(hresult, this, out)(self._bounding_rectangle),
            self._slot(hresult, this, out)(self._embedded_fragment_roots),
            self._slot(hresult, this)(self._set_focus),
            self._slot(hresult, this, out)(self._fragment_root),
        )
        fragment_root = (
            *unknown,
            self._slot(hresult, this, ctypes.c_double, ctypes.c_double, out)(
                self._element_from_point
            ),
            self._slot(hresult, this, out)(self._focused_element),
        )
        return {
            "simple": _a_vtable(simple),
            "invoke": _a_vtable(invoke),
            "toggle": _a_vtable(toggle),
            "value": _a_vtable(value),
            "range": _a_vtable(range_value),
            "selection": _a_vtable(selection),
            "fragment": _a_vtable(fragment),
            "fragment_root": _a_vtable(fragment_root),
        }

    def _the_row_vtables(self) -> dict[str, Any]:
        hresult = _HRESULT
        this = ctypes.c_void_p
        out = ctypes.c_void_p

        unknown = (
            self._slot(hresult, this, out, out)(self._row_query_interface),
            self._slot(ctypes.c_ulong, this)(self._row_add_reference),
            self._slot(ctypes.c_ulong, this)(self._row_release),
        )
        simple = (
            *unknown,
            self._slot(hresult, this, out)(self._provider_options),
            self._slot(hresult, this, ctypes.c_int, out)(self._row_pattern_provider),
            self._slot(hresult, this, ctypes.c_int, out)(self._row_property_value),
            self._slot(hresult, this, out)(self._row_host_provider),
        )
        fragment = (
            *unknown,
            self._slot(hresult, this, ctypes.c_int, out)(self._row_navigate),
            self._slot(hresult, this, out)(self._row_runtime_id),
            self._slot(hresult, this, out)(self._row_bounding_rectangle),
            self._slot(hresult, this, out)(self._embedded_fragment_roots),
            self._slot(hresult, this)(self._set_focus),
            self._slot(hresult, this, out)(self._row_fragment_root),
        )
        selection = (
            *unknown,
            self._slot(hresult, this)(self._row_select),
            self._slot(hresult, this)(self._row_add_to_selection),
            self._slot(hresult, this)(self._row_remove_from_selection),
            self._slot(hresult, this, out)(self._row_is_selected),
            self._slot(hresult, this, out)(self._row_selection_container),
        )
        scroll = (
            *unknown,
            self._slot(hresult, this)(self._row_scroll_into_view),
        )
        # Vtable order from UIAutomationCore.h: Expand, Collapse,
        # get_ExpandCollapseState.
        expand = (
            *unknown,
            self._slot(hresult, this)(self._row_expand),
            self._slot(hresult, this)(self._row_collapse),
            self._slot(hresult, this, out)(self._row_expand_state),
        )
        return {
            "simple": _a_vtable(simple),
            "fragment": _a_vtable(fragment),
            "selection": _a_vtable(selection),
            "scroll": _a_vtable(scroll),
            "expand": _a_vtable(expand),
        }

    def _slot(self, restype: Any, *argtypes: Any) -> Any:
        kind = ctypes.WINFUNCTYPE(restype, *argtypes)
        self.kept_alive.append(kind)
        answers_an_hresult = restype is _HRESULT

        def bind(implementation: Any) -> Any:
            bound = kind(
                _never_raising(implementation) if answers_an_hresult else implementation
            )
            self.kept_alive.append(bound)
            return bound

        return bind

    def _query_interface(self, this: int, riid: int, out: int) -> int:
        hosted = _hosted_for(this)
        asked = ctypes.string_at(riid, 16)
        kind = self.iids.get(asked)
        if kind is None or (
            kind in _THE_KINDS_ONLY_A_CONTAINER_ANSWERS
            and hosted.blueprint.items is None
        ):
            _write_pointer(out, None)
            return _E_NOINTERFACE
        _write_pointer(out, ctypes.addressof(hosted.shells[kind]))
        hosted.refcount += 1
        return _S_OK

    def _add_reference(self, this: int) -> int:
        hosted = _BY_ADDRESS.get(int(this))
        if hosted is None:
            return 0
        hosted.refcount += 1
        return hosted.refcount

    def _release(self, this: int) -> int:
        hosted = _BY_ADDRESS.get(int(this))
        if hosted is None:
            return 0
        # Never freed at zero: the registry owns the memory for the widget's
        # lifetime, so a transient walk can never leave a husk behind.
        hosted.refcount = max(hosted.refcount - 1, 0)
        return hosted.refcount

    def _provider_options(self, this: int, out: int) -> int:
        _write_int(out, _ProviderOptions_ServerSideProvider)
        return _S_OK

    def _pattern_provider(self, this: int, pattern_id: int, out: int) -> int:
        hosted = _hosted_for(this)
        _write_pointer(out, None)
        asked = _THE_PATTERN_WITH_EACH_ID.get(pattern_id)
        if asked is None:
            return _S_OK
        answers = hosted.blueprint.patterns.get(asked)
        if answers is None:
            if asked is Pattern.VALUE and _the_value_said_for(hosted) is not None:
                _write_pointer(out, ctypes.addressof(hosted.shells["value"]))
                hosted.refcount += 1
            return _S_OK
        # A button with nothing to run does not advertise a press.
        if asked is Pattern.INVOKE and not answers.offered():
            return _S_OK
        _write_pointer(
            out, ctypes.addressof(hosted.shells[_THE_SHELL_FOR_EACH_PATTERN[asked]])
        )
        hosted.refcount += 1
        return _S_OK

    def _property_value(self, this: int, property_id: int, out: int) -> int:
        hosted = _hosted_for(this)
        variant = ctypes.cast(out, ctypes.POINTER(_Variant))[0]
        blueprint = hosted.blueprint
        if property_id == _UIA_NamePropertyId:
            name = blueprint.name()
            if name:
                variant.hold_words(name)
        elif property_id == _UIA_ControlTypePropertyId:
            variant.hold_number(blueprint.control_type())
        elif property_id == _UIA_IsEnabledPropertyId:
            variant.hold_truth(bool(blueprint.is_enabled()))
        elif property_id == _UIA_IsKeyboardFocusablePropertyId:
            if blueprint.is_keyboard_focusable:
                variant.hold_truth(True)
        elif property_id == _UIA_HelpTextPropertyId:
            help_text = blueprint.help_text()
            if help_text:
                variant.hold_words(help_text)
        elif property_id == _UIA_FullDescriptionPropertyId:
            description = blueprint.description()
            if description:
                variant.hold_words(description)
        # Anything else stays VT_EMPTY: the HWND host provider answers the
        # rectangles, the runtime id, and the rest.
        return _S_OK

    def _host_provider(self, this: int, out: int) -> int:
        # Written straight into the out parameter: the reference UIA hands
        # back is the caller's, with no counting done here.
        return self.core.UiaHostProviderFromHwnd(_hosted_for(this).hwnd, out)

    def _invoke(self, this: int) -> int:
        return self._with_the_answers_for(
            this, Pattern.INVOKE, lambda answers: answers.press()
        )

    def _toggle(self, this: int) -> int:
        return self._with_the_answers_for(
            this, Pattern.TOGGLE, lambda answers: answers.flip()
        )

    def _toggle_state(self, this: int, out: int) -> int:
        return self._tell_a_truth(
            this, Pattern.TOGGLE, out, lambda answers: answers.is_on()
        )

    def _set_value(self, this: int, text: str | None) -> int:
        answers = _hosted_for(this).blueprint.patterns.get(Pattern.VALUE)
        if answers is None:
            # A said value is the application's word about itself; nobody
            # writes the application's words for it.
            return _UIA_E_INVALIDOPERATION
        # Refused here as well as by the client API: Tk swallows an edit
        # on a read-only widget, and a swallowed edit must not answer S_OK.
        if answers.is_read_only():
            return _UIA_E_INVALIDOPERATION
        return self._with_the_answers_for(
            this, Pattern.VALUE, lambda answers: answers.write(text or "")
        )

    def _value(self, this: int, out: int) -> int:
        hosted = _hosted_for(this)
        if hosted.blueprint.patterns.get(Pattern.VALUE) is None:
            _write_pointer(
                out, _oleaut32().SysAllocString(_the_value_said_for(hosted) or "")
            )
            return _S_OK

        def answer(answers: ValueAnswers) -> None:
            _write_pointer(out, _oleaut32().SysAllocString(answers.read()))

        return self._with_the_answers_for(this, Pattern.VALUE, answer)

    def _value_read_only(self, this: int, out: int) -> int:
        if _hosted_for(this).blueprint.patterns.get(Pattern.VALUE) is None:
            _write_int(out, 1)
            return _S_OK
        return self._tell_a_truth(
            this, Pattern.VALUE, out, lambda answers: answers.is_read_only()
        )

    def _set_range_value(self, this: int, value: float) -> int:
        answers = _hosted_for(this).blueprint.patterns.get(Pattern.RANGE_VALUE)
        if answers is None or answers.write is None or answers.is_read_only():
            # The documented refusal for a range nobody may set now.
            return _UIA_E_INVALIDOPERATION
        answers.write(value)
        return _S_OK

    def _range_value(self, this: int, out: int) -> int:
        return self._tell_a_number(this, out, lambda answers: answers.now())

    def _range_read_only(self, this: int, out: int) -> int:
        return self._tell_a_truth(
            this, Pattern.RANGE_VALUE, out, lambda answers: answers.is_read_only()
        )

    def _range_maximum(self, this: int, out: int) -> int:
        return self._tell_a_number(this, out, lambda answers: answers.high())

    def _range_minimum(self, this: int, out: int) -> int:
        return self._tell_a_number(this, out, lambda answers: answers.low())

    def _range_large_change(self, this: int, out: int) -> int:
        return self._tell_a_number(this, out, lambda answers: answers.step() or 0.0)

    def _range_small_change(self, this: int, out: int) -> int:
        return self._tell_a_number(this, out, lambda answers: answers.step() or 0.0)

    def _select(self, this: int) -> int:
        return self._with_the_answers_for(
            this, Pattern.SELECTION_ITEM, lambda answers: answers.select()
        )

    def _add_to_selection(self, this: int) -> int:
        # A radio's group holds exactly one selection; adding is not a thing.
        return _UIA_E_INVALIDOPERATION

    def _remove_from_selection(self, this: int) -> int:
        return _UIA_E_INVALIDOPERATION

    def _is_selected(self, this: int, out: int) -> int:
        return self._tell_a_truth(
            this, Pattern.SELECTION_ITEM, out, lambda answers: answers.is_selected()
        )

    def _selection_container(self, this: int, out: int) -> int:
        _write_pointer(out, None)
        return _S_OK

    def _navigate(self, this: int, direction: int, out: int) -> int:
        hosted = _hosted_for(this)
        _write_pointer(out, None)
        items = hosted.blueprint.items
        if items is None:
            return _S_OK
        if direction == _NavigateDirection_FirstChild:
            key = items.first()
        elif direction == _NavigateDirection_LastChild:
            key = items.last()
        else:
            # Parent and siblings are the window tree's to answer.
            return _S_OK
        if key is not None:
            _hand_out_a_row(hosted, key, out)
        return _S_OK

    def _runtime_id(self, this: int, out: int) -> int:
        # Nothing: a fragment root has a window, and the window names it.
        _write_pointer(out, None)
        return _S_OK

    def _bounding_rectangle(self, this: int, out: int) -> int:
        ctypes.cast(out, ctypes.POINTER(_UiaRect))[0] = _UiaRect(0.0, 0.0, 0.0, 0.0)
        return _S_OK

    def _embedded_fragment_roots(self, this: int, out: int) -> int:
        _write_pointer(out, None)
        return _S_OK

    def _set_focus(self, this: int) -> int:
        # Focus is the window's; there is nothing separate to move it to.
        return _S_OK

    def _fragment_root(self, this: int, out: int) -> int:
        hosted = _hosted_for(this)
        _write_pointer(out, ctypes.addressof(hosted.shells["fragment_root"]))
        hosted.refcount += 1
        return _S_OK

    def _element_from_point(self, this: int, x: float, y: float, out: int) -> int:
        # Nothing chosen: UIA falls back to the container itself.
        _write_pointer(out, None)
        return _S_OK

    def _focused_element(self, this: int, out: int) -> int:
        _write_pointer(out, None)
        return _S_OK

    def _row_query_interface(self, this: int, riid: int, out: int) -> int:
        row = _row_for(this)
        asked = ctypes.string_at(riid, 16)
        kind = self.row_iids.get(asked)
        if kind is None:
            _write_pointer(out, None)
            return _E_NOINTERFACE
        _write_pointer(out, ctypes.addressof(row.shells[kind]))
        row.refcount += 1
        return _S_OK

    def _row_add_reference(self, this: int) -> int:
        row = _ROW_BY_ADDRESS.get(int(this))
        if row is None:
            return 0
        row.refcount += 1
        return row.refcount

    def _row_release(self, this: int) -> int:
        row = _ROW_BY_ADDRESS.get(int(this))
        if row is None:
            return 0
        # Never freed at zero, exactly as the container is not.
        row.refcount = max(row.refcount - 1, 0)
        return row.refcount

    def _row_pattern_provider(self, this: int, pattern_id: int, out: int) -> int:
        row = _row_for(this)
        _write_pointer(out, None)
        offered = _THE_SHELL_A_ROW_OFFERS_FOR_EACH_PATTERN_ID.get(pattern_id)
        if pattern_id == _UIA_ExpandCollapsePatternId:
            # Only a row with branches beneath it promises to open.
            items = row.container.blueprint.items
            if items is not None and items.first_child(row.key) is not None:
                offered = "expand"
        if offered is not None:
            _write_pointer(out, ctypes.addressof(row.shells[offered]))
            row.refcount += 1
        return _S_OK

    def _row_property_value(self, this: int, property_id: int, out: int) -> int:
        row = _row_for(this)
        variant = ctypes.cast(out, ctypes.POINTER(_Variant))[0]
        items = row.container.blueprint.items
        if items is None:
            return _S_OK
        if property_id == _UIA_NamePropertyId:
            words = items.words(row.key)
            if words:
                variant.hold_words(words)
        elif property_id == _UIA_ControlTypePropertyId:
            variant.hold_number(items.row_control_type())
        elif property_id == _UIA_IsEnabledPropertyId:
            variant.hold_truth(bool(row.container.blueprint.is_enabled()))
        elif property_id == _UIA_IsOffscreenPropertyId:
            # A row scrolled out of view has no rectangle, and says so.
            variant.hold_truth(items.rectangle(row.key) is None)
        return _S_OK

    def _row_host_provider(self, this: int, out: int) -> int:
        # No window behind a row; the container's window hosts the tree.
        _write_pointer(out, None)
        return _S_OK

    def _row_navigate(self, this: int, direction: int, out: int) -> int:
        row = _row_for(this)
        _write_pointer(out, None)
        items = row.container.blueprint.items
        if items is None or not items.still_there(row.key):
            return _S_OK
        if direction == _NavigateDirection_Parent:
            holder = items.parent(row.key)
            if holder is None:
                _write_pointer(out, ctypes.addressof(row.container.shells["fragment"]))
                row.container.refcount += 1
            else:
                _hand_out_a_row(row.container, holder, out)
        elif direction == _NavigateDirection_NextSibling:
            _hand_out_another_row(row, items.after(row.key), out)
        elif direction == _NavigateDirection_PreviousSibling:
            _hand_out_another_row(row, items.before(row.key), out)
        elif direction == _NavigateDirection_FirstChild:
            _hand_out_another_row(row, items.first_child(row.key), out)
        elif direction == _NavigateDirection_LastChild:
            _hand_out_another_row(row, items.last_child(row.key), out)
        return _S_OK

    def _row_runtime_id(self, this: int, out: int) -> int:
        row = _row_for(this)
        _write_pointer(out, _a_runtime_id_appending(row.number))
        return _S_OK

    def _row_bounding_rectangle(self, this: int, out: int) -> int:
        row = _row_for(this)
        items = row.container.blueprint.items
        painted = items.rectangle(row.key) if items is not None else None
        left, top, width, height = painted if painted is not None else (0, 0, 0, 0)
        ctypes.cast(out, ctypes.POINTER(_UiaRect))[0] = _UiaRect(
            float(left), float(top), float(width), float(height)
        )
        return _S_OK

    def _row_fragment_root(self, this: int, out: int) -> int:
        row = _row_for(this)
        _write_pointer(out, ctypes.addressof(row.container.shells["fragment_root"]))
        row.container.refcount += 1
        return _S_OK

    def _row_select(self, this: int) -> int:
        row = _row_for(this)
        items = row.container.blueprint.items
        if items is None or not items.still_there(row.key):
            return _UIA_E_INVALIDOPERATION
        items.select(row.key)
        return _S_OK

    def _row_add_to_selection(self, this: int) -> int:
        return self._selection_move(
            this, lambda items, key: items.add_to_selection(key)
        )

    def _row_remove_from_selection(self, this: int) -> int:
        return self._selection_move(
            this, lambda items, key: items.remove_from_selection(key)
        )

    def _selection_move(self, this: int, move: Any) -> int:
        row = _row_for(this)
        items = row.container.blueprint.items
        if (
            items is None
            or not items.still_there(row.key)
            # The widget's own selectmode decides; on a one-at-a-time
            # container these are the documented refusal.
            or not items.takes_more_than_one()
        ):
            return _UIA_E_INVALIDOPERATION
        move(items, row.key)
        return _S_OK

    def _row_is_selected(self, this: int, out: int) -> int:
        row = _row_for(this)
        items = row.container.blueprint.items
        selected = items.is_selected(row.key) if items is not None else False
        _write_int(out, 1 if selected else 0)
        return _S_OK

    def _row_selection_container(self, this: int, out: int) -> int:
        row = _row_for(this)
        _write_pointer(out, ctypes.addressof(row.container.shells["simple"]))
        row.container.refcount += 1
        return _S_OK

    def _row_scroll_into_view(self, this: int) -> int:
        row = _row_for(this)
        items = row.container.blueprint.items
        if items is None or not items.still_there(row.key):
            return _UIA_E_INVALIDOPERATION
        items.show(row.key)
        return _S_OK

    def _row_expand(self, this: int) -> int:
        return self._branch_turned(this, lambda items, key: items.open(key))

    def _row_collapse(self, this: int) -> int:
        return self._branch_turned(this, lambda items, key: items.close(key))

    def _branch_turned(self, this: int, turn: Any) -> int:
        row = _row_for(this)
        items = row.container.blueprint.items
        if (
            items is None
            or not items.still_there(row.key)
            or items.first_child(row.key) is None
        ):
            return _UIA_E_INVALIDOPERATION
        turn(items, row.key)
        return _S_OK

    def _row_expand_state(self, this: int, out: int) -> int:
        row = _row_for(this)
        items = row.container.blueprint.items
        if items is None or items.first_child(row.key) is None:
            state = _ExpandCollapseState_LeafNode
        elif items.is_open(row.key):
            state = _ExpandCollapseState_Expanded
        else:
            state = _ExpandCollapseState_Collapsed
        _write_int(out, state)
        return _S_OK

    def _with_the_answers_for(self, this: int, pattern: Pattern, use: Any) -> int:
        answers = _hosted_for(this).blueprint.patterns.get(pattern)
        if answers is None:
            return _UIA_E_INVALIDOPERATION
        use(answers)
        return _S_OK

    def _tell_a_truth(self, this: int, pattern: Pattern, out: int, read: Any) -> int:
        return self._with_the_answers_for(
            this, pattern, lambda answers: _write_int(out, 1 if read(answers) else 0)
        )

    def _tell_a_number(self, this: int, out: int, read: Any) -> int:
        def answer(answers: Any) -> None:
            ctypes.cast(out, ctypes.POINTER(ctypes.c_double))[0] = float(read(answers))

        return self._with_the_answers_for(this, Pattern.RANGE_VALUE, answer)


def _never_raising(implementation: Callable[..., int]) -> Callable[..., int]:
    def answer(*args: Any) -> int:
        try:
            return implementation(*args)
        except Exception:  # noqa: BLE001 - a COM callback must never raise
            return _E_FAIL

    return answer


def _a_vtable(slots: tuple[Any, ...]) -> Any:
    fields = [(f"slot{index}", type(bound)) for index, bound in enumerate(slots)]
    vtable_type = type("Vtable", (ctypes.Structure,), {"_fields_": fields})
    return vtable_type(*slots)


def _guid_bytes(text: str) -> bytes:
    buffer = (ctypes.c_ubyte * 16)()
    if ctypes.WinDLL("ole32.dll").CLSIDFromString(text, ctypes.byref(buffer)):
        raise ValueError(f"not a GUID: {text}")
    return bytes(buffer)


def _load_uiautomationcore() -> Any:
    from ctypes import wintypes

    core = ctypes.WinDLL("UIAutomationCore.dll")
    core.UiaReturnRawElementProvider.restype = wintypes.LPARAM
    core.UiaReturnRawElementProvider.argtypes = [
        wintypes.HWND,
        wintypes.WPARAM,
        wintypes.LPARAM,
        ctypes.c_void_p,
    ]
    core.UiaHostProviderFromHwnd.restype = ctypes.c_long
    core.UiaHostProviderFromHwnd.argtypes = [wintypes.HWND, ctypes.c_void_p]
    core.UiaDisconnectProvider.restype = ctypes.c_long
    core.UiaDisconnectProvider.argtypes = [ctypes.c_void_p]
    core.UiaClientsAreListening.restype = wintypes.BOOL
    core.UiaRaiseAutomationEvent.restype = ctypes.c_long
    core.UiaRaiseAutomationEvent.argtypes = [ctypes.c_void_p, ctypes.c_int]
    core.UiaRaiseAutomationPropertyChangedEvent.restype = ctypes.c_long
    core.UiaRaiseAutomationPropertyChangedEvent.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        _Variant,
        _Variant,
    ]
    return core


def _oleaut32() -> Any:
    global _OLEAUT32
    if _OLEAUT32 is None:
        oleaut32 = ctypes.WinDLL("oleaut32.dll")
        oleaut32.SysAllocString.restype = ctypes.c_void_p
        oleaut32.SysAllocString.argtypes = [ctypes.c_wchar_p]
        oleaut32.VariantClear.restype = ctypes.c_long
        oleaut32.VariantClear.argtypes = [ctypes.c_void_p]
        oleaut32.SafeArrayCreateVector.restype = ctypes.c_void_p
        oleaut32.SafeArrayCreateVector.argtypes = [
            ctypes.c_ushort,
            ctypes.c_long,
            ctypes.c_ulong,
        ]
        oleaut32.SafeArrayPutElement.restype = ctypes.c_long
        oleaut32.SafeArrayPutElement.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_long),
            ctypes.c_void_p,
        ]
        _OLEAUT32 = oleaut32
    return _OLEAUT32


def _the_com_layer() -> _ComLayer:
    global _COM_LAYER
    if _COM_LAYER is None:
        _COM_LAYER = _ComLayer()
    return _COM_LAYER


_COM_LAYER: _ComLayer | None = None
_OLEAUT32: Any = None
