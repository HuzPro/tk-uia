"""Behavioral spec for the one liveness rule: actions answer first, run after."""

from __future__ import annotations

from tests.doubles import (
    AnInvoke,
    ASelection,
    AToggle,
    AValue,
    FakeWidget,
    HeldPoster,
    attached,
)
from tk_uia.provide import Pattern

_A_BUTTON_HANDLE = 0x000807D2
_A_CHECK_HANDLE = 0x000807D3
_A_RADIO_HANDLE = 0x000807D4
_AN_ENTRY_HANDLE = 0x000807D5


def test_invoke_answers_before_the_command_it_posted_has_run() -> None:
    # Given a button whose command could open anything, a modal dialog included
    poster = HeldPoster()
    invoke = AnInvoke()
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task")
    blueprint = attached(button, post=poster, invoke=invoke)

    # When a client presses through the pattern
    blueprint.patterns[Pattern.INVOKE].press()

    # Then the answer went back before the command ran, so nothing the command
    # opens can pin the callback and queue every later question behind it
    assert invoke.pressed == 0, (
        "the command ran inside the pattern callback; a modal dialog there "
        "would have held every later UIA request hostage"
    )

    # And the posted press still happens, exactly once
    poster.run_everything_posted()
    assert invoke.pressed == 1, "the posted press never ran"


def test_toggle_answers_before_the_flip_it_posted_has_run() -> None:
    # Given a checkbutton
    poster = HeldPoster()
    toggle = AToggle()
    check = FakeWidget("Checkbutton", _A_CHECK_HANDLE, text="Notify")
    blueprint = attached(check, post=poster, toggle=toggle)

    # When a client toggles
    blueprint.patterns[Pattern.TOGGLE].flip()

    # Then the same rule holds
    assert toggle.on is False, "the flip ran inside the pattern callback"
    poster.run_everything_posted()
    assert toggle.on is True, "the posted flip never ran"


def test_selecting_a_radio_answers_before_the_selection_it_posted_has_run() -> None:
    # Given a radio
    poster = HeldPoster()
    selection = ASelection()
    radio = FakeWidget("Radiobutton", _A_RADIO_HANDLE, text="High")
    blueprint = attached(radio, post=poster, selection=selection)

    # When a client selects it
    blueprint.patterns[Pattern.SELECTION_ITEM].select()

    # Then the same rule holds
    assert selection.selected is False, "the select ran inside the callback"
    poster.run_everything_posted()
    assert selection.selected is True, "the posted select never ran"


def test_set_value_writes_before_it_answers_so_a_read_back_sees_the_new_text() -> None:
    # Given an entry
    poster = HeldPoster()
    value = AValue()
    entry = FakeWidget("Entry", _AN_ENTRY_HANDLE)
    blueprint = attached(entry, post=poster, value=value)

    # When a client writes and reads straight back
    answers = blueprint.patterns[Pattern.VALUE]
    answers.write("hello")

    # Then the write is deliberately synchronous: nothing was posted, and the
    # read-back is already true
    assert poster.held == [], "SetValue was posted, so a read-back would race it"
    assert answers.read() == "hello", "a read straight after the write missed it"


def test_a_posted_press_is_skipped_when_the_widget_has_gone_in_the_meantime() -> None:
    # Given a press posted against a button that dies before the idle runs
    poster = HeldPoster()
    invoke = AnInvoke()
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task")
    blueprint = attached(button, post=poster, invoke=invoke)
    blueprint.patterns[Pattern.INVOKE].press()
    button.destroy()

    # When the posted work finally runs
    poster.run_everything_posted()

    # Then it walked away rather than pressing a dead widget
    assert invoke.pressed == 0, (
        "a posted press ran against a widget that had already gone"
    )


def test_a_puller_over_a_widget_mid_teardown_answers_nothing_rather_than_raising() -> (
    None
):
    # Given a puller whose widget Tk is tearing down mid-question
    from tests.doubles import FakeTclError
    from tk_uia.provide import answers_nothing_once_the_widget_is_gone

    def a_read_that_arrives_too_late() -> str:
        raise FakeTclError('bad window path name ".!entry"')

    guarded = answers_nothing_once_the_widget_is_gone(
        a_read_that_arrives_too_late, FakeTclError
    )

    # When a client's question lands between <Destroy> and the handle's end
    # Then the answer is nothing, never an exception into the callback layer
    assert guarded() is None, (
        "a mid-teardown read must answer nothing; an exception here escapes "
        "into a COM callback that is forbidden to raise"
    )
