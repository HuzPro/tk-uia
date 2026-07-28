"""What a Tk widget tells Windows about itself, and the seam it says it through.

Holds the whole of the package's behaviour and imports nothing
platform-specific: `enable()` builds an :class:`Annotator` over the real COM
store, and specs build one over a recording double.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Protocol

from tk_uia.roles import ROLE_FOR_TK_CLASS, Role
from tk_uia.tkversion import Strategy, TkInterpreter, strategy_for

_A_WIDGET_APPEARED = "<Map>"
_A_WIDGET_DIED = "<Destroy>"
_THE_TABS_CHANGED = "<<NotebookTabChanged>>"

# Anything else replaces whatever Tk and the application already had bound to
# the same event.
_ALONGSIDE_WHAT_IS_ALREADY_BOUND = "+"

_A_WRITE = "write"

# `-text` for almost everything; `-label` only for the classic `tk.Scale`,
# which has no `-text` option. Nothing has both.
_WHERE_A_WIDGET_KEEPS_ITS_WORDS = ("text", "label")

# `cget` answers the variable's *name* (`'PY_VAR0'`), or `''` when unset.
# A `Listbox`'s `-listvariable` and a `Scale`'s `-variable` are deliberately
# not this.
_WHERE_A_WIDGET_KEEPS_THE_VARIABLE_IT_SHOWS = "textvariable"

_NO_VARIABLE_AT_ALL = ""

# A caption's trailing colon is not part of the name it gives.
_HOW_A_CAPTION_IS_PUNCTUATED = ":"

# The roles whose variable is what the widget *holds* rather than what it *is*.
_ROLES_WHOSE_VARIABLE_IS_WHAT_THEY_HOLD = frozenset(
    {Role.TEXT, Role.COMBO_BOX, Role.SPIN_BUTTON}
)

_WHAT_EVERY_TK_WIDGET_ANSWERS_TO = "winfo_class"

_THE_WIDGET_PARAMETER = "widget"
_THE_LABEL_PARAMETER = "label"

# A table because `Role(43)` raises for a number no member carries.
_THE_ROLE_EACH_NUMBER_MEANS: Mapping[int, Role] = {role.value: role for role in Role}


def is_a_window(widget: TkWidget) -> bool:
    """Whether this widget is a toplevel window, whatever its class says.

    Structural because a root's class name is application-chosen:
    `tk.Tk(className='Idle')` answers `'Idle'`. Menus are excluded, being built
    out of a native Windows menu rather than a window a title names.
    """
    return widget.winfo_class() != "Menu" and widget.winfo_toplevel() is widget


_NEVER_SAID = object()

# Win32's answer for "this control has no id"; anything else was put there by
# somebody who is using it.
_NO_CONTROL_ID = 0


class AnnotationRefused(Exception):
    """The annotator would not do what it was asked, and says why.

    Raised rather than shrugged: every failure mode this package refuses looks
    like success from outside, with `S_OK` returned and nothing changed.
    """


class PropId(Enum):
    """The MSAA properties a widget can be annotated with."""

    NAME = auto()
    ROLE = auto()
    VALUE = auto()
    DESCRIPTION = auto()
    DEFAULT_ACTION = auto()
    HELP = auto()
    STATE = auto()


class AccessibilityStore(Protocol):
    """Where annotations go. The only thing in the package that knows about COM."""

    def set_string(self, hwnd: int, prop: PropId, value: str) -> None: ...

    def set_number(self, hwnd: int, prop: PropId, value: int) -> None: ...

    def control_id(self, hwnd: int) -> int: ...

    def set_control_id(self, hwnd: int, control_id: int) -> None: ...

    def clear(self, hwnd: int) -> None: ...


class TkWidget(Protocol):
    """A Tk widget, as the annotator uses it."""

    def winfo_id(self) -> int: ...

    def winfo_class(self) -> str: ...

    def winfo_ismapped(self) -> bool: ...

    # `winfo exists` answers 0 for a path Tk no longer has, where every other
    # `winfo` subcommand raises.
    def winfo_exists(self) -> bool: ...

    def winfo_toplevel(self) -> TkWidget: ...

    def winfo_children(self) -> Sequence[TkWidget]: ...

    def keys(self) -> Sequence[str]: ...

    def cget(self, key: str) -> object: ...


class TkApplication(TkWidget, Protocol):
    """A Tk root: a widget that also owns the interpreter and the bindings."""

    tk: TkInterpreter

    def bind_all(
        self, sequence: str, func: Callable[[TkEvent], object], add: str
    ) -> None: ...


class TkEvent(Protocol):
    """A Tk event, of which only the widget it happened to matters here."""

    widget: TkWidget | str


class TkVariable(Protocol):
    """A `tkinter.Variable`: a value, and a way to hear about changes to it."""

    def get(self) -> object: ...

    # The name `trace_add` hands back is the only way to take the registration
    # off again.
    def trace_add(self, mode: str, callback: Callable[..., object]) -> str: ...

    def trace_remove(self, mode: str, callback_name: str) -> None: ...


class VariableCalled(Protocol):
    """How the Tcl name a widget declares becomes a variable that can be followed.

    `None` where nothing platform-specific was wired in, or where Tk has no
    such variable: the widget is then left exactly as it was.
    """

    def __call__(self, widget: object, name: str) -> TkVariable | None: ...


def no_variables_to_follow(widget: object, name: str) -> TkVariable | None:
    """The null :class:`VariableCalled`, for an annotator wired to no Tcl."""
    return None


class TabbedWidgets(Protocol):
    """Whatever is keeping a notebook's tabs reachable, if anything is."""

    def refresh(self, widget: TkWidget) -> None: ...

    def forget(self, path: str) -> None: ...

    def on(self, path: str) -> Sequence[object]: ...


