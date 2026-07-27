"""Behavioral spec for putting the annotator in the path of a running Tk.

Two halves, and both are needed: a binding for everything Tk maps from now on,
and a sweep of everything already on screen. `<Map>` fires once per widget, on
the way up, so a window already showing when `enable()` is called will never
fire it again and without the sweep stays anonymous forever.
"""

from __future__ import annotations

from tests.doubles import (
    FakeInterpreter,
    FakeRoot,
    FakeVariable,
    FakeWidget,
    RecordingStore,
    VariablesByName,
)
from tk_uia.annotate import PropId, install
from tk_uia.tkversion import Strategy

_A_BUTTON_HANDLE = 0x000407A2
_A_LABEL_HANDLE = 0x000407A5

# What Tcl calls the first `StringVar` an application makes.
_A_DECLARED_VARIABLE = "PY_VAR0"

_NOTHING_STILL_LISTENING = 0


def _a_tk_that_needs_annotating() -> FakeInterpreter:
    return FakeInterpreter("8.6.15", "win32", native=False)


def test_enabling_accessibility_on_tk_eight_six_installs_the_class_bindings_and_reports_it() -> (
    None
):
    # Given a window that is already on screen when accessibility is switched on
    store = RecordingStore()
    already_showing = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task")
    root = FakeRoot(_a_tk_that_needs_annotating(), children=[already_showing])

    # When it is switched on
    installation = install(root, store)

    # Then the caller is told which of the three things happened, which is the
    # only way a suite can tell "annotated" from "the gate mis-fired and this
    # did nothing at all"
    assert installation.strategy is Strategy.ANNOTATED, (
        f"reported {installation.strategy} for a Tk that has no accessibility"
    )

    # And Tk will hand over every widget it maps or destroys from here on,
    # without displacing the bindings Tk and the application already have
    assert root.class_bindings == [
        ("<Map>", "+"),
        ("<Destroy>", "+"),
        # A notebook's tabs are not widgets, so they never map and `<Map>` says
        # nothing about one being added or removed. This is the event that does.
        ("<<NotebookTabChanged>>", "+"),
    ], (
        f"bound {root.class_bindings}; anything but `add='+'` silently replaces "
        "whatever else was listening for the same event"
    )

    # And the widget that was already up has been annotated, because its own
    # `<Map>` came and went before any of this was listening
    assert store.properties(_A_BUTTON_HANDLE)[PropId.NAME] == "New Task", (
        "every widget on screen at the moment enable() is called stays anonymous"
    )


def test_a_widget_mapped_after_enabling_is_annotated_as_soon_as_tk_says_so() -> None:
    # Given accessibility already switched on for an empty window
    store = RecordingStore()
    root = FakeRoot(_a_tk_that_needs_annotating())
    install(root, store)
    label = FakeWidget("Label", _A_LABEL_HANDLE, text="ready")

    # When Tk maps a new widget
    root.announce("<Map>", label)

    # Then it announces itself without the application having to say anything
    assert store.properties(_A_LABEL_HANDLE)[PropId.NAME] == "ready", (
        "a widget added after startup never became visible to a client"
    )


def test_a_widget_destroyed_after_enabling_gives_its_handle_back_clean() -> None:
    # Given a widget that has been mapped and annotated
    store = RecordingStore()
    root = FakeRoot(_a_tk_that_needs_annotating())
    install(root, store)
    label = FakeWidget("Label", _A_LABEL_HANDLE, text="ready")
    root.announce("<Map>", label)

    # When Tk destroys it, passing only the path, which is all `<Destroy>`
    # carries once the widget object has already gone
    root.announce("<Destroy>", str(label))

    # Then the handle is released, so whatever Windows issues it to next is not
    # wearing a dead label's name
    assert store.cleared == [_A_LABEL_HANDLE], (
        f"the destroyed widget's handle was left annotated: cleared {store.cleared}"
    )


def test_a_widget_destroyed_after_enabling_lets_go_of_the_variable_it_was_following() -> (
    None
):
    # Given a status label whose name follows a Tk variable
    store = RecordingStore()
    root = FakeRoot(_a_tk_that_needs_annotating())
    installation = install(root, store)
    label = FakeWidget("Label", _A_LABEL_HANDLE)
    status = FakeVariable("ready")
    root.announce("<Map>", label)
    installation.annotator.bind_text_variable(label, status)

    # When Tk destroys the label and the variable goes on being written, as a
    # variable does: it belongs to the application, not to the widget, and
    # routinely outlives every widget that ever displayed it
    label.destroy()
    root.announce("<Destroy>", str(label))
    status.set("task created")

    # Then the trace is off the variable rather than merely inert. A guard that
    # declined to announce would leave the registration in place for the life of
    # the process, firing on every write.
    assert status.traces_left() == _NOTHING_STILL_LISTENING, (
        f"{status.traces_left()} trace(s) outlived the widget they were "
        "registered for, and will go on firing at a dead window path forever"
    )


def test_a_widget_already_showing_follows_the_variable_it_declares_from_the_start() -> (
    None
):
    # Given a status label on screen before accessibility is switched on, driven
    # by a variable the application never mentions to this package
    store = RecordingStore()
    status = FakeVariable("ready")
    label = FakeWidget("Label", _A_LABEL_HANDLE, textvariable=_A_DECLARED_VARIABLE)
    root = FakeRoot(_a_tk_that_needs_annotating(), children=[label])

    # When it is switched on, and the application gets on with its work
    install(root, store, variables=VariablesByName({_A_DECLARED_VARIABLE: status}))
    status.set("task created")

    # Then the label announces what the variable says now. The widget told Tk
    # which variable drives it when it was built, so the wiring from `enable()`
    # down to the trace has to be real for an application to say nothing.
    assert store.properties(_A_LABEL_HANDLE)[PropId.NAME] == "task created", (
        "the variable the widget declares is not being followed at all: "
        f"{store.properties(_A_LABEL_HANDLE)}"
    )


def test_a_tk_that_answers_for_itself_is_neither_bound_to_nor_written_to() -> None:
    # Given a Tk 9.1 with its own accessibility, and a widget on screen
    store = RecordingStore()
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task")
    root = FakeRoot(FakeInterpreter("9.1.0", "win32", native=True), children=[button])

    # When accessibility is switched on
    installation = install(root, store)

    # Then nothing is bound and nothing is written. Standing aside has to mean
    # standing aside: a binding left in place would keep annotating over an
    # implementation that is already answering correctly.
    assert installation.strategy is Strategy.NATIVE
    assert root.class_bindings == [], f"bound anyway: {root.class_bindings}"
    assert store.writes == [], f"annotated over a native Tk: {store.writes}"


def test_the_whole_surface_can_still_be_called_where_there_is_nothing_to_annotate() -> (
    None
):
    # Given an application on X11, which calls the same code as on Windows
    store = RecordingStore()
    root = FakeRoot(FakeInterpreter("8.6.15", "x11", native=False))
    installation = install(root, store)

    # When it goes on to say the things it would say on Windows
    label = FakeWidget("Label", _A_LABEL_HANDLE, text="ready")
    installation.annotator.add(label)
    installation.annotator.set_name(label, "ready")
    installation.annotator.set_value(label, "ready")
    installation.annotator.set_automation_id(label, 4207)
    installation.annotator.forget(label)

    # Then every one of them is a no-op rather than an error. An application
    # guarding each call in a platform check will get one of them wrong, and the
    # failure only ever shows up on the other platform.
    assert installation.strategy is Strategy.UNSUPPORTED
    assert store.writes == [], (
        f"reached for MSAA on a machine without it: {store.writes}"
    )
