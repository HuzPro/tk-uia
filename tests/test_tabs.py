"""A notebook's tabs, which have no window handle until this gives them one.

Tk draws a notebook's tab strip inside the notebook's own window, so there is
nothing for `SetHwndProp` to annotate and a client sees a tab control with no
tabs in it. Everything specified here decides *what* handles should exist and
what each should say; making one is four lines of Win32 behind a seam, and the
gui specs are what prove a client can read them.
"""

from __future__ import annotations

from tests.doubles import RecordingStore
from tk_uia.annotate import PropId
from tk_uia.roles import Role
from tk_uia.tabs import Tab, TabHandles, tabs_on


class FakeStrip:
    """A tab strip, answering the two questions the scan asks of a real one.

    Tabs sit side by side along the top of the notebook and share a height,
    which is how ttk lays a strip out. `tab_at` answers None off the strip,
    where the real one raises — the seam is what turns one into the other.
    """

    def __init__(
        self,
        spans: dict[int, tuple[int, int]],
        texts: dict[int, str],
        *,
        size: tuple[int, int] = (400, 300),
        strip: tuple[int, int] = (0, 24),
        taller: int | None = None,
    ) -> None:
        self._spans = spans
        self._texts = texts
        self._size = size
        self._top, self._bottom = strip
        self.measurements_before_settling = 0
        self._settled = False
        # Which tab, if any, is the selected one. Measured on Tk 8.6.15: ttk
        # draws the selected tab standing two pixels proud at the top *and*
        # bottom, so no single row of the strip crosses every tab.
        self._taller = taller

    def settle(self) -> None:
        self._settled = True

    def tab_at(self, x: int, y: int) -> int | None:
        if not self._settled:
            self.measurements_before_settling += 1
        for index, (left, right) in self._spans.items():
            if (
                left <= x < right
                and self._runs_down(index)[0] <= y < self._runs_down(index)[1]
            ):
                return index
        return None

    def _runs_down(self, index: int) -> tuple[int, int]:
        if self._taller is None or index == self._taller:
            return self._top, self._bottom
        return self._top + _HOW_FAR_A_SELECTED_TAB_STANDS_PROUD, (
            self._bottom - _HOW_FAR_A_SELECTED_TAB_STANDS_PROUD
        )

    def text_of(self, index: int) -> str:
        return self._texts[index]

    def size(self) -> tuple[int, int]:
        return self._size


class RecordingWindows:
    """The Win32 seam: handles made, moved and destroyed, in the order it happened."""

    def __init__(self) -> None:
        self.made: list[tuple[int, tuple[int, int, int, int]]] = []
        self.moved: list[tuple[int, tuple[int, int, int, int]]] = []
        self.destroyed: list[int] = []
        self._next = 5000

    def create(self, parent: int, left: int, top: int, width: int, height: int) -> int:
        self._next += 1
        self.made.append((parent, (left, top, width, height)))
        return self._next

    def move(self, hwnd: int, left: int, top: int, width: int, height: int) -> None:
        self.moved.append((hwnd, (left, top, width, height)))

    def destroy(self, hwnd: int) -> None:
        self.destroyed.append(hwnd)

    def alive(self) -> int:
        return len(self.made) - len(self.destroyed)


def a_strip_of(*names: str) -> FakeStrip:
    """Tabs laid out left to right, 40 wide each, as ttk packs them."""
    return FakeStrip(
        spans={index: (index * 40, index * 40 + 40) for index in range(len(names))},
        texts=dict(enumerate(names)),
    )


def a_notebook_of(*names: str) -> tuple[RecordingStore, RecordingWindows, TabHandles]:
    store, windows = RecordingStore(), RecordingWindows()
    handles = TabHandles(store, windows)
    handles.refresh(_A_NOTEBOOK, _ITS_HANDLE, tabs_on(a_strip_of(*names)))
    return store, windows, handles