class NoTabs:
    """The null :class:`TabbedWidgets`, for a Tk that needs none."""

    def refresh(self, widget: TkWidget) -> None: ...

    def forget(self, path: str) -> None: ...

    def on(self, path: str) -> Sequence[object]:
        return ()


class Notifier(Protocol):
    """Whoever needs to hear that a written property changed, if anyone does."""

    def changed(self, hwnd: int, prop: PropId, now: str | int) -> None: ...


class SaysNothing:
    """The null Notifier."""

    def changed(self, hwnd: int, prop: PropId, now: str | int) -> None: ...


class AnswersForItself(Protocol):
    """What the provider layer records per path, as the report reads it."""

    def patterns_on(self, path: str) -> tuple[object, ...]: ...

    def is_left_to_the_proxy(self, path: str) -> bool: ...


class _NothingAnswersForItself:
    def patterns_on(self, path: str) -> tuple[object, ...]:
        return ()

    def is_left_to_the_proxy(self, path: str) -> bool:
        return False


class ProvidedWidgets(Protocol):
    """Whatever is making widgets answer UIA for themselves, if anything is."""

    ledger: AnswersForItself

    def attach(self, widget: TkWidget) -> None: ...

    def forget(self, path: str) -> None: ...


class NoProviders:
    """The null ProvidedWidgets, for a Tk that needs none."""

    def __init__(self) -> None:
        self.ledger = _NothingAnswersForItself()

    def attach(self, widget: TkWidget) -> None: ...

    def forget(self, path: str) -> None: ...


class TroubleSoFar(Protocol):
    """Whatever the callback machinery swallowed, as the report reads it."""

    def so_far(self) -> tuple[str, ...]: ...


class NoTroubleAtAll:
    def so_far(self) -> tuple[str, ...]:
        return ()


@dataclass(frozen=True)
class OwningThread:
    """The thread Tk and the COM apartment both belong to, and the rule about it."""

    ident: int

    @classmethod
    def whichever_is_calling(cls) -> OwningThread:
        return cls(threading.get_ident())

    def refuse_any_other_caller(self) -> None:
        caller = threading.get_ident()
        if caller == self.ident:
            return
        # Both layers below are thread-affine and fail quietly: Tcl corrupts,
        # and a wrong-apartment annotation lands where no client will look.
        raise AnnotationRefused(
            f"thread {caller} reached for widgets owned by thread {self.ident}; "
            "Tk and the COM apartment both belong to the thread that called "
            "enable(), so marshal the call back to it (root.after(0, ...)) "
            "rather than making it from here"
        )


class Wrote(Enum):
    """Where a written property came from, which decides whether it can go stale."""

    INFERRED = auto()
    SAID_ONCE = auto()
    KEPT_IN_STEP = auto()


@dataclass(frozen=True)
class Written:
    """One property, as it was written, and how it came to be written."""

    value: str | int
    source: Wrote


def roles_in_force(roles: Mapping[str, Role] | None) -> Mapping[str, Role]:
    """The built-in role table with the caller's additions laid over it."""
    return {**ROLE_FOR_TK_CLASS, **(roles or {})}


def a_widget_this_package_speaks_for(
    widget: TkWidget, roles: Mapping[str, Role]
) -> Role | None:
    """The role this package would speak for the widget with, or None to leave it be.

    One rule for both layers, so they can never drift over which widgets this
    package speaks for.
    """
    if is_a_window(widget):
        return None
    return roles.get(widget.winfo_class())


