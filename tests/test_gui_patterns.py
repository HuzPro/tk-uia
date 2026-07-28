"""Behavioral spec for widgets answering UIA themselves, read from another process.

Everything here happens through the accessibility tree alone: no synthetic
input, no foreground, and the machine's own mouse never moves.
"""

from __future__ import annotations

import time

import pytest

from tests.conftest import RunningApp
from tests.fixture_apps.provided_app import (
    ADVANCED_TAB,
    CONFIRMATION,
    HIGH,
    NEW_TASK,
    NOTIFY,
    ON_THE_SECOND_PAGE,
    OPEN_DIALOG,
    PRESSES,
    PROXY_BUTTON,
    PROXY_PRESSES,
    SAVE,
    THE_HELP,
    TITLE_ENTRY,
    TTK_PRESSES,
    presses,
)

_LONG_ENOUGH_FOR_A_POSTED_PRESS_SECONDS = 1.0
_LONG_ENOUGH_FOR_A_REACTION_THAT_WILL_NOT_COME_SECONDS = 2.0
_A_FEW_TRIES = 10

_ONCE = 1
_NEVER = 0


def _eventually(read, expected, why: str) -> None:
    for _ in range(_A_FEW_TRIES):
        if read() == expected:
            return
        time.sleep(0.3)
    raise AssertionError(f"{why}: still {read()!r}, wanted {expected!r}")


def _the_tally(window, kind: str):
    import uiautomation as auto

    def read() -> str:
        return auto.TextControl(searchFromControl=window, SubName=kind).Name

    return read


def test_a_button_is_pressed_for_real_through_its_invoke_pattern(
    provided_app: RunningApp,
) -> None:
    # Given the button, and the tally its own command keeps
    import uiautomation as auto

    button = auto.ButtonControl(searchFromControl=provided_app.window, Name=NEW_TASK)
    tally = _the_tally(provided_app.window, PRESSES)
    assert tally() == presses(PRESSES, _NEVER)

    # When a client presses through the pattern, which is all assistive
    # technology has
    button.GetPattern(auto.PatternId.InvokePattern).Invoke()

    # Then the command genuinely ran
    _eventually(
        tally,
        presses(PRESSES, _ONCE),
        "InvokePattern.Invoke() returned cleanly and pressed nothing",
    )


def test_an_invoke_that_opens_a_modal_dialog_leaves_the_process_answering_uia(
    provided_app: RunningApp,
) -> None:
    # Given a button whose command opens a modal messagebox
    import uiautomation as auto

    button = auto.ButtonControl(
        searchFromControl=provided_app.window, Name=OPEN_DIALOG
    )

    # When a client presses it
    button.GetPattern(auto.PatternId.InvokePattern).Invoke()

    # Then the dialog appears AND the process still answers questions, because
    # the press was posted rather than run inside the callback
    dialog = auto.WindowControl(
        searchFromControl=provided_app.window, Name=CONFIRMATION
    )
    assert dialog.Exists(10, 0.5), (
        "the modal dialog never appeared, or the process stopped answering "
        "UIA the moment the command ran"
    )

    # And the dialog is dismissed the same way, through the tree
    ok = auto.ButtonControl(searchFromControl=dialog, Name="OK")
    ok.GetPattern(auto.PatternId.InvokePattern).Invoke()
    still_answering = auto.ButtonControl(
        searchFromControl=provided_app.window, Name=NEW_TASK
    )
    assert still_answering.Exists(10, 0.5), (
        "the process stopped answering after the dialog was dismissed"
    )


def test_a_ttk_button_is_typed_named_and_pressable(provided_app: RunningApp) -> None:
    # Given the themed button, which annotation alone could never type or press
    import uiautomation as auto

    button = auto.ButtonControl(searchFromControl=provided_app.window, Name=SAVE)
    assert button.Exists(5, 0.25), (
        "the ttk button is not a named ButtonControl; the themed half of the "
        "toolkit is still anonymous"
    )
    tally = _the_tally(provided_app.window, TTK_PRESSES)

    # When a client presses it
    button.GetPattern(auto.PatternId.InvokePattern).Invoke()

    # Then it pressed
    _eventually(
        tally,
        presses(TTK_PRESSES, _ONCE),
        "a ttk button advertised Invoke and pressed nothing",
    )


def test_an_entry_round_trips_text_through_the_value_pattern(
    provided_app: RunningApp,
) -> None:
    # Given the entry the application named
    import uiautomation as auto

    entry = auto.EditControl(searchFromControl=provided_app.window, Name=TITLE_ENTRY)
    pattern = entry.GetPattern(auto.PatternId.ValuePattern)

    # When a client writes and reads back
    pattern.SetValue("write the quarterly report")

    # Then the widget holds the text, and says so when asked again
    assert (
        entry.GetPattern(auto.PatternId.ValuePattern).Value
        == "write the quarterly report"
    ), "SetValue returned cleanly and the widget never took the text"


def test_a_checkbutton_toggles_its_variable_through_the_toggle_pattern(
    provided_app: RunningApp,
) -> None:
    # Given the checkbutton, unchecked
    import uiautomation as auto

    checkbox = auto.CheckBoxControl(searchFromControl=provided_app.window, Name=NOTIFY)
    assert checkbox.GetPattern(auto.PatternId.TogglePattern).ToggleState == 0

    # When a client toggles it
    checkbox.GetPattern(auto.PatternId.TogglePattern).Toggle()

    # Then the state genuinely flipped
    _eventually(
        lambda: checkbox.GetPattern(auto.PatternId.TogglePattern).ToggleState,
        1,
        "Toggle() returned cleanly and the variable never moved",
    )


