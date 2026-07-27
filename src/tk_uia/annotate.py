"""What a Tk widget tells Windows about itself, and the seam it says it through.

Where it plugs in: `enable()` builds an :class:`Annotator` over the real COM
store and puts it in the path of every widget Tk maps; specs build one over a
recording double. This module is the whole of the package's behaviour and it
imports nothing platform-specific, which is what lets that be true.
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
# the same event, which is a startling amount of a Tk application to break in
# exchange for switching accessibility on.
_ALONGSIDE_WHAT_IS_ALREADY_BOUND = "+"

# The only kind of variable change worth re-announcing.
_A_WRITE = "write"

# `-text` for almost everything, and `-label` for the classic `tk.Scale`, which
# is the one widget in either toolkit with no `-text` option at all. In order:
# nothing has both, and if anything ever does, the option every other widget
# uses is the one to believe.
_WHERE_A_WIDGET_KEEPS_ITS_WORDS = ("text", "label")

# Where a widget keeps the *name* of the variable driving it, which is all it
# keeps: measured, `cget` answers `'PY_VAR0'` where one is declared and `''`
# where the option exists and nobody filled it in. Sixteen classes across both
# toolkits have the option; `tk.Text` has none, and a `Listbox`'s
# `-listvariable` and a `Scale`'s `-variable` are deliberately not this.
_WHERE_A_WIDGET_KEEPS_THE_VARIABLE_IT_SHOWS = "textvariable"

# Nothing declared, which is what an untouched `-textvariable` answers with.
_NO_VARIABLE_AT_ALL = ""

# How a form punctuates a caption, and what none of it means: measured across a
# real six-tab settings dialog, every caption in it ends with a colon, and no
# screen reader user wants to hear one read out as part of a control's name.
_HOW_A_CAPTION_IS_PUNCTUATED = ":"

# The three roles whose variable is what the widget *holds* rather than what it
# *is*: an entry, a combobox and a spinbox are all controls a client asks the
# contents of, and a `-textvariable` on one of them is those contents. Every
# other class carrying the option — a label, a button, a checkbutton, a
# menubutton — shows the variable *instead of* a caption, so there it is the
# widget's whole name.
_ROLES_WHOSE_VARIABLE_IS_WHAT_THEY_HOLD = frozenset(
    {Role.TEXT, Role.COMBO_BOX, Role.SPIN_BUTTON}
)

# Checked ahead of the role table rather than merely left out of it: a window
# gets a correct accessible name from `wm title` for free, and overriding it
# breaks resolving the window by its title, which is where every other query
# starts. A caller supplying their own table must not be able to undo that.
WINDOWS_THAT_ALREADY_NAME_THEMSELVES = frozenset({"Tk", "Toplevel"})

_NEVER_SAID = object()

# Win32's answer for "this control has no id". Anything else was put there by
# somebody who is using it.
_NO_CONTROL_ID = 0


class AnnotationRefused(Exception):
    """The annotator would not do what it was asked, and says why.

    Raised rather than shrugged: every failure mode this package exists to
    refuse looks like success from the outside — `S_OK` returned, nothing
    changed — so an annotation that cannot be made honestly has to be loud.
    """


class PropId(Enum):
    """The MSAA properties a widget can be annotated with.

    Named rather than numbered on purpose: the GUIDs `oleacc.h` gives these live
    in the one module that talks to COM, so nothing above it can pass the wrong
    one by transcribing it from memory.
    """

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

    # Asked rather than inferred from a raise: `winfo exists` answers 0 for a
    # path Tk no longer has, where every other `winfo` subcommand raises.
    def winfo_exists(self) -> bool: ...

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

    # The name `trace_add` hands back is the only handle on the registration it
    # made, and the only way to take it off again.
    def trace_add(self, mode: str, callback: Callable[..., object]) -> str: ...

    def trace_remove(self, mode: str, callback_name: str) -> None: ...


class VariableCalled(Protocol):
    """How the Tcl name a widget declares becomes a variable that can be followed.

    A seam rather than a call, and for a sharper reason than the rest of them:
    reaching an application's variable by name means raw Tcl, because
    `tkinter.Variable.__del__` *unsets* the variable it names — measured, a
    wrapper built around somebody else's `StringVar` destroys that `StringVar`
    the moment it is collected. So the domain says which name it wants and
    something platform-specific answers with a value and somewhere to hang a
    trace.

    `None` for a Tk that has no such variable, and for every installation
    nothing platform-specific was wired into: a declared name is then a string
    and nothing more, and the widget is left exactly as it was.
    """

    def __call__(self, widget: object, name: str) -> TkVariable | None: ...


def no_variables_to_follow(widget: object, name: str) -> TkVariable | None:
    """For every annotator built without a way to reach an application's variables.

    Same reason as :class:`NoTabs`: the alternative is an "is anything wired in"
    branch at the one place a declared variable is noticed, which is the kind of
    branch only ever wrong on the platform nobody is testing on.
    """
    return None


class TabbedWidgets(Protocol):
    """Whatever is keeping a notebook's tabs reachable, if anything is.

    A protocol rather than an import: the implementation lives in `tabs`, which
    already imports this module for its store and its property ids, and one
    seam declared here is cheaper than untangling that into a third.
    """

    def refresh(self, widget: TkWidget) -> None: ...

    def forget(self, path: str) -> None: ...

    def on(self, path: str) -> Sequence[object]: ...


class NoTabs:
    """For a Tk that needs none, and for every spec not about tabs.

    Same reason as :class:`InertAnnotator`: the alternative is a "is anything
    installed" branch at each of the three places a notebook is noticed, and
    those are the branches only ever wrong on the platform nobody is testing on.
    """

    def refresh(self, widget: TkWidget) -> None: ...

    def forget(self, path: str) -> None: ...

    def on(self, path: str) -> Sequence[object]:
        return ()


@dataclass(frozen=True)
class OwningThread:
    """The thread Tk and the COM apartment both belong to, and the rule about it.

    A value object rather than a method on the annotator, because `describe`
    needs the same rule and cannot get it from there: on a Tk that needs no
    annotating the annotator is an :class:`InertAnnotator`, whose whole job is
    to refuse nothing.
    """

    ident: int

    @classmethod
    def whichever_is_calling(cls) -> OwningThread:
        return cls(threading.get_ident())

    def refuse_any_other_caller(self) -> None:
        caller = threading.get_ident()
        if caller == self.ident:
            return
        # Both layers below here are thread-affine. Reading `winfo_id` off the
        # Tk thread corrupts the interpreter, and a COM apartment belongs to the
        # thread that entered it — an annotation made from the wrong one is
        # written somewhere no client will ever look.
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
    """The role table an installation will really use, caller's additions and all.

    Laid over the built-in table rather than replacing it: a caller who names
    one class means "and this one too", not "forget the rest". Read by
    `describe`, which would otherwise tell an application that has already
    passed `roles=` to go and pass `roles=`.
    """
    return {**ROLE_FOR_TK_CLASS, **(roles or {})}


class Ledger:
    """What has been said about each window handle, so it is never said twice.

    Two readers and one writer: the annotator asks whether a value is already in
    place before paying for a COM call, and `describe` asks what is in place at
    all. It is deliberately not thread-safe and does not need to be — every path
    into it is already behind the annotator's owning-thread refusal.
    """

    def __init__(self) -> None:
        self._said: dict[int, dict[PropId, Written]] = {}
        # Kept against the widget's Tk path as well as its handle, so `forget`
        # can still find it once `winfo_id` has started raising — which it does
        # from the moment Tk begins tearing the widget down.
        self._handles: dict[str, int] = {}
        # Beside the properties rather than among them: an automation id goes
        # into `GWLP_ID` and has no `PROPID_ACC_*` GUID at all, so a PropId
        # member for it would be one `clear()` iterates over and cannot map.
        self._automation_ids: dict[int, int] = {}

    def already_says(self, hwnd: int, prop: PropId, value: str | int) -> bool:
        written = self._said.get(hwnd, {}).get(prop)
        return written is not None and written.value == value

    def the_application_chose(self, hwnd: int, prop: PropId) -> bool:
        """Whether this property was said by the application rather than inferred.

        `<Map>` fires every time Tk shows a widget again — a notebook tab
        reopened, a `pack_forget` undone — and the automatic annotation runs
        over it each time. Without this, the caption quietly wins back every
        name the application deliberately gave a widget, on an event the
        application never sees.
        """
        written = self._said.get(hwnd, {}).get(prop)
        return written is not None and written.source is not Wrote.INFERRED

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
        # id while the report stops claiming it. Reporting one this package can
        # no longer account for would be the worse of the two.
        self._automation_ids.pop(hwnd, None)


@dataclass(frozen=True)
class _WhatAVariableIsBoundTo:
    """One `trace_add` registration, kept so that it can be taken back off.

    A trace lives on the *variable*, which routinely outlives the widget it was
    bound for: without this the trace goes on firing at a dead window path
    forever, one unhandled traceback on stderr per write, for the life of the
    process — and a `forget()` that left it there would find the next write
    quietly re-announcing the widget the caller had just taken back.
    """

    variable: TkVariable
    callback_name: str

    def let_go(self) -> None:
        self.variable.trace_remove(_A_WRITE, self.callback_name)


@dataclass(frozen=True)
class _TheCaptionAVariableHolds:
    """A variable read as a caption: whatever it holds, tidied the way one is.

    A decorator over the variable rather than a transform threaded through the
    announcing, because the rule belongs to the words and not to the mechanism:
    a widget named after a caption someone retitles follows that variable
    exactly as every other bound widget follows one, and the colon is off the
    words wherever they came from.
    """

    variable: TkVariable

    def get(self) -> object:
        return a_caption_read_as_a_name(str(self.variable.get()))

    def trace_add(self, mode: str, callback: Callable[..., object]) -> str:
        return self.variable.trace_add(mode, callback)

    def trace_remove(self, mode: str, callback_name: str) -> None:
        self.variable.trace_remove(mode, callback_name)


@dataclass(frozen=True)
class _TheVariableAWidgetDeclared:
    """The variable a widget named in its own options, and what it is driving.

    Held apart from the bindings an application asked for by hand, which sit
    beside it in `_bindings`: only this one is the library's to take back. An
    application that names a widget itself has the last word, and the binding it
    never asked for has to stop rather than take that name back on the next
    write.
    """

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
    ) -> None:
        self._store = store
        self.roles = roles_in_force(roles)
        self.ledger = Ledger()
        self._bindings: dict[str, list[_WhatAVariableIsBoundTo]] = {}
        self._declared: dict[str, _TheVariableAWidgetDeclared] = {}
        self._variable_called = (
            variables if variables is not None else no_variables_to_follow
        )
        # Built here rather than defaulted in the signature, which would freeze
        # whichever thread happened to import this module.
        self._owner = (
            owner if owner is not None else OwningThread.whichever_is_calling()
        )

    def add(self, widget: TkWidget) -> None:
        # Before the first question is asked of the widget, rather than at the
        # store below: `winfo_class`, `keys` and `cget` each cross into the Tcl
        # interpreter, and doing that from a foreign thread corrupts it quietly
        # — where a misplaced COM write merely goes somewhere nobody reads.
        self._owner.refuse_any_other_caller()
        tk_class = widget.winfo_class()
        if tk_class in WINDOWS_THAT_ALREADY_NAME_THEMSELVES:
            return
        role = self.roles.get(tk_class)
        if role is None:
            return
        # Written as inferred rather than through `set_role`/`set_name`, so that
        # `describe` can tell a name this package read off the widget from one
        # the application chose. Only the first can go stale; calling the second
        # stale would fire on the pattern the README encourages.
        self._infer(widget, PropId.ROLE, role.value)
        name = words_the_widget_shows(widget)
        if name:
            self._infer(widget, PropId.NAME, name)
        # Last, so that a variable outranks the caption where a widget has both:
        # a classic `tk.Label` keeps its `-text` in step with its `-textvariable`
        # and so agrees, and where the two ever disagree the variable is the one
        # still moving.
        self._follow_whatever_variable_the_widget_declares(widget, role)

    def _infer(self, widget: TkWidget, prop: PropId, value: str | int) -> None:
        # Never over the application's own answer. This runs again on every
        # `<Map>`, and a widget shown a second time must not start announcing
        # its caption in place of the name its author chose for it.
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
            # `<Map>` fires on every unhide, tab change and geometry shuffle,
            # and `add_acc_object` is the escape hatch the README tells an
            # application to call. Following again on each would stack a trace
            # per event, on a variable that lives as long as the application.
            return
        prop = _what_a_declared_variable_is(role)
        if following is None and self.ledger.the_application_chose(
            self._handle_of(widget), prop
        ):
            # The application has said this property itself, once or by binding
            # a variable of its own. `<Map>` fires on events it never sees, so a
            # binding made on one of them would quietly take that word back —
            # where a binding already ours is ours to move.
            return
        # Whatever it declared before this, whether or not it declares anything
        # now: two traces on two variables would both fire, in registration
        # order, and the widget would read as whichever was written last.
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
        self._write(widget, PropId.ROLE, role.value)

    def set_name(self, widget: TkWidget, name: str) -> None:
        self._the_application_has_the_last_word_on(widget, PropId.NAME)
        self._write(widget, PropId.NAME, name)

    def label_for(self, label: TkWidget, widget: TkWidget) -> None:
        """Name a widget after the label that captions it, and follow it if it moves.

        In Tk a caption is a *sibling* and nothing records the relationship, so
        no amount of reading the widget can find it: this is the application
        saying it, and it is said once for both properties a caption can be
        kept in.
        """
        self._owner.refuse_any_other_caller()
        variable = self._whatever_variable_the_label_declares(label)
        if variable is not None:
            # Released before the new one is bound, exactly as the manual
            # bindings do it: a binding of the library's own left in place would
            # take the name back on the next write, from inside Tcl.
            self._the_application_has_the_last_word_on(widget, PropId.NAME)
            self._keep_in_step_with(
                widget, _TheCaptionAVariableHolds(variable), PropId.NAME
            )
            return
        words = words_the_widget_shows(label)
        if not words:
            # Loudly, because the quiet alternative is naming the widget `''`,
            # and a client cannot tell a confident empty answer from a true one.
            raise AnnotationRefused(
                f"{label} shows no words and declares no variable, so there is "
                f"nothing for it to call {widget}. Give the label a `-text` or a "
                "`-textvariable`, or name the widget outright with "
                "set_acc_name(widget, ...)."
            )
        # Read once and stale from the next `config(text=...)`, exactly as every
        # other caption in this package is — say it again to re-read it, or
        # drive the label from a variable, which is followed above.
        self.set_name(widget, a_caption_read_as_a_name(words))

    def name_of(self, widget: TkWidget) -> str | None:
        """Whatever this widget is called now, or None if nothing has named it.

        Asked by anything working names out from the widgets *around* a widget
        rather than from the widget itself: a convention that guessed instead
        would overwrite the one name in the window somebody chose deliberately.
        """
        self._owner.refuse_any_other_caller()
        hwnd = self.ledger.handle_of(str(widget))
        if hwnd is None:
            return None
        written = self.ledger.about(hwnd).get(PropId.NAME)
        return None if written is None else str(written.value)

    def set_value(self, widget: TkWidget, value: str) -> None:
        self._the_application_has_the_last_word_on(widget, PropId.VALUE)
        self._write(widget, PropId.VALUE, value)

    def set_description(self, widget: TkWidget, description: str) -> None:
        self._write(widget, PropId.DESCRIPTION, description)

    def set_action(self, widget: TkWidget, action: str) -> None:
        self._write(widget, PropId.DEFAULT_ACTION, action)

    def set_help(self, widget: TkWidget, help_text: str) -> None:
        self._write(widget, PropId.HELP, help_text)

    def set_state(self, widget: TkWidget, state: int) -> None:
        self._write(widget, PropId.STATE, state)

    def bind_text_variable(self, widget: TkWidget, variable: TkVariable) -> None:
        # The override for the variable a widget declares, and the whole answer
        # for a widget that declares none — the name a client reads is often not
        # the one on screen, and only the application knows which variable
        # really says who the widget is.
        self._the_application_has_the_last_word_on(widget, PropId.NAME)
        self._keep_in_step_with(widget, variable, PropId.NAME)

    def bind_value_variable(self, widget: TkWidget, variable: TkVariable) -> None:
        # The contents of an entry are not on the widget to be read back — they
        # are in the variable, and where the widget did not name that variable
        # itself, only the application knows which one it is.
        self._the_application_has_the_last_word_on(widget, PropId.VALUE)
        self._keep_in_step_with(widget, variable, PropId.VALUE)

    def set_automation_id(self, widget: TkWidget, automation_id: int) -> None:
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

    def _whatever_variable_the_label_declares(
        self, label: TkWidget
    ) -> TkVariable | None:
        # `None` for a label driving itself from `-text`, and for one whose
        # variable nothing platform-specific can reach — on a Tk with no such
        # variable the declared name is a string and nothing more, and the words
        # the label is showing are still the honest answer.
        declared = variable_the_widget_declares(label)
        if declared == _NO_VARIABLE_AT_ALL:
            return None
        return self._variable_called(label, declared)

    def _keep_in_step_with(
        self, widget: TkWidget, variable: TkVariable, prop: PropId
    ) -> _WhatAVariableIsBoundTo:
        # Said once here as well as on every write from now on: a trace fires on
        # the *next* change and never for the one already made, so a binding that
        # only traced would leave the widget announcing whatever it was annotated
        # with before the variable existed — for most widgets, nothing at all.
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
        # Second line behind `forget`, which is what actually takes the trace
        # off. A widget can still go away by a route that never reaches it — an
        # annotator driven directly rather than through `enable()`, or an earlier
        # `<Destroy>` handler that raised before ours ran — and the write that
        # follows lands inside Tcl's own callback, where the application has no
        # call of its own to wrap it in.
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

        Released rather than merely outranked. The trace fires from inside Tcl,
        on a write the application makes to its own variable — so a binding left
        in place would take back the name or the value it had just chosen, with
        no call of its own anywhere in the traceback.
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
        # sit in the same list, and those are `forget()`'s to release rather
        # than this package's.
        self._bindings[path] = [
            binding
            for binding in self._bindings.get(path, ())
            if binding is not following.binding
        ]

    def _stop_following_any_variable_bound_to(self, path: str) -> None:
        # Everything at once, whoever asked for it: `forget()` is the
        # application saying it wants nothing more said about this widget.
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
            # `<Map>` fires on every unhide, tab change and geometry shuffle.
            # Without this the cost of annotating a window is paid again on
            # every repaint, forever, for no change to what a client reads.
            self._put(hwnd, prop, value)
        self.ledger.record(hwnd, prop, value, source)

    def _put(self, hwnd: int, prop: PropId, value: str | int) -> None:
        # The one place the two kinds of property part company, because COM has
        # a separate entry point for each: a string, or a number in a VARIANT.
        if isinstance(value, str):
            self._store.set_string(hwnd, prop, value)
        else:
            self._store.set_number(hwnd, prop, value)

    def _handle_of(self, widget: TkWidget) -> int:
        path = str(widget)
        hwnd = widget.winfo_id()
        abandoned = self.ledger.handle_of(path)
        if abandoned is not None and abandoned != hwnd:
            # Tk rebuilt the widget at the same path on a new window. The
            # `<Destroy>` that would have released the old handle is already
            # past, so nothing else is ever going to clear it.
            self._take_it_all_back(abandoned)
        self.ledger.now_at(path, hwnd)
        return hwnd

    def _refuse_a_window_that_already_names_itself(self, widget: TkWidget) -> None:
        if widget.winfo_class() not in WINDOWS_THAT_ALREADY_NAME_THEMSELVES:
            return
        # `add()` has always skipped these, but the manual calls walked straight
        # past that rule — and this is the one case where doing as asked is
        # worse than refusing. `winfo_id()` on a toplevel answers with the
        # container child Tk puts every widget under, not with the window, so
        # the property lands on an inner pane: the window stays unnamed, and a
        # client reading the pane finds a confident, wrong answer where before
        # it found none.
        raise AnnotationRefused(
            f"{widget} is a window, and a window already has an accessible name "
            "from `wm title` — which is what resolves it for every query that "
            "follows. Annotating one writes to the container pane behind it "
            "instead of to the window, so use `root.title(...)` to name it, and "
            "annotate the widgets inside it."
        )

    def _take_it_all_back(self, hwnd: int) -> None:
        self._store.clear(hwnd)
        self.ledger.forget(hwnd)


class InertAnnotator:
    """An annotator for the Tks that need none, answering to everything, doing nothing.

    Where it plugs in: `install()` hands one back for `NATIVE` and
    `UNSUPPORTED`. The alternative is every function on the public surface
    repeating the same "is there anything installed" branch, and an application
    repeating a platform check around every call it makes — which is the kind of
    thing that is only ever wrong on the platform the author is not using.
    """

    def __init__(self, roles: Mapping[str, Role] | None = None) -> None:
        # Carried rather than discarded so that `describe` can say what a widget
        # class *would* have been announced as, on a platform where nothing was.
        self.roles = roles_in_force(roles)
        # An empty one, for the same reason this class exists at all: it keeps
        # the "is there anything installed" branch out of `describe`, which
        # would otherwise be the one branch only ever wrong on the platform its
        # author is not using.
        self.ledger = Ledger()

    def add(self, widget: TkWidget) -> None: ...

    def bind_text_variable(self, widget: TkWidget, variable: TkVariable) -> None: ...

    def bind_value_variable(self, widget: TkWidget, variable: TkVariable) -> None: ...

    def set_role(self, widget: TkWidget, role: Role) -> None: ...

    def set_name(self, widget: TkWidget, name: str) -> None: ...

    def label_for(self, label: TkWidget, widget: TkWidget) -> None: ...

    def name_of(self, widget: TkWidget) -> str | None:
        # `None` rather than the caption the widget is showing: nothing here was
        # written, so anything working names out from the widgets around one
        # reports having named nothing rather than claiming names no client can
        # read — which is the same honesty `describe` leads its report with.
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
    # Defaulted so that a spec can build one without naming it, and built at
    # construction rather than at import so it is never the import thread.
    owner: OwningThread = field(default_factory=OwningThread.whichever_is_calling)
    tabs: TabbedWidgets = field(default_factory=NoTabs)


def install(
    root: TkApplication,
    store: AccessibilityStore,
    roles: Mapping[str, Role] | None = None,
    tabs: TabbedWidgets | None = None,
    variables: VariableCalled | None = None,
) -> Installation:
    strategy = strategy_for(root.tk)
    owner = OwningThread.whichever_is_calling()
    if strategy is not Strategy.ANNOTATED:
        return Installation(strategy, InertAnnotator(roles), owner)
    notebooks = tabs if tabs is not None else NoTabs()
    annotator = Annotator(store, roles, owner, variables)
    _follow_every_widget_tk_maps_or_destroys(root, annotator, notebooks)
    _annotate_everything_already_on_screen(root, annotator, notebooks)
    return Installation(strategy, annotator, owner, notebooks)


def _follow_every_widget_tk_maps_or_destroys(
    root: TkApplication, annotator: Annotator, notebooks: TabbedWidgets
) -> None:
    root.bind_all(
        _A_WIDGET_APPEARED,
        lambda event: _annotate_if_there_is_still_a_widget(
            annotator, notebooks, event.widget
        ),
        add=_ALONGSIDE_WHAT_IS_ALREADY_BOUND,
    )
    root.bind_all(
        _A_WIDGET_DIED,
        lambda event: _let_go_of(annotator, notebooks, event.widget),
        add=_ALONGSIDE_WHAT_IS_ALREADY_BOUND,
    )
    # A notebook's tabs are not widgets and never map, so `<Map>` says nothing
    # about one being added, removed or renamed. This is the event that does.
    root.bind_all(
        _THE_TABS_CHANGED,
        lambda event: _refresh_if_there_is_still_a_widget(notebooks, event.widget),
        add=_ALONGSIDE_WHAT_IS_ALREADY_BOUND,
    )


def _annotate_everything_already_on_screen(
    root: TkApplication, annotator: Annotator, notebooks: TabbedWidgets
) -> None:
    # `<Map>` fires once, on the way up. Every widget showing at the moment
    # accessibility is switched on has already had its, and will not get another.
    for widget in every_widget_under(root):
        if widget.winfo_ismapped():
            annotator.add(widget)
            notebooks.refresh(widget)


def every_widget_under(widget: TkWidget) -> Iterator[TkWidget]:
    for child in widget.winfo_children():
        yield child
        yield from every_widget_under(child)


def _annotate_if_there_is_still_a_widget(
    annotator: Annotator, notebooks: TabbedWidgets, widget: TkWidget | str
) -> None:
    if isinstance(widget, str):
        # Tk passes the path rather than the object when it can no longer
        # resolve one, and a path answers no question worth asking here.
        return
    annotator.add(widget)
    notebooks.refresh(widget)


def _refresh_if_there_is_still_a_widget(
    notebooks: TabbedWidgets, widget: TkWidget | str
) -> None:
    if isinstance(widget, str):
        return
    notebooks.refresh(widget)


def _let_go_of(
    annotator: Annotator, notebooks: TabbedWidgets, widget: TkWidget | str
) -> None:
    annotator.forget(widget)
    # By path, not by widget: `<Destroy>` is the one event that routinely
    # carries a path whose widget object has already gone.
    notebooks.forget(str(widget))


def _whatever_the_variable_holds(variable: TkVariable) -> str:
    return str(variable.get())


def words_the_widget_shows(widget: TkWidget) -> str | None:
    """Whatever is in the widget's `-text` right now, or None if it has no such option.

    `None` rather than `""` because the two are different answers and `describe`
    has to tell them apart: a widget showing nothing could have gone stale, and
    one with nowhere to keep words never could.
    """
    # Asked rather than attempted: an entry, a listbox and a canvas have no
    # `-text` option at all, and reading one raises. There is nothing else on a
    # widget that is a name — the path is an implementation detail and the
    # class is not a label — so one without any words stays unnamed rather than
    # named something the application never wrote.
    options_this_widget_has = widget.keys()
    for where in _WHERE_A_WIDGET_KEEPS_ITS_WORDS:
        if where in options_this_widget_has:
            return str(widget.cget(where))
    return None


def a_caption_read_as_a_name(caption: str) -> str:
    """A label's words as the name of the widget it captions: "Host:" names "Host".

    The punctuation and nothing else. Anything cleverer — dropping a leading
    verb, expanding an abbreviation — would be this package inventing words the
    application never wrote, and a name nobody can find in their own source is
    worse than a slightly long one.
    """
    return caption.strip().removesuffix(_HOW_A_CAPTION_IS_PUNCTUATED).strip()


def _what_a_declared_variable_is(role: Role) -> PropId:
    """Whether the variable driving this widget is what it *holds* or what it *is*.

    The same `-textvariable` option means two different things, and the role is
    what says which: in a control a client asks the contents of, the variable is
    those contents; in anything else — a status label, a button, a menubutton —
    the widget has no separate caption at all, so the variable is its whole
    name. Answering one question with the other is how "Title" ends up read back
    as whatever somebody typed into the box beneath it.
    """
    return (
        PropId.VALUE if role in _ROLES_WHOSE_VARIABLE_IS_WHAT_THEY_HOLD else PropId.NAME
    )


def variable_the_widget_declares(widget: TkWidget) -> str:
    """The Tcl name of the variable driving this widget, or "" if it names none.

    One string for both misses, where `words_the_widget_shows` distinguishes
    them: a widget with no `-textvariable` option and a widget whose option
    nobody filled in have the same nothing to follow, and no report tells them
    apart.
    """
    options_this_widget_has = widget.keys()
    if _WHERE_A_WIDGET_KEEPS_THE_VARIABLE_IT_SHOWS not in options_this_widget_has:
        return _NO_VARIABLE_AT_ALL
    return str(widget.cget(_WHERE_A_WIDGET_KEEPS_THE_VARIABLE_IT_SHOWS))
