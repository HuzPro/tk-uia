"""Behavioral spec for what a widget tells Windows about itself once annotated.

Runs against a recording store and fake widgets: no display, no Tk build, no
Windows. What is left underneath is three vtable slots into `oleacc`.
"""

from __future__ import annotations

import pytest

from tests.doubles import FakeVariable, FakeWidget, RecordingStore, VariablesByName
from tests.threads import the_failure_raised_on_another_thread
from tk_uia.annotate import AnnotationRefused, Annotator, PropId
from tk_uia.roles import Role

_A_BUTTON_HANDLE = 0x000407A2
_AN_ENTRY_HANDLE = 0x000407A3
_A_SCALE_HANDLE = 0x000A0C0E
_A_CANVAS_HANDLE = 0x000407A4
_A_ROOT_HANDLE = 0x000407A0
_A_DIALOG_HANDLE = 0x000407A1
_A_LABEL_HANDLE = 0x000407A5
_A_TEXT_HANDLE = 0x000407A6
_A_COMBOBOX_HANDLE = 0x000407A7
_A_RECYCLED_HANDLE = 0x000508B1

# STATE_SYSTEM_UNAVAILABLE, from oleacc.h: the widget is there but disabled.
_MSAA_STATE_UNAVAILABLE = 0x1

_NO_CONTROL_ID_AT_ALL = 0
_AN_ID_THE_APPLICATION_CHOSE = 4207
_AN_ID_WIN32_IS_USING = 1101
# `GWLP_ID` underneath holds a number and nothing else.
_AN_ID_SPELT_AS_A_NAME = "save-button"

# ROLE_SYSTEM_PUSHBUTTON, which is what `describe()` prints beside the member.
_THE_NUMBER_A_PUSH_BUTTON_IS = 43
_A_NUMBER_NO_ROLE_CARRIES = 7

_NOT_A_WIDGET_AT_ALL = "oops"

# What Tcl calls the first `StringVar` an application makes.
_THE_VARIABLE_THE_WIDGET_DECLARES = "PY_VAR0"
_A_SECOND_VARIABLE = "PY_VAR1"
_DECLARED_BY_NOBODY = ""

_NOTHING_STILL_LISTENING = 0
_ONE_REGISTRATION = 1


def test_annotating_a_widget_writes_its_role_and_the_name_from_its_text_into_the_store() -> (
    None
):
    # Given a button carrying the words it shows, and somewhere to write
    store = RecordingStore()
    annotator = Annotator(store)
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task")

    # When the annotator is told about the widget
    annotator.add(button)

    # Then the store holds both halves against that widget's own handle
    assert store.properties(_A_BUTTON_HANDLE) == {
        PropId.ROLE: Role.PUSH_BUTTON.value,
        PropId.NAME: "New Task",
    }, "an annotated button must announce both its kind and its name"


def test_a_widget_with_no_text_of_its_own_is_given_a_role_but_never_an_invented_name() -> (
    None
):
    # Given an entry, which has no `-text` option to read a name out of
    store = RecordingStore()
    annotator = Annotator(store)
    entry = FakeWidget("Entry", _AN_ENTRY_HANDLE)

    # When the annotator is told about it
    annotator.add(entry)

    # Then it is announced as editable text and left unnamed
    assert store.properties(_AN_ENTRY_HANDLE) == {PropId.ROLE: Role.TEXT.value}, (
        "an unnamed widget must stay unnamed; an honest miss is findable, a "
        "name the application never chose is not"
    )
    assert str(entry) not in [value for _, _, value in store.writes], (
        f"the widget path {entry} reached the store as if it were a name"
    )


def test_a_name_the_application_chose_survives_the_widget_being_mapped_again() -> None:
    # Given a button deliberately named something other than its caption
    store = RecordingStore()
    annotator = Annotator(store)
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="OK")
    annotator.add(button)
    annotator.set_name(button, "Confirm order")

    # When Tk maps it again and the automatic annotation runs over it
    annotator.add(button)

    # Then the application's name is still there
    assert store.properties(_A_BUTTON_HANDLE)[PropId.NAME] == "Confirm order", (
        "the caption overwrote the name the application chose: "
        f"{store.properties(_A_BUTTON_HANDLE)}"
    )


def test_a_role_the_application_chose_survives_the_widget_being_mapped_again() -> None:
    # Given a widget the application has given a role of its own
    store = RecordingStore()
    annotator = Annotator(store)
    label = FakeWidget("Label", _A_LABEL_HANDLE, text="12 unread")
    annotator.add(label)
    annotator.set_role(label, Role.PROGRESS_BAR)

    # When Tk maps it again
    annotator.add(label)

    # Then the chosen role stands
    assert store.properties(_A_LABEL_HANDLE)[PropId.ROLE] == Role.PROGRESS_BAR.value, (
        f"the inferred role came back: {store.properties(_A_LABEL_HANDLE)}"
    )


def test_naming_a_root_with_an_application_chosen_class_is_still_refused() -> None:
    # Given a root whose class the application named, as tk.Tk(className=...) does
    from tests.doubles import FakeInterpreter, FakeRoot

    store = RecordingStore()
    annotator = Annotator(store)
    root = FakeRoot(FakeInterpreter("8.6.15", "win32", native=False), tk_class="Idle")

    # When something tries to name it anyway
    # Then the window refusal fires just as it does for a plain root
    with pytest.raises(AnnotationRefused):
        annotator.set_name(root, "the app")
    assert store.writes == [], f"the pane behind the window was written: {store.writes}"


