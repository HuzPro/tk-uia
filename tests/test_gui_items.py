"""Behavioral spec for a container's rows as real elements, read from another process.

Everything here happens through the accessibility tree alone: no synthetic
input, no foreground, and the machine's own mouse never moves.
"""

from __future__ import annotations

from tests.conftest import RunningApp, eventually
from tests.fixture_apps.provided_app import (
    REFRESH_THE_RESULTS,
    RESULT_ROWS,
    SEARCH_RESULTS,
    TASK_TREE,
    THE_ROW_A_REFRESH_BRINGS,
    TREE_BRANCH,
    TREE_LEAVES,
    TREE_SECOND_BRANCH,
    picked,
    picked_in_tree,
)

_AN_EMPTY_RECTANGLE = 0


def test_a_listboxes_rows_are_elements_a_client_can_walk_and_read(
    provided_app: RunningApp,
) -> None:
    # Given the listbox the application filled
    listbox = _the_listbox_of(provided_app)

    # When a client walks into it
    rows = listbox.GetChildren()

    # Then every row is there: named, typed as a list item, in the
    # application's own order
    assert [row.Name for row in rows] == list(RESULT_ROWS), (
        f"the rows a client can walk: {[row.Name for row in rows]}"
    )
    assert {row.ControlTypeName for row in rows} == {"ListItemControl"}, (
        f"rows came back typed as {sorted({row.ControlTypeName for row in rows})}"
    )


def test_a_row_is_selected_for_real_through_its_selection_item_pattern(
    provided_app: RunningApp,
) -> None:
    # Given a row, unselected, in an application listening for its selection
    import uiautomation as auto

    row = _the_row_named(provided_app, RESULT_ROWS[1])
    assert row.GetPattern(auto.PatternId.SelectionItemPattern).IsSelected is False

    # When a client selects it, which is all assistive technology has
    row.GetPattern(auto.PatternId.SelectionItemPattern).Select()

    # Then the row is selected, and the application heard the same
    # <<ListboxSelect>> a user's own choice would have fired
    eventually(
        lambda: row.GetPattern(auto.PatternId.SelectionItemPattern).IsSelected,
        True,
        "Select() returned cleanly and the row never took the selection",
    )
    eventually(
        _what_the_list_heard(provided_app.window),
        picked(RESULT_ROWS[1]),
        "the selection landed without the application hearing <<ListboxSelect>>",
    )


def test_an_offscreen_row_says_so_and_scroll_into_view_gives_it_a_place(
    provided_app: RunningApp,
) -> None:
    # Given the last row, below a viewport three rows tall
    import uiautomation as auto

    row = _the_row_named(provided_app, RESULT_ROWS[-1])
    assert row.BoundingRectangle.width() == _AN_EMPTY_RECTANGLE, (
        "a row below the viewport claimed a place on screen"
    )

    # When a client asks for it to be brought into view
    row.GetPattern(auto.PatternId.ScrollItemPattern).ScrollIntoView()

    # Then the listbox scrolled and the row has a rectangle
    eventually(
        lambda: row.BoundingRectangle.width() > _AN_EMPTY_RECTANGLE,
        True,
        "ScrollIntoView returned cleanly and the row never got a place",
    )


def test_the_rows_a_client_walks_follow_the_applications_own_edits(
    provided_app: RunningApp,
) -> None:
    # Given the listbox as first shown, and an application that then refreshes
    # it: the first row deleted, a new one appended
    listbox = _the_listbox_of(provided_app)
    assert [row.Name for row in listbox.GetChildren()] == list(RESULT_ROWS)
    provided_app.ask_for(REFRESH_THE_RESULTS)

    # When a client walks in again
    # Then it gets the rows the widget holds now, never an echo of map time
    eventually(
        lambda: [row.Name for row in listbox.GetChildren()],
        [*RESULT_ROWS[1:], THE_ROW_A_REFRESH_BRINGS],
        "the walk kept serving rows the application no longer holds",
    )


def test_rows_join_and_leave_a_selection_where_the_widget_takes_more_than_one(
    provided_app: RunningApp,
) -> None:
    # Given an extended-selectmode listbox with one row already selected
    import uiautomation as auto

    first = _the_row_named(provided_app, RESULT_ROWS[0])
    second = _the_row_named(provided_app, RESULT_ROWS[1])
    first.GetPattern(auto.PatternId.SelectionItemPattern).Select()
    eventually(
        lambda: first.GetPattern(auto.PatternId.SelectionItemPattern).IsSelected,
        True,
        "the opening Select never landed",
    )

    # When a client adds a second row, which is all assistive technology has
    second.GetPattern(auto.PatternId.SelectionItemPattern).AddToSelection()

    # Then both rows are selected, and the application heard both
    eventually(
        lambda: second.GetPattern(auto.PatternId.SelectionItemPattern).IsSelected,
        True,
        "AddToSelection returned cleanly and the row never joined",
    )
    assert first.GetPattern(auto.PatternId.SelectionItemPattern).IsSelected is True, (
        "adding a second row silently dropped the first, which is Select, not Add"
    )
    eventually(
        _what_the_list_heard(provided_app.window),
        picked(RESULT_ROWS[0], RESULT_ROWS[1]),
        "the join landed without the application hearing <<ListboxSelect>>",
    )

    # And when the client takes the first row back out
    first.GetPattern(auto.PatternId.SelectionItemPattern).RemoveFromSelection()

    # Then only the second remains
    eventually(
        lambda: first.GetPattern(auto.PatternId.SelectionItemPattern).IsSelected,
        False,
        "RemoveFromSelection returned cleanly and the row never left",
    )
    assert second.GetPattern(auto.PatternId.SelectionItemPattern).IsSelected is True, (
        "removing one row took the other with it"
    )


