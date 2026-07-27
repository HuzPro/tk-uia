"""The row-and-label convention a form follows, applied because it was asked for.

Where it plugs in: `tk_uia.infer_names_from_layout(root)` hands this module the
installation `enable()` made, and it walks the widget tree naming the controls
that have no words of their own — an entry after the caption beside it, a
"Browse..." button after the row it acts on.

**Why this is not in `enable()`.** Everything else in this package is read off
the widget that is being annotated: its class, its `-text`, the variable it
declared. This is read off the widgets *around* it, and there is nothing in Tk
that says a label captions the entry to its right — only that they were packed
next to each other. That makes it a guess, and a library that guessed on its own
would put names into applications whose layout means something else. Asked for
explicitly, it is a convention the author has recognised in their own window; it
is also the difference measured on a real six-tab settings dialog between 83 of
its 110 controls being addressable and all 110 of them.

The walk asks a widget its class, its children, its options and its words, and
says what it worked out through the annotator — so nothing platform-specific is
reached from here, and the whole convention is specified against doubles.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Protocol

from tk_uia.annotate import (
    WINDOWS_THAT_ALREADY_NAME_THEMSELVES,
    Installation,
    TkWidget,
    a_caption_read_as_a_name,
    every_widget_under,
    variable_the_widget_declares,
    words_the_widget_shows,
)

# A row is a container, and a window is one too: a status bar, or a row of
# buttons along the bottom, is packed straight onto the toplevel and sits inside
# no frame at all. Measured — a walk that visited only frames missed exactly the
# control that reports what went wrong.
ROWS_A_FORM_IS_LAID_OUT_IN = (
    frozenset({"Frame", "TFrame", "Labelframe", "TLabelframe"})
    | WINDOWS_THAT_ALREADY_NAME_THEMSELVES
)

# The classes a caption speaks for: the controls a client asks the contents of,
# and the ones with no `-text` option to be named from. An entry is the whole
# reason this exists.
WIDGETS_A_CAPTION_SPEAKS_FOR = frozenset(
    {"Entry", "TEntry", "TCombobox", "Spinbox", "TSpinbox"}
)

# The classes whose words are a caption for the row they are in.
WIDGETS_THAT_CAPTION_A_ROW = frozenset({"Label", "TLabel"})

# The classes whose words say what pressing them does. Checkbuttons are here
# because a row's "Reset to Default" is as often one as it is a button, and
# radiobuttons are not: their caption is the option they select, which already
# says what it acts on.
WIDGETS_THAT_ACT_ON_A_ROW = frozenset(
    {"Button", "TButton", "Checkbutton", "TCheckbutton"}
)

# Captions that say what a control does and nothing about what it does it to.
# Two of these in one window are indistinguishable to a screen reader user
# choosing between them and to a locator trying to pick one — and the dialog
# this was measured on had six.
CAPTIONS_THAT_SAY_NOTHING_ON_THEIR_OWN = frozenset(
    {"Browse...", "Browse", "Reset to Default", "...", "?"}
)

_NO_WORDS_AT_ALL = ""

# What every generic caption becomes: the words it already had, and the row it
# acts on. Reads as "Browse... for GUI Executable".
_WHAT_A_GENERIC_CAPTION_ACTS_ON = "{caption} for {subject}"


@dataclass(frozen=True)
class NamedByTheLayout:
    """One widget the convention named, and what it decided to call it."""

    path: str
    name: str


class NamesWidgets(Protocol):
    """What the walk needs of an annotator: what a widget is called, and two ways to say.

    Narrower than the annotator on purpose. This module holds the one part of
    the package that guesses, and the only things a guess may do are ask what
    somebody has already said and speak where nobody has.
    """

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
    # Before the walk asks its first widget anything, and for the same reason
    # `describe` does it here rather than leaving it to the annotator: this
    # crosses into the Tcl interpreter four ways per widget, and doing that from
    # a foreign thread corrupts it quietly instead of raising.
    installation.owner.refuse_any_other_caller()
    return tuple(_whatever_the_convention_names(root, installation.annotator))


def _whatever_the_convention_names(
    root: TkWidget, names: NamesWidgets
) -> Iterator[NamedByTheLayout]:
    for row in _the_rows_under(root):
        yield from _whatever_this_row_names(row, names)


def _the_rows_under(root: TkWidget) -> Iterator[TkWidget]:
    # The root counts whatever class it is: it is where the caller pointed the
    # walk, and widgets packed straight onto it are a row like any other.
    yield root
    for widget in every_widget_under(root):
        if widget.winfo_class() in ROWS_A_FORM_IS_LAID_OUT_IN:
            yield widget


def _whatever_this_row_names(
    row: TkWidget, names: NamesWidgets
) -> Iterator[NamedByTheLayout]:
    children = tuple(row.winfo_children())
    subject = _what_this_row_is_about(children)
    if subject is None:
        # Nothing in the row says what it is for, and a name invented from
        # anywhere else — the widget's path, its class — would be worse than the
        # honest silence a client already has.
        return
    for child in children:
        yield from _whatever_naming_this_child_comes_to(child, subject, names)


def _what_this_row_is_about(children: Sequence[TkWidget]) -> _WhatARowIsAbout | None:
    """The row's subject: the first caption in it, or the button that stands in for one."""
    for child in children:
        if child.winfo_class() in WIDGETS_THAT_CAPTION_A_ROW and not _shows_a_variable(
            child
        ):
            # A label driven by a variable is showing what the row *holds*, not
            # saying what it is. Measured: taking a subject from one produced a
            # button announced as "Reset to Default for C:\Example\stopped.ico",
            # which changes every time the value does.
            about = _whatever_words_caption_a_row(child)
            if about is not None:
                return about
    for child in children:
        # A row captioned by its own action button, which is how the icon rows
        # of a real settings dialog are built: no separate label at all.
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
    # A label showing a variable needs nothing from here: `enable()` read the
    # `-textvariable` the widget declared and is already keeping its name in
    # step with it, which is a better answer than any convention could reach.


