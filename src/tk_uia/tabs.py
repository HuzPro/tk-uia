"""Giving a notebook's tabs the window handles Tk never gave them.

Where it plugs in: `install()` builds a :class:`TabHandles` over the real Win32
seam and refreshes it whenever a notebook maps or its tabs change; specs build
one over a recording double. Like the rest of the package this module knows
nothing platform-specific, which is what lets the whole of the decision — which
handles should exist, where, and saying what — be specified with no desktop.

Why handles at all. Everything else here annotates a window Tk already made: one
`SetHwndProp` per widget, and the MSAA-to-UIA bridge carries it. A notebook's
tabs are not windows. Tk draws the whole strip inside the notebook's own window,
so there is no handle to annotate and a client sees a `TabControl` with nothing
in it — findable, and impossible to change. The roadmap's answer to that was
MSAA's child-id model, which means implementing `IAccessible` and answering
`WM_GETOBJECT`: a COM server, and a different package from this one.

Measured, there is a smaller answer. A real child window over each tab is a
handle, so the machinery already here annotates it, and four things a client
needs all follow: the tab is in the tree, it has the tab's name, it has the
tab's rectangle, and — because the window is `WS_EX_TRANSPARENT` and owner-drawn
by a parent that ignores it — it paints nothing and a click at its centre passes
straight through to Tk, which selects the tab. That last one is the whole point:
a tab a client can see but not press would not have been worth the machinery.

The bound of the idea, stated because it is the obvious next question: this does
not generalise to a `Listbox` or a `Treeview`. Their items scroll, there can be
thousands, and a window per row would be absurd where a window per tab is four.
Those still want the server.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from tk_uia.annotate import AccessibilityStore, PropId
from tk_uia.roles import Role

# Where the scan starts looking for the strip, and how far it is willing to go.
# A tab strip is at the top of the notebook and is one row of text high; these
# bound the search so that a notebook whose tabs are hidden costs a fixed number
# of questions rather than one per pixel of its height.
_THE_TALLEST_A_TAB_STRIP_GETS = 120
# The scan's first job is to find any point at all on the strip, and it does
# that coarsely — a tab narrower than this would have no room for a caption.
_THE_NARROWEST_A_TAB_GETS = 8


@dataclass(frozen=True)
class Tab:
    """One tab on a notebook's strip: what it says, and where it is.

    In the notebook's own coordinates, because that is what a child window of
    the notebook is positioned in — no conversion, and nothing to get wrong when
    the window moves.
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
    """A notebook's tab strip, as the scan asks about it.

    Deliberately not "a notebook": the only three things wanted here are what is
    under a point, what a tab says, and how much room there is to look in. A
    seam this narrow is why the scan below is specified without a display.
    """

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
    """Every tab on the strip, by asking what is under each point.

    Asked of Tk rather than worked out from the theme's metrics: `index @x,y` is
    the same question the toolkit answers for a real mouse click, so a rectangle
    found this way cannot drift from where the tab actually is — which matters,
    because a client is going to aim a pointer at it.
    """
    # Before a single measurement. Tk lays a strip out on idle, so a tab added a
    # moment ago is not where it is going to be — measured, `notebook.add(...)`
    # followed straight away by a scan finds the strip exactly as it was, and the
    # new tab simply is not there.
    strip.settle()
    width, height = strip.size()
    somewhere = _anywhere_at_all_on_the_strip(strip, width, height)
    if somewhere is None:
        return ()
    found_at_x, _ = somewhere
    # Across the middle of the strip, never the edge of it. Measured on Tk
    # 8.6.15: ttk draws the *selected* tab standing two pixels proud at the top
    # and bottom, so the first row that answers belongs to that tab alone —
    # scanning there finds one tab and reports the notebook done.
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
    """The extent every tab is given, which is the one they cover between them.

    Each tab's own extent would be more precise and worse. The selected tab is
    the taller one, so per-tab extents would change for two tabs every time a
    user picked a different one — turning a refresh that currently writes
    nothing into one that moves two windows, on every click, forever. The union
    is stable under selection, always contains the tab, and always has the tab
    under its middle, which is what a client aiming a pointer needs.
    """
    bands = [
        _how_far_it_runs_down(strip, columns[len(columns) // 2], height)
        for columns in across.values()
    ]
    return min(top for top, _ in bands), max(bottom for _, bottom in bands)


def _anywhere_at_all_on_the_strip(
    strip: TabStrip, width: int, height: int
) -> tuple[int, int] | None:
    """One point known to be on a tab, to measure the rest relative to.

    Coarse on both axes on purpose. Every later scan is fine-grained and needs a
    line it knows is worth walking; finding that line by walking every pixel of
    an empty notebook would be the expensive way to learn there is nothing here.
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

    Keyed by the notebook's Tk path rather than its handle, for the reason the
    ledger is: a path survives Tk rebuilding the widget under it, and `<Destroy>`
    carries the path once the widget object has gone.
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
        # Compared before anything is written: a tab *selection* fires the same
        # event a tab *change* does, so most refreshes are asking about a strip
        # that has not moved, and each one that wrote anyway would be a COM call
        # and a window move for no change to what a client reads.
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
            # Cleared before the window goes, never after: Windows hands the
            # same handle out again, and an annotation left on a recycled one
            # mislabels an unrelated window and reads as a flaky locator.
            self._store.clear(one.hwnd)
            self._windows.destroy(one.hwnd)


class StripFor(Protocol):
    """How a widget becomes a strip to scan, or turns out not to be one at all."""

    def __call__(self, widget: object) -> TabStrip | None: ...


class Notebooks:
    """Every notebook in the application, and the handles standing in for its tabs.

    The piece that knows a widget is a notebook is the factory, not this: asking
    `isinstance(widget, ttk.Notebook)` needs tkinter, and the whole package is
    arranged so that nothing above the platform modules imports it.
    """

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