class Ledger:
    """What has been said about each window handle, so it is never said twice.

    Deliberately not thread-safe: every path into it is already behind the
    annotator's owning-thread refusal.
    """

    def __init__(self) -> None:
        self._said: dict[int, dict[PropId, Written]] = {}
        # Kept against the Tk path as well as the handle, so `forget` can still
        # find it once `winfo_id` has started raising, which it does from the
        # moment Tk begins tearing the widget down.
        self._handles: dict[str, int] = {}
        # Beside the properties rather than among them: an automation id has no
        # `PROPID_ACC_*` GUID, so a PropId member for it would be one `clear()`
        # iterates over and cannot map.
        self._automation_ids: dict[int, int] = {}

    def already_says(self, hwnd: int, prop: PropId, value: str | int) -> bool:
        written = self._said.get(hwnd, {}).get(prop)
        return written is not None and written.value == value

    def the_application_chose(self, hwnd: int, prop: PropId) -> bool:
        """Whether this property was said by the application rather than inferred.

        `<Map>` fires every time Tk shows a widget again. Without this, the
        caption wins back every name the application chose, on an event the
        application never sees.
        """
        written = self._said.get(hwnd, {}).get(prop)
        return written is not None and written.source is not Wrote.INFERRED

    def chosen(self, hwnd: int, prop: PropId) -> str | int | None:
        """The value the application chose, or None where it only ever inferred.

        An inferred write is an echo of map time and may be stale; a puller
        that preferred it would re-serve the very staleness it exists to cure.
        """
        written = self._said.get(hwnd, {}).get(prop)
        if written is None or written.source is Wrote.INFERRED:
            return None
        return written.value

    def record(self, hwnd: int, prop: PropId, value: str | int, source: Wrote) -> None:
        self._said.setdefault(hwnd, {})[prop] = Written(value, source)

    def record_automation_id(self, hwnd: int, automation_id: int) -> None:
        self._automation_ids[hwnd] = automation_id

    def about(self, hwnd: int) -> Mapping[PropId, Written]:
        return dict(self._said.get(hwnd, {}))

    def automation_id_of(self, hwnd: int) -> int | None:
        return self._automation_ids.get(hwnd)

    def handle_of(self, path: str) -> int | None:
        return self._handles.get(path)

    def paths(self) -> Sequence[str]:
        return tuple(self._handles)

    def now_at(self, path: str, hwnd: int) -> None:
        self._handles[path] = hwnd

    def gone_from(self, path: str) -> None:
        self._handles.pop(path, None)

    def forget(self, hwnd: int) -> None:
        self._said.pop(hwnd, None)
        # Nothing in Win32 resets `GWLP_ID`, so the widget goes on carrying the
        # id while the report stops claiming it.
        self._automation_ids.pop(hwnd, None)


@dataclass(frozen=True)
class _WhatAVariableIsBoundTo:
    """One `trace_add` registration, kept so that it can be taken back off.

    A trace lives on the *variable*, which routinely outlives the widget it was
    bound for, and goes on firing at a dead window path until it is removed.
    """

    variable: TkVariable
    callback_name: str

    def let_go(self) -> None:
        self.variable.trace_remove(_A_WRITE, self.callback_name)


@dataclass(frozen=True)
class _TheCaptionAVariableHolds:
    """A variable read as a caption: whatever it holds, tidied the way one is."""

    variable: TkVariable

    def get(self) -> object:
        return a_caption_read_as_a_name(str(self.variable.get()))

    def trace_add(self, mode: str, callback: Callable[..., object]) -> str:
        return self.variable.trace_add(mode, callback)

    def trace_remove(self, mode: str, callback_name: str) -> None:
        self.variable.trace_remove(mode, callback_name)


@dataclass(frozen=True)
class _TheVariableAWidgetDeclared:
    """The variable a widget named in its own options, and what it is driving."""

    name: str
    prop: PropId
    binding: _WhatAVariableIsBoundTo


