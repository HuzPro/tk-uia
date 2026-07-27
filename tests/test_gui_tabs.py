"""Behavioral spec for a notebook's tabs, read back by a real client.

Everything above `tabs.py`'s seams is decided against recording doubles, and a
double would agree just as happily with a window handle nothing can read. Tabs
raise the stakes: the package *makes* these handles rather than borrowing ones
Tk made, so "the handle exists" and "a client can see a tab there" are further
apart here than anywhere else in the package.

One of these presses a tab, which is the only spec in the suite that touches the
mouse. It has to: a tab a client can read and not press would leave a notebook
exactly as unusable as it was, and clicking is the only way to find out.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import pytest

from tests.conftest import RunningApp, the_widgets_the_application_shows
from tests.fixture_apps.notebook_app import (
    ADD_A_TAB,
    ADDED_LATER,
    FIRST,
    REMOVE_THE_SELECTED_TAB,
    RENAME_THE_FIRST_TAB,
    RENAMED,
    SECOND,
    THIRD,
)

pytestmark = pytest.mark.gui

_A_TAB = "TabItemControl"
_THE_TAB_CONTROL = "TabControl"

# The application checks for a dropped command every 50ms and Tk relays out on
# idle; this is the outside of both, and every wait below polls rather than
# spends it.
_LONG_ENOUGH_FOR_THE_APP_TO_ACT_SECONDS = 5.0
_HOW_OFTEN_TO_LOOK = 0.1


def tabs_a_client_can_see(window: Any) -> list[str]:
    return [
        control.Name
        for control in the_widgets_the_application_shows(window)
        if control.ControlTypeName == _A_TAB
    ]


def until(what: Callable[[], bool]) -> bool:
    ran_out_at = time.monotonic() + _LONG_ENOUGH_FOR_THE_APP_TO_ACT_SECONDS
    while time.monotonic() < ran_out_at:
        if what():
            return True
        time.sleep(_HOW_OFTEN_TO_LOOK)
    return False


def test_every_tab_on_a_notebook_is_a_control_a_client_can_see_and_name(
    notebook_app: RunningApp,
) -> None:
    # Given a Tk notebook that has switched accessibility on
    # When a client reads the window
    seen = tabs_a_client_can_see(notebook_app.window)

    # Then each tab is in the tree, named, and in the order the strip shows
    # them. Bare Tk gives a TabControl with nothing inside it at all: the tabs
    # are painted into the notebook's own window and have no handle of their own.
    assert seen == [FIRST, SECOND, THIRD], (
        f"a client saw {seen}; the tabs are painted rather than exposed, so a "
        "test can read whichever page is open and can never change it"
    )


def test_the_notebook_itself_is_still_the_tab_control_holding_them(
    notebook_app: RunningApp,
) -> None:
    # Given the same window
    shown = the_widgets_the_application_shows(notebook_app.window)

    # When the tab control is looked for among them
    controls = [
        control.ControlTypeName
        for control in shown
        if control.ControlTypeName in (_THE_TAB_CONTROL, _A_TAB)
    ]

    # Then the tabs sit under one tab control rather than replacing it. The
    # handles are children of the notebook's own window, so the shape a client
    # expects — a tab control with tabs in it — is the shape it gets.
    assert controls[0] == _THE_TAB_CONTROL, (
        f"the notebook reads as {controls}; a client walking down from the tab "
        "control would not find the tabs beneath it"
    )


def test_a_tab_added_after_startup_appears_without_the_application_saying_so(
    notebook_app: RunningApp,
) -> None:
    # Given a client that can already see the three tabs the window started with
    assert tabs_a_client_can_see(notebook_app.window) == [FIRST, SECOND, THIRD]

    # When the application adds another and re-announces the notebook
    notebook_app.ask_for(ADD_A_TAB)

    # Then it is there. Measured on Tk 8.6.15: adding a tab beside the open one
    # moves no selection, and `<<NotebookTabChanged>>` is fired for selection and
    # nothing else — so no Tk event announces this at all. `add_acc_object` is
    # the same escape hatch a `config(text=...)` needs, for the same reason.
    assert until(lambda: ADDED_LATER in tabs_a_client_can_see(notebook_app.window)), (
        f"a client still sees {tabs_a_client_can_see(notebook_app.window)} after "
        "a tab was added"
    )


def test_removing_the_open_tab_withdraws_it_without_the_application_saying_so(
    notebook_app: RunningApp,
) -> None:
    # Given the window as it starts, with the first tab open
    assert tabs_a_client_can_see(notebook_app.window) == [FIRST, SECOND, THIRD]

    # When the application removes the tab that is open, and says nothing
    notebook_app.ask_for(REMOVE_THE_SELECTED_TAB)

    # Then it goes anyway: removing the open tab moves the selection, which is
    # the one tab change Tk does announce, and the binding is what notices. A
    # tab left behind would be worse than one never shown — it is findable, it
    # has a rectangle, and pressing it reaches a page that is not there.
    assert until(
        lambda: tabs_a_client_can_see(notebook_app.window) == [SECOND, THIRD]
    ), (
        f"a client still sees {tabs_a_client_can_see(notebook_app.window)} after "
        f"{FIRST} was removed"
    )


def test_a_renamed_tab_says_its_new_name_once_the_application_re_announces_it(
    notebook_app: RunningApp,
) -> None:
    # Given the window as it starts
    assert FIRST in tabs_a_client_can_see(notebook_app.window)

    # When the application renames a tab and says so
    notebook_app.ask_for(RENAME_THE_FIRST_TAB)

    # Then the new name is what a client reads. Renaming fires no Tk event of
    # any kind, exactly as `config(text=...)` on a label does not, so this is
    # `add_acc_object(notebook)` — the same escape hatch, for the same reason.
    assert until(lambda: RENAMED in tabs_a_client_can_see(notebook_app.window)), (
        f"a client still sees {tabs_a_client_can_see(notebook_app.window)}"
    )


def test_a_tab_a_client_presses_is_the_tab_the_notebook_then_shows(
    notebook_app: RunningApp,
) -> None:
    # Given a notebook showing its first page
    import uiautomation as auto

    window = notebook_app.window
    third = next(
        control
        for control in the_widgets_the_application_shows(window)
        if control.ControlTypeName == _A_TAB and control.Name == THIRD
    )
    where = third.BoundingRectangle
    assert where.width() and where.height(), (
        "the tab has no rectangle, so there is nothing for a client to aim at"
    )

    # When a client clicks the middle of it
    auto.Click(where.left + where.width() // 2, where.top + where.height() // 2)

    # Then Tk selected that page. This is the whole justification for the
    # machinery: the handle is WS_EX_TRANSPARENT, so it is in the tree for
    # reading and invisible to hit-testing, and the click lands on the notebook
    # underneath. A tab that could be read and not pressed would leave the
    # window exactly as undriveable as it was.
    assert until(lambda: _the_page_now_showing(window) == f"the {THIRD} page"), (
        f"after clicking {THIRD} the notebook shows {_the_page_now_showing(window)!r}; "
        "the overlay swallowed the click instead of letting it through"
    )


def _the_page_now_showing(window: Any) -> str | None:
    # The page's own label, which only the visible page has: Tk unmaps the
    # others, so whatever a client can read is what the notebook is showing.
    for control in the_widgets_the_application_shows(window):
        if control.ControlTypeName == "TextControl" and control.Name.startswith("the "):
            return control.Name
    return None
