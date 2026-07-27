"""Behavioral spec for the row-and-label convention, applied on request.

The walk asks a widget its class, its children, its options and its words, and
says what it worked out through the annotator: every call the doubles already
answer. That is not only a convenience. This is the one part of the package that
*guesses*, and a guess has to be pinned down widget by widget rather than tried
against one real dialog and believed.
"""

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

# What Tcl calls the first `StringVar` an application makes, and what
# `cget("textvariable")` answers with once a widget has been given it.
_THE_VARIABLE_THE_WIDGET_DECLARES = "PY_VAR0"

_THE_BINDING_ENABLE_MADE = 1


def a_window_of(*children: FakeWidget) -> FakeWidget:
    """A toplevel with widgets under it, which is where every walk starts."""
    return FakeWidget("Tk", _A_WINDOW, children=children)


def a_row_of(*children: FakeWidget, hwnd: int = _A_ROW) -> FakeWidget:
    """A frame with widgets side by side in it, which is how a form lays a row out."""
    return FakeWidget("Frame", hwnd, children=children)


def already_annotated(root: FakeWidget, annotator: Annotator) -> None:
    """The window as `enable()` leaves it: every widget roled, and named from its words."""
    for widget in every_widget_under(root):
        annotator.add(widget)


def the_convention_applied_to(
    root: FakeWidget, annotator: Annotator
) -> tuple[NamedByTheLayout, ...]:
    """What an application gets for asking, which is never what it gets for free."""
    return infer_names_from_layout(root, Installation(Strategy.ANNOTATED, annotator))


def test_an_entry_beside_a_caption_is_named_after_it() -> None:
    # Given a form row as every Tk dialog builds one: a caption and the entry it
    # captions, side by side in a frame, with nothing anywhere in Tk recording
    # that the two have anything to do with each other
    store = RecordingStore()
    annotator = Annotator(store)
    entry = FakeWidget("Entry", _AN_ENTRY)
    root = a_window_of(a_row_of(FakeWidget("Label", _A_CAPTION, text="Host:"), entry))
    already_annotated(root, annotator)

    # When the application asks for the convention its own layout follows
    the_convention_applied_to(root, annotator)

    # Then the entry answers to the caption beside it. This is the largest gap
    # left in a real window: measured on a six-tab settings dialog, 15 of its
    # 110 controls were nameless entries, every one captioned by a sibling
    # label.
    assert store.properties(_AN_ENTRY)[PropId.NAME] == "Host", (
        f"the entry was left as {store.properties(_AN_ENTRY)}, so a screen "
        "reader still announces an edit control and not what it is for"
    )


def test_widgets_packed_straight_onto_a_window_are_a_row_like_any_frame() -> None:
    # Given two rows that sit inside no frame at all: one straight onto the
    # application's own window, which is where a status bar goes, and one onto a
    # dialog it opened
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

    # Then both are named. Measured: a walk that visited only frames missed the
    # status line of a real application, which is packed onto the toplevel like
    # almost every one is.
    assert store.properties(_AN_ENTRY).get(PropId.NAME) == "Host", (
        f"the row packed onto the window itself was skipped: {store.properties(_AN_ENTRY)}"
    )
    assert store.properties(_A_SECOND_ENTRY).get(PropId.NAME) == "Port", (
        f"a dialog is a window with rows on it too: {store.properties(_A_SECOND_ENTRY)}"
    )


def test_a_caption_showing_a_variable_is_not_what_a_row_is_about() -> None:
    # Given a row that shows a value and captions it: a label driven by a
    # variable, the caption for it, and a button that acts on the row
    store = RecordingStore()
    what_is_configured = FakeVariable(r"C:\Example\stopped.ico")
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

    # Then it is about the caption, never about the value. Measured: taking a
    # subject from a label driven by a variable produced a button announced as
    # "Reset to Default for C:\Example\stopped.ico", which changes every time
    # the value does.
    assert store.properties(_A_BUTTON)[PropId.NAME] == "Reset to Default for Icon", (
        f"the row's subject came from a value: {store.properties(_A_BUTTON)}"
    )


def test_a_row_with_no_caption_at_all_is_named_by_the_button_that_captions_it() -> None:
    # Given a row with no label in it, captioned by its own action button, which
    # is how the icon rows of a real settings dialog are built
    store = RecordingStore()
    annotator = Annotator(store)
    entry = FakeWidget("Entry", _AN_ENTRY)
    root = a_window_of(
        a_row_of(FakeWidget("Button", _A_BUTTON, text="Choose Icon:"), entry)
    )
    already_annotated(root, annotator)

    # When the convention looks for what the row is about
    the_convention_applied_to(root, annotator)

    # Then it falls through to the button's words. A label is the usual caption
    # and not the only one, and a fallback that stopped at labels would leave
    # every one of those rows exactly as anonymous as before.
    assert store.properties(_AN_ENTRY)[PropId.NAME] == "Choose Icon", (
        f"the row captioned by its own button named nothing: {store.properties(_AN_ENTRY)}"
    )


def test_an_entry_named_after_a_caption_that_moves_moves_with_it() -> None:
    # Given a row captioned by its own button, the one subject that can be
    # driven by a variable, since a *label* showing one is a value and the rule
    # above rejects it. The application retitles that caption as it runs.
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

    # Then the entry moves with it. The convention records the *association*
    # rather than copying a string out of one widget into another, so a caption
    # this package is already keeping in step takes the widget it names with it.
    assert store.properties(_AN_ENTRY)[PropId.NAME] == "Image", (
        "the entry is stuck on what its caption said when the convention ran: "
        f"{store.properties(_AN_ENTRY)}"
    )


