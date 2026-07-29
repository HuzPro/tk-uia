"""Behavioral spec for the row-and-label convention, applied on request."""

from __future__ import annotations

from tests.doubles import FakeVariable, FakeWidget, RecordingStore, VariablesByName
from tests.threads import the_failure_raised_on_another_thread
from tk_uia.annotate import (
    AnnotationRefused,
    Annotator,
    Installation,
    PropId,
    every_widget_under,
)
from tk_uia.layout import NamedByTheLayout, infer_names_from_layout
from tk_uia.tkversion import Strategy

_A_WINDOW = 0x000407A0
_A_DIALOG = 0x000407A1
_A_ROW = 0x000407A8
_A_SECOND_ROW = 0x000407A9
_A_CAPTION = 0x000407A5
_A_SECOND_CAPTION = 0x000407A6
_AN_ENTRY = 0x000407A3
_A_SECOND_ENTRY = 0x000407A7
_A_BUTTON = 0x000407A2

# What Tcl calls the first `StringVar` an application makes.
_THE_VARIABLE_THE_WIDGET_DECLARES = "PY_VAR0"

_THE_BINDING_ENABLE_MADE = 1


def a_window_of(*children: FakeWidget) -> FakeWidget:
    return FakeWidget("Tk", _A_WINDOW, children=children)


def a_row_of(*children: FakeWidget, hwnd: int = _A_ROW) -> FakeWidget:
    return FakeWidget("Frame", hwnd, children=children)


def already_annotated(root: FakeWidget, annotator: Annotator) -> None:
    for widget in every_widget_under(root):
        annotator.add(widget)


def the_convention_applied_to(
    root: FakeWidget, annotator: Annotator
) -> tuple[NamedByTheLayout, ...]:
    return infer_names_from_layout(root, Installation(Strategy.ANNOTATED, annotator))


def test_an_entry_beside_a_caption_is_named_after_it() -> None:
    # Given a caption and the entry it captions, side by side in a frame
    store = RecordingStore()
    annotator = Annotator(store)
    entry = FakeWidget("Entry", _AN_ENTRY)
    root = a_window_of(a_row_of(FakeWidget("Label", _A_CAPTION, text="Host:"), entry))
    already_annotated(root, annotator)

    # When the application asks for the convention its own layout follows
    the_convention_applied_to(root, annotator)

    # Then the entry answers to the caption beside it
    assert store.properties(_AN_ENTRY)[PropId.NAME] == "Host", (
        f"the entry was left as {store.properties(_AN_ENTRY)}, so a screen "
        "reader still announces an edit control and not what it is for"
    )


def test_widgets_packed_straight_onto_a_window_are_a_row_like_any_frame() -> None:
    # Given two rows that sit inside no frame at all: one on a window, one on a dialog
    store = RecordingStore()
    annotator = Annotator(store)
    on_the_window = FakeWidget("Entry", _AN_ENTRY)
    on_the_dialog = FakeWidget("Entry", _A_SECOND_ENTRY)
    root = a_window_of(
        FakeWidget("Label", _A_CAPTION, text="Host:"),
        on_the_window,
        FakeWidget(
            "Toplevel",
            _A_DIALOG,
            children=[
                FakeWidget("Label", _A_SECOND_CAPTION, text="Port:"),
                on_the_dialog,
            ],
        ),
    )
    already_annotated(root, annotator)

    # When the convention is applied to the whole application
    the_convention_applied_to(root, annotator)

    # Then both are named: a walk that visited only frames missed a real status line
    assert store.properties(_AN_ENTRY).get(PropId.NAME) == "Host", (
        f"the row packed onto the window itself was skipped: {store.properties(_AN_ENTRY)}"
    )
    assert store.properties(_A_SECOND_ENTRY).get(PropId.NAME) == "Port", (
        f"a dialog is a window with rows on it too: {store.properties(_A_SECOND_ENTRY)}"
    )


