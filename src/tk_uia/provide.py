"""What a widget answers UI Automation with itself, and the seams it answers through.

Properties are pulled at the moment a client asks: what the application chose
outranks what the widget shows, and what it shows outranks any echo of map
time. Actions answer first and run after, so nothing a command opens can pin
the callback that carried it.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from tk_uia.annotate import (
    AnnotationRefused,
    Ledger,
    OwningThread,
    PropId,
    TkWidget,
    a_widget_this_package_speaks_for,
    roles_in_force,
)
from tk_uia.roles import Role


class ProviderRefused(AnnotationRefused):
    """The provider layer would not do what it was asked, and says why."""


class Pattern(Enum):
    """The UIA patterns a provider can honestly offer, by their pattern ids."""

    INVOKE = 10000
    VALUE = 10002
    RANGE_VALUE = 10003
    SELECTION_ITEM = 10010
    TOGGLE = 10015


# Transcribed from UIAutomationClient.h; total over Role so a chosen role
# always lands somewhere a client can type.
_UIA_CONTROL_TYPE_FOR_ROLE: Mapping[Role, int] = {
    Role.SCROLL_BAR: 50014,
    Role.GRIP: 50027,
    Role.MENU_POPUP: 50009,
    Role.GROUPING: 50026,
    Role.SEPARATOR: 50038,
    Role.LIST: 50008,
    Role.OUTLINE: 50023,
    Role.PAGE_TAB: 50019,
    Role.GRAPHIC: 50006,
    Role.STATIC_TEXT: 50020,
    Role.TEXT: 50004,
    Role.PUSH_BUTTON: 50000,
    Role.CHECK_BUTTON: 50002,
    Role.RADIO_BUTTON: 50013,
    Role.COMBO_BOX: 50003,
    Role.PROGRESS_BAR: 50012,
    Role.SLIDER: 50015,
    Role.SPIN_BUTTON: 50016,
    Role.PAGE_TAB_LIST: 50018,
    # A SplitButton control type promises Invoke and ExpandCollapse, neither
    # of which a menubutton can honour here, so it stays a plain button.
    Role.MENU_BUTTON: 50000,
}

_THE_ROLE_BEHIND_EACH_NUMBER: Mapping[int, Role] = {role.value: role for role in Role}


class InvokeWiring(Protocol):
    """How a widget is pressed, and whether pressing it would do anything."""

    def press(self) -> None: ...

    def offered(self) -> bool: ...


class ToggleWiring(Protocol):
    """How a widget is flipped, and which way it is right now."""

    def flip(self) -> None: ...

    def is_on(self) -> bool: ...


class ValueWiring(Protocol):
    """How a widget's text is read and written."""

    def read(self) -> str: ...

    def write(self, text: str) -> None: ...

    def is_read_only(self) -> bool: ...


class RangeWiring(Protocol):
    """How a widget's number is read, and written where the class allows it."""

    write: Callable[[float], None] | None

    def now(self) -> float: ...

    def low(self) -> float: ...

    def high(self) -> float: ...

    def step(self) -> float | None: ...

    def is_read_only(self) -> bool: ...


class SelectionWiring(Protocol):
    """How a widget is selected, and whether it is."""

    def select(self) -> None: ...

    def is_selected(self) -> bool: ...


class ItemsWiring(Protocol):
    """How a container's rows are reached and driven, by the container's own keys.

    A flat container's keys are its indexes as words and its branches are
    empty; a tree's keys are its item ids and its branches open and close.
    """

    def roots(self) -> tuple[str, ...]: ...

    def children(self, key: str) -> tuple[str, ...]: ...

    def parent(self, key: str) -> str | None: ...

    def exists(self, key: str) -> bool: ...

    def words(self, key: str) -> str | None: ...

    def select(self, key: str) -> None: ...

    def is_selected(self, key: str) -> bool: ...

    def show(self, key: str) -> None: ...

    def rectangle(self, key: str) -> tuple[int, int, int, int] | None: ...

    def is_open(self, key: str) -> bool: ...

    def open(self, key: str) -> None: ...

    def close(self, key: str) -> None: ...