def test_a_tree_takes_a_second_row_into_its_selection(
    provided_app: RunningApp,
) -> None:
    # Given a tree whose extended selectmode takes more than one
    import uiautomation as auto

    first = _the_tree_item_of(provided_app, TREE_BRANCH)
    second = _the_tree_item_of(provided_app, TREE_SECOND_BRANCH)
    first.GetPattern(auto.PatternId.SelectionItemPattern).Select()

    # When a client adds the second branch
    second.GetPattern(auto.PatternId.SelectionItemPattern).AddToSelection()

    # Then both are selected
    eventually(
        lambda: second.GetPattern(auto.PatternId.SelectionItemPattern).IsSelected,
        True,
        "AddToSelection returned cleanly and the branch never joined",
    )
    assert first.GetPattern(auto.PatternId.SelectionItemPattern).IsSelected is True, (
        "adding the second branch dropped the first"
    )


def test_a_treeviews_items_are_a_walkable_tree_of_branches_and_rows(
    provided_app: RunningApp,
) -> None:
    # Given the tree the application filled: two branches, rows under the first
    tree = _the_tree_of(provided_app)

    # When a client walks in, and then into the first branch
    branches = tree.GetChildren()
    beneath = branches[0].GetChildren()

    # Then the branches are tree items in order, and the branch's rows hang
    # beneath it rather than beside it
    assert [branch.Name for branch in branches] == [TREE_BRANCH, TREE_SECOND_BRANCH], (
        f"the branches a client can walk: {[branch.Name for branch in branches]}"
    )
    assert {branch.ControlTypeName for branch in branches} == {"TreeItemControl"}, (
        f"branches came back typed as {[branch.ControlTypeName for branch in branches]}"
    )
    assert [row.Name for row in beneath] == list(TREE_LEAVES), (
        f"the rows beneath {TREE_BRANCH}: {[row.Name for row in beneath]}"
    )


def test_a_closed_branch_opens_for_real_through_its_expand_collapse_pattern(
    provided_app: RunningApp,
) -> None:
    # Given the first branch, closed, its rows folded out of view
    import uiautomation as auto

    branch = _the_tree_item_of(provided_app, TREE_BRANCH)
    row = _the_tree_item_of(provided_app, TREE_LEAVES[0])
    pattern = branch.GetPattern(auto.PatternId.ExpandCollapsePattern)
    assert pattern.ExpandCollapseState == auto.ExpandCollapseState.Collapsed, (
        f"a closed branch read back state {pattern.ExpandCollapseState}"
    )
    assert row.BoundingRectangle.width() == _AN_EMPTY_RECTANGLE, (
        "a row folded away claimed a place on screen"
    )

    # When a client expands it, which is all assistive technology has
    pattern.Expand()

    # Then the branch genuinely opened: it says so, and its row has a place
    eventually(
        lambda: (
            branch.GetPattern(auto.PatternId.ExpandCollapsePattern).ExpandCollapseState
        ),
        auto.ExpandCollapseState.Expanded,
        "Expand() returned cleanly and the branch never opened",
    )
    eventually(
        lambda: row.BoundingRectangle.width() > _AN_EMPTY_RECTANGLE,
        True,
        "the branch opened and its row still has no place on screen",
    )


def test_a_tree_row_is_selected_for_real_and_the_application_hears_it(
    provided_app: RunningApp,
) -> None:
    # Given the second branch, unselected, in an application listening
    import uiautomation as auto

    row = _the_tree_item_of(provided_app, TREE_SECOND_BRANCH)
    assert row.GetPattern(auto.PatternId.SelectionItemPattern).IsSelected is False

    # When a client selects it
    row.GetPattern(auto.PatternId.SelectionItemPattern).Select()

    # Then it is selected, and the application heard the same
    # <<TreeviewSelect>> a user's own choice would have fired
    eventually(
        lambda: row.GetPattern(auto.PatternId.SelectionItemPattern).IsSelected,
        True,
        "Select() returned cleanly and the row never took the selection",
    )
    eventually(
        _what_the_tree_heard(provided_app.window),
        picked_in_tree(TREE_SECOND_BRANCH),
        "the selection landed without the application hearing <<TreeviewSelect>>",
    )


def _the_listbox_of(app: RunningApp):
    import uiautomation as auto

    return auto.ListControl(searchFromControl=app.window, Name=SEARCH_RESULTS)


def _the_tree_of(app: RunningApp):
    import uiautomation as auto

    return auto.TreeControl(searchFromControl=app.window, Name=TASK_TREE)


def _the_tree_item_of(app: RunningApp, words: str):
    import uiautomation as auto

    return auto.TreeItemControl(searchFromControl=_the_tree_of(app), Name=words)


def _what_the_tree_heard(window):
    import uiautomation as auto

    heard = picked_in_tree("").rstrip()

    def read() -> str:
        return auto.TextControl(searchFromControl=window, SubName=heard).Name

    return read


def _the_row_named(app: RunningApp, words: str):
    import uiautomation as auto

    return auto.ListItemControl(searchFromControl=_the_listbox_of(app), Name=words)


def _what_the_list_heard(window):
    import uiautomation as auto

    heard = picked("").rstrip()

    def read() -> str:
        return auto.TextControl(searchFromControl=window, SubName=heard).Name

    return read
