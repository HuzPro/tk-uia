"""Behavioral spec for the rows a container answers for: who they are, in what
order, what hangs beneath them, and what happens to one that is no longer there."""

from __future__ import annotations

from tests.doubles import FakeWidget, HeldPoster, RecordingPlatform
from tk_uia.annotate import Ledger
from tk_uia.provide import Providers, WidgetWiring

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