Poster = Callable[[Callable[[], None]], None]
"""How an action reaches the Tk thread without holding the callback that asked."""


@dataclass(frozen=True)
class WidgetWiring:
    """Everything a provider can drive one widget through, None where the class has no such pattern."""

    words: Callable[[], str | None]
    is_enabled: Callable[[], bool]
    post: Poster
    still_there: Callable[[], bool]
    invoke: InvokeWiring | None = None
    toggle: ToggleWiring | None = None
    value: ValueWiring | None = None
    range_value: RangeWiring | None = None
    selection: SelectionWiring | None = None
    items: ItemsWiring | None = None


class WiringForClass(Protocol):
    """How a widget becomes the callables that drive it."""

    def __call__(self, widget: TkWidget) -> WidgetWiring: ...


@dataclass(frozen=True)
class InvokeAnswers:
    """Invoke, ready to hand out: the press already answers before it runs."""

    press: Callable[[], None]
    offered: Callable[[], bool]


@dataclass(frozen=True)
class ToggleAnswers:
    flip: Callable[[], None]
    is_on: Callable[[], bool]


@dataclass(frozen=True)
class ValueAnswers:
    """Value, deliberately synchronous, so a read straight back sees the write."""

    write: Callable[[str], None]
    read: Callable[[], str]
    is_read_only: Callable[[], bool]


@dataclass(frozen=True)
class RangeAnswers:
    """RangeValue; `write` is None for a class whose number no client may set."""

    write: Callable[[float], None] | None
    now: Callable[[], float]
    low: Callable[[], float]
    high: Callable[[], float]
    step: Callable[[], float | None]
    is_read_only: Callable[[], bool]


@dataclass(frozen=True)
class SelectionAnswers:
    select: Callable[[], None]
    is_selected: Callable[[], bool]


Answers = InvokeAnswers | ToggleAnswers | ValueAnswers | RangeAnswers | SelectionAnswers


class ItemsAnswers:
    """The rows a container answers for, in order, by key.

    Every answer is pulled from the wiring at the moment a client asks, so a
    row renamed, selected or deleted after attach is answered as it is now.
    """

    def __init__(
        self,
        wiring: ItemsWiring,
        post: Poster,
        widget_still_there: Callable[[], bool],
    ) -> None:
        self._wiring = wiring
        self._post = post
        self._widget_still_there = widget_still_there

    def still_there(self, key: str) -> bool:
        return self._widget_still_there() and self._wiring.exists(key)

    def select(self, key: str) -> None:
        self._posted_on_the_row(key, self._wiring.select)

    def show(self, key: str) -> None:
        self._posted_on_the_row(key, self._wiring.show)

    def open(self, key: str) -> None:
        self._posted_on_the_row(key, self._wiring.open)

    def close(self, key: str) -> None:
        self._posted_on_the_row(key, self._wiring.close)

    def _posted_on_the_row(self, key: str, act: Callable[[str], None]) -> None:
        # The posting rule actions follow everywhere here: answer first, run
        # on the Tk thread after, and only if the row is still there to run on.
        self._post(lambda: act(key) if self.still_there(key) else None)

    def rectangle(self, key: str) -> tuple[int, int, int, int] | None:
        return self._wiring.rectangle(key) if self.still_there(key) else None

    def words(self, key: str) -> str | None:
        return self._wiring.words(key) if self.still_there(key) else None

    def is_selected(self, key: str) -> bool:
        return self._wiring.is_selected(key) if self.still_there(key) else False

    def is_open(self, key: str) -> bool:
        return self._wiring.is_open(key) if self.still_there(key) else False

    def parent(self, key: str) -> str | None:
        return self._wiring.parent(key) if self.still_there(key) else None

    def first(self) -> str | None:
        return _an_edge_of(self._the_roots(), 0)

    def last(self) -> str | None:
        return _an_edge_of(self._the_roots(), -1)

    def first_child(self, key: str) -> str | None:
        return _an_edge_of(self._the_children_of(key), 0)

    def last_child(self, key: str) -> str | None:
        return _an_edge_of(self._the_children_of(key), -1)

    def after(self, key: str) -> str | None:
        return self._a_sibling_of(key, 1)

    def before(self, key: str) -> str | None:
        return self._a_sibling_of(key, -1)

    def _a_sibling_of(self, key: str, step: int) -> str | None:
        if not self.still_there(key):
            return None
        siblings = self._the_row_and_its_neighbours(key)
        position = siblings.index(key) + step
        if 0 <= position < len(siblings):
            return siblings[position]
        return None

    def _the_row_and_its_neighbours(self, key: str) -> tuple[str, ...]:
        holder = self._wiring.parent(key)
        return self._wiring.roots() if holder is None else self._wiring.children(holder)

    def _the_roots(self) -> tuple[str, ...]:
        return self._wiring.roots() if self._widget_still_there() else ()

    def _the_children_of(self, key: str) -> tuple[str, ...]:
        return self._wiring.children(key) if self.still_there(key) else ()


