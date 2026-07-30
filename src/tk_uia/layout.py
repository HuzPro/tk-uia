"""Name wordless controls from a form's row-and-label layout, on request.

A guess by convention, not a fact from Tk, which is why `enable()` never makes it.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Protocol

from tk_uia.annotate import (
    Installation,
    TkWidget,
    a_caption_read_as_a_name,
    every_widget_under,
    is_a_window,
    variable_the_widget_declares,
    words_the_widget_shows,
)

# A window is a row too: a status bar or button row packs straight onto the
# toplevel, inside no frame at all.
ROWS_A_FORM_IS_LAID_OUT_IN = frozenset({"Frame", "TFrame", "Labelframe", "TLabelframe"})

# The classes a caption speaks for: the controls a client asks the contents of,
# and the ones with no `-text` option to be named from.
WIDGETS_A_CAPTION_SPEAKS_FOR = frozenset(
    {"Entry", "TEntry", "TCombobox", "Spinbox", "TSpinbox"}
)

WIDGETS_THAT_CAPTION_A_ROW = frozenset({"Label", "TLabel"})

# No Radiobutton: its caption is the option it selects, which already says
# what it acts on.
WIDGETS_THAT_ACT_ON_A_ROW = frozenset(
    {"Button", "TButton", "Checkbutton", "TCheckbutton"}
)

# Captions that say what a control does and nothing about what it does it to.
CAPTIONS_THAT_SAY_NOTHING_ON_THEIR_OWN = frozenset(
    {"Browse...", "Browse", "Reset to Default", "...", "?"}
)

_NO_WORDS_AT_ALL = ""
_NO_VARIABLE_AT_ALL = ""

# Reads as "Browse... for Export Folder".
_WHAT_A_GENERIC_CAPTION_ACTS_ON = "{caption} for {subject}"


@dataclass(frozen=True)
class NamedByTheLayout:
    """One widget the convention named, and what it decided to call it."""

    path: str
    name: str


class NamesWidgets(Protocol):
    """What the walk needs of an annotator: what a widget is called, and two ways to say."""

    def name_of(self, widget: TkWidget) -> str | None: ...

    def label_for(self, label: TkWidget, widget: TkWidget) -> None: ...

    def set_name(self, widget: TkWidget, name: str) -> None: ...


@dataclass(frozen=True)
class _WhatARowIsAbout:
    """The widget a row is captioned by, and the words it captions it with."""

    widget: TkWidget
    words: str


def infer_names_from_layout(
    root: TkWidget, installation: Installation
) -> tuple[NamedByTheLayout, ...]:
    """Name what the layout says these widgets are, and report what that came to."""
    # Before anything crosses into the Tcl interpreter, which a foreign thread
    # corrupts quietly.
    installation.owner.refuse_any_other_caller()
    return tuple(_whatever_the_convention_names(root, installation.annotator))


def _whatever_the_convention_names(
    root: TkWidget, names: NamesWidgets
) -> Iterator[NamedByTheLayout]:
    for row in _the_rows_under(root):
        yield from _whatever_this_row_names(row, names)


def _the_rows_under(root: TkWidget) -> Iterator[TkWidget]:
    # The root counts whatever class it is: widgets packed straight onto it are
    # a row like any other.
    yield root
    for widget in every_widget_under(root):
        if widget.winfo_class() in ROWS_A_FORM_IS_LAID_OUT_IN or is_a_window(widget):
            yield widget


def _whatever_this_row_names(
    row: TkWidget, names: NamesWidgets
) -> Iterator[NamedByTheLayout]:
    for children in _the_lines_this_row_holds(row):
        subject = _what_this_row_is_about(children)
        if subject is None:
            continue
        for child in children:
            yield from _whatever_naming_this_child_comes_to(child, subject, names)


def _the_lines_this_row_holds(row: TkWidget) -> Iterator[tuple[TkWidget, ...]]:
    """A frame's rows: itself for a packed one, each grid row for a gridded one.

    Grid rows are read across their columns, so the leftmost caption speaks
    for the row however the widgets happened to be created.
    """
    packed: list[TkWidget] = []
    gridded: dict[int, list[tuple[int, TkWidget]]] = {}
    for child in row.winfo_children():
        placement = child.grid_info() if child.winfo_manager() == "grid" else {}
        if placement:
            gridded.setdefault(int(str(placement["row"])), []).append(
                (int(str(placement["column"])), child)
            )
        else:
            packed.append(child)
    for _, line in sorted(gridded.items()):
        yield tuple(child for _, child in sorted(line, key=lambda cell: cell[0]))
    if packed:
        yield tuple(packed)


def _what_this_row_is_about(children: Sequence[TkWidget]) -> _WhatARowIsAbout | None:
    """The row's subject: the first caption in it, or the button that stands in for one."""
    for child in children:
        if child.winfo_class() in WIDGETS_THAT_CAPTION_A_ROW and not _shows_a_variable(
            child
        ):
            # A label driven by a variable shows what the row *holds*, not what
            # it is, so it cannot be the subject.
            about = _whatever_words_caption_a_row(child)
            if about is not None:
                return about
    for child in children:
        # A row with no label at all can be captioned by its own action button.
        if child.winfo_class() in WIDGETS_THAT_ACT_ON_A_ROW:
            about = _whatever_words_caption_a_row(child)
            if about is not None:
                return about
    return None