def test_a_button_whose_caption_says_nothing_on_its_own_is_qualified_with_its_row() -> (
    None
):
    # Given the row a settings dialog repeats six times over: a caption, the
    # entry, and a browse button whose words say what it does and nothing about
    # what it does it to
    store = RecordingStore()
    annotator = Annotator(store)
    root = a_window_of(
        a_row_of(
            FakeWidget("Label", _A_CAPTION, text="GUI Executable:"),
            FakeWidget("Entry", _AN_ENTRY),
            FakeWidget("Button", _A_BUTTON, text="Browse..."),
        )
    )
    already_annotated(root, annotator)

    # When the convention is applied
    the_convention_applied_to(root, annotator)

    # Then the button is qualified by the row it is in. Two buttons called
    # "Browse..." in one window are indistinguishable to a screen reader user
    # choosing between them and to a locator trying to pick one.
    assert store.properties(_A_BUTTON)[PropId.NAME] == "Browse... for GUI Executable", (
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

    # Then it says what it always said. Qualifying every button in a window
    # would make a screen reader read the row's caption twice for the one
    # control that never needed it.
    assert store.properties(_A_BUTTON)[PropId.NAME] == "Restart the service", (
        f"a button that named itself was rewritten: {store.properties(_A_BUTTON)}"
    )
    assert named == (), f"the convention claims to have named something: {named}"


def test_a_button_that_captions_its_own_row_is_not_qualified_with_itself() -> None:
    # Given a row that is nothing but a generic button: a bare "Browse..." with
    # no caption anywhere near it, which is the row this convention cannot help
    store = RecordingStore()
    annotator = Annotator(store)
    root = a_window_of(a_row_of(FakeWidget("Button", _A_BUTTON, text="Browse...")))
    already_annotated(root, annotator)

    # When the convention looks at it, and finds the only thing that could
    # caption the row is the button it was about to qualify
    named = the_convention_applied_to(root, annotator)

    # Then it leaves it alone rather than announcing "Browse... for Browse...".
    # A convention that cannot tell you anything has to say nothing, because a
    # name that repeats itself reads to a listener as a fault in the reader.
    assert store.properties(_A_BUTTON)[PropId.NAME] == "Browse...", (
        f"the button was qualified with itself: {store.properties(_A_BUTTON)}"
    )
    assert named == (), f"the convention claims to have named something: {named}"


def test_a_caption_showing_a_variable_is_left_to_the_binding_enable_already_made() -> (
    None
):
    # Given a label with no words of its own, driven by a variable that
    # `enable()` has already named it from and keeps it in step with
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

    # Then it is not touched at all. Renaming it after the caption beside it
    # would replace a live value with a fixed word.
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
    # Given a row whose entry and whose generic button the application has both
    # named itself, which is the whole of the surface this call is a shortcut for
    store = RecordingStore()
    annotator = Annotator(store)
    entry = FakeWidget("Entry", _AN_ENTRY)
    button = FakeWidget("Button", _A_BUTTON, text="Browse...")
    root = a_window_of(
        a_row_of(FakeWidget("Label", _A_CAPTION, text="GUI Executable:"), entry, button)
    )
    already_annotated(root, annotator)
    annotator.set_name(entry, "Path to the application under test")
    annotator.set_name(button, "Choose the application under test")

    # When the convention is applied over the top
    named = the_convention_applied_to(root, annotator)

    # Then neither moves. This is a convention an application asked to have
    # applied, not a rule it agreed to be held to: the author who named one
    # control deliberately is the one person in the process who knows something
    # the layout does not.
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
        a_row_of(FakeWidget("Label", _A_CAPTION, text="GUI Executable:"), button)
    )
    already_annotated(root, annotator)
    the_convention_applied_to(root, annotator)

    # When Tk maps it again, which for a tabbed dialog is every tab change
    annotator.add(button)

    # Then the qualification stands. `<Map>` re-runs the automatic annotation,
    # which names a widget from its own `-text`, so a convention whose names
    # ranked below an inferred caption would have every one of them undone by
    # the first tab change. What the convention writes counts as the
    # application's own word, since it was asked for, and `set_acc_name` still
    # outranks it in both directions.
    assert store.properties(_A_BUTTON)[PropId.NAME] == "Browse... for GUI Executable", (
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
        a_row_of(
            FakeWidget("Label", _A_CAPTION, text="GUI Executable:"), entry, button
        ),
        a_row_of(
            FakeWidget("Label", _A_SECOND_CAPTION, text="Host:"),
            another_entry,
            hwnd=_A_SECOND_ROW,
        ),
    )
    already_annotated(root, annotator)

    # When the convention is applied
    named = the_convention_applied_to(root, annotator)

    # Then it says what it decided, widget by widget, read back out of what was
    # actually written rather than out of what it meant to write. A convention
    # is a guess, and an author has to be able to see every guess it made.
    assert named == (
        NamedByTheLayout(str(entry), "GUI Executable"),
        NamedByTheLayout(str(button), "Browse... for GUI Executable"),
        NamedByTheLayout(str(another_entry), "Host"),
    ), f"the convention reported {named}"


def test_working_names_out_from_a_thread_that_does_not_own_the_widgets_is_refused() -> (
    None
):
    # Given a window and an installation belonging to the thread that called
    # `enable()`, as they are whenever it is called from Tk's own event loop
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

    # Then it is stopped before a single Tk call. This walk asks every widget in
    # the application its class, its children and its options, and each crosses
    # into the Tcl interpreter, which from a foreign thread corrupts quietly
    # rather than raising.
    assert isinstance(refusal, AnnotationRefused), (
        f"a foreign thread got through to Tk with {refusal!r}"
    )
    assert store.writes == [], f"a foreign thread reached the store: {store.writes}"