def _an_edge_of(keys: tuple[str, ...], edge: int) -> str | None:
    return keys[edge] if keys else None


def _nobody_said_a_value() -> str | None:
    return None


@dataclass(frozen=True)
class Blueprint:
    """One widget's answers, resolved; the platform calls these and nothing else."""

    control_type: Callable[[], int]
    name: Callable[[], str | None]
    help_text: Callable[[], str | None]
    description: Callable[[], str | None]
    is_enabled: Callable[[], bool]
    is_keyboard_focusable: bool
    patterns: Mapping[Pattern, Answers]
    # Where the class has no live value of its own, a value the application
    # said (set_acc_value) is still served to clients, read-only.
    value_the_application_said: Callable[[], str | None] = _nobody_said_a_value
    # The rows a container answers for, None for a class that has no rows.
    items: ItemsAnswers | None = None


class ProviderPlatform(Protocol):
    """Where providers answer from; the only seam that knows COM and window procs."""

    def host(self, hwnd: int, blueprint: Blueprint) -> None: ...

    def unhost(self, hwnd: int) -> None: ...

    def announce_change(self, hwnd: int, uia_property: int, now: object) -> None: ...


def answers_nothing_once_the_widget_is_gone(
    read: Callable[..., object],
    gone: type[BaseException],
    nothing: object = None,
) -> Callable[..., object]:
    """The rule every puller obeys: a widget mid-teardown answers nothing.

    A client's question can land between `<Destroy>` and the handle's end,
    and an exception there escapes into a callback forbidden to raise.
    """

    def guarded(*args: object) -> object:
        try:
            return read(*args)
        except gone:
            return nothing

    return guarded


def a_press_that_returns_before_it_runs(
    post: Poster,
    action: Callable[[], None],
    still_there: Callable[[], bool],
) -> Callable[[], None]:
    """The rule Invoke, Toggle and Select go through; SetValue never does.

    Posted so a command that opens modal UI cannot pin the callback and queue
    every later UIA request behind it.
    """

    def press() -> None:
        post(lambda: action() if still_there() else None)

    return press