_A_NOTEBOOK = ".!notebook"
_ITS_HANDLE = 99
_HOW_FAR_A_SELECTED_TAB_STANDS_PROUD = 2


def test_a_strip_whose_selected_tab_stands_proud_still_yields_every_tab() -> None:
    # Given the strip ttk really draws: the selected tab is taller than its
    # neighbours at both ends, so the topmost row of the strip crosses that tab
    # and no other. Measured on Tk 8.6.15 — tab 0 ran rows 0..23, the rest 2..21.
    strip = FakeStrip(
        spans={index: (index * 40, index * 40 + 40) for index in range(3)},
        texts={0: "Alpha", 1: "Beta", 2: "Gamma"},
        taller=0,
    )

    found = tabs_on(strip)

    # Then all three are found. A scan that measured across the first row that
    # answered would report one tab and call the notebook done — which is a
    # notebook a client can see the selected page of and never leave.
    assert [tab.text for tab in found] == ["Alpha", "Beta", "Gamma"], (
        f"found {[tab.text for tab in found]}; the scan crossed a row that only "
        "the selected tab reaches"
    )
    # And every tab is given the strip's full extent rather than its own, so
    # that selecting a different one does not move every rectangle on the strip.
    assert {(tab.top, tab.height) for tab in found} == {(0, 24)}


def test_the_scan_finds_each_tab_where_the_notebook_says_it_is() -> None:
    found = tabs_on(a_strip_of("Alpha", "Beta"))

    assert found == (
        Tab(text="Alpha", left=0, top=0, width=40, height=24),
        Tab(text="Beta", left=40, top=0, width=40, height=24),
    )


def test_the_layout_is_left_to_settle_before_a_single_thing_is_measured() -> None:
    # Given a strip that records anything asked of it before it has settled
    strip = a_strip_of("Alpha", "Beta")

    tabs_on(strip)

    # Then nothing was. Tk lays a strip out on idle, so a tab added a moment ago
    # is not yet where it will be — measured, adding a tab and scanning straight
    # afterwards finds the strip exactly as it was and misses the new one.
    assert strip.measurements_before_settling == 0, (
        f"{strip.measurements_before_settling} measurements were taken against a "
        "layout Tk had not finished"
    )


def test_a_notebook_with_no_tabs_on_it_yields_nothing_to_give_a_handle_to() -> None:
    assert tabs_on(FakeStrip(spans={}, texts={})) == ()


def test_a_strip_inset_from_the_notebooks_top_left_is_measured_where_it_really_is() -> (
    None
):
    inset = FakeStrip(spans={0: (2, 60)}, texts={0: "Only"}, strip=(4, 30))

    assert tabs_on(inset) == (Tab(text="Only", left=2, top=4, width=58, height=26),)


def test_every_tab_is_given_a_window_of_its_own_saying_which_tab_it_is() -> None:
    store, windows, handles = a_notebook_of("Alpha", "Beta")

    assert [parent for parent, _ in windows.made] == [_ITS_HANDLE, _ITS_HANDLE]
    assert [rect for _, rect in windows.made] == [(0, 0, 40, 24), (40, 0, 40, 24)]
    assert [store.properties(hwnd) for hwnd in handles.handles(_A_NOTEBOOK)] == [
        {PropId.ROLE: Role.PAGE_TAB.value, PropId.NAME: "Alpha"},
        {PropId.ROLE: Role.PAGE_TAB.value, PropId.NAME: "Beta"},
    ]


def test_a_strip_that_has_not_changed_costs_nothing_to_refresh() -> None:
    _, windows, handles = a_notebook_of("Alpha", "Beta")
    already = list(handles.handles(_A_NOTEBOOK))

    handles.refresh(_A_NOTEBOOK, _ITS_HANDLE, tabs_on(a_strip_of("Alpha", "Beta")))

    # `<<NotebookTabChanged>>` fires on every tab *selection*, not only on the
    # ones that change the strip. Without this the cost of a notebook is paid
    # again every time a user clicks a tab, for no change to what a client reads.
    assert list(handles.handles(_A_NOTEBOOK)) == already
    assert len(windows.made) == 2
    assert windows.moved == []
    assert windows.destroyed == []


