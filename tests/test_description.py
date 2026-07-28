"""Behavioral spec for what an application is told it has told Windows."""

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
_A_MENU_HANDLE = 0x000407B7
_A_SECOND_FRAME_HANDLE = 0x000407B1
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

    # Then it is told, per widget, what was written
    said = _what_the_description_says_about(description, str(button))

    assert (said.role, said.name) == (Role.PUSH_BUTTON, "New Task"), (
        f"the description reports role {said.role} and name {said.name!r} for a "
        "button annotated as a named push button"
    )


def test_a_widget_whose_class_has_no_role_is_named_as_unwritten_rather_than_left_out_of_the_report() -> (
    None
):
    # Given somebody's own widget, of a class `enable()` has never seen, in a frame
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
    said = _what_the_description_says_about(description, str(homemade))

    assert said.gaps == (Gap.NO_ROLE_FOR_ITS_CLASS,), (
        f"the canvas is reported with gaps {said.gaps}, so a reader is not told "
        "why a widget in their own window carries nothing"
    )


def test_a_widget_tk_never_mapped_is_reported_as_never_mapped_and_not_as_a_missing_role() -> (
    None
):
    # Given a frame the geometry manager never found room for, so `<Map>` never fired
    store = RecordingStore()
    annotator = Annotator(store)
    never_fitted = FakeWidget("Frame", _A_FRAME_HANDLE, mapped=False)
    root = FakeRoot(
        FakeInterpreter("8.6.15", "win32", native=False), children=[never_fitted]
    )

    # When the application asks what it has told Windows
    description = describe(root, Installation(Strategy.ANNOTATED, annotator))

    # Then it is told the widget was never mapped, not that its class has no role
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

    # Then both windows are in the report, carrying the one reason that is not a fault
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
    # Given a button on screen, in a window where nothing was ever annotated
    store = RecordingStore()
    annotator = Annotator(store)
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task")
    root = FakeRoot(FakeInterpreter("8.6.15", "win32", native=False), children=[button])

    # When the application asks what it has told Windows
    description = describe(root, Installation(Strategy.ANNOTATED, annotator))

    # Then the widget is reported as showing, roleable, and carrying nothing
    said = _what_the_description_says_about(description, str(button))

    assert said.gaps == (Gap.NOTHING_WRITTEN,), (
        f"a mapped button whose class has a role is reported as {said.gaps}, "
        "which sends the reader looking for a mapping problem that is not there"
    )


def test_a_class_the_application_gave_a_role_to_is_never_reported_as_a_class_with_no_role() -> (
    None
):
    # Given a canvas the application gave a role to, which was then never mapped
    store = RecordingStore()
    annotator = Annotator(store, {"Canvas": Role.STATIC_TEXT})
    canvas = FakeWidget("Canvas", _A_CANVAS_HANDLE, mapped=False)
    root = FakeRoot(FakeInterpreter("8.6.15", "win32", native=False), children=[canvas])

    # When the application asks what it has told Windows
    description = describe(root, Installation(Strategy.ANNOTATED, annotator))

    # Then it is told the widget was never mapped, not that its class needs a role
    said = _what_the_description_says_about(description, str(canvas))

    assert said.gaps == (Gap.NEVER_MAPPED,), (
        f"a class the caller added a role for is reported as {said.gaps}, so "
        "the report is reading a role table the application is not using"
    )


def test_an_annotated_entry_is_reported_as_having_neither_a_name_nor_a_value_a_client_can_read() -> (
    None
):
    # Given an entry `enable()` annotated and the application said no more about
    store = RecordingStore()
    annotator = Annotator(store)
    entry = FakeWidget("Entry", _AN_ENTRY_HANDLE)
    root = FakeRoot(FakeInterpreter("8.6.15", "win32", native=False), children=[entry])
    annotator.add(entry)

    # When the application asks what it has told Windows
    description = describe(root, Installation(Strategy.ANNOTATED, annotator))

    # Then both halves are named: the role gave it a ValuePattern that answers `''`
    said = _what_the_description_says_about(description, str(entry))

    assert said.gaps == (Gap.NO_NAME, Gap.NO_VALUE), (
        f"an annotated entry nobody named or filled in is reported as "
        f"{said.gaps}, so the reader is not told what a client will read"
    )