def _whatever_words_caption_a_row(widget: TkWidget) -> _WhatARowIsAbout | None:
    words = a_caption_read_as_a_name(_the_words(widget))
    return None if not words else _WhatARowIsAbout(widget, words)


def _whatever_naming_this_child_comes_to(
    child: TkWidget, subject: _WhatARowIsAbout, names: NamesWidgets
) -> Iterator[NamedByTheLayout]:
    tk_class = child.winfo_class()
    if tk_class in WIDGETS_A_CAPTION_SPEAKS_FOR:
        yield from _whatever_captioning_this_control_comes_to(child, subject, names)
    if tk_class in WIDGETS_THAT_ACT_ON_A_ROW:
        yield from _whatever_qualifying_this_button_comes_to(child, subject, names)
    # A label showing a variable needs nothing from here: `enable()` is already
    # keeping its name in step with the `-textvariable` it declared.


def _whatever_captioning_this_control_comes_to(
    control: TkWidget, subject: _WhatARowIsAbout, names: NamesWidgets
) -> Iterator[NamedByTheLayout]:
    if names.name_of(control) is not None:
        return
    # Through the association rather than by copying the words across, so that a
    # caption kept in step with a variable takes the widget it names with it.
    names.label_for(subject.widget, control)
    yield from _what_it_is_called_now(control, names)


def _whatever_qualifying_this_button_comes_to(
    button: TkWidget, subject: _WhatARowIsAbout, names: NamesWidgets
) -> Iterator[NamedByTheLayout]:
    caption = _the_words(button)
    if caption not in CAPTIONS_THAT_SAY_NOTHING_ON_THEIR_OWN:
        return
    if button is subject.widget:
        # This button is the only thing captioning its own row, and "Browse...
        # for Browse..." reads to a listener as a fault in the screen reader.
        return
    if names.name_of(button) not in (None, caption):
        return
    names.set_name(
        button,
        _WHAT_A_GENERIC_CAPTION_ACTS_ON.format(caption=caption, subject=subject.words),
    )
    yield from _what_it_is_called_now(button, names)


def _what_it_is_called_now(
    widget: TkWidget, names: NamesWidgets
) -> Iterator[NamedByTheLayout]:
    # Read back rather than reported from what was meant: where `enable()` stood
    # down nothing was written, and no name here is readable by a client.
    name = names.name_of(widget)
    if name is None:
        return
    yield NamedByTheLayout(str(widget), name)


def _shows_a_variable(widget: TkWidget) -> bool:
    return variable_the_widget_declares(widget) != _NO_VARIABLE_AT_ALL


def _the_words(widget: TkWidget) -> str:
    """A widget's words, with "has none" and "shows none" answered the same way."""
    return words_the_widget_shows(widget) or _NO_WORDS_AT_ALL