def test_a_caption_showing_a_variable_is_not_what_a_row_is_about() -> None:
    # Given a row that shows a value and captions it, with a button that acts on it
    store = RecordingStore()
    what_is_configured = FakeVariable(r"C:\Example\draft.txt")
    annotator = Annotator(
        store,
        variables=VariablesByName(
            {_THE_VARIABLE_THE_WIDGET_DECLARES: what_is_configured}
        ),
    )
    button = FakeWidget("Button", _A_BUTTON, text="Reset to Default")
    root = a_window_of(
        a_row_of(
            FakeWidget(
                "Label", _A_CAPTION, textvariable=_THE_VARIABLE_THE_WIDGET_DECLARES
            ),
            FakeWidget("Label", _A_SECOND_CAPTION, text="Icon:"),
            button,
        )
    )
    already_annotated(root, annotator)

    # When the convention decides what this row is about
    the_convention_applied_to(root, annotator)

    # Then it is about the caption: a subject from a value changes as the value does
    assert store.properties(_A_BUTTON)[PropId.NAME] == "Reset to Default for Icon", (
        f"the row's subject came from a value: {store.properties(_A_BUTTON)}"
    )


def test_a_row_with_no_caption_at_all_is_named_by_the_button_that_captions_it() -> None:
    # Given a row with no label in it, captioned by its own action button
    store = RecordingStore()
    annotator = Annotator(store)
    entry = FakeWidget("Entry", _AN_ENTRY)
    root = a_window_of(
        a_row_of(FakeWidget("Button", _A_BUTTON, text="Choose Icon:"), entry)
    )
    already_annotated(root, annotator)

    # When the convention looks for what the row is about
    the_convention_applied_to(root, annotator)

    # Then it falls through to the button's words
    assert store.properties(_AN_ENTRY)[PropId.NAME] == "Choose Icon", (
        f"the row captioned by its own button named nothing: {store.properties(_AN_ENTRY)}"
    )


def test_an_entry_named_after_a_caption_that_moves_moves_with_it() -> None:
    # Given a row captioned by its own button, retitled by a variable as it runs
    store = RecordingStore()
    what_the_caption_says = FakeVariable("Icon:")
    annotator = Annotator(
        store,
        variables=VariablesByName(
            {_THE_VARIABLE_THE_WIDGET_DECLARES: what_the_caption_says}
        ),
    )
    entry = FakeWidget("Entry", _AN_ENTRY)
    root = a_window_of(
        a_row_of(
            FakeWidget(
                "Button",
                _A_BUTTON,
                text="Icon:",
                textvariable=_THE_VARIABLE_THE_WIDGET_DECLARES,
            ),
            entry,
        )
    )
    already_annotated(root, annotator)

    # When the convention names the entry, and the caption is retitled after
    the_convention_applied_to(root, annotator)
    what_the_caption_says.set("Image:")

    # Then the entry moves with it
    assert store.properties(_AN_ENTRY)[PropId.NAME] == "Image", (
        "the entry is stuck on what its caption said when the convention ran: "
        f"{store.properties(_AN_ENTRY)}"
    )


def test_a_button_whose_caption_says_nothing_on_its_own_is_qualified_with_its_row() -> (
    None
):
    # Given a caption, an entry, and a browse button whose words say only what it does
    store = RecordingStore()
    annotator = Annotator(store)
    root = a_window_of(
        a_row_of(
            FakeWidget("Label", _A_CAPTION, text="Export Folder:"),
            FakeWidget("Entry", _AN_ENTRY),
            FakeWidget("Button", _A_BUTTON, text="Browse..."),
        )
    )
    already_annotated(root, annotator)

    # When the convention is applied
    the_convention_applied_to(root, annotator)

    # Then the button is qualified by the row it is in
    assert store.properties(_A_BUTTON)[PropId.NAME] == "Browse... for Export Folder", (
        f"the generic button was left as {store.properties(_A_BUTTON)}"
    )


def test_a_button_that_already_says_what_it_acts_on_is_left_exactly_as_it_was() -> None:
    # Given a button whose caption is a whole sentence about its own row
    store = RecordingStore()
    annotator = Annotator(store)
    root = a_window_of(
        a_row_of(
            FakeWidget("Label", _A_CAPTION, text="Service:"),
            FakeWidget("Button", _A_BUTTON, text="Restart the service"),
        )
    )
    already_annotated(root, annotator)

    # When the convention passes over it
    named = the_convention_applied_to(root, annotator)

    # Then it says what it always said
    assert store.properties(_A_BUTTON)[PropId.NAME] == "Restart the service", (
        f"a button that named itself was rewritten: {store.properties(_A_BUTTON)}"
    )
    assert named == (), f"the convention claims to have named something: {named}"