def test_an_annotated_spinbox_with_nothing_in_it_is_reported_as_having_no_value() -> (
    None
):
    # Given a spinbox `enable()` annotated and the application said no more about
    store = RecordingStore()
    annotator = Annotator(store)
    spinbox = FakeWidget("Spinbox", _A_SPINBOX_HANDLE)
    root = FakeRoot(
        FakeInterpreter("8.6.15", "win32", native=False), children=[spinbox]
    )
    annotator.add(spinbox)

    # When the application asks what it has told Windows
    description = describe(root, Installation(Strategy.ANNOTATED, annotator))

    # Then the value is reported missing; measured cross-process, it has a ValuePattern
    said = _what_the_description_says_about(description, str(spinbox))

    assert said.gaps == (Gap.NO_NAME, Gap.NO_VALUE), (
        f"an annotated spinbox nobody named or filled in is reported as "
        f"{said.gaps}, so a control a client will ask the contents of is "
        "described as complete while it answers ''"
    )


def test_an_annotated_progressbar_is_reported_as_having_no_value_until_one_is_said() -> (
    None
):
    # Given a progressbar `enable()` annotated, showing 40 percent on screen
    store = RecordingStore()
    annotator = Annotator(store)
    progressbar = FakeWidget("TProgressbar", _A_PROGRESSBAR_HANDLE)
    root = FakeRoot(
        FakeInterpreter("8.6.15", "win32", native=False), children=[progressbar]
    )
    annotator.add(progressbar)

    # When the application asks what it has told Windows
    description = describe(root, Installation(Strategy.ANNOTATED, annotator))

    # Then the value is reported missing; measured, the pattern says '' at -value 90
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

    # Then nothing is held against it
    said = _what_the_description_says_about(description, str(spinbox))

    assert Gap.NO_VALUE not in said.gaps, (
        f"a spinbox carrying the value '3' is reported as {said.gaps}"
    )


def test_a_frame_is_not_reported_as_unnamed_because_a_grouping_is_not_what_a_screen_reader_announces() -> (
    None
):
    # Given the two widget kinds nobody names: layout frames, and a scrollbar
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

    # Then neither is held against it
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
    # Given the three widget kinds whose contents are the reason they exist
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

    # Then each is reported as findable and hollow
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


def test_a_root_given_its_own_class_name_is_still_reported_as_a_window() -> None:
    # Given tk.Tk(className='Idle'), which makes winfo_class() answer 'Idle'
    store = RecordingStore()
    annotator = Annotator(store)
    root = FakeRoot(FakeInterpreter("8.6.15", "win32", native=False), tk_class="Idle")

    # When the application asks what it has told Windows
    description = describe(root, Installation(Strategy.ANNOTATED, annotator))

    # Then the root reads as what it is: a window named by its title
    said = _what_the_description_says_about(description, str(root))
    assert said.gaps == (Gap.NAMED_BY_ITS_TITLE,), (
        f"a className root is reported as {said.gaps}"
    )


def test_a_menu_is_reported_as_natively_accessible_rather_than_as_a_hole() -> None:
    # Given a menubar, which Tk builds natively and never maps as a widget
    store = RecordingStore()
    annotator = Annotator(store)
    menu = FakeWidget("Menu", _A_MENU_HANDLE, mapped=False)
    root = FakeRoot(FakeInterpreter("8.6.15", "win32", native=False), children=[menu])

    # When the application asks what it has told Windows
    description = describe(root, Installation(Strategy.ANNOTATED, annotator))

    # Then it is left alone: a bare Tk window already shows a MenuBarControl
    said = _what_the_description_says_about(description, str(menu))
    assert said.gaps == (Gap.MENUS_ARE_NATIVE,), f"a menu is reported as {said.gaps}"
    assert Gap.MENUS_ARE_NATIVE in ON_PURPOSE, (
        "the menu reason reads as a fault unless the report files it under "
        "left alone on purpose"
    )