class Annotator:
    """Decides what each widget should say, and says it once."""

    def __init__(
        self,
        store: AccessibilityStore,
        roles: Mapping[str, Role] | None = None,
        owner: OwningThread | None = None,
        variables: VariableCalled | None = None,
        notifier: Notifier | None = None,
    ) -> None:
        self._store = store
        self._notifier = notifier if notifier is not None else SaysNothing()
        self.roles = roles_in_force(roles)
        self.ledger = Ledger()
        self._bindings: dict[str, list[_WhatAVariableIsBoundTo]] = {}
        self._declared: dict[str, _TheVariableAWidgetDeclared] = {}
        self._variable_called = (
            variables if variables is not None else no_variables_to_follow
        )
        # Built here rather than defaulted in the signature, which would freeze
        # whichever thread imported this module.
        self._owner = (
            owner if owner is not None else OwningThread.whichever_is_calling()
        )

    def add(self, widget: TkWidget) -> None:
        _every_call_here_takes_a_widget(widget, _THE_WIDGET_PARAMETER)
        # Before anything crosses into the Tcl interpreter, which a foreign
        # thread corrupts quietly.
        self._owner.refuse_any_other_caller()
        role = a_widget_this_package_speaks_for(widget, self.roles)
        if role is None:
            return
        # Inferred rather than said, so `describe` can tell a name read off the
        # widget from one the application chose. Only the first can go stale.
        self._infer(widget, PropId.ROLE, role.value)
        name = words_the_widget_shows(widget)
        if name:
            self._infer(widget, PropId.NAME, name)
        # Last, so a variable outranks the caption where a widget has both.
        self._follow_whatever_variable_the_widget_declares(widget, role)

    def _infer(self, widget: TkWidget, prop: PropId, value: str | int) -> None:
        if self.ledger.the_application_chose(self._handle_of(widget), prop):
            return
        self._write(widget, prop, value, Wrote.INFERRED)

    def _follow_whatever_variable_the_widget_declares(
        self, widget: TkWidget, role: Role
    ) -> None:
        path = str(widget)
        declared = variable_the_widget_declares(widget)
        following = self._declared.get(path)
        if following is not None and following.name == declared:
            # Following again on each `<Map>` would stack a trace per event, on
            # a variable that lives as long as the application.
            return
        prop = _what_a_declared_variable_is(role)
        if following is None and self.ledger.the_application_chose(
            self._handle_of(widget), prop
        ):
            # The application has said this itself, and `<Map>` fires on events
            # it never sees. A binding already ours is ours to move.
            return
        # Two traces on two variables would both fire, in registration order,
        # and the widget would read as whichever was written last.
        self._let_go_of_the_variable_the_widget_declared(path)
        if declared == _NO_VARIABLE_AT_ALL:
            return
        variable = self._variable_called(widget, declared)
        if variable is None:
            return
        self._declared[path] = _TheVariableAWidgetDeclared(
            declared, prop, self._keep_in_step_with(widget, variable, prop)
        )

    def set_role(self, widget: TkWidget, role: Role) -> None:
        _every_call_here_takes_a_widget(widget, _THE_WIDGET_PARAMETER)
        _a_role_is_named_rather_than_numbered(role)
        self._write(widget, PropId.ROLE, role.value)

    def set_name(self, widget: TkWidget, name: str) -> None:
        _every_call_here_takes_a_widget(widget, _THE_WIDGET_PARAMETER)
        self._the_application_has_the_last_word_on(widget, PropId.NAME)
        self._write(widget, PropId.NAME, name)

    def label_for(self, label: TkWidget, widget: TkWidget) -> None:
        """Name a widget after the label that captions it, and follow it if it moves."""
        _every_call_here_takes_a_widget(label, _THE_LABEL_PARAMETER)
        _every_call_here_takes_a_widget(widget, _THE_WIDGET_PARAMETER)
        self._owner.refuse_any_other_caller()
        self._refuse_a_caption_that_holds_its_own_contents(label, widget)
        variable = self._whatever_variable_the_label_declares(label)
        if variable is not None:
            # Released before the new one is bound: a binding of the library's
            # own left in place would take the name back on the next write.
            self._the_application_has_the_last_word_on(widget, PropId.NAME)
            self._keep_in_step_with(
                widget, _TheCaptionAVariableHolds(variable), PropId.NAME
            )
            return
        words = words_the_widget_shows(label)
        if not words:
            raise AnnotationRefused(
                f"{label} shows no words and declares no variable, so there is "
                f"nothing for it to call {widget}. Give the label a `-text` or a "
                "`-textvariable`, or name the widget outright with "
                "set_acc_name(widget, ...)."
            )
        self.set_name(widget, a_caption_read_as_a_name(words))

    def name_of(self, widget: TkWidget) -> str | None:
        """Whatever this widget is called now, or None if nothing has named it."""
        self._owner.refuse_any_other_caller()
        hwnd = self.ledger.handle_of(str(widget))
        if hwnd is None:
            return None
        written = self.ledger.about(hwnd).get(PropId.NAME)
        return None if written is None else str(written.value)

    def set_value(self, widget: TkWidget, value: str) -> None:
        _every_call_here_takes_a_widget(widget, _THE_WIDGET_PARAMETER)
        self._the_application_has_the_last_word_on(widget, PropId.VALUE)
        self._write(widget, PropId.VALUE, value)

    def set_description(self, widget: TkWidget, description: str) -> None:
        _every_call_here_takes_a_widget(widget, _THE_WIDGET_PARAMETER)
        self._write(widget, PropId.DESCRIPTION, description)

    def set_action(self, widget: TkWidget, action: str) -> None:
        _every_call_here_takes_a_widget(widget, _THE_WIDGET_PARAMETER)
        self._write(widget, PropId.DEFAULT_ACTION, action)

    def set_help(self, widget: TkWidget, help_text: str) -> None:
        _every_call_here_takes_a_widget(widget, _THE_WIDGET_PARAMETER)
        self._write(widget, PropId.HELP, help_text)

    def set_state(self, widget: TkWidget, state: int) -> None:
        _every_call_here_takes_a_widget(widget, _THE_WIDGET_PARAMETER)
        self._write(widget, PropId.STATE, state)

    def bind_text_variable(self, widget: TkWidget, variable: TkVariable) -> None:
        _every_call_here_takes_a_widget(widget, _THE_WIDGET_PARAMETER)
        self._the_application_has_the_last_word_on(widget, PropId.NAME)
        self._keep_in_step_with(widget, variable, PropId.NAME)

    def bind_value_variable(self, widget: TkWidget, variable: TkVariable) -> None:
        _every_call_here_takes_a_widget(widget, _THE_WIDGET_PARAMETER)
        self._the_application_has_the_last_word_on(widget, PropId.VALUE)
        self._keep_in_step_with(widget, variable, PropId.VALUE)

    def set_automation_id(self, widget: TkWidget, automation_id: int) -> None:
        _every_call_here_takes_a_widget(widget, _THE_WIDGET_PARAMETER)
        # Checked first: a string reaches ctypes as an argument error several
        # frames below anything the application wrote.
        _an_automation_id_is_a_number(automation_id)
        self._owner.refuse_any_other_caller()
        hwnd = self._handle_of(widget)
        in_use = self._store.control_id(hwnd)
        if in_use == automation_id:
            return
        if in_use != _NO_CONTROL_ID:
            raise AnnotationRefused(
                f"window {hwnd:#x} already carries control id {in_use}, which "
                "Win32 sends it its WM_COMMAND and WM_DRAWITEM messages under; "
                "every Tk button is owner-drawn, so replacing it would stop the "
                f"widget being painted. Refusing to write {automation_id}."
            )
        self._store.set_control_id(hwnd, automation_id)
        self.ledger.record_automation_id(hwnd, automation_id)

    def forget(self, widget: TkWidget | str) -> None:
        self._owner.refuse_any_other_caller()
        path = str(widget)
        self._stop_following_any_variable_bound_to(path)
        hwnd = self.ledger.handle_of(path)
        self.ledger.gone_from(path)
        if hwnd is None:
            return
        self._take_it_all_back(hwnd)

    def _refuse_a_caption_that_holds_its_own_contents(
        self, label: TkWidget, widget: TkWidget
    ) -> None:
        """Refuse a control whose variable is what it holds as the caption for another.

        Asked before the label's `-textvariable` is read, which an entry
        declares exactly as a caption driven by one does. Read the other way
        round, swapped arguments bind the caption to whatever somebody types.
        """
        role = self.roles.get(label.winfo_class())
        if role not in _ROLES_WHOSE_VARIABLE_IS_WHAT_THEY_HOLD:
            return
        raise AnnotationRefused(
            f"{label} is a control a client asks the contents of, so whatever "
            f"drives it is what it holds rather than a caption for {widget}. "
            "The usual cause is swapped arguments: label_for(caption, control) "
            "names the control after the caption, in that order. Where the "
            "words really are on this widget, say set_acc_name(widget, ...) or "
            "follow a variable of your own with bind_text_variable(widget, ...)."
        )

    def _whatever_variable_the_label_declares(
        self, label: TkWidget
    ) -> TkVariable | None:
        declared = variable_the_widget_declares(label)
        if declared == _NO_VARIABLE_AT_ALL:
            return None
        return self._variable_called(label, declared)

    def _keep_in_step_with(
        self, widget: TkWidget, variable: TkVariable, prop: PropId
    ) -> _WhatAVariableIsBoundTo:
        # Said once here as well as on every write from now on: a trace fires
        # on the *next* change and never for the one already made.
        callback_name = variable.trace_add(
            _A_WRITE,
            lambda *_: self._announce_unless_the_widget_has_gone(
                widget, variable, prop
            ),
        )
        bound = _WhatAVariableIsBoundTo(variable, callback_name)
        self._bindings.setdefault(str(widget), []).append(bound)
        self._announce(widget, variable, prop)
        return bound

    def _announce_unless_the_widget_has_gone(
        self, widget: TkWidget, variable: TkVariable, prop: PropId
    ) -> None:
        # Second line behind `forget`: a widget can go by a route that never
        # reaches it, and this write would then land inside Tcl's own callback.
        if not widget.winfo_exists():
            return
        self._announce(widget, variable, prop)

    def _announce(self, widget: TkWidget, variable: TkVariable, prop: PropId) -> None:
        self._write(
            widget, prop, _whatever_the_variable_holds(variable), Wrote.KEPT_IN_STEP
        )

    def _the_application_has_the_last_word_on(
        self, widget: TkWidget, prop: PropId
    ) -> None:
        """Stop following a declared variable for a property the application is setting.

        Released rather than merely outranked: a binding left in place fires
        from inside Tcl and takes back the word the application just chose.
        """
        path = str(widget)
        following = self._declared.get(path)
        if following is None or following.prop is not prop:
            return
        self._let_go_of_the_variable_the_widget_declared(path)

    def _let_go_of_the_variable_the_widget_declared(self, path: str) -> None:
        following = self._declared.pop(path, None)
        if following is None:
            return
        following.binding.let_go()
        # This one and no other: the bindings an application asked for by hand
        # sit in the same list, and those are `forget()`'s to release.
        self._bindings[path] = [
            binding
            for binding in self._bindings.get(path, ())
            if binding is not following.binding
        ]

    def _stop_following_any_variable_bound_to(self, path: str) -> None:
        self._declared.pop(path, None)
        for binding in self._bindings.pop(path, ()):
            binding.let_go()

    def _write(
        self,
        widget: TkWidget,
        prop: PropId,
        value: str | int,
        source: Wrote = Wrote.SAID_ONCE,
    ) -> None:
        self._owner.refuse_any_other_caller()
        self._refuse_a_window_that_already_names_itself(widget)
        hwnd = self._handle_of(widget)
        if not self.ledger.already_says(hwnd, prop, value):
            # `<Map>` fires on every unhide, tab change and geometry shuffle,
            # so without this the COM call is paid for again on every repaint.
            self._put(hwnd, prop, value)
            # The same dedup decides who hears about it: no change, no event.
            self._notifier.changed(hwnd, prop, value)
        self.ledger.record(hwnd, prop, value, source)

    def _put(self, hwnd: int, prop: PropId, value: str | int) -> None:
        # COM has a separate entry point for each: a string, or a number in a
        # VARIANT.
        if isinstance(value, str):
            self._store.set_string(hwnd, prop, value)
        else:
            self._store.set_number(hwnd, prop, value)

    def _handle_of(self, widget: TkWidget) -> int:
        path = str(widget)
        hwnd = widget.winfo_id()
        abandoned = self.ledger.handle_of(path)
        if abandoned is not None and abandoned != hwnd:
            # Tk rebuilt the widget at the same path on a new window, and the
            # `<Destroy>` that would have released the old handle is past.
            self._take_it_all_back(abandoned)
        self.ledger.now_at(path, hwnd)
        return hwnd

    def _refuse_a_window_that_already_names_itself(self, widget: TkWidget) -> None:
        if not is_a_window(widget):
            return
        # `winfo_id()` on a toplevel answers Tk's inner container, not the
        # window, so the property would land on a pane and name nothing.
        raise AnnotationRefused(
            f"{widget} is a window, and a window already has an accessible name "
            "from `wm title`, which is what resolves it for every query that "
            "follows. Annotating one writes to the container pane behind it "
            "instead of to the window, so use `root.title(...)` to name it, and "
            "annotate the widgets inside it."
        )

    def _take_it_all_back(self, hwnd: int) -> None:
        self._store.clear(hwnd)
        self.ledger.forget(hwnd)


