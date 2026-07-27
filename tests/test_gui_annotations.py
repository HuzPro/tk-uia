"""Behavioral spec for what a Windows accessibility client sees in an annotated Tk.

A recording double would agree just as happily with a COM call that returned
`S_OK` and did nothing, so the proof has to come from outside: a real Tk window
in a process of its own, read back through UI Automation from this one. Nothing
here touches the mouse or the foreground.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Callable
from typing import Any

import pytest

from tests.conftest import RunningApp, the_widgets_the_application_shows
from tests.fixture_apps.annotated_app import (
    ADVANCE_THE_STATUS,
    DESTROY_THE_STATUS_LABEL,
    DISPOSABLE,
    DRAFT,
    FORGET_THE_DISPOSABLE_WIDGETS,
    HEADLINE,
    HOST,
    HOST_CAPTION,
    MOVE_WHAT_NOBODY_BOUND,
    NEW_TASK,
    NEW_TASK_NUMBER,
    PRESS_THE_BUTTON,
    READY,
    REVISE_THE_DRAFT,
    REVISION,
    SCRATCH,
    TASK_CREATED,
    TITLE,
    UNBOUND_DRAFT,
    UNBOUND_DRAFT_REVISED,
    UNBOUND_ENTRY_NAME,
    UNBOUND_STATUS,
    UNBOUND_STATUS_MOVED,
    presses,
    traces,
)

# What the MSAA bridge calls a window it has been told nothing about.
_A_PANE = "PaneControl"

# What it calls a Tk label: `Static` with SS_OWNERDRAW, which reads as a picture.
_AN_IMAGE = "ImageControl"

_TEXT = "TextControl"
_AN_EDIT = "EditControl"

_THE_CANVAS_AND_THE_CLEARED_ENTRY = 2

# The application checks for a command a few times a second.
_A_REACTION_TIMEOUT_SECONDS = 5.0
_HOW_OFTEN_TO_LOOK_AGAIN_SECONDS = 0.1

# Generous for a Tk command that does one addition.
_LONG_ENOUGH_FOR_A_REACTION_THAT_WILL_NOT_COME_SECONDS = 1.0

_NEVER = 0
_ONCE = 1

_ONE_BINDING = 1
_NOTHING_STILL_LISTENING = 0


pytestmark = [
    pytest.mark.gui,
    pytest.mark.skipif(
        sys.platform != "win32",
        reason="MSAA and UI Automation are Windows APIs",
    ),
]


def _what_the_application_shows(window: Any) -> list[tuple[str, str]]:
    """The application's widgets as a client reads them: what, and called what."""
    return [
        (control.ControlTypeName, control.Name)
        for control in the_widgets_the_application_shows(window)
    ]


def _eventually_shows(window: Any, widget: tuple[str, str], complaint: str) -> None:
    _eventually(lambda: widget in _what_the_application_shows(window), complaint)


def _eventually_stops_showing(
    window: Any, widget: tuple[str, str], complaint: str
) -> None:
    _eventually(lambda: widget not in _what_the_application_shows(window), complaint)


def _eventually(settled: Callable[[], bool], complaint: str) -> None:
    """Wait for the application to react, which it does on its own event loop."""
    deadline = time.monotonic() + _A_REACTION_TIMEOUT_SECONDS
    while not _settled_or_still_being_rebuilt(settled):
        if time.monotonic() >= deadline:
            pytest.fail(f"{complaint} (waited {_A_REACTION_TIMEOUT_SECONDS:.0f}s)")
        time.sleep(_HOW_OFTEN_TO_LOOK_AGAIN_SECONDS)


def _settled_or_still_being_rebuilt(settled: Callable[[], bool]) -> bool:
    """Read the tree, treating one caught mid-edit as "not yet" rather than as an error.

    A spec that destroys a widget races every walk of the tree: the control is
    enumerated, the application destroys it, and asking the handle for its type
    raises `COMError`.
    """
    import comtypes

    try:
        return settled()
    except comtypes.COMError:
        return False


