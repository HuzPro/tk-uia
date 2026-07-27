"""Behavioral spec for what an application is told it has told Windows.

Every one of these runs against the same doubles the annotator's own specs use,
which is the point rather than a compromise: the description is a reading of the
annotation ledger and a walk of the widget tree, and neither needs a display, a
Tk build or Windows to be specified. The report a reader prints is specified the
same way, so the whole feature is covered by the lane that has no Tk at all.
"""

from __future__ import annotations

from tests.doubles import (
    FakeInterpreter,
    FakeRoot,
    FakeVariable,
    FakeWidget,
    RecordingStore,
)
from tests.threads import the_failure_raised_on_another_thread
from tk_uia import __version__
from tk_uia.annotate import (
    AnnotationRefused,
    Annotator,
    Installation,
    PropId,
    install,
)
from tk_uia.describe import (
    ON_PURPOSE,
    Description,
    Gap,
    WidgetDescription,
    describe,
)
from tk_uia.roles import Role
from tk_uia.tkversion import Strategy

_A_BUTTON_HANDLE = 0x000407A2
_A_CANVAS_HANDLE = 0x000407A4
_A_FRAME_HANDLE = 0x000407A6
_A_DIALOG_HANDLE = 0x000407A1
_AN_ENTRY_HANDLE = 0x000407A3
_A_SCROLLBAR_HANDLE = 0x000407A7
_A_LISTBOX_HANDLE = 0x000407A8
_A_TREEVIEW_HANDLE = 0x000407A9
_A_NOTEBOOK_HANDLE = 0x000407AA
_A_LABEL_HANDLE = 0x000407A5
_A_RECYCLED_HANDLE = 0x000508B1
_AN_ID_THE_APPLICATION_CHOSE = 4207

_LEFT_ALONE = "LEFT ALONE ON PURPOSE"
_THE_TABLE = "WIDGET"
_THE_CLOSING_CAVEAT_BEGINS = "Everything above"

# STATE_SYSTEM_UNAVAILABLE, from oleacc.h: the widget is there but disabled.
_MSAA_STATE_UNAVAILABLE = 0x1


def test_describing_an_annotated_widget_reports_the_role_and_the_name_that_were_written() -> (
    None
):
    # Given a button in a window, annotated as `enable()` would have annotated it
    store = RecordingStore()
    annotator = Annotator(store)
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task")
    root = FakeRoot(FakeInterpreter("8.6.15", "win32", native=False), children=[button])
    annotator.add(button)

    # When the application asks what it has told Windows about its widgets
    description = describe(root, Installation(Strategy.ANNOTATED, annotator))

    # Then it is told, per widget, what was written. Every failure mode this
    # package has returns `S_OK` and does nothing, so an application that cannot
    # ask what it wrote has no way to tell an annotation from a silence.
    said = _what_the_description_says_about(description, str(button))

    assert (said.role, said.name) == (Role.PUSH_BUTTON, "New Task"), (
        f"the description reports role {said.role} and name {said.name!r} for a "
        "button annotated as a named push button"
    )


def test_a_widget_whose_class_has_no_role_is_named_as_unwritten_rather_than_left_out_of_the_report() -> (
    None
):
    # Given somebody's own widget nested inside a frame. Every class both
    # toolkits ship has a role now, so the widget `enable()` walks past is no
    # longer a canvas — it is a custom one registered under its own class name.
    store = RecordingStore()
    annotator = Annotator(store)
    homemade = FakeWidget("SparklineChart", _A_CANVAS_HANDLE)
    frame = FakeWidget("Frame", _A_FRAME_HANDLE, children=[homemade])
    root = FakeRoot(FakeInterpreter("8.6.15", "win32", native=False), children=[frame])
    annotator.add(frame)
    annotator.add(homemade)

    # When the application asks what it has told Windows
    description = describe(root, Installation(Strategy.ANNOTATED, annotator))

    # Then it is in the report, by its path, with the reason nothing was
    # written about it. A description that listed only what it had written would
    # render an application nobody annotated as a blank page — and the widget an
    # author most needs to see is the one they never thought about.
    said = _what_the_description_says_about(description, str(homemade))

    assert said.gaps == (Gap.NO_ROLE_FOR_ITS_CLASS,), (
        f"the canvas is reported with gaps {said.gaps}, so a reader is not told "
        "why a widget in their own window carries nothing"
    )


