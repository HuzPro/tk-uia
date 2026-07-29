"""Behavioral spec for the rows a container answers for: who they are, in what
order, what hangs beneath them, and what happens to one that is no longer there."""

from __future__ import annotations

from tests.doubles import FakeWidget, HeldPoster, RecordingPlatform
from tk_uia.annotate import Ledger
from tk_uia.provide import (
    Providers,
    SelectionChange,
    WidgetWiring,
    the_selection_changes_between,
)

_A_BUTTON_HANDLE = 0x000807D1
_A_LISTBOX_HANDLE = 0x000807D2
_A_TREE_HANDLE = 0x000807D3


class ARunOfRows:
    """A flat keyed container: a list standing in for what a listbox holds."""

    def __init__(self, *rows: str) -> None:
        self.rows = list(rows)
        self.selected: set[str] = set()
        self.shown: list[str] = []

    def roots(self) -> tuple[str, ...]:
        return tuple(str(index) for index in range(len(self.rows)))

    def children(self, key: str) -> tuple[str, ...]:
        return ()

    def parent(self, key: str) -> str | None:
        return None

    def exists(self, key: str) -> bool:
        return key in self.roots()

    def words(self, key: str) -> str | None:
        return self.rows[int(key)]

    def select(self, key: str) -> None:
        self.selected = {key}

    def is_selected(self, key: str) -> bool:
        return key in self.selected

    def show(self, key: str) -> None:
        self.shown.append(key)

    def rectangle(self, key: str) -> tuple[int, int, int, int] | None:
        return (10, 20 + 15 * int(key), 120, 15)

    def is_open(self, key: str) -> bool:
        return False

    def open(self, key: str) -> None: ...

    def close(self, key: str) -> None: ...

    def takes_more_than_one(self) -> bool:
        return True

    def add_to_selection(self, key: str) -> None:
        self.selected.add(key)

    def remove_from_selection(self, key: str) -> None:
        self.selected.discard(key)

    def announce_selection_to(self, say) -> None:
        self.say = say


class ATreeOfRows(ARunOfRows):
    """Two branches, one holding two rows, as a treeview holds them."""

    def __init__(self) -> None:
        super().__init__()
        self._held = {"": ("chores", "errands"), "chores": ("sweep", "dust")}
        self.opened: set[str] = set()

    def roots(self) -> tuple[str, ...]:
        return self._held[""]

    def children(self, key: str) -> tuple[str, ...]:
        return self._held.get(key, ())

    def parent(self, key: str) -> str | None:
        return next(
            (holder or None for holder, held in self._held.items() if key in held),
            None,
        )

    def exists(self, key: str) -> bool:
        return any(key in held for held in self._held.values())

    def words(self, key: str) -> str | None:
        return key

    def is_open(self, key: str) -> bool:
        return key in self.opened

    def open(self, key: str) -> None:
        self.opened.add(key)

    def close(self, key: str) -> None:
        self.opened.discard(key)


def _attached(widget: FakeWidget, platform: RecordingPlatform, **wiring_fields):
    fields = {
        "words": lambda: None,
        "is_enabled": lambda: True,
        "post": HeldPoster(),
        "still_there": widget.winfo_exists,
    }
    fields.update(wiring_fields)
    providers = Providers(platform, lambda _: WidgetWiring(**fields), said=Ledger())
    providers.attach(widget)
    return platform.hosted[widget.winfo_id()]


def test_a_widget_whose_class_has_no_items_answers_that_it_has_none() -> None:
    # Given a button, whose class holds nothing a client could walk into
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task")

    # When it is attached and a client asks after its items
    blueprint = _attached(button, RecordingPlatform())

    # Then the honest answer is that there are none, not an empty something
    assert blueprint.items is None, (
        f"a button invented items for itself: {blueprint.items!r}"
    )


def test_a_rows_words_are_read_from_the_widget_at_the_moment_a_client_asks() -> None:
    # Given a listbox holding three rows, whose application then renames one
    rows = ARunOfRows("Alpha", "Beta", "Gamma")
    listbox = FakeWidget("Listbox", _A_LISTBOX_HANDLE)
    blueprint = _attached(listbox, RecordingPlatform(), items=rows)

    # When a row's words change and a client asks
    rows.rows[1] = "Beta, renamed"

    # Then the answer is the moment's truth, never an echo of attach time
    assert blueprint.items.words("1") == "Beta, renamed", (
        "a row's words were frozen at attach time; the pull happens when asked"
    )


def test_an_empty_container_has_no_first_or_last_row() -> None:
    # Given a listbox holding nothing
    listbox = FakeWidget("Listbox", _A_LISTBOX_HANDLE)
    blueprint = _attached(listbox, RecordingPlatform(), items=ARunOfRows())

    # When a client asks where a walk into it would land
    # Then there is nowhere to land
    assert blueprint.items.first() is None, "an empty listbox offered a first row"
    assert blueprint.items.last() is None, "an empty listbox offered a last row"