def test_a_tab_that_shifts_along_moves_the_window_it_already_has() -> None:
    _, windows, handles = a_notebook_of("Alpha", "Beta")
    shifted = (Tab("Alpha", 0, 0, 40, 24), Tab("Beta", 55, 0, 40, 24))

    handles.refresh(_A_NOTEBOOK, _ITS_HANDLE, shifted)

    assert len(windows.made) == 2
    assert windows.moved == [(handles.handles(_A_NOTEBOOK)[1], (55, 0, 40, 24))]


def test_a_renamed_tab_says_its_new_name_without_being_given_a_new_window() -> None:
    store, windows, handles = a_notebook_of("Alpha")

    handles.refresh(_A_NOTEBOOK, _ITS_HANDLE, (Tab("Renamed", 0, 0, 40, 24),))

    only = handles.handles(_A_NOTEBOOK)[0]
    assert store.properties(only)[PropId.NAME] == "Renamed"
    assert len(windows.made) == 1


def test_a_tab_that_has_gone_takes_its_window_with_it() -> None:
    _, windows, handles = a_notebook_of("Alpha", "Beta")
    surplus = handles.handles(_A_NOTEBOOK)[1]

    handles.refresh(_A_NOTEBOOK, _ITS_HANDLE, tabs_on(a_strip_of("Alpha")))

    assert windows.destroyed == [surplus]
    assert windows.alive() == 1


def test_a_surrendered_window_is_cleared_before_windows_can_hand_it_out_again() -> None:
    store, _, handles = a_notebook_of("Alpha", "Beta")
    surplus = handles.handles(_A_NOTEBOOK)[1]

    handles.refresh(_A_NOTEBOOK, _ITS_HANDLE, tabs_on(a_strip_of("Alpha")))

    # Cleared, and cleared *first*: an annotation outliving the handle it was
    # made on is the recycling hazard the ledger already guards against, and here
    # the package owns the handle rather than merely borrowing it.
    assert store.cleared == [surplus]
    assert store.properties(surplus) == {}


def test_a_notebook_that_goes_away_takes_every_tab_window_with_it() -> None:
    store, windows, handles = a_notebook_of("Alpha", "Beta")
    made = list(handles.handles(_A_NOTEBOOK))

    handles.forget(_A_NOTEBOOK)

    assert windows.destroyed == made
    assert store.cleared == made
    assert handles.handles(_A_NOTEBOOK) == ()


def test_one_notebook_going_away_leaves_another_notebooks_tabs_alone() -> None:
    store, windows = RecordingStore(), RecordingWindows()
    handles = TabHandles(store, windows)
    handles.refresh(".!one", 11, tabs_on(a_strip_of("Alpha")))
    handles.refresh(".!two", 22, tabs_on(a_strip_of("Beta", "Gamma")))

    handles.forget(".!one")

    assert len(handles.handles(".!two")) == 2
    assert windows.alive() == 2


def test_forgetting_a_notebook_that_was_never_reached_is_not_an_error() -> None:
    handles = TabHandles(RecordingStore(), RecordingWindows())

    handles.forget(".!never-seen")

    assert handles.handles(".!never-seen") == ()


def test_the_tabs_a_notebook_has_handles_for_can_be_read_back_for_a_report() -> None:
    _, _, handles = a_notebook_of("Alpha", "Beta")

    assert [tab.text for tab in handles.on(_A_NOTEBOOK)] == ["Alpha", "Beta"]


def test_a_notebook_nothing_reached_reports_no_tabs_rather_than_raising() -> None:
    handles = TabHandles(RecordingStore(), RecordingWindows())

    assert handles.on(_A_NOTEBOOK) == ()