def test_a_widget_two_containers_both_claim_is_described_once() -> None:
    # Given a widget in two parents' child lists: on Thonny, 6 of 85 walked twice
    store = RecordingStore()
    annotator = Annotator(store)
    shared = FakeWidget("Entry", _AN_ENTRY_HANDLE)
    first = FakeWidget("Frame", _A_FRAME_HANDLE, children=[shared])
    second = FakeWidget("Frame", _A_SECOND_FRAME_HANDLE, children=[shared])
    root = FakeRoot(
        FakeInterpreter("8.6.15", "win32", native=False), children=[first, second]
    )
    annotator.add(shared)

    # When the application asks what it has told Windows
    description = describe(root, Installation(Strategy.ANNOTATED, annotator))

    # Then the widget is one row, not two
    described = [w.path for w in description.widgets if w.path == str(shared)]
    assert described == [str(shared)], (
        f"{len(described)} rows for one widget; the walk has no memory of what "
        "it has already yielded"
    )


def test_a_widget_tk_has_unmapped_since_it_was_annotated_is_reported_as_out_of_reach() -> (
    None
):
    # Given a widget annotated on screen, which Tk has since taken off it
    store = RecordingStore()
    annotator = Annotator(store)
    entry = FakeWidget("Entry", _AN_ENTRY_HANDLE)
    root = FakeRoot(FakeInterpreter("8.6.15", "win32", native=False), children=[entry])
    annotator.add(entry)
    annotator.set_name(entry, "Host")
    entry.is_taken_off_the_screen()

    # When the application asks what it has told Windows
    description = describe(root, Installation(Strategy.ANNOTATED, annotator))

    # Then it is out of reach: UI Automation does not list an unmapped window
    said = _what_the_description_says_about(description, str(entry))
    assert said.gaps == (Gap.UNMAPPED_SINCE_ANNOTATED,), (
        f"reported {said.gaps} for a widget nothing can currently read"
    )
    assert (said.role, said.name) == (Role.TEXT, "Host"), (
        f"the row lost what was written about it: role {said.role}, name {said.name!r}"
    )


def test_an_annotated_button_is_reported_as_advertising_an_invoke_pattern_that_presses_nothing() -> (
    None
):
    # Given a button annotated exactly as `enable()` leaves it
    store = RecordingStore()
    annotator = Annotator(store)
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task")
    root = FakeRoot(FakeInterpreter("8.6.15", "win32", native=False), children=[button])
    annotator.add(button)

    # When the application asks what it has told Windows
    description = describe(root, Installation(Strategy.ANNOTATED, annotator))

    # Then the caveat is repeated by path: Invoke is a `BM_CLICK` nothing listens for
    said = _what_the_description_says_about(description, str(button))

    assert said.gaps == (Gap.CANNOT_BE_PRESSED,), (
        f"an annotated button is reported as {said.gaps}, so a reader planning "
        "to drive this window through Invoke is not warned"
    )


def test_a_name_that_no_longer_matches_the_widgets_text_is_reported_as_possibly_stale() -> (
    None
):
    # Given a label annotated from its caption, which a `config(text=...)` changed
    store = RecordingStore()
    annotator = Annotator(store)
    label = FakeWidget("Label", _A_LABEL_HANDLE, text="Task list")
    root = FakeRoot(FakeInterpreter("8.6.15", "win32", native=False), children=[label])
    annotator.add(label)
    label.says_something_else("in progress")

    # When the application asks what it has told Windows
    description = describe(root, Installation(Strategy.ANNOTATED, annotator))

    # Then the disagreement is reported: `-text` is read at `<Map>` and never again
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
    # Given a button whose caption is short for the screen, named at length
    store = RecordingStore()
    annotator = Annotator(store)
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="OK")
    root = FakeRoot(FakeInterpreter("8.6.15", "win32", native=False), children=[button])
    annotator.add(button)
    annotator.set_name(button, "Confirm order")

    # When the application asks what it has told Windows
    description = describe(root, Installation(Strategy.ANNOTATED, annotator))

    # Then the disagreement between the two is not held against it
    said = _what_the_description_says_about(description, str(button))

    assert Gap.NAME_MAY_BE_STALE not in said.gaps, (
        f"a name the application chose over a shorter caption is reported as "
        f"possibly stale: {said.gaps}"
    )