def test_a_widget_tk_never_mapped_is_reported_as_never_mapped_and_not_as_a_missing_role() -> (
    None
):
    # Given a frame the geometry manager never found room for, in a window that
    # switched accessibility on. A fixed `geometry()` silently drops whatever
    # the packer cannot fit: `<Map>` never fires, so the sweep never sees it and
    # nothing anywhere raises. This widget has a role — it is not the canvas.
    store = RecordingStore()
    annotator = Annotator(store)
    never_fitted = FakeWidget("Frame", _A_FRAME_HANDLE, mapped=False)
    root = FakeRoot(
        FakeInterpreter("8.6.15", "win32", native=False), children=[never_fitted]
    )

    # When the application asks what it has told Windows
    description = describe(root, Installation(Strategy.ANNOTATED, annotator))

    # Then it is told the widget was never mapped, which is the actionable
    # answer, rather than that its class has no role — which is not even true.
    # Two reasons apply to a widget at once far more often than they look like
    # they will, and which one is reported is the whole value of the line.
    said = _what_the_description_says_about(description, str(never_fitted))

    assert said.gaps == (Gap.NEVER_MAPPED,), (
        f"an unmapped frame is reported as {said.gaps}; a Frame has a role, so "
        "reporting a missing one sends the reader to the wrong fix"
    )


def test_a_toplevel_is_reported_as_left_alone_on_purpose_rather_than_as_a_failure() -> (
    None
):
    # Given an application with a dialog open as well as its main window
    store = RecordingStore()
    annotator = Annotator(store)
    dialog = FakeWidget("Toplevel", _A_DIALOG_HANDLE)
    root = FakeRoot(FakeInterpreter("8.6.15", "win32", native=False), children=[dialog])

    # When the application asks what it has told Windows
    description = describe(root, Installation(Strategy.ANNOTATED, annotator))

    # Then both windows are in the report, and both carry the one reason that is
    # not a fault. Leaving them out would read as the description having lost
    # them; listing them among the failures would send a reader off to fix
    # something this package refuses to do on purpose.
    windows = [
        _what_the_description_says_about(description, path)
        for path in (str(root), str(dialog))
    ]

    assert [window.gaps for window in windows] == [(Gap.NAMED_BY_ITS_TITLE,)] * 2, (
        f"the two windows are reported as {[w.gaps for w in windows]}"
    )
    assert Gap.NAMED_BY_ITS_TITLE in ON_PURPOSE, (
        "a window left to `wm title` is not a gap to close, and counting it as "
        "one buries the widgets that are"
    )


def test_a_mapped_widget_with_a_role_that_was_never_written_to_is_reported_as_such() -> (
    None
):
    # Given a button on screen, in a window where nothing was ever annotated —
    # which is what an author sees when the version gate stood down, or when
    # `enable()` was called before the widget existed
    store = RecordingStore()
    annotator = Annotator(store)
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task")
    root = FakeRoot(FakeInterpreter("8.6.15", "win32", native=False), children=[button])

    # When the application asks what it has told Windows
    description = describe(root, Installation(Strategy.ANNOTATED, annotator))

    # Then the widget is reported as showing, roleable, and carrying nothing —
    # which is a different complaint from either of the two above it, and the
    # only one that means something has actually gone wrong.
    said = _what_the_description_says_about(description, str(button))

    assert said.gaps == (Gap.NOTHING_WRITTEN,), (
        f"a mapped button whose class has a role is reported as {said.gaps}, "
        "which sends the reader looking for a mapping problem that is not there"
    )


def test_a_class_the_application_gave_a_role_to_is_never_reported_as_a_class_with_no_role() -> (
    None
):
    # Given an application that has already done the thing the report would tell
    # it to do — named its canvas in `enable(root, roles=...)` — and a canvas the
    # geometry manager then never mapped
    store = RecordingStore()
    annotator = Annotator(store, {"Canvas": Role.STATIC_TEXT})
    canvas = FakeWidget("Canvas", _A_CANVAS_HANDLE, mapped=False)
    root = FakeRoot(FakeInterpreter("8.6.15", "win32", native=False), children=[canvas])

    # When the application asks what it has told Windows
    description = describe(root, Installation(Strategy.ANNOTATED, annotator))

    # Then it is told the widget was never mapped, not that its class needs a
    # role. Reading the built-in table rather than the one actually in force
    # would answer "pass roles={...} to enable()" to a reader who did exactly
    # that — a confident wrong answer, which is the failure mode this whole
    # package exists to refuse.
    said = _what_the_description_says_about(description, str(canvas))

    assert said.gaps == (Gap.NEVER_MAPPED,), (
        f"a class the caller added a role for is reported as {said.gaps}, so "
        "the report is reading a role table the application is not using"
    )