def test_a_radiobutton_selects_through_selection_item_and_reports_selected(
    provided_app: RunningApp,
) -> None:
    # Given the radio, unselected
    import uiautomation as auto

    radio = auto.RadioButtonControl(searchFromControl=provided_app.window, Name=HIGH)
    assert (
        radio.GetPattern(auto.PatternId.SelectionItemPattern).IsSelected is False
    )

    # When a client selects it
    radio.GetPattern(auto.PatternId.SelectionItemPattern).Select()

    # Then it is selected, and says so
    _eventually(
        lambda: radio.GetPattern(auto.PatternId.SelectionItemPattern).IsSelected,
        True,
        "Select() returned cleanly and the radio never took the selection",
    )


def test_a_scale_moves_through_range_value_and_reads_back_where_it_went(
    provided_app: RunningApp,
) -> None:
    # Given the scale
    import uiautomation as auto

    slider = auto.SliderControl(searchFromControl=provided_app.window)
    pattern = slider.GetPattern(auto.PatternId.RangeValuePattern)
    assert (pattern.Minimum, pattern.Maximum) == (0.0, 10.0), (
        f"the scale's range read back as {pattern.Minimum}..{pattern.Maximum}"
    )

    # When a client moves it
    pattern.SetValue(7)

    # Then it moved
    _eventually(
        lambda: slider.GetPattern(auto.PatternId.RangeValuePattern).Value,
        7.0,
        "RangeValue.SetValue returned cleanly and the scale never moved",
    )


def test_a_progressbar_refuses_the_write_and_reads_back_read_only(
    provided_app: RunningApp,
) -> None:
    # Given the progressbar
    import uiautomation as auto

    bar = auto.ProgressBarControl(searchFromControl=provided_app.window)
    pattern = bar.GetPattern(auto.PatternId.RangeValuePattern)

    # When a client reads it
    # Then the numbers are honest and the write is refused, never swallowed
    assert pattern.Value == 40.0 and pattern.IsReadOnly is True, (
        f"a progressbar read back {pattern.Value}, read-only {pattern.IsReadOnly}"
    )
    with pytest.raises(Exception):  # noqa: B017 - the COMError type lives client-side
        pattern.SetValue(90)


def test_help_the_application_set_reaches_a_uia_client_in_provider_mode(
    provided_app: RunningApp,
) -> None:
    # Given the button carrying a chosen help text
    import uiautomation as auto

    button = auto.ButtonControl(searchFromControl=provided_app.window, Name=NEW_TASK)

    # When a client asks for the help
    help_text = button.GetPropertyValue(auto.PropertyId.HelpTextProperty)

    # Then set_acc_help still reaches UIA clients with a provider answering
    assert help_text == THE_HELP, (
        f"HelpText read back {help_text!r}; set_acc_help lost its effect the "
        "moment the widget answered for itself"
    )


def test_a_notebook_tab_is_selected_through_its_provider_without_a_click(
    provided_app: RunningApp,
) -> None:
    # Given the notebook, open on its first page
    import uiautomation as auto

    tab = auto.TabItemControl(
        searchFromControl=provided_app.window, Name=ADVANCED_TAB
    )
    assert tab.Exists(5, 0.25), "the second tab never got a window of its own"
    assert (
        tab.GetPattern(auto.PatternId.SelectionItemPattern).IsSelected is False
    )

    # When a client selects the second tab through its pattern
    tab.GetPattern(auto.PatternId.SelectionItemPattern).Select()

    # Then the notebook switched pages, with no click anywhere
    _eventually(
        lambda: tab.GetPattern(auto.PatternId.SelectionItemPattern).IsSelected,
        True,
        "Select() returned cleanly and the notebook never switched",
    )
    second_page = auto.TextControl(
        searchFromControl=provided_app.window, Name=ON_THE_SECOND_PAGE
    )
    assert second_page.Exists(10, 0.5), (
        "the tab says selected and its page's widgets never reached the tree"
    )


def test_a_widget_left_to_the_proxy_reads_as_annotation_alone_from_outside(
    provided_app: RunningApp,
) -> None:
    # Given the button the application left to the MSAA proxy
    import uiautomation as auto

    button = auto.ButtonControl(
        searchFromControl=provided_app.window, Name=PROXY_BUTTON
    )
    assert button.Exists(5, 0.25), (
        "leaving a widget to the proxy took its annotations with it"
    )
    tally = _the_tally(provided_app.window, PROXY_PRESSES)

    # When a client does what assistive technology does to press it
    button.GetPattern(auto.PatternId.InvokePattern).Invoke()
    time.sleep(_LONG_ENOUGH_FOR_A_REACTION_THAT_WILL_NOT_COME_SECONDS)

    # Then nothing pressed: the proxy's Invoke is the old posted BM_CLICK,
    # which is exactly the behaviour the application asked to keep
    assert tally() == presses(PROXY_PRESSES, _NEVER), (
        "a widget left to the proxy was pressed through the tree, so the "
        "opt-out did not opt out"
    )