class ProviderLedger:
    """Which paths answer for themselves with what, and which asked not to."""

    def __init__(self) -> None:
        self._hosting: dict[str, tuple[int, tuple[Pattern, ...], bool]] = {}
        self._with_the_proxy: set[str] = set()

    def hosted(
        self,
        path: str,
        hwnd: int,
        patterns: tuple[Pattern, ...],
        *,
        rows: bool = False,
    ) -> None:
        self._hosting[path] = (hwnd, patterns, rows)

    def gone_from(self, path: str) -> None:
        self._hosting.pop(path, None)

    def hwnd_of(self, path: str) -> int | None:
        standing = self._hosting.get(path)
        return standing[0] if standing is not None else None

    def patterns_on(self, path: str) -> tuple[Pattern, ...]:
        standing = self._hosting.get(path)
        return standing[1] if standing is not None else ()

    def answers_rows_on(self, path: str) -> bool:
        standing = self._hosting.get(path)
        return standing[2] if standing is not None else False

    def left_to_the_proxy(self, path: str) -> None:
        self._with_the_proxy.add(path)

    def is_left_to_the_proxy(self, path: str) -> bool:
        return path in self._with_the_proxy

    def paths(self) -> tuple[str, ...]:
        return tuple(self._hosting)


class Trouble:
    """A bounded record of what the callback machinery swallowed.

    The subclass proc must never raise, so this is the one window into a
    callback that failed; `describe()` renders it.
    """

    def __init__(self, keep: int = 25) -> None:
        self._kept: deque[str] = deque(maxlen=keep)

    def note(self, what: str) -> None:
        self._kept.append(what)

    def so_far(self) -> tuple[str, ...]:
        return tuple(self._kept)


class Providers:
    """Decides which widgets answer UIA for themselves, and wires each one once."""

    def __init__(
        self,
        platform: ProviderPlatform,
        wiring_for: WiringForClass,
        roles: Mapping[str, Role] | None = None,
        owner: OwningThread | None = None,
        said: Ledger | None = None,
    ) -> None:
        self._platform = platform
        self._wiring_for = wiring_for
        self._roles = roles_in_force(roles)
        self._owner = (
            owner if owner is not None else OwningThread.whichever_is_calling()
        )
        self._said = said if said is not None else Ledger()
        self.ledger = ProviderLedger()

    def attach(self, widget: TkWidget) -> None:
        self._owner.refuse_any_other_caller()
        role = a_widget_this_package_speaks_for(widget, self._roles)
        # A menu is a window Tk posts, not a control a provider could speak for.
        if role is None or role is Role.MENU_POPUP:
            return
        path = str(widget)
        if self.ledger.is_left_to_the_proxy(path):
            return
        hwnd = widget.winfo_id()
        standing = self.ledger.hwnd_of(path)
        if standing == hwnd:
            return
        if standing is not None:
            # Tk rebuilt the widget at the same path; Windows recycles handles,
            # so the abandoned one must stop answering before the new one starts.
            self._platform.unhost(standing)
            self.ledger.gone_from(path)
        blueprint = self._blueprint(hwnd, role, self._wiring_for(widget))
        self._platform.host(hwnd, blueprint)
        self.ledger.hosted(
            path, hwnd, tuple(blueprint.patterns), rows=blueprint.items is not None
        )

    def forget(self, path: str) -> None:
        # Bookkeeping only: `<Destroy>` means Windows already ordered the
        # handle's own teardown, which is the platform's to answer.
        self.ledger.gone_from(path)

    def detach(self, path: str) -> None:
        """Take a living widget's provider back off, unlike the `<Destroy>` route."""
        self._owner.refuse_any_other_caller()
        standing = self.ledger.hwnd_of(path)
        if standing is not None:
            self._platform.unhost(standing)
        self.ledger.gone_from(path)

    def leave_to_the_proxy(self, widget: TkWidget) -> None:
        self._owner.refuse_any_other_caller()
        path = str(widget)
        self.ledger.left_to_the_proxy(path)
        self.detach(path)

    def _blueprint(self, hwnd: int, role: Role, wiring: WidgetWiring) -> Blueprint:
        patterns = _the_answers_this_wiring_carries(wiring)
        return Blueprint(
            control_type=lambda: _UIA_CONTROL_TYPE_FOR_ROLE[
                self._role_in_force(hwnd, role)
            ],
            name=lambda: self._chosen_text(hwnd, PropId.NAME) or wiring.words() or None,
            help_text=lambda: self._chosen_text(hwnd, PropId.HELP),
            description=lambda: self._chosen_text(hwnd, PropId.DESCRIPTION),
            is_enabled=wiring.is_enabled,
            is_keyboard_focusable=bool(patterns),
            patterns=patterns,
            value_the_application_said=lambda: self._chosen_text(hwnd, PropId.VALUE),
            items=(
                ItemsAnswers(wiring.items, wiring.post, wiring.still_there)
                if wiring.items is not None
                else None
            ),
        )

    def _role_in_force(self, hwnd: int, role: Role) -> Role:
        said = self._said.chosen(hwnd, PropId.ROLE)
        if isinstance(said, int) and said in _THE_ROLE_BEHIND_EACH_NUMBER:
            return _THE_ROLE_BEHIND_EACH_NUMBER[said]
        return role

    def _chosen_text(self, hwnd: int, prop: PropId) -> str | None:
        said = self._said.chosen(hwnd, prop)
        return str(said) if said is not None else None


