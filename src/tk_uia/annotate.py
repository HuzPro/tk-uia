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

# Anything else replaces whatever Tk and the application already had bound to
# the same event, which is a startling amount of a Tk application to break in
# exchange for switching accessibility on.
_ALONGSIDE_WHAT_IS_ALREADY_BOUND = "+"

# The only kind of variable change worth re-announcing.
_A_WRITE = "write"

_WHERE_A_WIDGET_KEEPS_ITS_WORDS = "text"

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


class Annotator:
    """Decides what each widget should say, and says it once."""

    def __init__(
        self,
        store: AccessibilityStore,
        roles: Mapping[str, Role] | None = None,
        owner: OwningThread | None = None,
    ) -> None:
        self._store = store
        self.roles = roles_in_force(roles)
        self.ledger = Ledger()
        self._bindings: dict[str, list[_WhatAVariableIsBoundTo]] = {}
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
        self._write(widget, PropId.ROLE, role.value, Wrote.INFERRED)
        name = words_the_widget_shows(widget)
        if name:
            self._write(widget, PropId.NAME, name, Wrote.INFERRED)

    def set_role(self, widget: TkWidget, role: Role) -> None:
        self._write(widget, PropId.ROLE, role.value)

    def set_name(self, widget: TkWidget, name: str) -> None:
        self._write(widget, PropId.NAME, name)

    def set_value(self, widget: TkWidget, value: str) -> None:
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
        # A `textvariable` widget has no `-text` to infer from, so the widget
        # whose entire job is to say what just happened is the one widget that
        # would otherwise say nothing.
        self._keep_in_step_with(
            widget,
            variable,
            lambda words: self._write(widget, PropId.NAME, words, Wrote.KEPT_IN_STEP),
        )

    def bind_value_variable(self, widget: TkWidget, variable: TkVariable) -> None:
        # The contents of an entry are not on the widget to be read back — they
        # are in the variable, and only the application knows when it moved. So
        # the property a client re-reads more than any other is the one nothing
        # here can keep true on its own.
        self._keep_in_step_with(
            widget,
            variable,
            lambda held: self._write(widget, PropId.VALUE, held, Wrote.KEPT_IN_STEP),
        )

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

    def _keep_in_step_with(
        self, widget: TkWidget, variable: TkVariable, announce: Callable[[str], None]
    ) -> None:
        # Said once here as well as on every write from now on: a trace fires on
        # the *next* change and never for the one already made, so a binding that
        # only traced would leave the widget announcing whatever it was annotated
        # with before the variable existed — for most widgets, nothing at all.
        callback_name = variable.trace_add(
            _A_WRITE,
            lambda *_: self._announce_unless_the_widget_has_gone(
                widget, variable, announce
            ),
        )
        self._bindings.setdefault(str(widget), []).append(
            _WhatAVariableIsBoundTo(variable, callback_name)
        )
        announce(_whatever_the_variable_holds(variable))

    def _announce_unless_the_widget_has_gone(
        self, widget: TkWidget, variable: TkVariable, announce: Callable[[str], None]
    ) -> None:
        # Second line behind `forget`, which is what actually takes the trace
        # off. A widget can still go away by a route that never reaches it — an
        # annotator driven directly rather than through `enable()`, or an earlier
        # `<Destroy>` handler that raised before ours ran — and the write that
        # follows lands inside Tcl's own callback, where the application has no
        # call of its own to wrap it in.
        if not widget.winfo_exists():
            return
        announce(_whatever_the_variable_holds(variable))

    def _stop_following_any_variable_bound_to(self, path: str) -> None:
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


def install(
    root: TkApplication,
    store: AccessibilityStore,
    roles: Mapping[str, Role] | None = None,
) -> Installation:
    strategy = strategy_for(root.tk)
    owner = OwningThread.whichever_is_calling()
    if strategy is not Strategy.ANNOTATED:
        return Installation(strategy, InertAnnotator(roles), owner)
    annotator = Annotator(store, roles, owner)
    _follow_every_widget_tk_maps_or_destroys(root, annotator)
    _annotate_everything_already_on_screen(root, annotator)
    return Installation(strategy, annotator, owner)


def _follow_every_widget_tk_maps_or_destroys(
    root: TkApplication, annotator: Annotator
) -> None:
    root.bind_all(
        _A_WIDGET_APPEARED,
        lambda event: _annotate_if_there_is_still_a_widget(annotator, event.widget),
        add=_ALONGSIDE_WHAT_IS_ALREADY_BOUND,
    )
    root.bind_all(
        _A_WIDGET_DIED,
        lambda event: annotator.forget(event.widget),
        add=_ALONGSIDE_WHAT_IS_ALREADY_BOUND,
    )


def _annotate_everything_already_on_screen(
    root: TkApplication, annotator: Annotator
) -> None:
    # `<Map>` fires once, on the way up. Every widget showing at the moment
    # accessibility is switched on has already had its, and will not get another.
    for widget in every_widget_under(root):
        if widget.winfo_ismapped():
            annotator.add(widget)


def every_widget_under(widget: TkWidget) -> Iterator[TkWidget]:
    for child in widget.winfo_children():
        yield child
        yield from every_widget_under(child)


def _annotate_if_there_is_still_a_widget(
    annotator: Annotator, widget: TkWidget | str
) -> None:
    if isinstance(widget, str):
        # Tk passes the path rather than the object when it can no longer
        # resolve one, and a path answers no question worth asking here.
        return
    annotator.add(widget)


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
    if _WHERE_A_WIDGET_KEEPS_ITS_WORDS not in options_this_widget_has:
        return None
    return str(widget.cget(_WHERE_A_WIDGET_KEEPS_ITS_WORDS))