def test_two_widgets_a_client_cannot_tell_apart_are_both_reported_as_ambiguous() -> (
    None
):
    # Given a form with two `Browse...` buttons
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

    # Then both are named as ambiguous
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
    # Given those same two buttons, which also advertise an InvokePattern
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

    # Then the widget carries both reasons
    said = _what_the_description_says_about(description, str(for_the_log))

    assert said.gaps == (Gap.CANNOT_BE_PRESSED, Gap.NAME_NOT_UNIQUE), (
        f"a duplicate-named button is reported as {said.gaps}, so a reason that "
        "was true before the second button existed has been dropped"
    )


def test_the_same_name_on_two_different_roles_is_not_reported_as_ambiguous() -> None:
    # Given a heading and a button that both read "Options"
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

    # Then neither is held against it: a query names a control type and a name
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
    # Given two entries in a form, neither named
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

    # Then neither is reported as a duplicate of the other
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

    # Then neither is ambiguous: a client finds a window by title and searches it
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
    # Given `.!toplevel22`, which begins with `.!toplevel2` and is not inside it
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

    # Then neither is reported as ambiguous
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
    # Given a label bound to a variable already holding what it shows: no COM write
    store = RecordingStore()
    annotator = Annotator(store)
    label = FakeWidget("Label", _A_LABEL_HANDLE, text="ready")
    root = FakeRoot(FakeInterpreter("8.6.15", "win32", native=False), children=[label])
    annotator.add(label)
    annotator.bind_text_variable(label, FakeVariable("ready"))
    label.says_something_else("in progress")

    # When the application asks what it has told Windows
    description = describe(root, Installation(Strategy.ANNOTATED, annotator))

    # Then the name is reported as kept true, not as stale
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
    # Given a label driven by a `textvariable`, whose `-text` Tk keeps in step with it
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

    # Then the report says a variable is keeping this name true
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
    # Given a button an application numbered by hand
    store = RecordingStore()
    annotator = Annotator(store)
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task")
    root = FakeRoot(FakeInterpreter("8.6.15", "win32", native=False), children=[button])
    annotator.add(button)
    annotator.set_automation_id(button, _AN_ID_THE_APPLICATION_CHOSE)

    # When the application asks what it has told Windows
    description = describe(root, Installation(Strategy.ANNOTATED, annotator))

    # Then the number is reported beside it: it goes to `GWLP_ID`, not the ledger
    said = _what_the_description_says_about(description, str(button))

    assert said.automation_id == _AN_ID_THE_APPLICATION_CHOSE, (
        f"the button is reported carrying automation id {said.automation_id}"
    )


def test_every_other_property_that_was_written_is_reported_rather_than_only_the_four_in_the_table() -> (
    None
):
    # Given a button the application has filled in completely
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

    # Then all four come back
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
    # Given an annotated button Tk has since rebuilt on a fresh handle
    store = RecordingStore()
    annotator = Annotator(store)
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task")
    root = FakeRoot(FakeInterpreter("8.6.15", "win32", native=False), children=[button])
    annotator.add(button)
    button.take_a_new_handle(_A_RECYCLED_HANDLE)

    # When the application asks what it has told Windows
    description = describe(root, Installation(Strategy.ANNOTATED, annotator))

    # Then the report says so rather than repeating the annotation as in force
    said = _what_the_description_says_about(description, str(button))

    assert said.gaps == (Gap.ANNOTATED_ON_A_HANDLE_IT_NO_LONGER_HAS,), (
        f"a rebuilt widget is reported as {said.gaps}, so the report is "
        "vouching for properties that are on a window nobody is looking at"
    )


def test_a_ledger_entry_whose_widget_is_no_longer_in_the_tree_is_named_rather_than_dropped() -> (
    None
):
    # Given an annotated widget the walk from this root will never reach
    store = RecordingStore()
    annotator = Annotator(store)
    somewhere_else = FakeWidget("Entry", _AN_ENTRY_HANDLE)
    root = FakeRoot(FakeInterpreter("8.6.15", "win32", native=False))
    annotator.add(somewhere_else)

    # When the application asks what it has told Windows about this root
    description = describe(root, Installation(Strategy.ANNOTATED, annotator))

    # Then the entry is named as unaccounted for rather than silently left out
    assert description.orphans == (str(somewhere_else),), (
        f"the description accounts for {description.orphans}, so an annotation "
        "the walk never reached has gone missing from the report entirely"
    )


