"""Behavioral spec for what a widget tells Windows about itself once annotated.

Everything here runs against a recording store and fake widgets, and that is the
point rather than a compromise: the annotator holds every decision the package
makes, and none of those decisions needs a display, a Tk build or Windows to be
specified. What is left underneath — three vtable slots into `oleacc` — holds no
decision at all.
"""

from __future__ import annotations

import pytest

from tests.doubles import FakeVariable, FakeWidget, RecordingStore
from tests.threads import the_failure_raised_on_another_thread
from tk_uia.annotate import AnnotationRefused, Annotator, PropId
from tk_uia.roles import Role

_A_BUTTON_HANDLE = 0x000407A2
_AN_ENTRY_HANDLE = 0x000407A3
_A_CANVAS_HANDLE = 0x000407A4
_A_ROOT_HANDLE = 0x000407A0
_A_DIALOG_HANDLE = 0x000407A1
_A_LABEL_HANDLE = 0x000407A5
_A_RECYCLED_HANDLE = 0x000508B1

# STATE_SYSTEM_UNAVAILABLE, from oleacc.h: the widget is there but disabled.
_MSAA_STATE_UNAVAILABLE = 0x1

_NO_CONTROL_ID_AT_ALL = 0
_AN_ID_THE_APPLICATION_CHOSE = 4207
_AN_ID_WIN32_IS_USING = 1101


def test_annotating_a_widget_writes_its_role_and_the_name_from_its_text_into_the_store() -> (
    None
):
    # Given a button carrying the words it shows, and somewhere to write
    store = RecordingStore()
    annotator = Annotator(store)
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task")

    # When the annotator is told about the widget
    annotator.add(button)

    # Then the store holds both halves against that widget's own handle: what it
    # is, and what to call it. Neither was there before — Tk hands a client an
    # unnamed control, which no name-based query and no screen reader can use.
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

    # Then it is announced as editable text and left unnamed. The tempting
    # fallback is the widget's path, and it would make `app.textbox(".!entry")`
    # appear to work: a locator nobody wrote down, that every repack breaks.
    assert store.properties(_AN_ENTRY_HANDLE) == {PropId.ROLE: Role.TEXT.value}, (
        "an unnamed widget must stay unnamed; an honest miss is findable, a "
        "name the application never chose is not"
    )
    assert str(entry) not in [value for _, _, value in store.writes], (
        f"the widget path {entry} reached the store as if it were a name"
    )


def test_a_widget_class_the_role_table_has_never_heard_of_is_left_exactly_as_tk_left_it() -> (
    None
):
    # Given a widget of a class nobody has decided a role for — a canvas, whose
    # contents are drawn and which a client cannot meaningfully be told about
    store = RecordingStore()
    annotator = Annotator(store)
    canvas = FakeWidget("Canvas", _A_CANVAS_HANDLE, text="not really a label")

    # When the annotator meets it
    annotator.add(canvas)

    # Then nothing is written. Guessing a role invents a control that is not
    # there; a client would go looking for text it can never read.
    assert store.writes == [], (
        f"an unmapped widget class must be passed over, not guessed at: {store.writes}"
    )


def test_a_toplevel_is_never_annotated_even_when_the_role_table_is_told_to() -> None:
    # Given a caller who has gone out of their way to put windows in the table
    store = RecordingStore()
    annotator = Annotator(store, {"Tk": Role.GROUPING, "Toplevel": Role.GROUPING})

    # When both kinds of window are offered to the annotator
    annotator.add(FakeWidget("Tk", _A_ROOT_HANDLE))
    annotator.add(FakeWidget("Toplevel", _A_DIALOG_HANDLE))

    # Then neither is touched. `wm title` already gives a window a correct
    # accessible name, and overriding it breaks the one query — find the window
    # by its title — that everything downstream starts from.
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

    # When it tries to say what the window is called, which is the obvious
    # reading of a surface whose other calls all take a widget
    with pytest.raises(AnnotationRefused) as refusal:
        annotator.set_name(root, "Tasks")

    # Then it is told, rather than the name landing somewhere that looks right
    # and is not. `winfo_id()` on a Tk root returns the container child, not the
    # toplevel — so the name would go on an inner pane, leaving the window
    # itself unnamed while every assertion about it appeared to pass. The
    # refusal has to say where a window's name really comes from.
    assert store.writes == [], f"the window's pane was annotated anyway: {store.writes}"
    assert "wm title" in str(refusal.value), (
        f"the refusal must point at what already names a window: {refusal.value}"
    )

    # And the rule holds for every property and for both kinds of window: the
    # automatic path has always skipped these, and the manual one walked past it.
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

    # Then the application wins on both counts. Inference is a default for the
    # widgets nobody thought about, never a ceiling on the ones somebody did:
    # the visible caption is often an abbreviation, an icon, or nothing at all.
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

    # Then the addition is honoured and everything else still works. Naming one
    # class must not silently un-announce every widget the caller did not list.
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

    # When the same widget is offered again, as `<Map>` will do on every
    # unhide, every notebook tab change and every geometry manager shuffle
    annotator.add(button)

    # Then not one call crosses into COM. This is the difference between
    # annotating a window once and annotating it on every repaint forever.
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

    # Then the change reaches the store. The ledger exists to skip repeats, and
    # a ledger that skips changes too would leave every screen reader in the
    # world announcing the first thing an application ever said.
    assert store.properties(_A_LABEL_HANDLE)[PropId.NAME] == "task created", (
        "the ledger swallowed a real change"
    )