def test_a_client_walks_the_rows_in_order_and_the_walk_ends_at_both_edges() -> None:
    # Given a listbox holding three rows
    listbox = FakeWidget("Listbox", _A_LISTBOX_HANDLE)
    items = _attached(
        listbox, RecordingPlatform(), items=ARunOfRows("Alpha", "Beta", "Gamma")
    ).items

    # When a client walks forward from the first row and back from the last
    # Then it visits every row once, in order, and each edge answers nothing
    assert (items.first(), items.after("0"), items.after("1")) == ("0", "1", "2"), (
        "walking forward missed a row or took them out of order"
    )
    assert (items.last(), items.before("2"), items.before("1")) == ("2", "1", "0"), (
        "walking backward missed a row or took them out of order"
    )
    assert items.after("2") is None, "the walk ran off the end instead of stopping"
    assert items.before("0") is None, "the walk ran off the start instead of stopping"


def test_a_branchs_rows_hang_beneath_it_and_name_it_as_their_holder() -> None:
    # Given a tree with two branches, the first holding two rows
    tree = FakeWidget("Treeview", _A_TREE_HANDLE)
    items = _attached(tree, RecordingPlatform(), items=ATreeOfRows()).items

    # When a client walks into the first branch and back out of it
    # Then the rows are there, in order, and each names the branch it hangs on
    assert (items.first_child("chores"), items.last_child("chores")) == (
        "sweep",
        "dust",
    ), "the branch's own rows are not reachable beneath it"
    assert items.after("sweep") == "dust" and items.after("dust") is None, (
        "the walk along a branch's rows leaked out of the branch"
    )
    assert items.parent("sweep") == "chores", (
        f"a row names {items.parent('sweep')!r} as its holder"
    )
    assert items.parent("chores") is None, (
        "a top-level branch invented a holder for itself"
    )
    assert items.first_child("errands") is None, "an empty branch offered a first row"


def test_a_branch_opens_and_closes_through_the_poster_and_reads_back_openness() -> None:
    # Given a closed branch
    rows = ATreeOfRows()
    poster = HeldPoster()
    tree = FakeWidget("Treeview", _A_TREE_HANDLE)
    items = _attached(tree, RecordingPlatform(), items=rows, post=poster).items
    assert items.is_open("chores") is False, "a closed branch read back as open"

    # When a client opens it
    items.open("chores")

    # Then the call answered first, and the opening lands with the Tk thread
    assert rows.opened == set(), "the opening ran inside the client's call"
    poster.run_everything_posted()
    assert items.is_open("chores") is True, "the posted opening never landed"

    # And closing takes the same road back
    items.close("chores")
    poster.run_everything_posted()
    assert items.is_open("chores") is False, "the posted closing never landed"


def test_a_row_the_container_no_longer_holds_answers_nothing_rather_than_raising() -> (
    None
):
    # Given a client holding the last row of three when the application
    # deletes two, as a refresh does
    rows = ARunOfRows("Alpha", "Beta", "Gamma")
    listbox = FakeWidget("Listbox", _A_LISTBOX_HANDLE)
    items = _attached(listbox, RecordingPlatform(), items=rows).items
    del rows.rows[1:]

    # When the client asks after the row it still holds
    # Then every answer is nothing: the question outlived the row, and the
    # callback it lands in is forbidden to raise
    assert items.still_there("2") is False, "a deleted row still claimed to exist"
    assert items.words("2") is None, "a deleted row still answered words"
    assert items.is_selected("2") is False, "a deleted row still claimed selection"
    assert items.rectangle("2") is None, "a row nobody holds still had a rectangle"


def test_selecting_a_row_answers_first_and_reaches_the_widget_through_the_poster() -> (
    None
):
    # Given a listbox whose rows a client can select
    rows = ARunOfRows("Alpha", "Beta")
    poster = HeldPoster()
    listbox = FakeWidget("Listbox", _A_LISTBOX_HANDLE)
    items = _attached(listbox, RecordingPlatform(), items=rows, post=poster).items

    # When a client selects a row
    items.select("1")

    # Then the call answered before anything ran, and the selection lands
    # when the Tk thread gets to it
    assert rows.selected == set(), (
        "the selection ran inside the client's call instead of being posted"
    )
    poster.run_everything_posted()
    assert items.is_selected("1") is True, "the posted selection never landed"


def test_a_select_posted_for_a_row_deleted_before_it_ran_does_nothing() -> None:
    # Given a selection in flight when the application deletes the row
    rows = ARunOfRows("Alpha", "Beta")
    poster = HeldPoster()
    listbox = FakeWidget("Listbox", _A_LISTBOX_HANDLE)
    items = _attached(listbox, RecordingPlatform(), items=rows, post=poster).items
    items.select("1")
    del rows.rows[1:]

    # When the Tk thread gets to the post
    poster.run_everything_posted()

    # Then nothing was selected on the row's old key
    assert rows.selected == set(), (
        "a posted select landed on a key whose row was already gone"
    )