def test_a_scale_is_named_from_the_label_option_it_keeps_its_words_in() -> None:
    # Given a classic Scale, whose options carry `-label` and no `-text` at all
    store = RecordingStore()
    annotator = Annotator(store)
    scale = FakeWidget("Scale", _A_SCALE_HANDLE, label="Volume")

    # When the annotator meets it
    annotator.add(scale)

    # Then it is named from there
    assert store.properties(_A_SCALE_HANDLE)[PropId.NAME] == "Volume", (
        f"a labelled Scale was left unnamed: {store.properties(_A_SCALE_HANDLE)}"
    )


def test_a_widget_class_the_role_table_has_never_heard_of_is_left_exactly_as_tk_left_it() -> (
    None
):
    # Given a widget of a class nobody has decided a role for
    store = RecordingStore()
    annotator = Annotator(store)
    homemade = FakeWidget("SparklineChart", _A_CANVAS_HANDLE, text="not really a label")

    # When the annotator meets it
    annotator.add(homemade)

    # Then nothing is written
    assert store.writes == [], (
        f"a class with no role must be passed over, not guessed at: {store.writes}"
    )


def test_a_toplevel_is_never_annotated_even_when_the_role_table_is_told_to() -> None:
    # Given a caller who has gone out of their way to put windows in the table
    store = RecordingStore()
    annotator = Annotator(store, {"Tk": Role.GROUPING, "Toplevel": Role.GROUPING})

    # When both kinds of window are offered to the annotator
    annotator.add(FakeWidget("Tk", _A_ROOT_HANDLE))
    annotator.add(FakeWidget("Toplevel", _A_DIALOG_HANDLE))

    # Then neither is touched: `wm title` already names a window correctly
    assert store.writes == [], (
        f"a window's own title must be left to speak for it: {store.writes}"
    )


def test_annotating_a_window_by_hand_is_refused_rather_than_naming_the_pane_behind_it() -> (
    None
):
    # Given an application holding its own root window, and a dialog
    store = RecordingStore()
    annotator = Annotator(store)
    root = FakeWidget("Tk", _A_ROOT_HANDLE)
    dialog = FakeWidget("Toplevel", _A_DIALOG_HANDLE)

    # When it tries to say what the window is called
    with pytest.raises(AnnotationRefused) as refusal:
        annotator.set_name(root, "Tasks")

    # Then it is told: `winfo_id()` on a Tk root returns the container child
    assert store.writes == [], f"the window's pane was annotated anyway: {store.writes}"
    assert "wm title" in str(refusal.value), (
        f"the refusal must point at what already names a window: {refusal.value}"
    )

    with pytest.raises(AnnotationRefused):
        annotator.set_value(dialog, "anything")
    with pytest.raises(AnnotationRefused):
        annotator.set_role(dialog, Role.GROUPING)


def test_an_explicit_name_or_role_overrides_the_one_derived_from_the_widget() -> None:
    # Given a button the annotator has already made up its own mind about
    store = RecordingStore()
    annotator = Annotator(store)
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task")
    annotator.add(button)

    # When the application says what it actually wants announced
    annotator.set_name(button, "Create a task")
    annotator.set_role(button, Role.CHECK_BUTTON)

    # Then the application wins on both counts
    assert store.properties(_A_BUTTON_HANDLE) == {
        PropId.NAME: "Create a task",
        PropId.ROLE: Role.CHECK_BUTTON.value,
    }, "an explicit name and role must replace the derived ones, not sit beside them"


