"""Behavioral spec for what a widget tells Windows about itself once annotated.

Everything here runs against a recording store and fake widgets, and that is the
point rather than a compromise: the annotator holds every decision the package
makes, and none of those decisions needs a display, a Tk build or Windows to be
specified. What is left underneath — three vtable slots into `oleacc` — holds no
decision at all.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

import pytest

from tests.doubles import FakeVariable, FakeWidget, RecordingStore
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
    refusal = _the_failure_raised_on_another_thread(lambda: annotator.add(button))

    # Then it is stopped at the door and nothing is written. Both layers under
    # this one are thread-affine: reading `winfo_id` off the Tk thread corrupts
    # the interpreter, and COM apartments are per-thread, so an annotation made
    # on the wrong one goes somewhere no client will ever read it.
    assert isinstance(refusal, AnnotationRefused), (
        f"a foreign thread got through with {refusal!r}"
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


def _the_failure_raised_on_another_thread(work: Callable[[], None]) -> BaseException:
    caught: list[BaseException] = []

    def run() -> None:
        try:
            work()
        except BaseException as failure:  # noqa: BLE001 - reported, not handled
            caught.append(failure)

    worker = threading.Thread(target=run)
    worker.start()
    worker.join()

    assert caught, "the call went through on a thread that does not own the widgets"
    return caught[0]
