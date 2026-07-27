"""Behavioral spec for what an application is told it has told Windows.

The description is a reading of the annotation ledger and a walk of the widget
tree, so it is specified against the same doubles the annotator's own specs use.
So is the report a reader prints, which puts the whole feature in the lane that
needs no Tk, no display and no Windows.
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
_A_PROGRESSBAR_HANDLE = 0x000A0D11
_A_SPINBOX_HANDLE = 0x000407AB
_A_SECOND_BUTTON_HANDLE = 0x000407AC
_A_SECOND_ENTRY_HANDLE = 0x000407AD
_A_SECOND_DIALOG_HANDLE = 0x000407AE
_A_RECYCLED_HANDLE = 0x000508B1
_AN_ID_THE_APPLICATION_CHOSE = 4207

# What Tcl calls the first `StringVar` an application makes.
_A_DECLARED_VARIABLE = "PY_VAR0"

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

    # Then it is told, per widget, what was written. Every failure mode here
    # returns `S_OK` and does nothing, so silence and success read alike.
    said = _what_the_description_says_about(description, str(button))

    assert (said.role, said.name) == (Role.PUSH_BUTTON, "New Task"), (
        f"the description reports role {said.role} and name {said.name!r} for a "
        "button annotated as a named push button"
    )


def test_a_widget_whose_class_has_no_role_is_named_as_unwritten_rather_than_left_out_of_the_report() -> (
    None
):
    # Given somebody's own widget nested inside a frame. Every class both
    # toolkits ship has a role, so the only widget `enable()` walks past is one
    # registered under a class name it has never seen.
    store = RecordingStore()
    annotator = Annotator(store)
    homemade = FakeWidget("SparklineChart", _A_CANVAS_HANDLE)
    frame = FakeWidget("Frame", _A_FRAME_HANDLE, children=[homemade])
    root = FakeRoot(FakeInterpreter("8.6.15", "win32", native=False), children=[frame])
    annotator.add(frame)
    annotator.add(homemade)

    # When the application asks what it has told Windows
    description = describe(root, Installation(Strategy.ANNOTATED, annotator))

    # Then it is in the report, by its path, with the reason nothing was written
    # about it. A description listing only successes would render an application
    # nobody annotated as a blank page.
    said = _what_the_description_says_about(description, str(homemade))

    assert said.gaps == (Gap.NO_ROLE_FOR_ITS_CLASS,), (
        f"the canvas is reported with gaps {said.gaps}, so a reader is not told "
        "why a widget in their own window carries nothing"
    )


def test_a_widget_tk_never_mapped_is_reported_as_never_mapped_and_not_as_a_missing_role() -> (
    None
):
    # Given a frame the geometry manager never found room for. A fixed
    # `geometry()` silently drops whatever the packer cannot fit: `<Map>` never
    # fires, so the sweep never sees it and nothing anywhere raises.
    store = RecordingStore()
    annotator = Annotator(store)
    never_fitted = FakeWidget("Frame", _A_FRAME_HANDLE, mapped=False)
    root = FakeRoot(
        FakeInterpreter("8.6.15", "win32", native=False), children=[never_fitted]
    )

    # When the application asks what it has told Windows
    description = describe(root, Installation(Strategy.ANNOTATED, annotator))

    # Then it is told the widget was never mapped rather than that its class has
    # no role. Two reasons apply to a widget at once more often than they look
    # like they will, and which one is reported is the value of the line.
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
    # something this package refuses on purpose.
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
    # Given a button on screen, in a window where nothing was ever annotated:
    # the version gate stood down, or `enable()` was called before the widget
    # existed
    store = RecordingStore()
    annotator = Annotator(store)
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task")
    root = FakeRoot(FakeInterpreter("8.6.15", "win32", native=False), children=[button])

    # When the application asks what it has told Windows
    description = describe(root, Installation(Strategy.ANNOTATED, annotator))

    # Then the widget is reported as showing, roleable, and carrying nothing:
    # a different complaint from either of the two above it, and the only one
    # that means something has actually gone wrong.
    said = _what_the_description_says_about(description, str(button))

    assert said.gaps == (Gap.NOTHING_WRITTEN,), (
        f"a mapped button whose class has a role is reported as {said.gaps}, "
        "which sends the reader looking for a mapping problem that is not there"
    )


def test_a_class_the_application_gave_a_role_to_is_never_reported_as_a_class_with_no_role() -> (
    None
):
    # Given an application that has already done what the report would tell it
    # to do, naming its canvas in `enable(root, roles=...)`, and a canvas the
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
    # that.
    said = _what_the_description_says_about(description, str(canvas))

    assert said.gaps == (Gap.NEVER_MAPPED,), (
        f"a class the caller added a role for is reported as {said.gaps}, so "
        "the report is reading a role table the application is not using"
    )


def test_an_annotated_entry_is_reported_as_having_neither_a_name_nor_a_value_a_client_can_read() -> (
    None
):
    # Given an entry that `enable()` annotated and the application said no more
    # about: no `-text` to be named from, and its contents in a variable
    store = RecordingStore()
    annotator = Annotator(store)
    entry = FakeWidget("Entry", _AN_ENTRY_HANDLE)
    root = FakeRoot(FakeInterpreter("8.6.15", "win32", native=False), children=[entry])
    annotator.add(entry)

    # When the application asks what it has told Windows
    description = describe(root, Installation(Strategy.ANNOTATED, annotator))

    # Then both halves are named. The role alone gave this widget a ValuePattern
    # it did not have before, and until something writes one it answers `''`:
    # the one place in this package where annotating leaves a client worse
    # informed than bare Tk did.
    said = _what_the_description_says_about(description, str(entry))

    assert said.gaps == (Gap.NO_NAME, Gap.NO_VALUE), (
        f"an annotated entry nobody named or filled in is reported as "
        f"{said.gaps}, so the reader is not told what a client will read"
    )


def test_an_annotated_spinbox_with_nothing_in_it_is_reported_as_having_no_value() -> (
    None
):
    # Given a spinbox that `enable()` annotated and the application said no more
    # about: the quantity box in a form, showing a number nobody introduced
    store = RecordingStore()
    annotator = Annotator(store)
    spinbox = FakeWidget("Spinbox", _A_SPINBOX_HANDLE)
    root = FakeRoot(
        FakeInterpreter("8.6.15", "win32", native=False), children=[spinbox]
    )
    annotator.add(spinbox)

    # When the application asks what it has told Windows
    description = describe(root, Installation(Strategy.ANNOTATED, annotator))

    # Then the value is reported missing, exactly as an entry's is. COVERAGE.md
    # measures this one from another process: an annotated spinbox reaches a
    # client as a `SpinnerControl` carrying a ValuePattern.
    said = _what_the_description_says_about(description, str(spinbox))

    assert said.gaps == (Gap.NO_NAME, Gap.NO_VALUE), (
        f"an annotated spinbox nobody named or filled in is reported as "
        f"{said.gaps}, so a control a client will ask the contents of is "
        "described as complete while it answers ''"
    )


def test_an_annotated_progressbar_is_reported_as_having_no_value_until_one_is_said() -> (
    None
):
    # Given a progressbar `enable()` annotated and the application said no more
    # about, showing 40 percent on screen the whole time
    store = RecordingStore()
    annotator = Annotator(store)
    progressbar = FakeWidget("TProgressbar", _A_PROGRESSBAR_HANDLE)
    root = FakeRoot(
        FakeInterpreter("8.6.15", "win32", native=False), children=[progressbar]
    )
    annotator.add(progressbar)

    # When the application asks what it has told Windows
    description = describe(root, Installation(Strategy.ANNOTATED, annotator))

    # Then the value is reported missing. Measured cross-process, three ways: an
    # annotated progressbar's ValuePattern answers '' with nothing written, and
    # still '' after the widget's own -value moved from 10 to 90. Only
    # set_acc_value reads back, so a bar visibly at 40 percent says nothing.
    said = _what_the_description_says_about(description, str(progressbar))

    assert Gap.NO_VALUE in said.gaps, (
        f"{said.gaps}: a progressbar whose pattern answers '' is described as "
        "complete while the widget shows a number"
    )


def test_a_spinbox_whose_value_was_written_is_not_reported_as_missing_one() -> None:
    # Given the same spinbox, with the application having said what is in it
    store = RecordingStore()
    annotator = Annotator(store)
    spinbox = FakeWidget("Spinbox", _A_SPINBOX_HANDLE)
    root = FakeRoot(
        FakeInterpreter("8.6.15", "win32", native=False), children=[spinbox]
    )
    annotator.add(spinbox)
    annotator.set_value(spinbox, "3")

    # When the application asks what it has told Windows
    description = describe(root, Installation(Strategy.ANNOTATED, annotator))

    # Then nothing is held against it. The gap is a missing value and not the
    # role that offers one.
    said = _what_the_description_says_about(description, str(spinbox))

    assert Gap.NO_VALUE not in said.gaps, (
        f"a spinbox carrying the value '3' is reported as {said.gaps}"
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

    # Then neither is held against it. A signal-to-noise decision, pinned so
    # that changing it has to be deliberate: a report flagging every container
    # would bury the one entry that genuinely needs a name.
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

    # Then each is reported as findable and hollow: a screen-reader user can
    # find the listbox and cannot hear what is in it.
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

    # Then the tabs are named as reachable rather than reported missing.
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
    # Given a widget annotated while it was on screen, and which Tk has since
    # taken off it. An unselected notebook tab is the everyday case.
    store = RecordingStore()
    annotator = Annotator(store)
    entry = FakeWidget("Entry", _AN_ENTRY_HANDLE)
    root = FakeRoot(FakeInterpreter("8.6.15", "win32", native=False), children=[entry])
    annotator.add(entry)
    annotator.set_name(entry, "Host")
    entry.is_taken_off_the_screen()

    # When the application asks what it has told Windows
    description = describe(root, Installation(Strategy.ANNOTATED, annotator))

    # Then it is reported as out of reach rather than as written: UI Automation
    # does not list an unmapped window, however intact the annotation on it is.
    said = _what_the_description_says_about(description, str(entry))
    assert said.gaps == (Gap.UNMAPPED_SINCE_ANNOTATED,), (
        f"reported {said.gaps} for a widget nothing can currently read"
    )
    # And the row still shows what was written, because it is all still there.
    # The widget comes back the moment Tk maps it again.
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
    # Both patterns lie: every Tk button is owner-drawn, and the proxy
    # synthesises Invoke from a `BM_CLICK` nothing is listening for.
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
    # 'Task list'. A stale answer reads exactly like a true one.
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
    # encouraged pattern, and a diagnostic that cries wolf gets ignored.
    said = _what_the_description_says_about(description, str(button))

    assert Gap.NAME_MAY_BE_STALE not in said.gaps, (
        f"a name the application chose over a shorter caption is reported as "
        f"possibly stale: {said.gaps}"
    )


def test_two_widgets_a_client_cannot_tell_apart_are_both_reported_as_ambiguous() -> (
    None
):
    # Given the shape measured on a real settings dialog: two `Browse...`
    # buttons on one tab, each correctly typed, each correctly named, and named
    # identically
    store = RecordingStore()
    annotator = Annotator(store)
    for_the_executable = FakeWidget("Button", _A_BUTTON_HANDLE, text="Browse...")
    for_the_log = FakeWidget("Button", _A_SECOND_BUTTON_HANDLE, text="Browse...")
    root = FakeRoot(
        FakeInterpreter("8.6.15", "win32", native=False),
        children=[for_the_executable, for_the_log],
    )
    annotator.add(for_the_executable)
    annotator.add(for_the_log)

    # When the application asks what it has told Windows
    description = describe(root, Installation(Strategy.ANNOTATED, annotator))

    # Then both are named as ambiguous. Nothing is wrong with either widget on
    # its own, which is why no per-widget check can see this: a client asking
    # for "the Browse... button" reaches one of the two at random.
    said = [
        _what_the_description_says_about(description, str(widget))
        for widget in (for_the_executable, for_the_log)
    ]

    assert [Gap.NAME_NOT_UNIQUE in widget.gaps for widget in said] == [True, True], (
        f"two buttons a client cannot choose between are reported as "
        f"{[widget.gaps for widget in said]}"
    )


def test_the_ambiguity_is_added_to_what_a_widget_is_already_missing_rather_than_replacing_it() -> (
    None
):
    # Given those same two buttons, which like every Tk button also advertise an
    # InvokePattern that presses nothing
    store = RecordingStore()
    annotator = Annotator(store)
    for_the_executable = FakeWidget("Button", _A_BUTTON_HANDLE, text="Browse...")
    for_the_log = FakeWidget("Button", _A_SECOND_BUTTON_HANDLE, text="Browse...")
    root = FakeRoot(
        FakeInterpreter("8.6.15", "win32", native=False),
        children=[for_the_executable, for_the_log],
    )
    annotator.add(for_the_executable)
    annotator.add(for_the_log)

    # When the application asks what it has told Windows
    description = describe(root, Installation(Strategy.ANNOTATED, annotator))

    # Then the widget carries both reasons. This one is additive where
    # UNMAPPED_SINCE_ANNOTATED replaces, and the difference is whether the other
    # reasons are still true: two buttons that cannot be told apart are still
    # two buttons that cannot be pressed.
    said = _what_the_description_says_about(description, str(for_the_log))

    assert said.gaps == (Gap.CANNOT_BE_PRESSED, Gap.NAME_NOT_UNIQUE), (
        f"a duplicate-named button is reported as {said.gaps}, so a reason that "
        "was true before the second button existed has been dropped"
    )


def test_the_same_name_on_two_different_roles_is_not_reported_as_ambiguous() -> None:
    # Given a heading and a button that both read "Options": a section captioned
    # above the control that opens it
    store = RecordingStore()
    annotator = Annotator(store)
    heading = FakeWidget("Label", _A_LABEL_HANDLE, text="Options")
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="Options")
    root = FakeRoot(
        FakeInterpreter("8.6.15", "win32", native=False), children=[heading, button]
    )
    annotator.add(heading)
    annotator.add(button)

    # When the application asks what it has told Windows
    description = describe(root, Installation(Strategy.ANNOTATED, annotator))

    # Then neither is held against it. A query names a control type as well as a
    # name, so `app.text("Options")` and `app.button("Options")` reach one
    # widget each.
    said = [
        _what_the_description_says_about(description, str(widget))
        for widget in (heading, button)
    ]

    assert not any(Gap.NAME_NOT_UNIQUE in widget.gaps for widget in said), (
        f"a label and a button sharing a caption are reported as "
        f"{[widget.gaps for widget in said]}"
    )


def test_widgets_nobody_named_are_never_reported_as_ambiguous_with_one_another() -> (
    None
):
    # Given two entries in a form, neither named, which is the state `enable()`
    # alone leaves every entry in
    store = RecordingStore()
    annotator = Annotator(store)
    host = FakeWidget("Entry", _AN_ENTRY_HANDLE)
    port = FakeWidget("Entry", _A_SECOND_ENTRY_HANDLE)
    root = FakeRoot(
        FakeInterpreter("8.6.15", "win32", native=False), children=[host, port]
    )
    annotator.add(host)
    annotator.add(port)

    # When the application asks what it has told Windows
    description = describe(root, Installation(Strategy.ANNOTATED, annotator))

    # Then neither is reported as a duplicate of the other. Both are already
    # reported as NO_NAME, which is the fix and is one call each; the advice
    # under NAME_NOT_UNIQUE is to qualify a caption neither of them has.
    said = [
        _what_the_description_says_about(description, str(widget))
        for widget in (host, port)
    ]

    assert [widget.gaps for widget in said] == [(Gap.NO_NAME, Gap.NO_VALUE)] * 2, (
        f"two nameless entries are reported as {[widget.gaps for widget in said]}"
    )


def test_the_same_control_in_two_windows_is_not_a_collision_because_a_client_asks_one_window_at_a_time() -> (
    None
):
    # Given a dialog's "Confirm" button and the main window's own
    store = RecordingStore()
    annotator = Annotator(store)
    in_the_dialog = FakeWidget(
        "Button", _A_BUTTON_HANDLE, text="Confirm", path=".!toplevel.!button"
    )
    dialog = FakeWidget(
        "Toplevel", _A_DIALOG_HANDLE, path=".!toplevel", children=[in_the_dialog]
    )
    in_the_main_window = FakeWidget(
        "Button", _A_SECOND_BUTTON_HANDLE, text="Confirm", path=".!button"
    )
    root = FakeRoot(
        FakeInterpreter("8.6.15", "win32", native=False),
        children=[dialog, in_the_main_window],
    )
    annotator.add(in_the_dialog)
    annotator.add(in_the_main_window)

    # When the application asks what it has told Windows
    description = describe(root, Installation(Strategy.ANNOTATED, annotator))

    # Then neither is reported as ambiguous. Ambiguity is counted per window
    # because that is how a client resolves one: every query finds the window by
    # its title and searches inside it. Counting it globally would flag the OK
    # button of every dialog an application has.
    said = [
        _what_the_description_says_about(description, str(widget))
        for widget in (in_the_dialog, in_the_main_window)
    ]

    assert not any(Gap.NAME_NOT_UNIQUE in widget.gaps for widget in said), (
        f"the same button in two windows is reported as "
        f"{[widget.gaps for widget in said]}"
    )


def test_a_window_whose_path_merely_begins_with_anothers_is_still_a_different_window() -> (
    None
):
    # Given two dialogs whose Tk paths differ only by a digit on the end, each
    # with a "Confirm" of its own. `.!toplevel22` begins with the whole of
    # `.!toplevel2` and is not inside it: Tk separates a path by segments.
    store = RecordingStore()
    annotator = Annotator(store)
    in_the_second = FakeWidget(
        "Button", _A_BUTTON_HANDLE, text="Confirm", path=".!toplevel2.!button"
    )
    second = FakeWidget(
        "Toplevel", _A_DIALOG_HANDLE, path=".!toplevel2", children=[in_the_second]
    )
    in_the_twenty_second = FakeWidget(
        "Button", _A_SECOND_BUTTON_HANDLE, text="Confirm", path=".!toplevel22.!button"
    )
    twenty_second = FakeWidget(
        "Toplevel",
        _A_SECOND_DIALOG_HANDLE,
        path=".!toplevel22",
        children=[in_the_twenty_second],
    )
    root = FakeRoot(
        FakeInterpreter("8.6.15", "win32", native=False),
        children=[second, twenty_second],
    )
    annotator.add(in_the_second)
    annotator.add(in_the_twenty_second)

    # When the application asks what it has told Windows
    description = describe(root, Installation(Strategy.ANNOTATED, annotator))

    # Then neither is reported as ambiguous. These two windows share eleven
    # characters and hold nothing of each other, so each "Confirm" is the only
    # answer to the only question that will be asked of it.
    said = [
        _what_the_description_says_about(description, str(widget))
        for widget in (in_the_second, in_the_twenty_second)
    ]

    assert not any(Gap.NAME_NOT_UNIQUE in widget.gaps for widget in said), (
        f"buttons in `.!toplevel2` and `.!toplevel22` are reported as "
        f"{[widget.gaps for widget in said]}, so two windows that merely read "
        "alike were scoped as one"
    )


def test_the_report_says_which_properties_a_variable_is_keeping_in_step_so_a_reader_knows_they_will_not_go_stale() -> (
    None
):
    # Given a status label showing "ready" and bound to a variable that already
    # holds "ready", the ordinary shape of a startup. The ledger skips the COM
    # write, which is the job it exists for.
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
    # the value came from.
    said = _what_the_description_says_about(description, str(label))

    assert said.kept_in_step == (PropId.NAME,), (
        f"a bound name is reported as kept in step by {said.kept_in_step}"
    )
    assert Gap.NAME_MAY_BE_STALE not in said.gaps, (
        f"a name a variable is keeping in step is reported as stale: {said.gaps}"
    )


def test_a_widget_following_the_variable_it_declares_is_reported_as_kept_in_step() -> (
    None
):
    # Given a status label driven by a `textvariable` and bound by nobody, whose
    # variable has moved on since. Tk keeps a classic label's `-text` in step
    # with its variable, so both sides move together.
    store = RecordingStore()
    status = FakeVariable("ready")
    annotator = Annotator(
        store, variables=VariablesByName({_A_DECLARED_VARIABLE: status})
    )
    label = FakeWidget(
        "Label", _A_LABEL_HANDLE, text="ready", textvariable=_A_DECLARED_VARIABLE
    )
    root = FakeRoot(FakeInterpreter("8.6.15", "win32", native=False), children=[label])
    annotator.add(label)
    status.set("task created")
    label.says_something_else("task created")

    # When the application asks what it has told Windows
    description = describe(root, Installation(Strategy.ANNOTATED, annotator))

    # Then the report says a variable is keeping this name true, and nothing
    # asks the author to go and fix it. A widget looking after itself listed
    # beside the ones that are genuinely wrong is how the list stops being read.
    said = _what_the_description_says_about(description, str(label))

    assert said.name == "task created", (
        f"the report says the label is announcing {said.name!r} after its own "
        "variable moved on"
    )
    assert said.kept_in_step == (PropId.NAME,), (
        f"a name followed from the widget's own -textvariable is reported as "
        f"kept in step by {said.kept_in_step}"
    )
    assert Gap.NAME_MAY_BE_STALE not in said.gaps, (
        f"a widget that needs nothing from its author is reported as {said.gaps}"
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
    # report reading only the properties would show it as absent.
    said = _what_the_description_says_about(description, str(button))

    assert said.automation_id == _AN_ID_THE_APPLICATION_CHOSE, (
        f"the button is reported carrying automation id {said.automation_id}"
    )


def test_every_other_property_that_was_written_is_reported_rather_than_only_the_four_in_the_table() -> (
    None
):
    # Given a button the application has filled in completely: the four
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

    # Then all four come back. A report that must not quietly omit what it
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
    # fresh window, as it does whenever a frame is torn down and laid out again,
    # with nothing having re-annotated it
    store = RecordingStore()
    annotator = Annotator(store)
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task")
    root = FakeRoot(FakeInterpreter("8.6.15", "win32", native=False), children=[button])
    annotator.add(button)
    button.take_a_new_handle(_A_RECYCLED_HANDLE)

    # When the application asks what it has told Windows
    description = describe(root, Installation(Strategy.ANNOTATED, annotator))

    # Then the report says so rather than repeating the annotation as if it were
    # in force. Everything in the ledger describes a window this widget no
    # longer owns, and the new one carries nothing.
    said = _what_the_description_says_about(description, str(button))

    assert said.gaps == (Gap.ANNOTATED_ON_A_HANDLE_IT_NO_LONGER_HAS,), (
        f"a rebuilt widget is reported as {said.gaps}, so the report is "
        "vouching for properties that are on a window nobody is looking at"
    )


def test_a_ledger_entry_whose_widget_is_no_longer_in_the_tree_is_named_rather_than_dropped() -> (
    None
):
    # Given an annotated widget the walk from this root will never reach: a
    # dialog's contents when the main window was the one described, or a widget
    # that went away without `<Destroy>` ever reaching the annotator
    store = RecordingStore()
    annotator = Annotator(store)
    somewhere_else = FakeWidget("Entry", _AN_ENTRY_HANDLE)
    root = FakeRoot(FakeInterpreter("8.6.15", "win32", native=False))
    annotator.add(somewhere_else)

    # When the application asks what it has told Windows about this root
    description = describe(root, Installation(Strategy.ANNOTATED, annotator))

    # Then the entry is named as unaccounted for rather than silently left out.
    # Dropping it would hide two things worth knowing: that `describe` was
    # handed something that is not the real root, and that an annotation is
    # alive for a widget nothing here can find.
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
    # window is named as carrying nothing. A report that showed only successes
    # would render a window where the gate mis-fired as a blank page.
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

    # When a background worker asks what the application has told Windows
    refusal = the_failure_raised_on_another_thread(lambda: describe(root, installation))

    # Then it is stopped at the door. Describing asks every widget for its
    # class, its options, its text, its handle and whether it is mapped: six
    # kinds of trip into the Tcl interpreter. The widget double refuses a
    # foreign caller itself, so a `FakeTclError` here would mean the guard fired
    # after Tk was reached.
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
    # told. The Tk path is never truncated, because a shortened path cannot be
    # grepped for in your own source.
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


def test_the_report_lists_the_widgets_a_client_cannot_tell_apart_by_path() -> None:
    # Given the two `Browse...` buttons, which is the state a reader has to be
    # able to find in their own source before they can qualify either caption
    store = RecordingStore()
    annotator = Annotator(store)
    for_the_executable = FakeWidget("Button", _A_BUTTON_HANDLE, text="Browse...")
    for_the_log = FakeWidget("Button", _A_SECOND_BUTTON_HANDLE, text="Browse...")
    root = FakeRoot(
        FakeInterpreter("8.6.15", "win32", native=False),
        children=[for_the_executable, for_the_log],
    )
    annotator.add(for_the_executable)
    annotator.add(for_the_log)

    # When the description is printed
    printed = str(describe(root, Installation(Strategy.ANNOTATED, annotator)))

    # Then the reason has a block of its own with both paths under it. Both Tk
    # paths are what turns this into a two-line fix.
    assert "NAME_NOT_UNIQUE  (2)" in printed, (
        f"no counted block for NAME_NOT_UNIQUE:\n{printed}"
    )
    assert "infer_names_from_layout" in printed, (
        f"the reason names no way out of it:\n{printed}"
    )
    assert [str(for_the_executable), str(for_the_log)] == [
        path
        for path in (str(for_the_executable), str(for_the_log))
        if f"      {path}  (Button)" in printed
    ], f"a widget a client cannot tell apart is not listed under it:\n{printed}"


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
    # any row of the table.
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
    # exists so that the caveat cannot be deleted quietly: the difference
    # between what was written and what a client reads is the entire class of
    # bug this library has.
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

    # Then it says so. Carried in the data and dropped from the page is the
    # same silence in a different place.
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