def test_an_annotated_entry_is_reported_as_having_neither_a_name_nor_a_value_a_client_can_read() -> (
    None
):
    # Given an entry that `enable()` annotated and the application said no more
    # about — the widget with no `-text` to be named from, and whose contents
    # live in a variable rather than on the widget
    store = RecordingStore()
    annotator = Annotator(store)
    entry = FakeWidget("Entry", _AN_ENTRY_HANDLE)
    root = FakeRoot(FakeInterpreter("8.6.15", "win32", native=False), children=[entry])
    annotator.add(entry)

    # When the application asks what it has told Windows
    description = describe(root, Installation(Strategy.ANNOTATED, annotator))

    # Then both halves are named. The role alone gave this widget a ValuePattern
    # it did not have before, and until something writes one it answers `''` —
    # a confident wrong answer where bare Tk gave no answer at all, and the one
    # place in this package where annotating leaves a client worse informed.
    said = _what_the_description_says_about(description, str(entry))

    assert said.gaps == (Gap.NO_NAME, Gap.NO_VALUE), (
        f"an annotated entry nobody named or filled in is reported as "
        f"{said.gaps}, so the reader is not told what a client will read"
    )


def test_a_frame_is_not_reported_as_unnamed_because_a_grouping_is_not_what_a_screen_reader_announces() -> (
    None
):
    # Given the two widget kinds every window is full of and nobody names: the
    # frames holding the layout together, and a scrollbar
    store = RecordingStore()
    annotator = Annotator(store)
    frame = FakeWidget("Frame", _A_FRAME_HANDLE)
    scrollbar = FakeWidget("Scrollbar", _A_SCROLLBAR_HANDLE)
    root = FakeRoot(
        FakeInterpreter("8.6.15", "win32", native=False), children=[frame, scrollbar]
    )
    annotator.add(frame)
    annotator.add(scrollbar)

    # When the application asks what it has told Windows
    description = describe(root, Installation(Strategy.ANNOTATED, annotator))

    # Then neither is held against it. This is a signal-to-noise decision, and
    # it is pinned so that changing it has to be deliberate: a report that
    # flagged every container would bury the one entry that genuinely needs a
    # name under a list of frames nobody was ever going to name.
    structural = [
        _what_the_description_says_about(description, path)
        for path in (str(frame), str(scrollbar))
    ]

    assert [widget.gaps for widget in structural] == [(), ()], (
        f"a frame and a scrollbar are reported as {[w.gaps for w in structural]}"
    )


def test_a_listbox_is_reported_as_findable_with_its_rows_not_in_the_tree_at_all() -> (
    None
):
    # Given the three widget kinds whose contents are the reason they exist,
    # each annotated and named, so that a client can find every one of them
    store = RecordingStore()
    annotator = Annotator(store)
    compound = [
        FakeWidget("Listbox", _A_LISTBOX_HANDLE),
        FakeWidget("Treeview", _A_TREEVIEW_HANDLE),
        FakeWidget("TNotebook", _A_NOTEBOOK_HANDLE),
    ]
    root = FakeRoot(FakeInterpreter("8.6.15", "win32", native=False), children=compound)
    for widget in compound:
        annotator.add(widget)
        annotator.set_name(widget, "Tasks")

    # When the application asks what it has told Windows
    description = describe(root, Installation(Strategy.ANNOTATED, annotator))

    # Then each is reported as findable and hollow. Tk gives one window handle
    # per widget and annotation works on handles; the rows, items and tabs would
    # need MSAA's child-id model, which is a different piece of machinery. A
    # screen-reader user can find the listbox and cannot hear what is in it.
    said = [
        _what_the_description_says_about(description, str(widget))
        for widget in compound
    ]

    assert [widget.gaps for widget in said] == [(Gap.ITEMS_NOT_IN_THE_TREE,)] * 3, (
        f"a listbox, a treeview and a notebook are reported as "
        f"{[widget.gaps for widget in said]}"
    )


