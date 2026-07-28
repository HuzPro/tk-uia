"""Giving a notebook's tabs the window handles Tk never gave them.

Tk draws the whole tab strip inside the notebook's own window, so there is no
handle to annotate and a client sees a `TabControl` with nothing in it. A real
child window over each tab is a handle the machinery already here annotates,
which puts the tab in the tree with its name and its rectangle. Nothing in this
module is platform-specific.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from tk_uia.annotate import AccessibilityStore, PropId
from tk_uia.roles import Role

# Bounds the search, so a notebook whose tabs are hidden costs a fixed number
# of questions rather than one per pixel.
_THE_TALLEST_A_TAB_STRIP_GETS = 120
# How coarsely the first pass sweeps across: a tab narrower than this would
# have no room for a caption.
_THE_NARROWEST_A_TAB_GETS = 8


@dataclass(frozen=True)
class Tab:
    """One tab on a notebook's strip: what it says, and where it is.

    In the notebook's own coordinates, which is what a child window of the
    notebook is positioned in.
    """

    text: str
    left: int
    top: int
    width: int
    height: int

    @property
    def rectangle(self) -> tuple[int, int, int, int]:
        return (self.left, self.top, self.width, self.height)


class TabStrip(Protocol):
    """A notebook's tab strip, as the scan asks about it."""

    def settle(self) -> None: ...

    def tab_at(self, x: int, y: int) -> int | None: ...

    def text_of(self, index: int) -> str: ...

    def size(self) -> tuple[int, int]: ...


class OverlayWindows(Protocol):
    """Where a tab's window handle comes from. The only thing here that is Win32."""

    def create(
        self, parent: int, left: int, top: int, width: int, height: int
    ) -> int: ...

    def move(self, hwnd: int, left: int, top: int, width: int, height: int) -> None: ...

    def destroy(self, hwnd: int) -> None: ...


def tabs_on(strip: TabStrip) -> tuple[Tab, ...]:
    """Every tab on the strip, by asking what is under each point."""
    # Tk lays a strip out on idle; an immediate scan finds it stale.
    strip.settle()
    width, height = strip.size()
    somewhere = _anywhere_at_all_on_the_strip(strip, width, height)
    if somewhere is None:
        return ()
    found_at_x, _ = somewhere
    # Across the middle of the strip, never the edge: ttk draws the selected
    # tab a little proud, so the first answering row belongs to it alone.
    across = _how_far_each_tab_runs_across(
        strip, width, _the_middle_of(_how_far_it_runs_down(strip, found_at_x, height))
    )
    top, bottom = _the_band_the_whole_strip_covers(strip, across, height)
    return tuple(
        Tab(
            text=strip.text_of(index),
            left=min(columns),
            top=top,
            width=max(columns) - min(columns) + 1,
            height=bottom - top + 1,
        )
        for index, columns in sorted(across.items())
    )


def _the_middle_of(band: tuple[int, int]) -> int:
    top, bottom = band
    return (top + bottom) // 2