def test_a_destroyed_widget_has_its_annotations_cleared_before_windows_can_reuse_its_handle() -> (
    None
):
    # Given an annotated button that Tk is now tearing down. By the time
    # `<Destroy>` runs the widget is already half gone and `winfo_id` raises.
    store = RecordingStore()
    annotator = Annotator(store)
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task")
    annotator.add(button)
    button.destroy()

    # When the annotator is told the widget is going
    annotator.forget(button)

    # Then the annotations come off the handle it had when it was alive.
    # Windows reissues window handles: an annotation left on a dead one names
    # whatever gets that handle next, and reads exactly like a flaky locator.
    assert store.cleared == [_A_BUTTON_HANDLE], (
        f"expected the handle cached while the widget lived, cleared {store.cleared}"
    )
    assert store.properties(_A_BUTTON_HANDLE) == {}, (
        "a dead widget's name outlived it and is now free to mislabel another"
    )


def test_a_widget_rebuilt_at_the_same_path_lets_go_of_the_handle_it_used_to_have() -> (
    None
):
    # Given an annotated button that Tk has since rebuilt at the same path,
    # which happens whenever a frame is torn down and laid out again
    store = RecordingStore()
    annotator = Annotator(store)
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task")
    annotator.add(button)
    button.take_a_new_handle(_A_RECYCLED_HANDLE)

    # When it is annotated again on its new handle
    annotator.add(button)

    # Then the handle it left behind is released first, and the new one carries
    # the annotation. Without the release the old handle keeps a name nothing
    # will ever clear, because the `<Destroy>` that would have has already been
    # and gone.
    assert store.cleared == [_A_BUTTON_HANDLE], (
        f"the abandoned handle was left annotated; cleared {store.cleared}"
    )
    assert store.properties(_A_RECYCLED_HANDLE)[PropId.NAME] == "New Task"


def test_setting_a_widgets_value_writes_it_where_a_client_reads_an_edit_controls_content() -> (
    None
):
    # Given an annotated entry, which the role alone has just given a
    # ValuePattern it did not have before
    store = RecordingStore()
    annotator = Annotator(store)
    entry = FakeWidget("Entry", _AN_ENTRY_HANDLE)
    annotator.add(entry)

    # When the application says what is currently in it
    annotator.set_value(entry, "typed words")

    # Then it is the value that carries the contents, and the name is left
    # alone. A client asks a text box its value and its label separately; one
    # answering with the other is how "Title" ends up read back as the thing
    # somebody typed.
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

    # Then all six sit side by side. They are separate questions a screen reader
    # asks in sequence, and the failure this pins down is a routing mistake in
    # the property table underneath, which returns S_OK either way.
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

    # Then that one carries it and the other is untouched. An automation id is
    # `GWLP_ID`, which is the control id Win32 puts in `WM_COMMAND.wParam` and
    # `WM_DRAWITEM.idCtl` — and every Tk button is owner-drawn, so it receives
    # `WM_DRAWITEM`. Deriving ids from widget paths would also make every
    # repack a breaking change for whoever is writing the locators.
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

    # Then it is told, rather than the id being quietly replaced. Overwriting it
    # redirects the messages that widget is drawn by, and the symptom would be a
    # button that stops painting, a long way from the line that caused it.
    assert store.control_id(_A_BUTTON_HANDLE) == _AN_ID_WIN32_IS_USING, (
        "the control id Windows was using has been overwritten"
    )
    assert str(_AN_ID_WIN32_IS_USING) in str(refusal.value), (
        f"the refusal must name the id already in place: {refusal.value}"
    )