class TabsThatWereFound:
    """Whatever the tab handles are keeping, as `describe` reads it."""

    def __init__(self, **by_path: tuple[str, ...]) -> None:
        self._by_path = by_path

    def refresh(self, widget: object) -> None: ...

    def forget(self, path: str) -> None: ...

    def on(self, path: str) -> tuple[object, ...]:
        return tuple(
            type("Tab", (), {"text": text})() for text in self._by_path.get(path, ())
        )


def test_a_notebook_whose_tabs_were_given_handles_is_not_reported_as_hollow() -> None:
    # Given a notebook whose tabs have been found and given window handles
    store = RecordingStore()
    annotator = Annotator(store)
    notebook = FakeWidget("TNotebook", _A_NOTEBOOK_HANDLE)
    root = FakeRoot(
        FakeInterpreter("8.6.15", "win32", native=False), children=[notebook]
    )
    annotator.add(notebook)
    annotator.set_name(notebook, "Settings")

    # When the application asks what it has told Windows
    description = describe(
        root,
        Installation(
            Strategy.ANNOTATED,
            annotator,
            tabs=TabsThatWereFound(**{str(notebook): ("General", "Paths")}),
        ),
    )

    # Then the tabs are named as reachable rather than reported missing. Saying
    # a notebook is hollow when a client can already see and press every tab on
    # it would send an author looking for a gap that is not there.
    said = _what_the_description_says_about(description, str(notebook))
    assert Gap.ITEMS_NOT_IN_THE_TREE not in said.gaps, (
        f"a notebook with handles for both its tabs is reported as {said.gaps}"
    )
    assert said.tabs == ("General", "Paths"), (
        f"the report says its tabs are {said.tabs}"
    )


def test_a_widget_tk_has_unmapped_since_it_was_annotated_is_reported_as_out_of_reach() -> (
    None
):
    # Given a widget that was annotated while it was on screen, and which Tk has
    # since taken off it — an unselected notebook tab is the everyday case
    store = RecordingStore()
    annotator = Annotator(store)
    entry = FakeWidget("Entry", _AN_ENTRY_HANDLE)
    root = FakeRoot(FakeInterpreter("8.6.15", "win32", native=False), children=[entry])
    annotator.add(entry)
    annotator.set_name(entry, "Host")
    entry.is_taken_off_the_screen()

    # When the application asks what it has told Windows
    description = describe(root, Installation(Strategy.ANNOTATED, annotator))

    # Then it is reported as out of reach rather than as written. Measured
    # against a real tabbed dialog: after a tab change, 23 widgets kept their
    # handles and every annotation on them, and a client could read none of
    # them — UI Automation does not list an unmapped window. A report that
    # still called those written was the one thing this file exists to refuse.
    said = _what_the_description_says_about(description, str(entry))
    assert said.gaps == (Gap.UNMAPPED_SINCE_ANNOTATED,), (
        f"reported {said.gaps} for a widget nothing can currently read"
    )
    # And the row still shows what was written, because it is all still there:
    # the widget comes back the moment Tk maps it again, and nothing has to be
    # re-annotated for that to happen.
    assert (said.role, said.name) == (Role.TEXT, "Host"), (
        f"the row lost what was written about it: role {said.role}, name {said.name!r}"
    )


def test_an_annotated_button_is_reported_as_advertising_an_invoke_pattern_that_presses_nothing() -> (
    None
):
    # Given a button annotated exactly as `enable()` leaves it: found, named,
    # and offering a client an InvokePattern and a DefaultAction of "Press"
    store = RecordingStore()
    annotator = Annotator(store)
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task")
    root = FakeRoot(FakeInterpreter("8.6.15", "win32", native=False), children=[button])
    annotator.add(button)

    # When the application asks what it has told Windows
    description = describe(root, Installation(Strategy.ANNOTATED, annotator))

    # Then the README's central caveat is repeated against this widget, by path.
    # Both of those patterns lie: they return cleanly and the Tk command behind
    # the button never runs, because every Tk button is owner-drawn and the
    # proxy synthesises Invoke from a `BM_CLICK` nothing is listening for.
    said = _what_the_description_says_about(description, str(button))

    assert said.gaps == (Gap.CANNOT_BE_PRESSED,), (
        f"an annotated button is reported as {said.gaps}, so a reader planning "
        "to drive this window through Invoke is not warned"
    )