def _whatever_captioning_this_control_comes_to(
    control: TkWidget, subject: _WhatARowIsAbout, names: NamesWidgets
) -> Iterator[NamedByTheLayout]:
    if names.name_of(control) is not None:
        # Somebody has already said what this is, and they knew something the
        # layout does not.
        return
    # Through the association rather than by copying the words across: a caption
    # this package is already keeping in step with a variable takes the widget
    # it names along with it.
    names.label_for(subject.widget, control)
    yield from _what_it_is_called_now(control, names)


def _whatever_qualifying_this_button_comes_to(
    button: TkWidget, subject: _WhatARowIsAbout, names: NamesWidgets
) -> Iterator[NamedByTheLayout]:
    caption = _the_words(button)
    if caption not in CAPTIONS_THAT_SAY_NOTHING_ON_THEIR_OWN:
        return
    if button is subject.widget:
        # The only thing captioning this row is the button about to be qualified
        # by it, and "Browse... for Browse..." reads to a listener as a fault in
        # the screen reader.
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
    # Read back rather than reported from what was meant: on a Tk where
    # `enable()` stood down, nothing was written at all, and a report claiming
    # names no client can read would be exactly the confident wrong answer this
    # package exists to refuse.
    name = names.name_of(widget)
    if name is None:
        return
    yield NamedByTheLayout(str(widget), name)


def _shows_a_variable(widget: TkWidget) -> bool:
    return variable_the_widget_declares(widget) != _NO_WORDS_AT_ALL


def _the_words(widget: TkWidget) -> str:
    """A widget's words, with "has none" and "shows none" answered the same way.

    The distinction `words_the_widget_shows` keeps matters to a report about one
    widget; here a control with no caption and a control whose caption is empty
    both leave the convention with nothing to go on.
    """
    return words_the_widget_shows(widget) or _NO_WORDS_AT_ALL