def test_a_button_that_captions_its_own_row_is_not_qualified_with_itself() -> None:
    # Given a row that is nothing but a generic button, with no caption near it
    store = RecordingStore()
    annotator = Annotator(store)
    root = a_window_of(a_row_of(FakeWidget("Button", _A_BUTTON, text="Browse...")))
    already_annotated(root, annotator)

    # When the convention finds the only possible caption is the button itself
    named = the_convention_applied_to(root, annotator)

    # Then it leaves it alone rather than announcing "Browse... for Browse..."
    assert store.properties(_A_BUTTON)[PropId.NAME] == "Browse...", (
        f"the button was qualified with itself: {store.properties(_A_BUTTON)}"
    )
    assert named == (), f"the convention claims to have named something: {named}"


def test_a_caption_showing_a_variable_is_left_to_the_binding_enable_already_made() -> (
    None
):
    # Given a label with no words of its own, driven by a variable `enable()` bound
    store = RecordingStore()
    what_went_wrong = FakeVariable("disk full")
    annotator = Annotator(
        store,
        variables=VariablesByName({_THE_VARIABLE_THE_WIDGET_DECLARES: what_went_wrong}),
    )
    root = a_window_of(
        a_row_of(
            FakeWidget("Label", _A_CAPTION, text="Last error:"),
            FakeWidget(
                "Label",
                _A_SECOND_CAPTION,
                textvariable=_THE_VARIABLE_THE_WIDGET_DECLARES,
            ),
        )
    )
    already_annotated(root, annotator)

    # When the convention walks the row it sits in
    named = the_convention_applied_to(root, annotator)

    # Then it is not touched at all
    assert store.properties(_A_SECOND_CAPTION)[PropId.NAME] == "disk full", (
        f"the convention renamed a label that was already right: "
        f"{store.properties(_A_SECOND_CAPTION)}"
    )
    assert what_went_wrong.traces_left() == _THE_BINDING_ENABLE_MADE, (
        f"{what_went_wrong.traces_left()} traces are on the variable, so the "
        "convention bound one over the binding enable() had already made"
    )
    assert named == (), f"the convention claims to have named something: {named}"


def test_a_name_the_application_chose_is_never_replaced_by_the_convention() -> None:
    # Given a row whose entry and generic button the application has both named itself
    store = RecordingStore()
    annotator = Annotator(store)
    entry = FakeWidget("Entry", _AN_ENTRY)
    button = FakeWidget("Button", _A_BUTTON, text="Browse...")
    root = a_window_of(
        a_row_of(FakeWidget("Label", _A_CAPTION, text="Export Folder:"), entry, button)
    )
    already_annotated(root, annotator)
    annotator.set_name(entry, "Path to the application under test")
    annotator.set_name(button, "Choose the application under test")

    # When the convention is applied over the top
    named = the_convention_applied_to(root, annotator)

    # Then neither moves
    assert store.properties(_AN_ENTRY)[PropId.NAME] == (
        "Path to the application under test"
    ), f"the convention overwrote a chosen name: {store.properties(_AN_ENTRY)}"
    assert store.properties(_A_BUTTON)[PropId.NAME] == (
        "Choose the application under test"
    ), f"the convention overwrote a chosen name: {store.properties(_A_BUTTON)}"
    assert named == (), f"the convention claims to have named something: {named}"


def test_a_qualified_button_keeps_its_qualification_when_tk_maps_it_again() -> None:
    # Given a browse button the convention has qualified with the row it acts on
    store = RecordingStore()
    annotator = Annotator(store)
    button = FakeWidget("Button", _A_BUTTON, text="Browse...")
    root = a_window_of(
        a_row_of(FakeWidget("Label", _A_CAPTION, text="Export Folder:"), button)
    )
    already_annotated(root, annotator)
    the_convention_applied_to(root, annotator)

    # When Tk maps it again, which for a tabbed dialog is every tab change
    annotator.add(button)

    # Then the qualification stands, though `<Map>` re-annotates from the `-text`
    assert store.properties(_A_BUTTON)[PropId.NAME] == "Browse... for Export Folder", (
        f"the caption won the name back on the next <Map>: {store.properties(_A_BUTTON)}"
    )


def test_the_convention_reports_every_widget_it_named_and_what_it_called_it() -> None:
    # Given two rows of the kind this convention exists for
    store = RecordingStore()
    annotator = Annotator(store)
    entry = FakeWidget("Entry", _AN_ENTRY)
    button = FakeWidget("Button", _A_BUTTON, text="Browse...")
    another_entry = FakeWidget("Entry", _A_SECOND_ENTRY)
    root = a_window_of(
        a_row_of(FakeWidget("Label", _A_CAPTION, text="Export Folder:"), entry, button),
        a_row_of(
            FakeWidget("Label", _A_SECOND_CAPTION, text="Host:"),
            another_entry,
            hwnd=_A_SECOND_ROW,
        ),
    )
    already_annotated(root, annotator)

    # When the convention is applied
    named = the_convention_applied_to(root, annotator)

    # Then it says what it decided, read back out of what was actually written
    assert named == (
        NamedByTheLayout(str(entry), "Export Folder"),
        NamedByTheLayout(str(button), "Browse... for Export Folder"),
        NamedByTheLayout(str(another_entry), "Host"),
    ), f"the convention reported {named}"