def test_a_name_that_no_longer_matches_the_widgets_text_is_reported_as_possibly_stale() -> (
    None
):
    # Given a label annotated from its own caption, whose caption the
    # application has since changed with a plain `config(text=...)`
    store = RecordingStore()
    annotator = Annotator(store)
    label = FakeWidget("Label", _A_LABEL_HANDLE, text="Task list")
    root = FakeRoot(FakeInterpreter("8.6.15", "win32", native=False), children=[label])
    annotator.add(label)
    label.says_something_else("in progress")

    # When the application asks what it has told Windows
    description = describe(root, Installation(Strategy.ANNOTATED, annotator))

    # Then the disagreement is reported, along with what the widget says now.
    # `-text` is read at `<Map>` and never again, so a client goes on being told
    # 'Task list' indefinitely — and staleness is the worst way an accessibility
    # tree can be wrong, because a stale answer reads exactly like a true one.
    said = _what_the_description_says_about(description, str(label))

    assert said.gaps == (Gap.NAME_MAY_BE_STALE,), (
        f"a label whose caption moved on is reported as {said.gaps}"
    )
    assert said.shows_now == "in progress", (
        f"the report says the widget shows {said.shows_now!r}, so a reader "
        "cannot see which of the two the client is stuck on"
    )


def test_a_name_the_application_chose_itself_is_never_called_stale_when_the_widgets_text_differs() -> (
    None
):
    # Given the pattern the README encourages: a button whose caption is short
    # for the screen, named at length for a listener
    store = RecordingStore()
    annotator = Annotator(store)
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="OK")
    root = FakeRoot(FakeInterpreter("8.6.15", "win32", native=False), children=[button])
    annotator.add(button)
    annotator.set_name(button, "Confirm order")

    # When the application asks what it has told Windows
    description = describe(root, Installation(Strategy.ANNOTATED, annotator))

    # Then the disagreement between the two is not held against it. Without
    # knowing where a name came from, the staleness check fires on a documented,
    # encouraged pattern — and a diagnostic that cries wolf on good code is
    # ignored, which is how the one genuinely stale name gets missed too.
    said = _what_the_description_says_about(description, str(button))

    assert Gap.NAME_MAY_BE_STALE not in said.gaps, (
        f"a name the application chose over a shorter caption is reported as "
        f"possibly stale: {said.gaps}"
    )


def test_the_report_says_which_properties_a_variable_is_keeping_in_step_so_a_reader_knows_they_will_not_go_stale() -> (
    None
):
    # Given a status label showing "ready" and bound to a variable that already
    # holds "ready" — the ordinary shape of a startup, and the arrangement where
    # binding announces a value the ledger has already written. The COM write is
    # skipped, which is the ledger doing exactly the job it exists for.
    store = RecordingStore()
    annotator = Annotator(store)
    label = FakeWidget("Label", _A_LABEL_HANDLE, text="ready")
    root = FakeRoot(FakeInterpreter("8.6.15", "win32", native=False), children=[label])
    annotator.add(label)
    annotator.bind_text_variable(label, FakeVariable("ready"))
    label.says_something_else("in progress")

    # When the application asks what it has told Windows
    description = describe(root, Installation(Strategy.ANNOTATED, annotator))

    # Then the name is reported as one something is keeping true, and not as one
    # that has gone stale. Skipping the COM write must not skip recording where
    # the value came from: a report that did would tell an author to go and fix
    # the one widget in the window that is already looking after itself.
    said = _what_the_description_says_about(description, str(label))

    assert said.kept_in_step == (PropId.NAME,), (
        f"a bound name is reported as kept in step by {said.kept_in_step}"
    )
    assert Gap.NAME_MAY_BE_STALE not in said.gaps, (
        f"a name a variable is keeping in step is reported as stale: {said.gaps}"
    )


def test_the_automation_id_an_application_asked_for_is_reported_against_the_widget_that_carries_it() -> (
    None
):
    # Given a button an application numbered by hand, so a suite has something
    # stable to pin a locator to
    store = RecordingStore()
    annotator = Annotator(store)
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task")
    root = FakeRoot(FakeInterpreter("8.6.15", "win32", native=False), children=[button])
    annotator.add(button)
    annotator.set_automation_id(button, _AN_ID_THE_APPLICATION_CHOSE)

    # When the application asks what it has told Windows
    description = describe(root, Installation(Strategy.ANNOTATED, annotator))

    # Then the number is reported beside the widget that was given it. It goes
    # straight through to `GWLP_ID` and never near the property ledger, so a
    # report reading only the properties would show the one identifier a test
    # suite is going to depend on as absent.
    said = _what_the_description_says_about(description, str(button))

    assert said.automation_id == _AN_ID_THE_APPLICATION_CHOSE, (
        f"the button is reported carrying automation id {said.automation_id}"
    )