def test_annotating_from_a_thread_other_than_the_one_that_owns_the_widgets_is_refused() -> (
    None
):
    # Given an annotator built on the thread that owns the widgets, as it is
    # whenever `enable()` is called from the thread running Tk's event loop
    store = RecordingStore()
    annotator = Annotator(store)
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task")

    # When a background worker tries to annotate — the ordinary shape of a
    # thread that has just finished loading something and wants to say so
    refusal = the_failure_raised_on_another_thread(lambda: annotator.add(button))

    # Then it is stopped at the door, before a single Tk call. `add` asks the
    # widget its class, its options and its text, and each of those crosses into
    # the Tcl interpreter — so a guard that only protected the store would have
    # let the interpreter be poked from the wrong thread first, which is the
    # half of this that corrupts rather than merely misplaces. The widget double
    # refuses a foreign caller precisely so that reaching it fails this spec.
    assert isinstance(refusal, AnnotationRefused), (
        f"a foreign thread got through to Tk with {refusal!r}; the guard must "
        "refuse before winfo_class(), keys() or cget() is called"
    )
    assert store.writes == [], f"a foreign thread reached the store: {store.writes}"
    assert "thread" in str(refusal), (
        f"the reader has to be told which rule they broke: {refusal}"
    )


def test_a_widget_bound_to_a_variable_re_announces_itself_whenever_it_changes() -> None:
    # Given a status label whose words come from a variable rather than from
    # `-text`, bound so that the annotation follows it
    store = RecordingStore()
    annotator = Annotator(store)
    label = FakeWidget("Label", _A_LABEL_HANDLE)
    status = FakeVariable("ready")
    annotator.add(label)
    annotator.bind_text_variable(label, status)
    announced_when_bound = store.properties(_A_LABEL_HANDLE).get(PropId.NAME)

    # When the application puts something new in the variable
    status.set("task created")

    # Then that is what a client now reads. A `textvariable` label has no
    # `-text` to infer from, so without this it is the one widget in the window
    # whose whole purpose is to say what just happened, saying nothing.
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

    # Then what is already in the box is readable straight away, and it is the
    # value that carries it. A trace only fires on the *next* write, so a
    # binding that waited for one would leave an entry announcing nothing until
    # somebody happened to type in it.
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

    # Then that is what a client now reads out of the edit control, with the
    # application saying nothing further. A value is the one property a client
    # re-reads constantly, and a stale one is indistinguishable from a true one
    # — the widget shows the new text while the tree keeps answering the old.
    assert store.properties(_AN_ENTRY_HANDLE)[PropId.VALUE] == (
        "Write the quarterly report"
    ), "the value is stuck on whatever the entry held when it was bound"


def test_a_forgotten_widget_stops_being_re_announced_when_its_variable_changes() -> (
    None
):
    # Given a status label whose annotation follows a variable, which the
    # application has since taken back
    store = RecordingStore()
    annotator = Annotator(store)
    label = FakeWidget("Label", _A_LABEL_HANDLE)
    status = FakeVariable("ready")
    annotator.add(label)
    annotator.bind_text_variable(label, status)
    annotator.forget(label)

    # When the variable moves on, as a running application's status variable does
    status.set("task created")

    # Then the widget stays forgotten. A trace that outlives `forget` puts the
    # annotation back on the next write, so a caller who un-annotated a widget
    # would find it re-announcing itself with no call of theirs in the traceback.
    assert store.properties(_A_LABEL_HANDLE) == {}, (
        f"forget() left the variable trace in place, so the next write "
        f"re-announced the widget: {store.properties(_A_LABEL_HANDLE)}"
    )


def test_a_destroyed_widgets_variable_can_still_be_written_without_raising() -> None:
    # Given a label bound to a variable, and destroyed without the annotator
    # being told — a `<Destroy>` handler that raises, an application tearing a
    # frame down before `enable()` ran, a widget whose parent went first
    store = RecordingStore()
    annotator = Annotator(store)
    label = FakeWidget("Label", _A_LABEL_HANDLE)
    status = FakeVariable("ready")
    annotator.add(label)
    annotator.bind_text_variable(label, status)
    label.destroy()
    while_it_was_alive = list(store.writes)

    # When the variable goes on changing, as an application's variables do long
    # after the widget that displayed them has gone
    status.set("task created")
    status.set("second task created")

    # Then not one of those writes raises, and none of them reaches the store. A
    # trace firing at a dead window path raises inside Tcl's own callback, where
    # the application has no call of its own to wrap it in: it lands as an
    # unhandled traceback on stderr, on every write, for the life of the process.
    assert store.writes == while_it_was_alive, (
        "a widget that no longer exists was annotated anyway: "
        f"{store.writes[len(while_it_was_alive) :]}"
    )