def test_describing_a_tk_that_was_never_annotated_says_so_before_it_says_anything_else() -> (
    None
):
    # Given the same application running where MSAA does not exist
    store = RecordingStore()
    label = FakeWidget("Label", _A_LABEL_HANDLE, text="Task list")
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task")
    root = FakeRoot(
        FakeInterpreter("8.6.15", "x11", native=False), children=[label, button]
    )
    installation = install(root, store)

    # When the application asks what it has told Windows
    description = describe(root, installation)

    # Then the strategy is on the description and every widget carries nothing
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
    # Given an application that switched accessibility on from Tk's own thread
    store = RecordingStore()
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task")
    root = FakeRoot(FakeInterpreter("8.6.15", "win32", native=False), children=[button])
    installation = install(root, store)

    # When a background worker asks what the application has told Windows
    refusal = the_failure_raised_on_another_thread(lambda: describe(root, installation))

    # Then it is stopped at the door, before the first winfo call
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

    # Then every widget has a row carrying everything a client was told
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

    assert (
        "also written: DESCRIPTION='creates a task and clears the form'" in printed
    ), f"four properties that were written are missing from the report:\n{printed}"
    assert [str(root), str(entry)] == [
        path for path in (str(root), str(entry)) if _the_line_about(printed, path)
    ], f"a widget in the window has no row at all:\n{printed}"


def test_the_report_prints_the_reason_for_every_gap_beside_the_widgets_it_applies_to() -> (
    None
):
    # Given a canvas nobody has a role for and an entry nobody named
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

    # Then each reason is a block, headed by how many widgets carry it
    assert "NO_VALUE  (1)" in printed, f"no counted block for NO_VALUE:\n{printed}"
    assert "The role gives this widget a ValuePattern it did" in printed, (
        f"the reason is named and never explained:\n{printed}"
    )
    assert f"      {entry}  (Entry)" in printed, (
        f"the widgets a reason applies to are not listed under it:\n{printed}"
    )

    assert printed.index(_LEFT_ALONE) > printed.index(f"      {canvas}  (Canvas)"), (
        f"a window this package refuses to touch is filed with the failures:\n{printed}"
    )
    assert printed.index(f"      {root}  (Tk)") > printed.index(_LEFT_ALONE), (
        f"the root is not under {_LEFT_ALONE!r}:\n{printed}"
    )


def test_the_report_lists_the_widgets_a_client_cannot_tell_apart_by_path() -> None:
    # Given the two `Browse...` buttons
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

    # Then the reason has a block of its own with both paths under it
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
    # Given the same application running where MSAA does not exist
    store = RecordingStore()
    label = FakeWidget("Label", _A_LABEL_HANDLE, text="Task list")
    root = FakeRoot(FakeInterpreter("8.6.15", "x11", native=False), children=[label])
    installation = install(root, store)

    # When the description is printed
    printed = str(describe(root, installation))

    # Then the first thing it says is that nothing here was annotated
    assert printed.index(Strategy.UNSUPPORTED.name) < printed.index(_THE_TABLE), (
        f"the strategy does not lead the report:\n{printed}"
    )
    assert __version__ in printed, (
        f"the report does not say which version wrote it:\n{printed}"
    )


def test_the_report_closes_by_saying_this_is_what_was_written_and_not_proof_a_client_can_read_it() -> (
    None
):
    # Given an application that annotated a widget and got `S_OK` back
    store = RecordingStore()
    annotator = Annotator(store)
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task")
    root = FakeRoot(FakeInterpreter("8.6.15", "win32", native=False), children=[button])
    annotator.add(button)

    # When the description is printed
    printed = str(describe(root, Installation(Strategy.ANNOTATED, annotator)))

    # Then the last thing it says is that none of it is evidence
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

    # Then it says so
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