def test_every_other_property_that_was_written_is_reported_rather_than_only_the_four_in_the_table() -> (
    None
):
    # Given a button the application has filled in completely — the four
    # properties a report's columns have no room for
    store = RecordingStore()
    annotator = Annotator(store)
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task")
    root = FakeRoot(FakeInterpreter("8.6.15", "win32", native=False), children=[button])
    annotator.add(button)
    annotator.set_description(button, "creates a task and clears the form")
    annotator.set_action(button, "Press")
    annotator.set_help(button, "keyboard shortcut is Ctrl+N")
    annotator.set_state(button, _MSAA_STATE_UNAVAILABLE)

    # When the application asks what it has told Windows
    description = describe(root, Installation(Strategy.ANNOTATED, annotator))

    # Then all four come back. They are rare and they are in the ledger, and a
    # report whose stated principle is that it must not quietly omit what it
    # cannot see cannot quietly omit four properties it can.
    said = _what_the_description_says_about(description, str(button))

    assert said.also_written == {
        PropId.DESCRIPTION: "creates a task and clears the form",
        PropId.DEFAULT_ACTION: "Press",
        PropId.HELP: "keyboard shortcut is Ctrl+N",
        PropId.STATE: _MSAA_STATE_UNAVAILABLE,
    }, f"the report accounts for {said.also_written} of what was written"


def test_a_widget_tk_rebuilt_on_a_new_handle_is_reported_as_annotated_on_a_handle_it_no_longer_has() -> (
    None
):
    # Given an annotated button that Tk has since rebuilt at the same path on a
    # fresh window — what happens whenever a frame is torn down and laid out
    # again — with nothing having re-annotated it since
    store = RecordingStore()
    annotator = Annotator(store)
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task")
    root = FakeRoot(FakeInterpreter("8.6.15", "win32", native=False), children=[button])
    annotator.add(button)
    button.take_a_new_handle(_A_RECYCLED_HANDLE)

    # When the application asks what it has told Windows
    description = describe(root, Installation(Strategy.ANNOTATED, annotator))

    # Then the report says so rather than repeating the annotation as if it were
    # in force. Everything in the ledger for this widget describes a window it
    # no longer owns; a client reading the widget on screen gets whatever bare
    # Tk gives the new one, which is nothing.
    said = _what_the_description_says_about(description, str(button))

    assert said.gaps == (Gap.ANNOTATED_ON_A_HANDLE_IT_NO_LONGER_HAS,), (
        f"a rebuilt widget is reported as {said.gaps}, so the report is "
        "vouching for properties that are on a window nobody is looking at"
    )


def test_a_ledger_entry_whose_widget_is_no_longer_in_the_tree_is_named_rather_than_dropped() -> (
    None
):
    # Given an annotated widget that the walk from this root will never reach —
    # a dialog's contents when the main window was the one described, or a
    # widget that went away without `<Destroy>` ever reaching the annotator
    store = RecordingStore()
    annotator = Annotator(store)
    somewhere_else = FakeWidget("Entry", _AN_ENTRY_HANDLE)
    root = FakeRoot(FakeInterpreter("8.6.15", "win32", native=False))
    annotator.add(somewhere_else)

    # When the application asks what it has told Windows about this root
    description = describe(root, Installation(Strategy.ANNOTATED, annotator))

    # Then the entry is named as unaccounted for rather than silently left out.
    # A report that dropped it would hide the two things worth knowing: that
    # `describe` was handed something that is not the real root, and that an
    # annotation is alive for a widget nothing here can find.
    assert description.orphans == (str(somewhere_else),), (
        f"the description accounts for {description.orphans}, so an annotation "
        "the walk never reached has gone missing from the report entirely"
    )