def test_an_annotated_button_announces_its_name_to_a_client_in_another_process(
    annotated_app: RunningApp,
) -> None:
    # Given a live Tk window belonging to somebody else's process
    import uiautomation as auto

    # When a client asks it for a push button called "New Task"
    button = auto.ButtonControl(searchFromControl=annotated_app.window, Name=NEW_TASK)

    # Then the button answers to its own name
    assert button.Exists(0), (
        "no button in the window carries the name the application gave it; "
        "without the annotation Tk offers a ButtonControl whose Name is ''"
    )


def test_an_annotated_label_is_read_as_text_rather_than_as_a_picture(
    annotated_app: RunningApp,
) -> None:
    # Given a live Tk window, in which one label carries the application's words
    import uiautomation as auto

    # When a client looks for text saying them
    headline = auto.TextControl(searchFromControl=annotated_app.window, Name=HEADLINE)

    # Then the label is text, and says so
    assert headline.Exists(0), (
        "the label is not readable as text: bare Tk offers it as an "
        "ImageControl, and no query for text can reach a picture"
    )


def test_an_annotated_entry_is_read_as_an_edit_control_whose_value_a_client_can_query(
    annotated_app: RunningApp,
) -> None:
    # Given a live Tk window with a text box in it
    import uiautomation as auto

    # When a client asks for the edit control the label calls "Title"
    entry = auto.EditControl(searchFromControl=annotated_app.window, Name=TITLE)

    # Then it is an edit control at all
    assert entry.Exists(0), (
        "the entry is not reachable as an edit control; annotating its role is "
        "what turns Tk's anonymous PaneControl into one"
    )

    # And its contents can be read, through a ValuePattern the role brought with it
    assert entry.GetValuePattern().Value == DRAFT, (
        "the entry offers no readable value; setting role 42 (ROLE_SYSTEM_TEXT) "
        "is what makes the bridge give this control a ValuePattern"
    )


def test_an_entry_named_after_its_caption_answers_to_the_label_beside_it(
    annotated_app: RunningApp,
) -> None:
    # Given the form row: a caption, the entry it captions, and one `label_for` call
    import uiautomation as auto

    # When a client asks for the edit control by the words on the label
    entry = auto.EditControl(searchFromControl=annotated_app.window, Name=HOST)

    # Then it is there, under the caption without its colon
    assert entry.Exists(0), (
        f"no edit control in the window answers to {HOST!r}, so the association "
        "between the label and the entry reached no client"
    )

    # And the label goes on saying what it says on screen, colon and all
    shown = _what_the_application_shows(annotated_app.window)

    assert (_TEXT, HOST_CAPTION) in shown, (
        f"the caption stopped reading {HOST_CAPTION!r} of its own: {shown}"
    )


def test_a_widget_left_unannotated_still_looks_anonymous_to_a_client(
    annotated_app: RunningApp,
) -> None:
    # Given the same window, which also holds a widget of a class nobody knows

    # When every widget the application itself put on screen is listed
    widgets = the_widgets_the_application_shows(annotated_app.window)

    # Then exactly one of them is still a pane with no name
    anonymous = [
        (control.ControlTypeName, control.Name)
        for control in widgets
        if control.ControlTypeName == _A_PANE
    ]

    assert anonymous == [(_A_PANE, "")], (
        f"expected the unannotated unknown_class_widget to be the only pane among the "
        f"application's own widgets, and nameless; found {anonymous} out of "
        f"{[(c.ControlTypeName, c.Name) for c in widgets]}"
    )


