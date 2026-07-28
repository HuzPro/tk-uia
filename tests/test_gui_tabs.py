"""Behavioral spec for a notebook's tabs, read back by a real client."""

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

# The application checks for a dropped command every 50ms and Tk relays out on idle.
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


def test_a_notebook_from_a_reimported_ttk_still_gets_its_tabs(
    reimported_ttk_app: RunningApp,
) -> None:
    # Given an app that deleted and re-imported tkinter.ttk after enable(), as IDLE does
    # When a client reads the window
    seen = [
        control.Name
        for control in the_widgets_the_application_shows(reimported_ttk_app.window)
        if control.ControlTypeName == _A_TAB
    ]

    # Then the tabs are there: a gate that asked isinstance failed this window silently
    assert seen == ["Fonts", "Keys"], (
        f"a client sees tabs {seen}; the notebook gate does not survive a "
        "re-imported tkinter.ttk"
    )


def test_every_tab_on_a_notebook_is_a_control_a_client_can_see_and_name(
    notebook_app: RunningApp,
) -> None:
    # Given a Tk notebook that has switched accessibility on
    # When a client reads the window
    seen = tabs_a_client_can_see(notebook_app.window)

    # Then each tab is in the tree, named, and in the order the strip shows them
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

    # Then the tabs sit under one tab control rather than replacing it
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

    # Then it is there: adding a tab fires no Tk event at all
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

    # Then it goes anyway: removing the open tab moves the selection, which Tk announces
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

    # Then the new name is what a client reads: renaming fires no Tk event of any kind
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

    # Then Tk selected that page: WS_EX_TRANSPARENT lets the click fall through
    assert until(lambda: _the_page_now_showing(window) == f"the {THIRD} page"), (
        f"after clicking {THIRD} the notebook shows {_the_page_now_showing(window)!r}; "
        "the overlay swallowed the click instead of letting it through"
    )


def _the_page_now_showing(window: Any) -> str | None:
    # Only the visible page has a readable label: Tk unmaps the others.
    for control in the_widgets_the_application_shows(window):
        if control.ControlTypeName == "TextControl" and control.Name.startswith("the "):
            return control.Name
    return None