def test_describing_a_tk_that_was_never_annotated_says_so_before_it_says_anything_else() -> (
    None
):
    # Given the same application, running where MSAA does not exist, having
    # switched accessibility on and been told plainly that nothing happened
    store = RecordingStore()
    label = FakeWidget("Label", _A_LABEL_HANDLE, text="Task list")
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task")
    root = FakeRoot(
        FakeInterpreter("8.6.15", "x11", native=False), children=[label, button]
    )
    installation = install(root, store)

    # When the application asks what it has told Windows
    description = describe(root, installation)

    # Then the strategy is carried on the description, and every widget in the
    # window is named as carrying nothing. This is the highest-value case in the
    # whole feature: a report that showed only successes would render an
    # application where the gate mis-fired as a blank page, and let its author
    # read that as a clean bill of health.
    assert description.strategy is Strategy.UNSUPPORTED, (
        f"the description claims {description.strategy}"
    )
    assert [widget.gaps for widget in description.widgets] == [
        (Gap.NAMED_BY_ITS_TITLE,),
        (Gap.NOTHING_WRITTEN,),
        (Gap.NOTHING_WRITTEN,),
    ], f"an unannotated window is described as {description}"


def test_describing_from_a_thread_other_than_the_one_that_owns_the_widgets_is_refused() -> (
    None
):
    # Given an application that switched accessibility on from the thread
    # running Tk's event loop, as every application does
    store = RecordingStore()
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task")
    root = FakeRoot(FakeInterpreter("8.6.15", "win32", native=False), children=[button])
    installation = install(root, store)

    # When a background worker asks what the application has told Windows —
    # the ordinary shape of a thread that wants to log the state of the window
    refusal = the_failure_raised_on_another_thread(lambda: describe(root, installation))

    # Then it is stopped at the door. Describing asks every widget for its
    # class, its options, its text, its handle and whether it is mapped: six
    # kinds of trip into the Tcl interpreter, each of which corrupts it quietly
    # from a foreign thread. The widget double refuses a foreign caller itself,
    # so a `FakeTclError` here would mean the guard fired after Tk was reached.
    assert isinstance(refusal, AnnotationRefused), (
        f"a foreign thread got through to Tk with {refusal!r}; the refusal has "
        "to come before the first winfo call, not after it"
    )
    assert "thread" in str(refusal), (
        f"the reader has to be told which rule they broke: {refusal}"
    )


def test_the_report_prints_one_row_for_every_widget_saying_what_was_written_about_it() -> (
    None
):
    # Given a small window, annotated the way an application would annotate it
    store = RecordingStore()
    annotator = Annotator(store)
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task")
    entry = FakeWidget("Entry", _AN_ENTRY_HANDLE)
    root = FakeRoot(
        FakeInterpreter("8.6.15", "win32", native=False), children=[button, entry]
    )
    annotator.add(button)
    annotator.add(entry)
    annotator.set_automation_id(button, _AN_ID_THE_APPLICATION_CHOSE)
    annotator.set_description(button, "creates a task and clears the form")

    # When the description is printed, which is what an author at a REPL does
    printed = str(describe(root, Installation(Strategy.ANNOTATED, annotator)))

    # Then every widget has a row, and the row carries everything a client was
    # told. The Tk path is never truncated: finding the widget in your own
    # source is the point, and a shortened path cannot be grepped for.
    assert _the_line_about(printed, str(button)).split() == [
        str(button),
        "Button",
        "PUSH_BUTTON",
        "(43)",
        "'New",
        "Task'",
        "-",
        str(_AN_ID_THE_APPLICATION_CHOSE),
    ], f"the button's row reads {_the_line_about(printed, str(button))!r}"

    # And the properties no column has room for are reported rather than
    # dropped, on a line of their own beneath it
    assert (
        "also written: DESCRIPTION='creates a task and clears the form'" in printed
    ), f"four properties that were written are missing from the report:\n{printed}"
    assert [str(root), str(entry)] == [
        path for path in (str(root), str(entry)) if _the_line_about(printed, path)
    ], f"a widget in the window has no row at all:\n{printed}"


def test_the_report_prints_the_reason_for_every_gap_beside_the_widgets_it_applies_to() -> (
    None
):
    # Given a window holding a canvas nobody has a role for and an entry nobody
    # named, under a root this package leaves to `wm title` on purpose
    store = RecordingStore()
    annotator = Annotator(store)
    canvas = FakeWidget("Canvas", _A_CANVAS_HANDLE)
    entry = FakeWidget("Entry", _AN_ENTRY_HANDLE)
    root = FakeRoot(
        FakeInterpreter("8.6.15", "win32", native=False), children=[canvas, entry]
    )
    annotator.add(entry)

    # When the description is printed
    printed = str(describe(root, Installation(Strategy.ANNOTATED, annotator)))

    # Then each reason is a block, headed by how many widgets carry it, with the
    # prose that says what to do about it and the paths it applies to beneath
    assert "NO_VALUE  (1)" in printed, f"no counted block for NO_VALUE:\n{printed}"
    assert "The role gives this widget a ValuePattern it did" in printed, (
        f"the reason is named and never explained:\n{printed}"
    )
    assert f"      {entry}  (Entry)" in printed, (
        f"the widgets a reason applies to are not listed under it:\n{printed}"
    )

    # And the one that is not a fault is under a heading of its own, so that a
    # reader counting the things to fix does not count the windows among them
    assert printed.index(_LEFT_ALONE) > printed.index(f"      {canvas}  (Canvas)"), (
        f"a window this package refuses to touch is filed with the failures:\n{printed}"
    )
    assert printed.index(f"      {root}  (Tk)") > printed.index(_LEFT_ALONE), (
        f"the root is not under {_LEFT_ALONE!r}:\n{printed}"
    )