def _an_installation_with_providers(root, wiring_for=None):
    from tests.doubles import HeldPoster, RecordingPlatform
    from tk_uia.provide import Providers, WidgetWiring

    def _bare_wiring(widget):
        return WidgetWiring(
            words=lambda: None,
            is_enabled=lambda: True,
            post=HeldPoster(),
            still_there=widget.winfo_exists,
        )

    providers = Providers(
        RecordingPlatform(), wiring_for if wiring_for is not None else _bare_wiring
    )
    installation = install(root, RecordingStore(), providers=providers)
    return installation, providers


def test_the_report_says_which_patterns_each_widget_answers_for_itself() -> None:
    # Given a button answering UIA itself with a working Invoke
    from tests.doubles import HeldPoster, RecordingPlatform
    from tk_uia.provide import Providers, WidgetWiring

    class AnInvoke:
        def press(self) -> None: ...

        def offered(self) -> bool:
            return True

    def wiring(widget):
        return WidgetWiring(
            words=lambda: None,
            is_enabled=lambda: True,
            post=HeldPoster(),
            still_there=widget.winfo_exists,
            invoke=AnInvoke() if widget.winfo_class() == "Button" else None,
        )

    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task")
    root = FakeRoot(FakeInterpreter("8.6.15", "win32", native=False),
                    children=[button])
    providers = Providers(RecordingPlatform(), wiring)
    installation = install(root, RecordingStore(), providers=providers)

    # When the application asks what it has told Windows
    report = str(describe(root, installation))

    # Then the row says the widget answers for itself, and with what
    assert "answers UIA itself, with working: Invoke" in report, (
        f"the report never says what the button answers with:\n{report}"
    )


def test_a_provided_headline_counts_the_widgets_answering_for_themselves() -> None:
    # Given an installation where providers were wired in
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task")
    root = FakeRoot(FakeInterpreter("8.6.15", "win32", native=False),
                    children=[button])
    installation, _ = _an_installation_with_providers(root)

    # When the application asks
    report = str(describe(root, installation))

    # Then the headline says PROVIDED rather than claiming nothing was written
    assert "enable() reported PROVIDED" in report, (
        f"a provided installation was reported as something else:\n{report}"
    )
    assert "nothing here was annotated" not in report, (
        "PROVIDED fell into the stood-down headline and reads as a page of blanks"
    )


def test_a_widget_left_to_the_proxy_is_reported_with_the_reason() -> None:
    # Given a button the application left to the proxy
    button = FakeWidget("Button", _A_BUTTON_HANDLE, text="New Task")
    root = FakeRoot(FakeInterpreter("8.6.15", "win32", native=False),
                    children=[button])
    installation, providers = _an_installation_with_providers(root)
    providers.leave_to_the_proxy(button)

    # When the application asks
    report = str(describe(root, installation))

    # Then the choice is reported per widget, in its own words
    assert Gap.LEFT_TO_THE_PROXY.name in report, (
        f"the proxy choice is invisible in the report:\n{report}"
    )


def test_trouble_the_callback_machinery_swallowed_appears_in_the_report() -> None:
    # Given an installation whose callbacks swallowed something
    from tk_uia.provide import Trouble

    trouble = Trouble()
    trouble.note("window 0x1234, message 0x3d: something broke")
    root = FakeRoot(FakeInterpreter("8.6.15", "win32", native=False))
    installation = install(root, RecordingStore(), trouble=trouble)

    # When the application asks
    report = str(describe(root, installation))

    # Then the swallowed failure is the report's to show, nobody else's
    assert "WHAT THE PROVIDER MACHINERY SWALLOWED" in report, (
        f"swallowed trouble never surfaced:\n{report}"
    )
    assert "something broke" in report


def test_the_reason_providers_stood_down_reaches_the_headline() -> None:
    # Given an honest downgrade carrying its reason
    root = FakeRoot(FakeInterpreter("8.6.15", "win32", native=False))
    installation = install(
        root,
        RecordingStore(),
        providers_stood_down_because="this Tcl was built without threads",
    )

    # When the application asks
    report = str(describe(root, installation))

    # Then the report says why no widget answers for itself
    assert "built without threads" in report, (
        f"the stand-down reason never reached the report:\n{report}"
    )
