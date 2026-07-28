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
from tk_uia.provide import Pattern, ValueAnswers

if TYPE_CHECKING:
    from collections.abc import Callable

    from tk_uia.provide import Blueprint

UiaRootObjectId = -25

_ProviderOptions_ServerSideProvider = 0x2

_UIA_ControlTypePropertyId = 30003
_UIA_NamePropertyId = 30005
_UIA_IsKeyboardFocusablePropertyId = 30009
_UIA_IsEnabledPropertyId = 30010
_UIA_HelpTextPropertyId = 30013
_UIA_FullDescriptionPropertyId = 30159

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
_IID_IInvokeProvider = "{54FCB24B-E18E-47A2-B4D3-ECCBE77599A2}"
_IID_IValueProvider = "{C7935180-6FB3-4201-B174-7DF73ADBF64A}"
_IID_IRangeValueProvider = "{36DC7AEF-33E6-4691-AFE1-2BE7274B3D33}"
_IID_ISelectionItemProvider = "{2ACAD808-B2D4-452D-A407-91FF1AD167B2}"
_IID_IToggleProvider = "{56D00BD0-C4F4-433C-A836-1A52A57E0892}"

_THE_SHELL_FOR_EACH_PATTERN = {
    Pattern.INVOKE: "invoke",
    Pattern.TOGGLE: "toggle",
    Pattern.VALUE: "value",
    Pattern.RANGE_VALUE: "range",
    Pattern.SELECTION_ITEM: "selection",
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


_BY_ADDRESS: dict[int, _Hosted] = {}
_BY_HWND: dict[int, _Hosted] = {}


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

    def announce_change(self, hwnd: int, uia_property: int, now: object) -> None:
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
        core.UiaDisconnectProvider(ctypes.addressof(hosted.shells["simple"]))
        hosted.refcount -= 1
        for shell in hosted.shells.values():
            _BY_ADDRESS.pop(ctypes.addressof(shell), None)


def _hosted_for(this: int) -> _Hosted:
    return _BY_ADDRESS[int(this)]


def _write_pointer(out: int, address: int | None) -> None:
    ctypes.cast(out, ctypes.POINTER(ctypes.c_void_p))[0] = address


class _ComLayer:
    """Everything built on first use: WINFUNCTYPE only exists on Windows."""

    def __init__(self) -> None:
        self.core = _load_uiautomationcore()
        self.iids = {
            _guid_bytes(_IID_IUnknown): "simple",  # identity: one pointer, always
            _guid_bytes(_IID_IRawElementProviderSimple): "simple",
            _guid_bytes(_IID_IInvokeProvider): "invoke",
            _guid_bytes(_IID_IToggleProvider): "toggle",
            _guid_bytes(_IID_IValueProvider): "value",
            _guid_bytes(_IID_IRangeValueProvider): "range",
            _guid_bytes(_IID_ISelectionItemProvider): "selection",
        }
        self.kept_alive: list[Any] = []
        self.vtables = self._the_vtables()

    def _the_vtables(self) -> dict[str, Any]:
        hresult = ctypes.c_long
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
        return {
            "simple": _a_vtable(simple),
            "invoke": _a_vtable(invoke),
            "toggle": _a_vtable(toggle),
            "value": _a_vtable(value),
            "range": _a_vtable(range_value),
            "selection": _a_vtable(selection),
        }

    def _slot(self, restype: Any, *argtypes: Any) -> Any:
        kind = ctypes.WINFUNCTYPE(restype, *argtypes)
        self.kept_alive.append(kind)

        def bind(implementation: Any) -> Any:
            bound = kind(implementation)
            self.kept_alive.append(bound)
            return bound

        return bind

    # -- IUnknown --

    def _query_interface(self, this: int, riid: int, out: int) -> int:
        try:
            hosted = _hosted_for(this)
            asked = bytes(ctypes.cast(riid, ctypes.POINTER(ctypes.c_ubyte * 16))[0])
            kind = self.iids.get(asked)
            if kind is None:
                _write_pointer(out, None)
                return _E_NOINTERFACE
            _write_pointer(out, ctypes.addressof(hosted.shells[kind]))
            hosted.refcount += 1
            return _S_OK
        except Exception:  # noqa: BLE001 - a COM callback must never raise
            return _E_FAIL

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

    # -- IRawElementProviderSimple --

    def _provider_options(self, this: int, out: int) -> int:
        ctypes.cast(out, ctypes.POINTER(ctypes.c_int))[0] = (
            _ProviderOptions_ServerSideProvider
        )
        return _S_OK

    def _pattern_provider(self, this: int, pattern_id: int, out: int) -> int:
        try:
            hosted = _hosted_for(this)
            _write_pointer(out, None)
            asked = _the_pattern_with_id(pattern_id)
            if asked is None:
                return _S_OK
            answers = hosted.blueprint.patterns.get(asked)
            if answers is None:
                return _S_OK
            # A button with nothing to run does not advertise a press.
            if asked is Pattern.INVOKE and not answers.offered():
                return _S_OK
            _write_pointer(
                out, ctypes.addressof(hosted.shells[_THE_SHELL_FOR_EACH_PATTERN[asked]])
            )
            hosted.refcount += 1
            return _S_OK
        except Exception:  # noqa: BLE001 - a COM callback must never raise
            return _E_FAIL

    def _property_value(self, this: int, property_id: int, out: int) -> int:
        try:
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
        except Exception:  # noqa: BLE001 - a COM callback must never raise
            return _E_FAIL

    def _host_provider(self, this: int, out: int) -> int:
        # Written straight into the out parameter: the reference UIA hands
        # back is the caller's, with no counting done here.
        return self.core.UiaHostProviderFromHwnd(_hosted_for(this).hwnd, out)

    # -- IInvokeProvider --

    def _invoke(self, this: int) -> int:
        return self._act(this, Pattern.INVOKE, lambda answers: answers.press())

    # -- IToggleProvider --

    def _toggle(self, this: int) -> int:
        return self._act(this, Pattern.TOGGLE, lambda answers: answers.flip())

    def _toggle_state(self, this: int, out: int) -> int:
        return self._tell(
            this,
            Pattern.TOGGLE,
            lambda answers: ctypes.memmove(
                out, ctypes.byref(ctypes.c_int(1 if answers.is_on() else 0)), 4
            ),
        )

    # -- IValueProvider --

    def _set_value(self, this: int, text: str | None) -> int:
        return self._act(
            this, Pattern.VALUE, lambda answers: answers.write(text or "")
        )

    def _value(self, this: int, out: int) -> int:
        def answer(answers: ValueAnswers) -> None:
            _write_pointer(out, _oleaut32().SysAllocString(answers.read()))

        return self._tell(this, Pattern.VALUE, answer)

    def _value_read_only(self, this: int, out: int) -> int:
        return self._tell(
            this,
            Pattern.VALUE,
            lambda answers: ctypes.memmove(
                out,
                ctypes.byref(ctypes.c_int(1 if answers.is_read_only() else 0)),
                4,
            ),
        )

    # -- IRangeValueProvider --

    def _set_range_value(self, this: int, value: float) -> int:
        try:
            answers = _hosted_for(this).blueprint.patterns.get(Pattern.RANGE_VALUE)
            if answers is None or answers.write is None:
                # The documented refusal for a range nobody may set.
                return _UIA_E_INVALIDOPERATION
            answers.write(value)
            return _S_OK
        except Exception:  # noqa: BLE001 - a COM callback must never raise
            return _E_FAIL

    def _range_value(self, this: int, out: int) -> int:
        return self._tell_a_number(this, out, lambda answers: answers.now())

    def _range_read_only(self, this: int, out: int) -> int:
        return self._tell(
            this,
            Pattern.RANGE_VALUE,
            lambda answers: ctypes.memmove(
                out,
                ctypes.byref(ctypes.c_int(1 if answers.is_read_only() else 0)),
                4,
            ),
        )

    def _range_maximum(self, this: int, out: int) -> int:
        return self._tell_a_number(this, out, lambda answers: answers.high())

    def _range_minimum(self, this: int, out: int) -> int:
        return self._tell_a_number(this, out, lambda answers: answers.low())

    def _range_large_change(self, this: int, out: int) -> int:
        return self._tell_a_number(this, out, lambda answers: answers.step() or 0.0)

    def _range_small_change(self, this: int, out: int) -> int:
        return self._tell_a_number(this, out, lambda answers: answers.step() or 0.0)

    # -- ISelectionItemProvider --

    def _select(self, this: int) -> int:
        return self._act(this, Pattern.SELECTION_ITEM, lambda answers: answers.select())

    def _add_to_selection(self, this: int) -> int:
        # A radio's group holds exactly one selection; adding is not a thing.
        return _UIA_E_INVALIDOPERATION

    def _remove_from_selection(self, this: int) -> int:
        return _UIA_E_INVALIDOPERATION

    def _is_selected(self, this: int, out: int) -> int:
        return self._tell(
            this,
            Pattern.SELECTION_ITEM,
            lambda answers: ctypes.memmove(
                out,
                ctypes.byref(ctypes.c_int(1 if answers.is_selected() else 0)),
                4,
            ),
        )

    def _selection_container(self, this: int, out: int) -> int:
        _write_pointer(out, None)
        return _S_OK

    # -- the two shapes every pattern slot reduces to --

    def _act(self, this: int, pattern: Pattern, act: Any) -> int:
        try:
            answers = _hosted_for(this).blueprint.patterns.get(pattern)
            if answers is None:
                return _UIA_E_INVALIDOPERATION
            act(answers)
            return _S_OK
        except Exception:  # noqa: BLE001 - a COM callback must never raise
            return _E_FAIL

    def _tell(self, this: int, pattern: Pattern, tell: Any) -> int:
        try:
            answers = _hosted_for(this).blueprint.patterns.get(pattern)
            if answers is None:
                return _UIA_E_INVALIDOPERATION
            tell(answers)
            return _S_OK
        except Exception:  # noqa: BLE001 - a COM callback must never raise
            return _E_FAIL

    def _tell_a_number(self, this: int, out: int, read: Any) -> int:
        try:
            answers = _hosted_for(this).blueprint.patterns.get(Pattern.RANGE_VALUE)
            if answers is None:
                return _UIA_E_INVALIDOPERATION
            ctypes.cast(out, ctypes.POINTER(ctypes.c_double))[0] = float(read(answers))
            return _S_OK
        except Exception:  # noqa: BLE001 - a COM callback must never raise
            return _E_FAIL


def _a_vtable(slots: tuple[Any, ...]) -> Any:
    fields = [(f"slot{index}", type(bound)) for index, bound in enumerate(slots)]
    vtable_type = type("Vtable", (ctypes.Structure,), {"_fields_": fields})
    return vtable_type(*slots)


def _the_pattern_with_id(pattern_id: int) -> Pattern | None:
    try:
        return Pattern(pattern_id)
    except ValueError:
        return None


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
        _OLEAUT32 = oleaut32
    return _OLEAUT32


def _the_com_layer() -> _ComLayer:
    global _COM_LAYER
    if _COM_LAYER is None:
        _COM_LAYER = _ComLayer()
    return _COM_LAYER


_COM_LAYER: _ComLayer | None = None
_OLEAUT32: Any = None