def test_a_caller_supplied_role_table_adds_to_the_built_in_one_rather_than_replacing_it() -> (
    None
):
    # Given an application that has decided its canvas should read as text
    store = RecordingStore()
    annotator = Annotator(store, {"Canvas": Role.STATIC_TEXT})

    # When both that widget and an ordinary one are annotated
    annotator.add(FakeWidget("Canvas", _A_CANVAS_HANDLE))
    annotator.add(FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task"))

    # Then the addition is honoured and everything else still works
    assert store.properties(_A_CANVAS_HANDLE)[PropId.ROLE] == Role.STATIC_TEXT.value
    assert store.properties(_A_BUTTON_HANDLE)[PropId.ROLE] == Role.PUSH_BUTTON.value, (
        "adding one class to the table dropped every class already in it"
    )


def test_annotating_the_same_widget_twice_writes_nothing_the_second_time() -> None:
    # Given a widget that has already been annotated once
    store = RecordingStore()
    annotator = Annotator(store)
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task")
    annotator.add(button)
    after_the_first_time = list(store.writes)

    # When the same widget is offered again, as `<Map>` does on every unhide
    annotator.add(button)

    # Then not one call crosses into COM
    assert store.writes == after_the_first_time, (
        f"re-announcing an unchanged widget cost {len(store.writes) - len(after_the_first_time)} "
        "extra cross-process writes"
    )


def test_a_widget_whose_words_have_changed_is_announced_again_with_the_new_ones() -> (
    None
):
    # Given a status label that has already announced itself once
    store = RecordingStore()
    annotator = Annotator(store)
    label = FakeWidget("Label", _A_LABEL_HANDLE, text="ready")
    annotator.add(label)

    # When the application changes what it says
    annotator.set_name(label, "task created")

    # Then the change reaches the store
    assert store.properties(_A_LABEL_HANDLE)[PropId.NAME] == "task created", (
        "the ledger swallowed a real change"
    )


def test_a_destroyed_widget_has_its_annotations_cleared_before_windows_can_reuse_its_handle() -> (
    None
):
    # Given an annotated button Tk is tearing down, whose `winfo_id` already raises
    store = RecordingStore()
    annotator = Annotator(store)
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task")
    annotator.add(button)
    button.destroy()

    # When the annotator is told the widget is going
    annotator.forget(button)

    # Then the handle it had while alive is cleared: Windows reissues handles
    assert store.cleared == [_A_BUTTON_HANDLE], (
        f"expected the handle cached while the widget lived, cleared {store.cleared}"
    )
    assert store.properties(_A_BUTTON_HANDLE) == {}, (
        "a dead widget's name outlived it and is now free to mislabel another"
    )


def test_a_widget_rebuilt_at_the_same_path_lets_go_of_the_handle_it_used_to_have() -> (
    None
):
    # Given an annotated button Tk has since rebuilt at the same path
    store = RecordingStore()
    annotator = Annotator(store)
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task")
    annotator.add(button)
    button.take_a_new_handle(_A_RECYCLED_HANDLE)

    # When it is annotated again on its new handle
    annotator.add(button)

    # Then the handle it left behind is released and the new one carries the name
    assert store.cleared == [_A_BUTTON_HANDLE], (
        f"the abandoned handle was left annotated; cleared {store.cleared}"
    )
    assert store.properties(_A_RECYCLED_HANDLE)[PropId.NAME] == "New Task"


def test_setting_a_widgets_value_writes_it_where_a_client_reads_an_edit_controls_content() -> (
    None
):
    # Given an annotated entry, which the role alone has given a ValuePattern
    store = RecordingStore()
    annotator = Annotator(store)
    entry = FakeWidget("Entry", _AN_ENTRY_HANDLE)
    annotator.add(entry)

    # When the application says what is currently in it
    annotator.set_value(entry, "typed words")

    # Then the value carries the contents and the name is left alone
    assert store.properties(_AN_ENTRY_HANDLE) == {
        PropId.ROLE: Role.TEXT.value,
        PropId.VALUE: "typed words",
    }, "the contents of a text box belong in its value, not in its name"


def test_every_property_a_client_can_ask_for_lands_in_its_own_slot() -> None:
    # Given an annotated button
    store = RecordingStore()
    annotator = Annotator(store)
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task")
    annotator.add(button)

    # When the application fills in everything else a client may ask it
    annotator.set_description(button, "creates a task and clears the form")
    annotator.set_action(button, "Press")
    annotator.set_help(button, "keyboard shortcut is Ctrl+N")
    annotator.set_state(button, _MSAA_STATE_UNAVAILABLE)

    # Then all six sit side by side
    assert store.properties(_A_BUTTON_HANDLE) == {
        PropId.ROLE: Role.PUSH_BUTTON.value,
        PropId.NAME: "New Task",
        PropId.DESCRIPTION: "creates a task and clears the form",
        PropId.DEFAULT_ACTION: "Press",
        PropId.HELP: "keyboard shortcut is Ctrl+N",
        PropId.STATE: _MSAA_STATE_UNAVAILABLE,
    }, "one property overwrote another on its way to the store"


def test_the_only_automation_id_a_widget_gets_is_the_one_an_application_asked_for() -> (
    None
):
    # Given two widgets, one of which the application has an id in mind for
    store = RecordingStore()
    annotator = Annotator(store)
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task")
    never_asked_about = FakeWidget("Entry", _AN_ENTRY_HANDLE)

    # When both are annotated and only one is given an id
    annotator.add(button)
    annotator.add(never_asked_about)
    annotator.set_automation_id(button, _AN_ID_THE_APPLICATION_CHOSE)

    # Then that one carries it and the other is untouched
    assert store.control_id(_A_BUTTON_HANDLE) == _AN_ID_THE_APPLICATION_CHOSE
    assert store.control_id(_AN_ENTRY_HANDLE) == _NO_CONTROL_ID_AT_ALL, (
        "an id was handed out that nobody asked for, into the field Win32 uses "
        "to route messages to an owner-drawn control"
    )


def test_an_automation_id_is_refused_rather_than_written_over_one_windows_is_using() -> (
    None
):
    # Given a widget whose control id Win32 has already filled in
    store = RecordingStore()
    store.set_control_id(_A_BUTTON_HANDLE, _AN_ID_WIN32_IS_USING)
    annotator = Annotator(store)
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task")

    # When the application asks for a different one
    with pytest.raises(AnnotationRefused) as refusal:
        annotator.set_automation_id(button, _AN_ID_THE_APPLICATION_CHOSE)

    # Then it is told, rather than the id being quietly replaced
    assert store.control_id(_A_BUTTON_HANDLE) == _AN_ID_WIN32_IS_USING, (
        "the control id Windows was using has been overwritten"
    )
    assert str(_AN_ID_WIN32_IS_USING) in str(refusal.value), (
        f"the refusal must name the id already in place: {refusal.value}"
    )


def test_a_role_given_as_the_number_behind_it_is_refused_and_told_which_member_that_is() -> (
    None
):
    # Given an application reaching for the number behind the member
    store = RecordingStore()
    annotator = Annotator(store)
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task")

    # When it is passed where a Role belongs
    with pytest.raises(TypeError) as complaint:
        annotator.set_role(button, _THE_NUMBER_A_PUSH_BUTTON_IS)

    # Then it is a TypeError, naming the member that was meant
    assert "Role.PUSH_BUTTON" in str(complaint.value), (
        f"the reader has to be told what to write instead: {complaint.value}"
    )
    assert store.writes == [], f"a role arrived as a bare number: {store.writes}"


def test_a_role_given_as_a_number_no_role_carries_is_told_the_contract_and_nothing_more() -> (
    None
):
    # Given a number that names no role at all, which is what a typo looks like
    store = RecordingStore()
    annotator = Annotator(store)
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task")

    # When it is passed where a Role belongs
    with pytest.raises(TypeError) as complaint:
        annotator.set_role(button, _A_NUMBER_NO_ROLE_CARRIES)

    # Then the contract is stated and no member is invented for it
    assert "Role" in str(complaint.value) and "int" in str(complaint.value), (
        f"the complaint has to say what the parameter takes: {complaint.value}"
    )
    assert store.writes == [], f"a role arrived as a bare number: {store.writes}"


def test_an_automation_id_given_as_text_is_refused_before_windows_is_asked_anything() -> (
    None
):
    # Given the natural first attempt, since a client reads an AutomationId as text
    store = RecordingStore()
    annotator = Annotator(store)
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task")

    # When a name is passed where the id belongs
    with pytest.raises(TypeError) as complaint:
        annotator.set_automation_id(button, _AN_ID_SPELT_AS_A_NAME)

    # Then the call is stopped at the door: underneath the id is `GWLP_ID`
    assert "GWLP_ID" in str(complaint.value), (
        f"the complaint has to say why an id here is a number: {complaint.value}"
    )
    assert store.control_id(_A_BUTTON_HANDLE) == _NO_CONTROL_ID_AT_ALL, (
        "a control id was written from a value Win32 cannot carry"
    )


def test_a_call_handed_something_that_is_not_a_widget_says_which_parameter_it_was() -> (
    None
):
    # Given an application that has passed a string where the widget belongs
    store = RecordingStore()
    annotator = Annotator(store)
    caption = FakeWidget("Label", _A_LABEL_HANDLE, text="Host:")

    # When two of the calls that take a widget are handed a string
    with pytest.raises(TypeError) as named:
        annotator.set_name(_NOT_A_WIDGET_AT_ALL, "Host")
    with pytest.raises(TypeError) as associated:
        annotator.label_for(caption, _NOT_A_WIDGET_AT_ALL)

    # Then each says which parameter it was and what arrived
    assert "widget" in str(named.value) and "str" in str(named.value), (
        f"the complaint names neither the parameter nor the type: {named.value}"
    )
    assert "widget" in str(associated.value), (
        f"the complaint does not say which of the two arguments was wrong: "
        f"{associated.value}"
    )
    assert store.writes == [], f"a string reached the store as a widget: {store.writes}"


def test_annotating_from_a_thread_other_than_the_one_that_owns_the_widgets_is_refused() -> (
    None
):
    # Given an annotator built on the thread that owns the widgets
    store = RecordingStore()
    annotator = Annotator(store)
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task")

    # When a background worker tries to annotate
    refusal = the_failure_raised_on_another_thread(lambda: annotator.add(button))

    # Then it is stopped before a single Tk call: Tcl corrupts rather than raises
    assert isinstance(refusal, AnnotationRefused), (
        f"a foreign thread got through to Tk with {refusal!r}; the guard must "
        "refuse before winfo_class(), keys() or cget() is called"
    )
    assert store.writes == [], f"a foreign thread reached the store: {store.writes}"
    assert "thread" in str(refusal), (
        f"the reader has to be told which rule they broke: {refusal}"
    )


def test_a_widget_bound_to_a_variable_re_announces_itself_whenever_it_changes() -> None:
    # Given a status label whose words come from a variable rather than `-text`
    store = RecordingStore()
    annotator = Annotator(store)
    label = FakeWidget("Label", _A_LABEL_HANDLE)
    status = FakeVariable("ready")
    annotator.add(label)
    annotator.bind_text_variable(label, status)
    announced_when_bound = store.properties(_A_LABEL_HANDLE).get(PropId.NAME)

    # When the application puts something new in the variable
    status.set("task created")

    # Then that is what a client now reads
    assert store.properties(_A_LABEL_HANDLE)[PropId.NAME] == "task created", (
        "the annotation is stuck on whatever the label said first"
    )
    assert announced_when_bound == "ready", (
        f"binding must announce what the variable already holds, said {announced_when_bound}"
    )


def test_a_value_bound_to_a_variable_is_written_as_soon_as_it_is_bound() -> None:
    # Given an annotated entry whose contents live in a variable
    store = RecordingStore()
    annotator = Annotator(store)
    entry = FakeWidget("Entry", _AN_ENTRY_HANDLE)
    draft = FakeVariable("Write the report")
    annotator.add(entry)

    # When its value is bound to that variable
    annotator.bind_value_variable(entry, draft)

    # Then it is readable straight away: a trace only fires on the *next* write
    assert store.properties(_AN_ENTRY_HANDLE) == {
        PropId.ROLE: Role.TEXT.value,
        PropId.VALUE: "Write the report",
    }, "binding must announce what the variable already holds, into the value"


def test_a_bound_value_follows_the_variable_when_the_application_changes_it() -> None:
    # Given an entry whose value is already bound to the variable behind it
    store = RecordingStore()
    annotator = Annotator(store)
    entry = FakeWidget("Entry", _AN_ENTRY_HANDLE)
    draft = FakeVariable("Write the report")
    annotator.add(entry)
    annotator.bind_value_variable(entry, draft)

    # When the application puts something else in the variable
    draft.set("Write the quarterly report")

    # Then that is what a client now reads out of the edit control
    assert store.properties(_AN_ENTRY_HANDLE)[PropId.VALUE] == (
        "Write the quarterly report"
    ), "the value is stuck on whatever the entry held when it was bound"


def test_a_forgotten_widget_stops_being_re_announced_when_its_variable_changes() -> (
    None
):
    # Given a status label whose annotation follows a variable, since taken back
    store = RecordingStore()
    annotator = Annotator(store)
    label = FakeWidget("Label", _A_LABEL_HANDLE)
    status = FakeVariable("ready")
    annotator.add(label)
    annotator.bind_text_variable(label, status)
    annotator.forget(label)

    # When the variable moves on, as a running application's status variable does
    status.set("task created")

    # Then the widget stays forgotten
    assert store.properties(_A_LABEL_HANDLE) == {}, (
        f"forget() left the variable trace in place, so the next write "
        f"re-announced the widget: {store.properties(_A_LABEL_HANDLE)}"
    )


def test_a_destroyed_widgets_variable_can_still_be_written_without_raising() -> None:
    # Given a label bound to a variable and destroyed without the annotator knowing
    store = RecordingStore()
    annotator = Annotator(store)
    label = FakeWidget("Label", _A_LABEL_HANDLE)
    status = FakeVariable("ready")
    annotator.add(label)
    annotator.bind_text_variable(label, status)
    label.destroy()
    while_it_was_alive = list(store.writes)

    # When the variable goes on changing
    status.set("task created")
    status.set("second task created")

    # Then nothing raises: a trace at a dead widget path raises inside Tcl's callback
    assert store.writes == while_it_was_alive, (
        "a widget that no longer exists was annotated anyway: "
        f"{store.writes[len(while_it_was_alive) :]}"
    )


def test_a_label_that_declares_a_textvariable_is_named_from_it_and_kept_in_step() -> (
    None
):
    # Given a label handed a variable at construction and nothing said about it
    store = RecordingStore()
    status = FakeVariable("ready")
    annotator = Annotator(
        store, variables=VariablesByName({_THE_VARIABLE_THE_WIDGET_DECLARES: status})
    )
    label = FakeWidget(
        "Label", _A_LABEL_HANDLE, textvariable=_THE_VARIABLE_THE_WIDGET_DECLARES
    )

    # When the annotator meets it, and the application writes the variable after
    annotator.add(label)
    named_when_annotated = store.properties(_A_LABEL_HANDLE).get(PropId.NAME)
    status.set("task created")

    # Then it announced itself straight away and follows the variable after
    assert named_when_annotated == "ready", (
        f"the label was annotated {named_when_annotated!r} rather than with what "
        "the variable it declares already held"
    )
    assert store.properties(_A_LABEL_HANDLE)[PropId.NAME] == "task created", (
        "the name stopped at whatever the variable held when the widget was "
        "annotated, so a client reads a status line that stopped being true"
    )


def test_an_entry_that_declares_a_textvariable_has_that_read_as_its_value() -> None:
    # Given an entry driven by a variable, whose ValuePattern reads '' until written
    store = RecordingStore()
    draft = FakeVariable("Write the report")
    annotator = Annotator(
        store, variables=VariablesByName({_THE_VARIABLE_THE_WIDGET_DECLARES: draft})
    )
    entry = FakeWidget(
        "Entry", _AN_ENTRY_HANDLE, textvariable=_THE_VARIABLE_THE_WIDGET_DECLARES
    )

    # When the annotator meets it
    annotator.add(entry)

    # Then what the entry holds is its *value*, and it is left unnamed
    assert store.properties(_AN_ENTRY_HANDLE) == {
        PropId.ROLE: Role.TEXT.value,
        PropId.VALUE: "Write the report",
    }, "an edit control's variable belongs in its value, not in its name"


def test_the_widgets_role_decides_whether_its_variable_is_its_value_or_its_name() -> (
    None
):
    # Given two of the sixteen classes that carry `-textvariable`
    store = RecordingStore()
    chosen = FakeVariable("Weekly")
    labelled = FakeVariable("Filter")
    annotator = Annotator(
        store,
        variables=VariablesByName(
            {_THE_VARIABLE_THE_WIDGET_DECLARES: chosen, _A_SECOND_VARIABLE: labelled}
        ),
    )
    combobox = FakeWidget(
        "TCombobox", _AN_ENTRY_HANDLE, textvariable=_THE_VARIABLE_THE_WIDGET_DECLARES
    )
    menubutton = FakeWidget(
        "Menubutton", _A_BUTTON_HANDLE, textvariable=_A_SECOND_VARIABLE
    )

    # When both are annotated
    annotator.add(combobox)
    annotator.add(menubutton)

    # Then the combobox's variable is its contents and the menubutton's is its name
    assert store.properties(_AN_ENTRY_HANDLE).get(PropId.VALUE) == "Weekly", (
        f"a combobox's selection is its value: {store.properties(_AN_ENTRY_HANDLE)}"
    )
    assert store.properties(_A_BUTTON_HANDLE).get(PropId.NAME) == "Filter", (
        "a menubutton shows its variable instead of a caption, so that is its "
        f"whole name: {store.properties(_A_BUTTON_HANDLE)}"
    )


def test_a_widget_that_declares_no_variable_is_left_exactly_as_it_was() -> None:
    # Given two widgets with no variable to follow: no option at all, and an empty one
    store = RecordingStore()
    annotator = Annotator(
        store,
        variables=VariablesByName(
            {_THE_VARIABLE_THE_WIDGET_DECLARES: FakeVariable("")}
        ),
    )
    text_box = FakeWidget("Text", _AN_ENTRY_HANDLE)
    plain_label = FakeWidget(
        "Label", _A_LABEL_HANDLE, text="Task list", textvariable=_DECLARED_BY_NOBODY
    )

    # When both are annotated
    annotator.add(text_box)
    annotator.add(plain_label)

    # Then each is left as it was: an empty `-textvariable` means nobody filled it in
    assert store.properties(_AN_ENTRY_HANDLE) == {PropId.ROLE: Role.TEXT.value}
    assert store.properties(_A_LABEL_HANDLE) == {
        PropId.ROLE: Role.STATIC_TEXT.value,
        PropId.NAME: "Task list",
    }, (
        "a widget declaring no variable was written to anyway: "
        f"{store.properties(_A_LABEL_HANDLE)}"
    )


def test_annotating_a_widget_again_follows_the_variable_it_declares_only_once() -> None:
    # Given a status label that has already been annotated once
    store = RecordingStore()
    status = FakeVariable("ready")
    annotator = Annotator(
        store, variables=VariablesByName({_THE_VARIABLE_THE_WIDGET_DECLARES: status})
    )
    label = FakeWidget(
        "Label", _A_LABEL_HANDLE, textvariable=_THE_VARIABLE_THE_WIDGET_DECLARES
    )
    annotator.add(label)

    # When Tk maps it again, and again
    annotator.add(label)
    annotator.add(label)

    # Then there is one registration on the variable, not three
    assert status.traces_left() == _ONE_REGISTRATION, (
        f"{status.traces_left()} traces are registered on a variable one widget "
        "declares, so every write to it now announces the widget that many times"
    )


def test_a_widget_pointed_at_a_different_variable_lets_go_of_the_one_it_had() -> None:
    # Given a label following the variable it declared when it was annotated
    store = RecordingStore()
    was = FakeVariable("ready")
    now = FakeVariable("busy")
    annotator = Annotator(
        store,
        variables=VariablesByName(
            {_THE_VARIABLE_THE_WIDGET_DECLARES: was, _A_SECOND_VARIABLE: now}
        ),
    )
    label = FakeWidget(
        "Label", _A_LABEL_HANDLE, textvariable=_THE_VARIABLE_THE_WIDGET_DECLARES
    )
    annotator.add(label)

    # When the application points the widget at another variable and says so
    label.declares_a_different_variable(_A_SECOND_VARIABLE)
    annotator.add(label)
    was.set("stale")

    # Then the widget announces the variable it declares now and lets go of the old
    assert store.properties(_A_LABEL_HANDLE)[PropId.NAME] == "busy", (
        "the widget is still announcing the variable it stopped declaring: "
        f"{store.properties(_A_LABEL_HANDLE)}"
    )
    assert was.traces_left() == _NOTHING_STILL_LISTENING, (
        f"{was.traces_left()} trace(s) are still registered on the variable the "
        "widget no longer declares, and each one can still take the name back"
    )
    assert now.traces_left() == _ONE_REGISTRATION


def test_a_name_the_application_says_itself_is_never_taken_back_by_a_declared_variable() -> (
    None
):
    # Given a label following its declared variable, then named by the application
    store = RecordingStore()
    status = FakeVariable("ready")
    annotator = Annotator(
        store, variables=VariablesByName({_THE_VARIABLE_THE_WIDGET_DECLARES: status})
    )
    label = FakeWidget(
        "Label", _A_LABEL_HANDLE, textvariable=_THE_VARIABLE_THE_WIDGET_DECLARES
    )
    annotator.add(label)
    annotator.set_name(label, "waiting for you")

    # When the variable moves on, and Tk maps the widget again afterwards
    status.set("task created")
    annotator.add(label)
    status.set("second task created")

    # Then the application's name stands, on both counts
    assert store.properties(_A_LABEL_HANDLE)[PropId.NAME] == "waiting for you", (
        "the declared variable took back the name the application chose: "
        f"{store.properties(_A_LABEL_HANDLE)}"
    )
    assert status.traces_left() == _NOTHING_STILL_LISTENING, (
        f"{status.traces_left()} trace(s) are still waiting to overwrite a name "
        "the application said itself"
    )


def test_a_variable_the_application_binds_by_hand_replaces_the_one_the_widget_declares() -> (
    None
):
    # Given a label following its declared variable, and an application wanting another
    store = RecordingStore()
    declared = FakeVariable("ready")
    what_the_application_would_rather_say = FakeVariable("waiting for you")
    annotator = Annotator(
        store, variables=VariablesByName({_THE_VARIABLE_THE_WIDGET_DECLARES: declared})
    )
    label = FakeWidget(
        "Label", _A_LABEL_HANDLE, textvariable=_THE_VARIABLE_THE_WIDGET_DECLARES
    )
    annotator.add(label)

    # When the application binds the other one by hand, and both move
    annotator.bind_text_variable(label, what_the_application_would_rather_say)
    declared.set("busy")
    what_the_application_would_rather_say.set("still working")

    # Then only the application's binding is left
    assert store.properties(_A_LABEL_HANDLE)[PropId.NAME] == "still working", (
        "the variable the widget declares is still overwriting the one the "
        f"application bound: {store.properties(_A_LABEL_HANDLE)}"
    )
    assert declared.traces_left() == _NOTHING_STILL_LISTENING, (
        f"{declared.traces_left()} trace(s) left on the declared variable after "
        "the application bound one of its own"
    )


def test_a_widget_named_after_a_label_is_called_what_that_label_says() -> None:
    # Given a form row: a caption, the entry it captions, and nothing linking them
    store = RecordingStore()
    annotator = Annotator(store)
    caption = FakeWidget("Label", _A_LABEL_HANDLE, text="Host:")
    entry = FakeWidget("Entry", _AN_ENTRY_HANDLE)
    annotator.add(caption)
    annotator.add(entry)

    # When the application says which widget that label is the caption for
    annotator.label_for(caption, entry)

    # Then the entry answers to the words beside it, without the colon
    assert store.properties(_AN_ENTRY_HANDLE)[PropId.NAME] == "Host", (
        "the entry is not called what the label beside it says: "
        f"{store.properties(_AN_ENTRY_HANDLE)}"
    )


def test_a_widget_named_after_a_label_that_shows_a_variable_follows_that_variable() -> (
    None
):
    # Given a caption whose words come from a variable rather than from `-text`
    store = RecordingStore()
    what_the_caption_says = FakeVariable("Host:")
    annotator = Annotator(
        store,
        variables=VariablesByName(
            {_THE_VARIABLE_THE_WIDGET_DECLARES: what_the_caption_says}
        ),
    )
    caption = FakeWidget(
        "Label", _A_LABEL_HANDLE, textvariable=_THE_VARIABLE_THE_WIDGET_DECLARES
    )
    entry = FakeWidget("Entry", _AN_ENTRY_HANDLE)
    annotator.add(caption)
    annotator.add(entry)

    # When the association is made, and the caption is later retitled
    annotator.label_for(caption, entry)
    named_when_associated = store.properties(_AN_ENTRY_HANDLE).get(PropId.NAME)
    what_the_caption_says.set("Server:")

    # Then the entry is named from the variable and follows it from then on
    assert named_when_associated == "Host", (
        f"the entry was named {named_when_associated!r} rather than from what "
        "the variable its caption declares already held"
    )
    assert store.properties(_AN_ENTRY_HANDLE)[PropId.NAME] == "Server", (
        "the entry is still called what its caption said first, so the "
        f"association stopped following the variable: {store.properties(_AN_ENTRY_HANDLE)}"
    )


def test_naming_a_widget_after_a_label_again_reads_what_that_label_says_now() -> None:
    # Given an entry named after a caption a plain `config(text=...)` has changed
    store = RecordingStore()
    annotator = Annotator(store)
    caption = FakeWidget("Label", _A_LABEL_HANDLE, text="Host:")
    entry = FakeWidget("Entry", _AN_ENTRY_HANDLE)
    annotator.label_for(caption, entry)
    caption.says_something_else("Hostname:")

    # When the application says the association again
    annotator.label_for(caption, entry)

    # Then the new words reach the entry
    assert store.properties(_AN_ENTRY_HANDLE)[PropId.NAME] == "Hostname", (
        "re-associating did not re-read the caption: "
        f"{store.properties(_AN_ENTRY_HANDLE)}"
    )


def test_naming_a_widget_after_a_label_with_nothing_to_say_is_refused() -> None:
    # Given a label showing no words and declaring no variable
    store = RecordingStore()
    annotator = Annotator(store)
    says_nothing = FakeWidget("Label", _A_LABEL_HANDLE, text="")
    entry = FakeWidget("Entry", _AN_ENTRY_HANDLE)

    # When the application tries to name an entry after it
    with pytest.raises(AnnotationRefused) as refusal:
        annotator.label_for(says_nothing, entry)

    # Then it is told, and the entry stays unnamed
    assert PropId.NAME not in store.properties(_AN_ENTRY_HANDLE), (
        f"the entry was named anyway: {store.properties(_AN_ENTRY_HANDLE)}"
    )
    assert str(says_nothing) in str(refusal.value), (
        f"the refusal has to name the label that said nothing: {refusal.value}"
    )


def test_naming_a_widget_after_an_entry_is_refused_because_an_entry_holds_contents() -> (
    None
):
    # Given an application that has said the two arguments the wrong way round
    store = RecordingStore()
    what_somebody_typed = FakeVariable("build.example.com")
    annotator = Annotator(
        store,
        variables=VariablesByName(
            {_THE_VARIABLE_THE_WIDGET_DECLARES: what_somebody_typed}
        ),
    )
    entry = FakeWidget(
        "Entry", _AN_ENTRY_HANDLE, textvariable=_THE_VARIABLE_THE_WIDGET_DECLARES
    )
    caption = FakeWidget("Label", _A_LABEL_HANDLE, text="Host:")

    # When it asks for the caption to be named after the entry
    with pytest.raises(AnnotationRefused) as refusal:
        annotator.label_for(entry, caption)

    # Then nothing was said about the caption and nothing is listening
    assert store.properties(_A_LABEL_HANDLE) == {}, (
        f"the caption was named after the entry's contents anyway: "
        f"{store.properties(_A_LABEL_HANDLE)}"
    )
    assert what_somebody_typed.traces_left() == _NOTHING_STILL_LISTENING, (
        f"{what_somebody_typed.traces_left()} trace(s) left on the entry's own "
        "variable by a call that was refused"
    )
    assert "set_acc_name" in str(refusal.value), (
        f"the refusal has to say what to reach for instead: {refusal.value}"
    )


def test_naming_a_widget_after_a_combobox_is_refused_the_same_way() -> None:
    # Given a themed combobox, whose variable is the option somebody chose
    store = RecordingStore()
    chosen = FakeVariable("High")
    annotator = Annotator(
        store, variables=VariablesByName({_THE_VARIABLE_THE_WIDGET_DECLARES: chosen})
    )
    combobox = FakeWidget(
        "TCombobox", _A_COMBOBOX_HANDLE, textvariable=_THE_VARIABLE_THE_WIDGET_DECLARES
    )
    caption = FakeWidget("Label", _A_LABEL_HANDLE, text="Priority:")

    # When it is offered as the caption
    with pytest.raises(AnnotationRefused) as refusal:
        annotator.label_for(combobox, caption)

    # Then it is refused by what the widget *is*, not by what it declares
    assert store.properties(_A_LABEL_HANDLE) == {}, (
        f"the caption was named after the chosen option: "
        f"{store.properties(_A_LABEL_HANDLE)}"
    )
    assert chosen.traces_left() == _NOTHING_STILL_LISTENING, (
        f"{chosen.traces_left()} trace(s) left on the combobox's own variable"
    )
    assert str(combobox) in str(refusal.value), (
        f"the refusal has to name the widget it would not read: {refusal.value}"
    )


def test_naming_a_widget_after_a_text_widget_is_refused_for_holding_contents() -> None:
    # Given a `tk.Text`, which has no `-textvariable` option at all
    store = RecordingStore()
    annotator = Annotator(store)
    notes = FakeWidget("Text", _A_TEXT_HANDLE)
    entry = FakeWidget("Entry", _AN_ENTRY_HANDLE)

    # When it is offered as the caption for an entry
    with pytest.raises(AnnotationRefused) as refusal:
        annotator.label_for(notes, entry)

    # Then it is refused for holding contents rather than for showing no words
    assert "contents" in str(refusal.value), (
        f"the refusal reads as though the widget merely said nothing: {refusal.value}"
    )
    assert PropId.NAME not in store.properties(_AN_ENTRY_HANDLE), (
        f"the entry was named anyway: {store.properties(_AN_ENTRY_HANDLE)}"
    )


def test_a_name_taken_from_a_label_survives_the_widget_being_mapped_again() -> None:
    # Given an entry named after its caption and holding what somebody typed
    store = RecordingStore()
    draft = FakeVariable("localhost")
    annotator = Annotator(
        store, variables=VariablesByName({_THE_VARIABLE_THE_WIDGET_DECLARES: draft})
    )
    caption = FakeWidget("Label", _A_LABEL_HANDLE, text="Host:")
    entry = FakeWidget(
        "Entry", _AN_ENTRY_HANDLE, textvariable=_THE_VARIABLE_THE_WIDGET_DECLARES
    )
    annotator.add(entry)
    annotator.label_for(caption, entry)

    # When Tk maps it again, and somebody types into it after
    annotator.add(entry)
    draft.set("build.example.com")

    # Then it still answers to its caption, and what it holds is still its value
    assert store.properties(_AN_ENTRY_HANDLE)[PropId.NAME] == "Host", (
        f"the entry lost the name its caption gave it: {store.properties(_AN_ENTRY_HANDLE)}"
    )
    assert store.properties(_AN_ENTRY_HANDLE)[PropId.VALUE] == "build.example.com", (
        "naming the entry after its caption stopped its own variable being read "
        f"as its contents: {store.properties(_AN_ENTRY_HANDLE)}"
    )


def test_a_label_association_replaces_the_variable_the_widget_itself_declared() -> None:
    # Given a menubutton showing a variable instead of a caption
    store = RecordingStore()
    showing = FakeVariable("Weekly")
    annotator = Annotator(
        store, variables=VariablesByName({_THE_VARIABLE_THE_WIDGET_DECLARES: showing})
    )
    caption = FakeWidget("Label", _A_LABEL_HANDLE, text="Report period:")
    menubutton = FakeWidget(
        "Menubutton", _A_BUTTON_HANDLE, textvariable=_THE_VARIABLE_THE_WIDGET_DECLARES
    )
    annotator.add(menubutton)

    # When the application says which label names it, and the variable moves on
    annotator.label_for(caption, menubutton)
    annotator.add(menubutton)
    showing.set("Monthly")

    # Then the caption stands, and the automatic binding has been let go of
    assert store.properties(_A_BUTTON_HANDLE)[PropId.NAME] == "Report period", (
        "the variable the widget declares took back the name its label gave it: "
        f"{store.properties(_A_BUTTON_HANDLE)}"
    )
    assert showing.traces_left() == _NOTHING_STILL_LISTENING, (
        f"{showing.traces_left()} trace(s) are still waiting to overwrite a name "
        "the application associated by hand"
    )


def test_what_a_widget_is_called_can_be_read_back_before_anything_is_written_over_it() -> (
    None
):
    # Given one widget nothing has named and one the application has
    store = RecordingStore()
    annotator = Annotator(store)
    entry = FakeWidget("Entry", _AN_ENTRY_HANDLE)
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task")
    annotator.add(entry)
    annotator.add(button)

    # When something asks what each is called already
    unnamed = annotator.name_of(entry)
    named = annotator.name_of(button)

    # Then it can tell them apart: `None` rather than `''` for a widget nothing named
    assert (unnamed, named) == (None, "New Task"), (
        f"asked what they are called, an unnamed entry answered {unnamed!r} and "
        f"a named button {named!r}"
    )


def test_forgetting_a_widget_releases_the_variable_it_was_following_on_its_own() -> (
    None
):
    # Given a label following the variable it declares, since forgotten
    store = RecordingStore()
    status = FakeVariable("ready")
    annotator = Annotator(
        store, variables=VariablesByName({_THE_VARIABLE_THE_WIDGET_DECLARES: status})
    )
    label = FakeWidget(
        "Label", _A_LABEL_HANDLE, textvariable=_THE_VARIABLE_THE_WIDGET_DECLARES
    )
    annotator.add(label)
    annotator.forget(label)

    # When the variable goes on being written
    status.set("task created")

    # Then nothing is listening and nothing came back
    assert status.traces_left() == _NOTHING_STILL_LISTENING, (
        f"{status.traces_left()} trace(s) outlived forget(), and each one will "
        "go on announcing a widget the application took back"
    )
    assert store.properties(_A_LABEL_HANDLE) == {}, (
        f"forget() left the widget annotated: {store.properties(_A_LABEL_HANDLE)}"
    )