class InertAnnotator:
    """An annotator for the Tks that need none, answering to everything, doing nothing.

    `install()` hands one back for `NATIVE` and `UNSUPPORTED`.
    """

    def __init__(self, roles: Mapping[str, Role] | None = None) -> None:
        # Carried rather than discarded so that `describe` can say what a widget
        # class *would* have been announced as, on a platform where nothing was.
        self.roles = roles_in_force(roles)
        self.ledger = Ledger()

    def add(self, widget: TkWidget) -> None: ...

    def bind_text_variable(self, widget: TkWidget, variable: TkVariable) -> None: ...

    def bind_value_variable(self, widget: TkWidget, variable: TkVariable) -> None: ...

    def set_role(self, widget: TkWidget, role: Role) -> None: ...

    def set_name(self, widget: TkWidget, name: str) -> None: ...

    def label_for(self, label: TkWidget, widget: TkWidget) -> None: ...

    def name_of(self, widget: TkWidget) -> str | None:
        # `None` rather than the caption the widget shows: nothing was written,
        # so nothing above may report a name no client can read.
        return None

    def set_value(self, widget: TkWidget, value: str) -> None: ...

    def set_description(self, widget: TkWidget, description: str) -> None: ...

    def set_action(self, widget: TkWidget, action: str) -> None: ...

    def set_help(self, widget: TkWidget, help_text: str) -> None: ...

    def set_state(self, widget: TkWidget, state: int) -> None: ...

    def set_automation_id(self, widget: TkWidget, automation_id: int) -> None: ...

    def forget(self, widget: TkWidget | str) -> None: ...