def _the_band_the_whole_strip_covers(
    strip: TabStrip, across: Mapping[int, Sequence[int]], height: int
) -> tuple[int, int]:
    """The union extent every tab is given, stable under selection changes."""
    bands = [
        _how_far_it_runs_down(strip, columns[len(columns) // 2], height)
        for columns in across.values()
    ]
    return min(top for top, _ in bands), max(bottom for _, bottom in bands)


def _anywhere_at_all_on_the_strip(
    strip: TabStrip, width: int, height: int
) -> tuple[int, int] | None:
    """One point known to be on a tab, to measure the rest relative to.

    Coarse on both axes, so an empty notebook is cheap to rule out.
    """
    for y in range(min(height, _THE_TALLEST_A_TAB_STRIP_GETS)):
        for x in range(0, width, _THE_NARROWEST_A_TAB_GETS):
            if strip.tab_at(x, y) is not None:
                return x, y
    return None


def _how_far_each_tab_runs_across(
    strip: TabStrip, width: int, y: int
) -> Mapping[int, Sequence[int]]:
    across: dict[int, list[int]] = {}
    for x in range(width):
        index = strip.tab_at(x, y)
        if index is not None:
            across.setdefault(index, []).append(x)
    return across


def _how_far_it_runs_down(strip: TabStrip, x: int, height: int) -> tuple[int, int]:
    """Top and bottom of whatever tab is under this column."""
    rows = [
        y
        for y in range(min(height, _THE_TALLEST_A_TAB_STRIP_GETS))
        if strip.tab_at(x, y) is not None
    ]
    return min(rows), max(rows)


@dataclass(frozen=True)
class _AHandledTab:
    """One tab, and the window handle standing in for it."""

    tab: Tab
    hwnd: int


class TabHandles:
    """One window handle per tab, kept in step with the strip beneath it.

    Keyed by the notebook's Tk path, which survives Tk rebuilding the widget
    and is all `<Destroy>` carries.
    """

    def __init__(self, store: AccessibilityStore, windows: OverlayWindows) -> None:
        self._store = store
        self._windows = windows
        self._handled: dict[str, list[_AHandledTab]] = {}

    def refresh(self, path: str, parent: int, tabs: Sequence[Tab]) -> None:
        """Make the handles for `path` say what these tabs say, and no more."""
        standing = self._handled.get(path, [])
        self._surrender(standing[len(tabs) :])
        kept = list(standing[: len(tabs)])
        self._handled[path] = [
            *(self._brought_into_step(was, now) for was, now in zip(kept, tabs)),
            *(self._given_a_handle(parent, tab) for tab in tabs[len(kept) :]),
        ]

    def forget(self, path: str) -> None:
        """Give back every handle made for this notebook."""
        self._surrender(self._handled.pop(path, []))

    def handles(self, path: str) -> tuple[int, ...]:
        return tuple(handled.hwnd for handled in self._handled.get(path, ()))

    def on(self, path: str) -> tuple[Tab, ...]:
        """The tabs this has given handles to, for a report to say so."""
        return tuple(handled.tab for handled in self._handled.get(path, ()))

    def every_handle(self) -> Iterator[int]:
        for handled in self._handled.values():
            yield from (one.hwnd for one in handled)

    def _given_a_handle(self, parent: int, tab: Tab) -> _AHandledTab:
        hwnd = self._windows.create(parent, *tab.rectangle)
        self._say_what_it_is(hwnd, tab)
        return _AHandledTab(tab, hwnd)

    def _brought_into_step(self, standing: _AHandledTab, now: Tab) -> _AHandledTab:
        # A tab *selection* fires the same event a tab *change* does, so most
        # refreshes ask about a strip that has not moved.
        if standing.tab == now:
            return standing
        if standing.tab.rectangle != now.rectangle:
            self._windows.move(standing.hwnd, *now.rectangle)
        if standing.tab.text != now.text:
            self._say_what_it_is(standing.hwnd, now)
        return _AHandledTab(now, standing.hwnd)

    def _say_what_it_is(self, hwnd: int, tab: Tab) -> None:
        self._store.set_number(hwnd, PropId.ROLE, Role.PAGE_TAB.value)
        self._store.set_string(hwnd, PropId.NAME, tab.text)

    def _surrender(self, handled: Sequence[_AHandledTab]) -> None:
        for one in handled:
            # Cleared before destroy: Windows recycles handles, and a leftover
            # annotation would mislabel an unrelated window.
            self._store.clear(one.hwnd)
            self._windows.destroy(one.hwnd)


class StripFor(Protocol):
    """How a widget becomes a strip to scan, or turns out not to be one at all."""

    def __call__(self, widget: object) -> TabStrip | None: ...


class Notebooks:
    """Every notebook in the application, and the handles standing in for its tabs."""

    def __init__(self, handles: TabHandles, strip_for: StripFor) -> None:
        self._handles = handles
        self._strip_for = strip_for

    def refresh(self, widget: object) -> None:
        strip = self._strip_for(widget)
        if strip is None:
            return
        self._handles.refresh(str(widget), widget.winfo_id(), tabs_on(strip))

    def forget(self, path: str) -> None:
        self._handles.forget(path)

    def on(self, path: str) -> tuple[Tab, ...]:
        return self._handles.on(path)