def test_the_report_opens_with_the_strategy_so_a_page_of_blanks_cannot_be_read_as_a_clean_bill_of_health() -> (
    None
):
    # Given the same application running where MSAA does not exist, so that not
    # one widget in the window was ever annotated
    store = RecordingStore()
    label = FakeWidget("Label", _A_LABEL_HANDLE, text="Task list")
    root = FakeRoot(FakeInterpreter("8.6.15", "x11", native=False), children=[label])
    installation = install(root, store)

    # When the description is printed
    printed = str(describe(root, installation))

    # Then the first thing it says is that nothing here was annotated, before
    # any row of the table. This is the reason the whole feature is worth
    # shipping: a report that showed only successes would render this window as
    # a blank page, and its author would read that as everything being fine.
    assert printed.index(Strategy.UNSUPPORTED.name) < printed.index(_THE_TABLE), (
        f"the strategy does not lead the report:\n{printed}"
    )
    assert __version__ in printed, (
        f"the report does not say which version wrote it:\n{printed}"
    )


def test_the_report_closes_by_saying_this_is_what_was_written_and_not_proof_a_client_can_read_it() -> (
    None
):
    # Given an application that annotated a widget and got `S_OK` back, as it
    # would have got for a write to a window handle nobody owns
    store = RecordingStore()
    annotator = Annotator(store)
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task")
    root = FakeRoot(FakeInterpreter("8.6.15", "win32", native=False), children=[button])
    annotator.add(button)

    # When the description is printed
    printed = str(describe(root, Installation(Strategy.ANNOTATED, annotator)))

    # Then the last thing it says is that none of it is evidence. This spec
    # exists so that the caveat cannot be deleted quietly: every row above it is
    # what this package *believes* it wrote, and the difference between that and
    # what a client reads is the entire class of bug this library has.
    closing = printed[printed.index(_THE_CLOSING_CAVEAT_BEGINS) :]

    assert "S_OK" in closing, f"the report does not name the silence:\n{printed}"
    assert "another process" in closing, (
        f"the report does not say what would count as proof:\n{printed}"
    )
    assert printed.rstrip().endswith(closing.rstrip()), (
        f"something was printed after the caveat, which is where it stops "
        f"being the last word:\n{printed}"
    )


def test_an_annotation_the_walk_never_reached_is_printed_and_not_only_kept_in_the_data() -> (
    None
):
    # Given an annotated widget the walk from this root will never reach
    store = RecordingStore()
    annotator = Annotator(store)
    somewhere_else = FakeWidget("Entry", _AN_ENTRY_HANDLE)
    root = FakeRoot(FakeInterpreter("8.6.15", "win32", native=False))
    annotator.add(somewhere_else)

    # When the description is printed
    printed = str(describe(root, Installation(Strategy.ANNOTATED, annotator)))

    # Then it says so. The whole principle of this report is that it must not
    # quietly omit what it cannot see, and an annotation alive for a widget the
    # walk cannot find is exactly that — carried in the data and dropped from
    # the page is the same silence in a different place.
    assert str(somewhere_else) in printed, (
        f"an annotation the walk never reached is missing from the page:\n{printed}"
    )


def _the_line_about(printed: str, path: str) -> str:
    for line in printed.splitlines():
        if line.startswith(f"{path} "):
            return line
    raise AssertionError(f"no row for {path} in:\n{printed}")


def _what_the_description_says_about(
    description: Description, path: str
) -> WidgetDescription:
    for widget in description.widgets:
        if widget.path == path:
            return widget
    raise AssertionError(f"{path} is not in the description at all: {description}")