@dataclass(frozen=True)
class Installation:
    """What switching accessibility on came to: what happened, and what to use."""

    strategy: Strategy
    annotator: Annotator | InertAnnotator
    # A factory rather than a default, so the thread is never the import thread.
    owner: OwningThread = field(default_factory=OwningThread.whichever_is_calling)
    tabs: TabbedWidgets = field(default_factory=NoTabs)
    providers: ProvidedWidgets = field(default_factory=NoProviders)
    providers_stood_down_because: str | None = None
    trouble: TroubleSoFar = field(default_factory=NoTroubleAtAll)


def install(
    root: TkApplication,
    store: AccessibilityStore,
    roles: Mapping[str, Role] | None = None,
    tabs: TabbedWidgets | None = None,
    variables: VariableCalled | None = None,
    providers: ProvidedWidgets | None = None,
    notifier: Notifier | None = None,
    providers_stood_down_because: str | None = None,
    trouble: TroubleSoFar | None = None,
) -> Installation:
    strategy = strategy_for(root.tk)
    owner = OwningThread.whichever_is_calling()
    if strategy is not Strategy.ANNOTATED:
        return Installation(strategy, InertAnnotator(roles), owner)
    notebooks = tabs if tabs is not None else NoTabs()
    provided = providers if providers is not None else NoProviders()
    annotator = Annotator(store, roles, owner, variables, notifier)
    _follow_every_widget_tk_maps_or_destroys(root, annotator, notebooks, provided)
    _annotate_everything_already_on_screen(root, annotator, notebooks, provided)
    reported = Strategy.PROVIDED if providers is not None else Strategy.ANNOTATED
    return Installation(
        reported,
        annotator,
        owner,
        notebooks,
        provided,
        providers_stood_down_because,
        trouble if trouble is not None else NoTroubleAtAll(),
    )