_A_TAB_ITEM = 50019


class ProvidedTabs:
    """Tab overlays answering UIA themselves, through the same platform as widgets."""

    def __init__(self, platform: ProviderPlatform) -> None:
        self._platform = platform

    def attach(self, hwnd: int, wiring: object) -> None:
        select = a_press_that_returns_before_it_runs(
            wiring.post, wiring.select, wiring.still_there
        )
        self._platform.host(
            hwnd,
            Blueprint(
                control_type=lambda: _A_TAB_ITEM,
                name=wiring.text,
                help_text=lambda: None,
                description=lambda: None,
                is_enabled=lambda: True,
                is_keyboard_focusable=True,
                patterns={
                    Pattern.SELECTION_ITEM: SelectionAnswers(
                        select=select, is_selected=wiring.is_selected
                    )
                },
            ),
        )

    def detach(self, hwnd: int) -> None:
        self._platform.unhost(hwnd)


class InertProviders:
    """The null Providers, for the Tks that answer for themselves or have no UIA."""

    def __init__(self) -> None:
        self.ledger = ProviderLedger()

    def attach(self, widget: TkWidget) -> None: ...

    def forget(self, path: str) -> None: ...

    def leave_to_the_proxy(self, widget: TkWidget) -> None: ...


def _the_answers_this_wiring_carries(
    wiring: WidgetWiring,
) -> Mapping[Pattern, Answers]:
    answers: dict[Pattern, Answers] = {}
    if wiring.invoke is not None:
        answers[Pattern.INVOKE] = InvokeAnswers(
            press=a_press_that_returns_before_it_runs(
                wiring.post, wiring.invoke.press, wiring.still_there
            ),
            offered=wiring.invoke.offered,
        )
    if wiring.toggle is not None:
        answers[Pattern.TOGGLE] = ToggleAnswers(
            flip=a_press_that_returns_before_it_runs(
                wiring.post, wiring.toggle.flip, wiring.still_there
            ),
            is_on=wiring.toggle.is_on,
        )
    if wiring.value is not None:
        answers[Pattern.VALUE] = ValueAnswers(
            write=wiring.value.write,
            read=wiring.value.read,
            is_read_only=wiring.value.is_read_only,
        )
    if wiring.range_value is not None:
        answers[Pattern.RANGE_VALUE] = RangeAnswers(
            write=wiring.range_value.write,
            now=wiring.range_value.now,
            low=wiring.range_value.low,
            high=wiring.range_value.high,
            step=wiring.range_value.step,
            is_read_only=wiring.range_value.is_read_only,
        )
    if wiring.selection is not None:
        answers[Pattern.SELECTION_ITEM] = SelectionAnswers(
            select=a_press_that_returns_before_it_runs(
                wiring.post, wiring.selection.select, wiring.still_there
            ),
            is_selected=wiring.selection.is_selected,
        )
    return answers
