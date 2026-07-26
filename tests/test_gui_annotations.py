"""Behavioral spec for what a Windows accessibility client sees in an annotated Tk.

These are the specs the rest of the package is written for. Everything above
:mod:`tk_uia._accprop` is decided against a recording double, and that double
would happily agree with a COM call that returned `S_OK` and did nothing — the
exact failure this package exists to refuse. So the proof has to come from
outside: a real Tk window in a process of its own, read back through UI
Automation from this one.

They cost a real window on the developer's desktop and a second or so each.
Nothing here touches the mouse or the foreground, so they are safe to run while
somebody is working, and immune to the input-privilege refusals that plague
tools which click.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Callable
from typing import Any

import pytest

from tests.conftest import RunningApp
from tests.fixture_apps.annotated_app import (
    ADVANCE_THE_STATUS,
    DISPOSABLE,
    DRAFT,
    FORGET_THE_DISPOSABLE_WIDGETS,
    HEADLINE,
    NEW_TASK,
    NEW_TASK_NUMBER,
    PRESS_THE_BUTTON,
    READY,
    REVISE_THE_DRAFT,
    REVISION,
    SCRATCH,
    TASK_CREATED,
    TITLE,
    presses,
)

# What the MSAA bridge calls a window it has been told nothing about.
_A_PANE = "PaneControl"

# What it calls the two widget classes Tk registers under a real Win32 class:
# `Static` with SS_OWNERDRAW for a label, which reads as a picture.
_AN_IMAGE = "ImageControl"

_TEXT = "TextControl"
_AN_EDIT = "EditControl"

_THE_CANVAS_AND_THE_CLEARED_ENTRY = 2

# The application checks for a command a few times a second; anything near this
# means it stopped checking.
_A_REACTION_TIMEOUT_SECONDS = 5.0
_HOW_OFTEN_TO_LOOK_AGAIN_SECONDS = 0.1

# Generous for a Tk command that does one addition: an unnoticed press would
# have landed many times over.
_LONG_ENOUGH_FOR_A_REACTION_THAT_WILL_NOT_COME_SECONDS = 1.0

_NEVER = 0
_ONCE = 1

# Tk gives its toplevel one container child, under which every widget lives.
# Everything else directly under the window is chrome Windows drew: a title bar
# with its own system menu and three real ButtonControls.
_THE_TK_CONTAINER = "TkChild"

pytestmark = [
    pytest.mark.gui,
    pytest.mark.skipif(
        sys.platform != "win32",
        reason="MSAA and UI Automation are Windows APIs",
    ),
]


def _the_widgets_the_application_shows(window: Any) -> list[Any]:
    """Every control under Tk's own container, and none of Windows' chrome."""
    import uiautomation as auto

    container = auto.PaneControl(
        searchFromControl=window, searchDepth=1, ClassName=_THE_TK_CONTAINER
    )
    return [control for control, _ in auto.WalkControl(container)]


def _what_the_application_shows(window: Any) -> list[tuple[str, str]]:
    """The application's widgets as a client reads them: what, and called what."""
    return [
        (control.ControlTypeName, control.Name)
        for control in _the_widgets_the_application_shows(window)
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
    while not settled():
        if time.monotonic() >= deadline:
            pytest.fail(f"{complaint} (waited {_A_REACTION_TIMEOUT_SECONDS:.0f}s)")
        time.sleep(_HOW_OFTEN_TO_LOOK_AGAIN_SECONDS)


def test_an_annotated_button_announces_its_name_to_a_client_in_another_process(
    annotated_app: RunningApp,
) -> None:
    # Given a live Tk window belonging to somebody else's process
    import uiautomation as auto

    # When a client asks it for a push button called "New Task" — the query a
    # screen reader's user makes, and the one a test tool makes
    button = auto.ButtonControl(searchFromControl=annotated_app.window, Name=NEW_TASK)

    # Then the button answers to its own name, which bare Tk leaves empty
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

    # Then the label is text, and says so. Bare Tk registers its labels under
    # the Win32 `Static` class with SS_OWNERDRAW, which the MSAA bridge reports
    # as an `ImageControl` — a picture, with nothing to read. The spec that
    # clears these annotations watches this same widget turn back into one.
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

    # Then it is an edit control at all — bare Tk offers an anonymous
    # `PaneControl` here, and a pane is not something a client types into
    assert entry.Exists(0), (
        "the entry is not reachable as an edit control; annotating its role is "
        "what turns Tk's anonymous PaneControl into one"
    )

    # And its contents can be read, through a ValuePattern that did not exist
    # until the role was annotated: the role is not a label on the same object,
    # it decides which patterns the bridge offers for it at all
    assert entry.GetValuePattern().Value == DRAFT, (
        "the entry offers no readable value; setting role 42 (ROLE_SYSTEM_TEXT) "
        "is what makes the bridge give this control a ValuePattern"
    )


def test_a_widget_left_unannotated_still_looks_anonymous_to_a_client(
    annotated_app: RunningApp,
) -> None:
    # Given the same window, which also holds a canvas — the one widget class
    # this package has no role for, and so the one widget it never touches

    # When every widget the application itself put on screen is listed
    widgets = _the_widgets_the_application_shows(annotated_app.window)

    # Then exactly one of them is still what the bridge hands out for a window
    # it has been told nothing about: a pane with no name. Without this control
    # the specs above prove the widgets read correctly, but not that annotating
    # them is what made them read that way.
    anonymous = [
        (control.ControlTypeName, control.Name)
        for control in widgets
        if control.ControlTypeName == _A_PANE
    ]

    assert anonymous == [(_A_PANE, "")], (
        f"expected the unannotated canvas to be the only pane among the "
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

    # Then each goes back to exactly what bare Tk offers for it: the label to a
    # picture with nothing to read, the entry to an anonymous pane alongside the
    # canvas. This is the widest a stale annotation could reach — Windows reuses
    # window handles, so an annotation left on a destroyed widget's handle would
    # eventually put a dead label's name on an unrelated control.
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
        f"from the canvas that was never annotated: {after}"
    )


def test_a_name_bound_to_a_tk_variable_follows_it_when_the_application_changes_it(
    annotated_app: RunningApp,
) -> None:
    # Given a status label showing a Tk variable, and saying so to a client
    at_rest = _what_the_application_shows(annotated_app.window)

    assert (_TEXT, READY) in at_rest, (
        f"the status label never took its name from the variable it displays: {at_rest}"
    )

    # When the application writes a new value into that variable, and says
    # nothing to this package about it
    annotated_app.ask_for(ADVANCE_THE_STATUS)

    # Then what a client reads follows. A widget with a `textvariable` has no
    # `-text` to be named from, so the one widget whose whole job is to say
    # what just happened is the one that would otherwise stay silent forever.
    _eventually_shows(
        annotated_app.window,
        (_TEXT, TASK_CREATED),
        f"the status label still does not read {TASK_CREATED!r}, so the "
        "binding stopped following the variable after the first write",
    )


def test_a_value_bound_to_a_tk_variable_follows_it_when_the_application_changes_it(
    annotated_app: RunningApp,
) -> None:
    # Given the entry whose contents come from a Tk variable, reading back to a
    # client as the words the application started it with
    import uiautomation as auto

    entry = auto.EditControl(searchFromControl=annotated_app.window, Name=TITLE)
    at_rest = entry.GetValuePattern().Value

    assert at_rest == DRAFT, (
        f"the entry never took its value from the variable it displays: {at_rest!r}"
    )

    # When the application rewrites that variable, and says nothing to this
    # package about it
    annotated_app.ask_for(REVISE_THE_DRAFT)

    # Then what a client reads out of the edit control follows. A value is the
    # property a screen reader and a test tool re-read most, and a stale one is
    # indistinguishable from a true one: the box on screen shows the new words
    # while the tree goes on answering with the old ones.
    _eventually(
        lambda: entry.GetValuePattern().Value == REVISION,
        f"the entry still reads {DRAFT!r} rather than {REVISION!r}, so the "
        "binding never followed the variable it was bound to",
    )


def test_an_explicitly_numbered_widget_reports_that_number_as_its_automation_id(
    annotated_app: RunningApp,
) -> None:
    # Given the button, which the application numbered by hand
    import uiautomation as auto

    button = auto.ButtonControl(searchFromControl=annotated_app.window, Name=NEW_TASK)

    # When a client asks for the id a suite would pin its locator to
    automation_id = button.AutomationId

    # Then it is the number the application chose. Explicit only, and never
    # invented: the id lives in `GWLP_ID`, which Win32 puts in `WM_COMMAND` and
    # `WM_DRAWITEM.idCtl`, and every Tk button is owner-drawn.
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

    # When a client does both of the things assistive technology and test tools
    # do to press a button, and each returns without complaint
    button.GetInvokePattern().Invoke()
    button.GetLegacyIAccessiblePattern().DoDefaultAction()
    time.sleep(_LONG_ENOUGH_FOR_A_REACTION_THAT_WILL_NOT_COME_SECONDS)

    # Then the button's command never ran. Tk paints its buttons owner-drawn,
    # and the generic MSAA proxy answering for them synthesises Invoke from a
    # posted BM_CLICK, which for Tk is a message into the void: no exception,
    # no press. Annotating makes a widget findable and readable, not
    # activatable, and this is the spec that keeps the README honest about it.
    assert (_TEXT, presses(_NEVER)) in _what_the_application_shows(
        annotated_app.window
    ), (
        "InvokePattern.Invoke() reached the Tk command — which would be very "
        "good news, and means the README's central caveat, and pytest-uia's "
        "click-through-the-mouse rule, both now need revisiting"
    )

    # And the counter is not merely stuck: when the application presses its own
    # button, it moves. Without this the spec above passes against a fixture
    # that could never have counted anything.
    annotated_app.ask_for(PRESS_THE_BUTTON)

    _eventually_shows(
        annotated_app.window,
        (_TEXT, presses(_ONCE)),
        "the press counter never moved even for a real press, so it could not "
        "have detected one either way",
    )