def _follow_every_widget_tk_maps_or_destroys(
    root: TkApplication,
    annotator: Annotator,
    notebooks: TabbedWidgets,
    provided: ProvidedWidgets,
) -> None:
    root.bind_all(
        _A_WIDGET_APPEARED,
        lambda event: _annotate_if_there_is_still_a_widget(
            annotator, notebooks, provided, event.widget
        ),
        add=_ALONGSIDE_WHAT_IS_ALREADY_BOUND,
    )
    root.bind_all(
        _A_WIDGET_DIED,
        lambda event: _let_go_of(annotator, notebooks, provided, event.widget),
        add=_ALONGSIDE_WHAT_IS_ALREADY_BOUND,
    )
    # A notebook's tabs are not widgets and never map, so `<Map>` says nothing
    # about one being added, removed or renamed.
    root.bind_all(
        _THE_TABS_CHANGED,
        lambda event: _refresh_if_there_is_still_a_widget(notebooks, event.widget),
        add=_ALONGSIDE_WHAT_IS_ALREADY_BOUND,
    )


def _annotate_everything_already_on_screen(
    root: TkApplication,
    annotator: Annotator,
    notebooks: TabbedWidgets,
    provided: ProvidedWidgets,
) -> None:
    # `<Map>` fires once, on the way up: every widget already showing has had
    # its and will not get another.
    for widget in every_widget_under(root):
        if widget.winfo_ismapped():
            annotator.add(widget)
            notebooks.refresh(widget)
            provided.attach(widget)


def every_widget_under(widget: TkWidget) -> Iterator[TkWidget]:
    # A widget created under one parent and managed into another is claimed by
    # both; a walk with no memory counts its subtree twice.
    yield from _every_widget_under(widget, seen=set())


def _every_widget_under(widget: TkWidget, seen: set[str]) -> Iterator[TkWidget]:
    for child in widget.winfo_children():
        path = str(child)
        if path in seen:
            continue
        seen.add(path)
        yield child
        yield from _every_widget_under(child, seen)