def test_clearing_a_widgets_annotations_returns_it_to_looking_anonymous(
    annotated_app: RunningApp,
) -> None:
    # Given a label and an entry the application annotated at startup
    before = _what_the_application_shows(annotated_app.window)

    assert (_TEXT, DISPOSABLE) in before, f"the label was never annotated: {before}"
    assert (_AN_EDIT, SCRATCH) in before, f"the entry was never annotated: {before}"

    # When the application takes both annotations back
    annotated_app.ask_for(FORGET_THE_DISPOSABLE_WIDGETS)

    # Then each goes back to exactly what bare Tk offers for it
    _eventually_stops_showing(
        annotated_app.window,
        (_TEXT, DISPOSABLE),
        "the label kept its name after the application cleared it, so "
        "ClearHwndProps did nothing",
    )
    after = _what_the_application_shows(annotated_app.window)

    assert (_AN_IMAGE, "") in after, (
        f"a cleared label should be back to Tk's own nameless ImageControl: {after}"
    )
    assert after.count((_A_PANE, "")) == _THE_CANVAS_AND_THE_CLEARED_ENTRY, (
        f"the cleared entry should be an anonymous pane again, indistinguishable "
        f"from the unknown_class_widget that was never annotated: {after}"
    )


def test_a_name_bound_to_a_tk_variable_follows_it_when_the_application_changes_it(
    annotated_app: RunningApp,
) -> None:
    # Given a status label showing a Tk variable, and saying so to a client
    at_rest = _what_the_application_shows(annotated_app.window)

    assert (_TEXT, READY) in at_rest, (
        f"the status label never took its name from the variable it displays: {at_rest}"
    )

    # When the application writes that variable, saying nothing to this package
    annotated_app.ask_for(ADVANCE_THE_STATUS)

    # Then what a client reads follows
    _eventually_shows(
        annotated_app.window,
        (_TEXT, TASK_CREATED),
        f"the status label still does not read {TASK_CREATED!r}, so the "
        "binding stopped following the variable after the first write",
    )


def test_a_value_bound_to_a_tk_variable_follows_it_when_the_application_changes_it(
    annotated_app: RunningApp,
) -> None:
    # Given the entry whose contents come from a Tk variable
    import uiautomation as auto

    entry = auto.EditControl(searchFromControl=annotated_app.window, Name=TITLE)
    at_rest = entry.GetValuePattern().Value

    assert at_rest == DRAFT, (
        f"the entry never took its value from the variable it displays: {at_rest!r}"
    )

    # When the application rewrites that variable, saying nothing to this package
    annotated_app.ask_for(REVISE_THE_DRAFT)

    # Then what a client reads out of the edit control follows
    _eventually(
        lambda: entry.GetValuePattern().Value == REVISION,
        f"the entry still reads {DRAFT!r} rather than {REVISION!r}, so the "
        "binding never followed the variable it was bound to",
    )


def test_a_label_that_declares_a_textvariable_is_named_from_it_with_no_binding_call(
    annotated_app: RunningApp,
) -> None:
    # Given a label built with a `textvariable` and never passed to `bind_text_variable`
    at_rest = _what_the_application_shows(annotated_app.window)

    assert (_TEXT, UNBOUND_STATUS) in at_rest, (
        "a label driven by a variable nobody bound is announcing nothing, so "
        f"`enable()` never read the `-textvariable` the widget declares: {at_rest}"
    )

    # When the application writes that variable, saying nothing to this package
    annotated_app.ask_for(MOVE_WHAT_NOBODY_BOUND)

    # Then a client in another process reads the new words
    _eventually_shows(
        annotated_app.window,
        (_TEXT, UNBOUND_STATUS_MOVED),
        f"the unbound label still reads {UNBOUND_STATUS!r}, so the variable it "
        "declares was read once and never followed",
    )