def test_scrolling_a_row_into_view_answers_first_and_is_skipped_once_stale() -> None:
    # Given a listbox a client asks to scroll
    rows = ARunOfRows("Alpha", "Beta")
    poster = HeldPoster()
    listbox = FakeWidget("Listbox", _A_LISTBOX_HANDLE)
    items = _attached(listbox, RecordingPlatform(), items=rows, post=poster).items

    # When it asks for a living row and a stale one
    items.show("1")
    items.show("5")

    # Then both answer at once, and only the living row's scroll ever runs
    assert rows.shown == [], "the scroll ran inside the client's call"
    poster.run_everything_posted()
    assert rows.shown == ["1"], f"the scrolls that ran: {rows.shown}"


def test_joining_and_leaving_a_selection_take_the_posted_road_and_skip_the_stale() -> (
    None
):
    # Given a multi-select listbox with one row already selected
    rows = ARunOfRows("Alpha", "Beta", "Gamma")
    rows.selected = {"0"}
    poster = HeldPoster()
    listbox = FakeWidget("Listbox", _A_LISTBOX_HANDLE)
    items = _attached(listbox, RecordingPlatform(), items=rows, post=poster).items

    # When a client adds a living row, adds a stale one, and removes the first
    items.add_to_selection("2")
    items.add_to_selection("9")
    items.remove_from_selection("0")

    # Then every call answered first, and only the living rows' moves ran
    assert rows.selected == {"0"}, "a selection move ran inside the client's call"
    poster.run_everything_posted()
    assert rows.selected == {"2"}, f"the selection ended as {rows.selected}"


def test_whether_more_than_one_row_may_be_selected_is_the_widgets_own_answer() -> None:
    # Given a container whose wiring takes more than one
    listbox = FakeWidget("Listbox", _A_LISTBOX_HANDLE)
    items = _attached(listbox, RecordingPlatform(), items=ARunOfRows("Alpha")).items

    # When a client asks
    # Then the answer is the wiring's, read at ask time
    assert items.takes_more_than_one() is True, (
        "the widget's own selectmode never reached the answers a client gets"
    )


def test_attaching_a_container_routes_its_selection_changes_to_the_platform() -> None:
    # Given a listbox whose wiring can say when its selection changed
    rows = ARunOfRows("Alpha", "Beta")
    platform = RecordingPlatform()
    listbox = FakeWidget("Listbox", _A_LISTBOX_HANDLE)
    _attached(listbox, platform, items=rows)

    # When the widget's own selection event fires, however it was caused
    rows.say(("1",))

    # Then the platform hears which rows are selected now, against the handle
    assert platform.selection_heard == [(_A_LISTBOX_HANDLE, ("1",))], (
        f"the platform heard {platform.selection_heard}"
    )


def test_a_selection_moving_to_one_new_row_is_announced_as_selected() -> None:
    # Given a selection that lands on a single new row, however it got there
    # When the change is weighed
    # Then it is one SELECTED announcement, which is what a screen reader
    # phrases as the row simply being chosen
    assert the_selection_changes_between((), ("1",)) == (
        (SelectionChange.SELECTED, "1"),
    ), "a first selection was not announced as selected"
    assert the_selection_changes_between(("0",), ("1",)) == (
        (SelectionChange.SELECTED, "1"),
    ), "a replaced selection was not announced as the new row selected"
    assert the_selection_changes_between(("0", "1"), ("2",)) == (
        (SelectionChange.SELECTED, "2"),
    ), "a selection collapsing onto a new row was not announced as selected"


def test_a_selection_growing_or_shrinking_names_each_row_that_moved() -> None:
    # Given a multi-selection gaining one row and then losing another
    # When each change is weighed
    # Then the rows that moved are named, and the ones that stayed are not
    assert the_selection_changes_between(("0",), ("0", "2")) == (
        (SelectionChange.ADDED, "2"),
    ), "growing a selection did not name the row that joined it"
    assert the_selection_changes_between(("0", "2"), ("2",)) == (
        (SelectionChange.REMOVED, "0"),
    ), "shrinking a selection did not name the row that left it"


def test_an_unchanged_selection_announces_nothing_at_all() -> None:
    # Given the same selection reported twice, as a click on a selected row does
    # When the change is weighed
    # Then there is nothing to say, and saying it anyway is what makes a
    # screen reader repeat itself
    assert the_selection_changes_between(("1",), ("1",)) == (), (
        "an unchanged selection was announced again"
    )
    assert the_selection_changes_between((), ()) == (), (
        "an empty selection staying empty was announced"
    )