def _annotate_if_there_is_still_a_widget(
    annotator: Annotator,
    notebooks: TabbedWidgets,
    provided: ProvidedWidgets,
    widget: TkWidget | str,
) -> None:
    if isinstance(widget, str):
        # Tk passes the path rather than the object when it can no longer
        # resolve one.
        return
    annotator.add(widget)
    notebooks.refresh(widget)
    provided.attach(widget)


def _refresh_if_there_is_still_a_widget(
    notebooks: TabbedWidgets, widget: TkWidget | str
) -> None:
    if isinstance(widget, str):
        return
    notebooks.refresh(widget)


def _let_go_of(
    annotator: Annotator,
    notebooks: TabbedWidgets,
    provided: ProvidedWidgets,
    widget: TkWidget | str,
) -> None:
    annotator.forget(widget)
    # By path, not by widget: `<Destroy>` is the one event that routinely
    # carries a path whose widget object has already gone.
    notebooks.forget(str(widget))
    provided.forget(str(widget))


def _whatever_the_variable_holds(variable: TkVariable) -> str:
    return str(variable.get())


def words_the_widget_shows(widget: TkWidget) -> str | None:
    """Whatever is in the widget's `-text` right now, or None if it has no such option.

    `None` rather than `""`: `describe` has to tell a widget showing nothing
    from one with nowhere to keep words.
    """
    # Asked rather than attempted: an entry, a listbox and a canvas have no
    # `-text` option at all, and reading one raises.
    options_this_widget_has = widget.keys()
    for where in _WHERE_A_WIDGET_KEEPS_ITS_WORDS:
        if where in options_this_widget_has:
            return str(widget.cget(where))
    return None


def a_caption_read_as_a_name(caption: str) -> str:
    """A label's words as the name of the widget it captions: "Host:" names "Host"."""
    return caption.strip().removesuffix(_HOW_A_CAPTION_IS_PUNCTUATED).strip()


def _what_a_declared_variable_is(role: Role) -> PropId:
    """Whether the variable driving this widget is what it *holds* or what it *is*."""
    return (
        PropId.VALUE if role in _ROLES_WHOSE_VARIABLE_IS_WHAT_THEY_HOLD else PropId.NAME
    )


def _every_call_here_takes_a_widget(widget: object, parameter: str) -> None:
    """Refuse anything that is not a Tk widget, and say which argument it was."""
    if hasattr(widget, _WHAT_EVERY_TK_WIDGET_ANSWERS_TO):
        return
    raise TypeError(
        f"{parameter} must be a Tk widget, and this is a "
        f"{type(widget).__name__}. Everything here is written against the "
        "window handle winfo_id() answers with, so each call takes the widget "
        "itself rather than its Tk path, its name or the words it shows."
    )


def _a_role_is_named_rather_than_numbered(role: object) -> None:
    if isinstance(role, Role):
        return
    raise TypeError(
        f"role must be a tk_uia.Role, and this is a {type(role).__name__}. "
        f"{_whichever_role_that_number_would_have_been(role)}"
    )


def _whichever_role_that_number_would_have_been(role: object) -> str:
    meant = _THE_ROLE_EACH_NUMBER_MEANS.get(role) if isinstance(role, int) else None
    if meant is None:
        return (
            "A role decides which patterns the MSAA-to-UIA bridge offers for "
            "the widget at all, so it is named here rather than numbered: "
            "set_acc_role(widget, Role.PUSH_BUTTON)."
        )
    return (
        f"Role({role}) is Role.{meant.name}; say "
        f"set_acc_role(widget, Role.{meant.name})."
    )


def _an_automation_id_is_a_number(automation_id: object) -> None:
    if isinstance(automation_id, int):
        return
    raise TypeError(
        f"automation_id must be an int, and this is a "
        f"{type(automation_id).__name__}. UI Automation renders an "
        "AutomationId as text, which is where the temptation comes from, but "
        "what is written here is GWLP_ID, the Win32 control id, and that is a "
        "number and nothing else: set_automation_id(widget, 4207) reads back "
        "as '4207'."
    )


def variable_the_widget_declares(widget: TkWidget) -> str:
    """The Tcl name of the variable driving this widget, or "" if it names none."""
    options_this_widget_has = widget.keys()
    if _WHERE_A_WIDGET_KEEPS_THE_VARIABLE_IT_SHOWS not in options_this_widget_has:
        return _NO_VARIABLE_AT_ALL
    return str(widget.cget(_WHERE_A_WIDGET_KEEPS_THE_VARIABLE_IT_SHOWS))