def test_working_names_out_from_a_thread_that_does_not_own_the_widgets_is_refused() -> (
    None
):
    # Given a window and an installation belonging to the thread that called `enable()`
    store = RecordingStore()
    installed = Installation(Strategy.ANNOTATED, Annotator(store))
    root = a_window_of(
        a_row_of(
            FakeWidget("Label", _A_CAPTION, text="Host:"),
            FakeWidget("Entry", _AN_ENTRY),
        )
    )

    # When a background worker asks for the convention to be applied
    refusal = the_failure_raised_on_another_thread(
        lambda: infer_names_from_layout(root, installed)
    )

    # Then it is stopped before a single Tk call: a foreign thread corrupts Tcl quietly
    assert isinstance(refusal, AnnotationRefused), (
        f"a foreign thread got through to Tk with {refusal!r}"
    )
    assert store.writes == [], f"a foreign thread reached the store: {store.writes}"


_A_THIRD_CAPTION = 0x000508C1
_A_THIRD_ENTRY = 0x000508C2


def test_a_grid_form_names_each_entry_after_the_caption_on_its_own_grid_row() -> None:
    # Given the most common form shape there is: one frame, three gridded rows
    store = RecordingStore()
    annotator = Annotator(store)
    frame = a_row_of(
        FakeWidget(
            "Label",
            _A_CAPTION,
            text="Server:",
            managed_by="grid",
            grid_row=0,
            grid_column=0,
        ),
        FakeWidget("Entry", _AN_ENTRY, managed_by="grid", grid_row=0, grid_column=1),
        FakeWidget(
            "Label",
            _A_SECOND_CAPTION,
            text="Port:",
            managed_by="grid",
            grid_row=1,
            grid_column=0,
        ),
        FakeWidget(
            "Entry", _A_SECOND_ENTRY, managed_by="grid", grid_row=1, grid_column=1
        ),
        FakeWidget(
            "Label",
            _A_THIRD_CAPTION,
            text="Username:",
            managed_by="grid",
            grid_row=2,
            grid_column=0,
        ),
        FakeWidget(
            "Entry", _A_THIRD_ENTRY, managed_by="grid", grid_row=2, grid_column=1
        ),
    )
    root = a_window_of(frame)
    already_annotated(root, annotator)

    # When the convention is applied
    named = the_convention_applied_to(root, annotator)

    # Then each entry takes the caption on its own grid row, never the first
    # caption in the frame
    assert [(one.path, one.name) for one in named] == [
        (str(root.winfo_children()[0].winfo_children()[1]), "Server"),
        (str(root.winfo_children()[0].winfo_children()[3]), "Port"),
        (str(root.winfo_children()[0].winfo_children()[5]), "Username"),
    ], f"a gridded frame was read as one row: {[(n.path, n.name) for n in named]}"


def test_a_grid_row_is_read_across_its_columns_rather_than_in_creation_order() -> None:
    # Given a grid row built out of order, with a trailing unit label created
    # before the caption that really names the row
    store = RecordingStore()
    annotator = Annotator(store)
    frame = a_row_of(
        FakeWidget("Entry", _AN_ENTRY, managed_by="grid", grid_row=0, grid_column=1),
        FakeWidget(
            "Label",
            _A_SECOND_CAPTION,
            text="px",
            managed_by="grid",
            grid_row=0,
            grid_column=2,
        ),
        FakeWidget(
            "Label",
            _A_CAPTION,
            text="Width:",
            managed_by="grid",
            grid_row=0,
            grid_column=0,
        ),
    )
    root = a_window_of(frame)
    already_annotated(root, annotator)

    # When the convention is applied
    named = the_convention_applied_to(root, annotator)

    # Then the leftmost caption speaks for the row: columns order a grid row,
    # not the order somebody happened to build it in
    assert [one.name for one in named] == ["Width"], (
        f"creation order won over the grid: {[(n.path, n.name) for n in named]}"
    )