def test_an_entry_that_declares_a_textvariable_reads_back_its_contents_with_no_binding_call(
    annotated_app: RunningApp,
) -> None:
    # Given the entry nothing ever bound either, named by the application and no more
    import uiautomation as auto

    entry = auto.EditControl(
        searchFromControl=annotated_app.window, Name=UNBOUND_ENTRY_NAME
    )
    at_rest = entry.GetValuePattern().Value

    assert at_rest == UNBOUND_DRAFT, (
        f"the unbound entry reads {at_rest!r}: annotating alone leaves a "
        "ValuePattern that answers '', a confident wrong answer where bare Tk "
        "gave none, and the variable the widget declares is what fills it"
    )

    # When the application rewrites the variable behind it
    annotated_app.ask_for(MOVE_WHAT_NOBODY_BOUND)

    # Then what a client reads follows, and the name set by hand is untouched
    _eventually(
        lambda: entry.GetValuePattern().Value == UNBOUND_DRAFT_REVISED,
        f"the unbound entry still reads {UNBOUND_DRAFT!r} rather than "
        f"{UNBOUND_DRAFT_REVISED!r}, so its declared variable is not followed",
    )
    assert entry.Name == UNBOUND_ENTRY_NAME, (
        f"the entry is now called {entry.Name!r}: following a declared variable "
        "into the value has overwritten the name the application chose"
    )


def test_a_destroyed_widget_lets_go_of_the_variable_its_annotation_was_following(
    annotated_app: RunningApp,
) -> None:
    # Given the status label, whose name follows a `StringVar` that will outlive it
    _eventually_shows(
        annotated_app.window,
        (_TEXT, traces(_ONE_BINDING)),
        "the application never reported a trace on its status variable, so it "
        "cannot show one being released either and this spec proves nothing",
    )

    # When the application destroys that label and then writes the variable
    annotated_app.ask_for(DESTROY_THE_STATUS_LABEL)

    # Then the trace is off the variable, which nothing in Tk does when a widget dies
    _eventually_shows(
        annotated_app.window,
        (_TEXT, traces(_NOTHING_STILL_LISTENING)),
        "the destroyed label's trace is still registered on the variable it was "
        "following, so every further write fires it at a window path Tk no "
        "longer has",
    )


def test_an_explicitly_numbered_widget_reports_that_number_as_its_automation_id(
    annotated_app: RunningApp,
) -> None:
    # Given the button, which the application numbered by hand
    import uiautomation as auto

    button = auto.ButtonControl(searchFromControl=annotated_app.window, Name=NEW_TASK)

    # When a client asks for the id a suite would pin its locator to
    automation_id = button.AutomationId

    # Then it is the number the application chose, never one invented here
    assert automation_id == str(NEW_TASK_NUMBER), (
        f"the button reports AutomationId {automation_id!r}, not the "
        f"{NEW_TASK_NUMBER} the application set"
    )


def test_an_annotated_button_still_cannot_be_pressed_through_its_invoke_pattern(
    annotated_app: RunningApp,
) -> None:
    # Given the button, and a counter of how often its command has run
    import uiautomation as auto

    button = auto.ButtonControl(searchFromControl=annotated_app.window, Name=NEW_TASK)

    assert (_TEXT, presses(_NEVER)) in _what_the_application_shows(
        annotated_app.window
    ), "the fixture app is not counting presses, so this spec can prove nothing"

    # When a client does both of the things assistive technology does to press a button
    button.GetInvokePattern().Invoke()
    button.GetLegacyIAccessiblePattern().DoDefaultAction()
    time.sleep(_LONG_ENOUGH_FOR_A_REACTION_THAT_WILL_NOT_COME_SECONDS)

    # Then the command never ran: Invoke is a posted BM_CLICK, a message into the void
    assert (_TEXT, presses(_NEVER)) in _what_the_application_shows(
        annotated_app.window
    ), (
        "InvokePattern.Invoke() reached the Tk command. That would be very "
        "good news, and means the README's central caveat, and pytest-uia's "
        "click-through-the-mouse rule, both now need revisiting"
    )

    # And the counter is not merely stuck: when the application presses, it moves
    annotated_app.ask_for(PRESS_THE_BUTTON)

    _eventually_shows(
        annotated_app.window,
        (_TEXT, presses(_ONCE)),
        "the press counter never moved even for a real press, so it could not "
        "have detected one either way",
    )
