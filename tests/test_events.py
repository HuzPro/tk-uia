"""Behavioral spec for saying that a written property changed, exactly once."""

from __future__ import annotations

from tests.doubles import (
    FakeVariable,
    FakeWidget,
    RecordingNotifier,
    RecordingStore,
    VariablesByName,
)
from tk_uia.annotate import Annotator, PropId

_AN_ENTRY_HANDLE = 0x000907E2
_A_LABEL_HANDLE = 0x000907E3
_A_BUTTON_HANDLE = 0x000907E4

_A_DECLARED_VARIABLE = "PY_VAR0"


def test_a_followed_variable_write_reaches_the_notifier_with_the_new_value() -> None:
    # Given an entry whose declared variable the annotator follows
    variable = FakeVariable("first draft")
    notifier = RecordingNotifier()
    annotator = Annotator(
        RecordingStore(),
        variables=VariablesByName({_A_DECLARED_VARIABLE: variable}),
        notifier=notifier,
    )
    entry = FakeWidget(
        "Entry", _AN_ENTRY_HANDLE, textvariable=_A_DECLARED_VARIABLE
    )
    annotator.add(entry)
    heard_before = len(notifier.heard)

    # When the application writes the variable
    variable.set("second draft")

    # Then whoever listens hears the new value against the widget's handle
    assert notifier.heard[heard_before:] == [
        (_AN_ENTRY_HANDLE, PropId.VALUE, "second draft")
    ], f"the notifier heard {notifier.heard[heard_before:]}"


def test_writing_the_value_already_said_reaches_no_notifier_at_all() -> None:
    # Given a label already announced once
    notifier = RecordingNotifier()
    annotator = Annotator(RecordingStore(), notifier=notifier)
    label = FakeWidget("Label", _A_LABEL_HANDLE, text="Task list")
    annotator.add(label)
    heard_before = len(notifier.heard)

    # When the same words are said again, as every `<Map>` does
    annotator.add(label)

    # Then nobody is told anything changed, because nothing did
    assert notifier.heard[heard_before:] == [], (
        "an unchanged value was announced as a change; a screen reader would "
        "repeat the widget on every geometry shuffle"
    )


def test_a_name_the_application_sets_by_hand_is_announced_as_changed() -> None:
    # Given a button
    notifier = RecordingNotifier()
    annotator = Annotator(RecordingStore(), notifier=notifier)
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task")
    annotator.add(button)

    # When the application renames it
    annotator.set_name(button, "Create a task")

    # Then the change is heard
    assert (_A_BUTTON_HANDLE, PropId.NAME, "Create a task") in notifier.heard, (
        f"set_acc_name went unannounced; the notifier heard {notifier.heard}"
    )
