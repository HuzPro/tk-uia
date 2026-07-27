"""Behavioral spec for the role a Tk widget class is announced as.

Tk tells Windows nothing about what a widget *is*: measured against a live
window, the MSAA proxy reports `tk.Label` as an image and `tk.Entry` as a bare
pane. The role number written here is why a screen reader says "button" and a UI
Automation client sees a `ButtonControl` with a ValuePattern where there was
none.
"""

from __future__ import annotations

import pytest

from tk_uia.roles import ROLE_FOR_TK_CLASS, Role

_MSAA_STATICTEXT = 41
_MSAA_TEXT = 42
_MSAA_PUSHBUTTON = 43

_THEMED_AND_CLASSIC = [
    ("TButton", "Button"),
    ("TLabel", "Label"),
    ("TEntry", "Entry"),
    ("TCheckbutton", "Checkbutton"),
    ("TRadiobutton", "Radiobutton"),
    ("TScale", "Scale"),
    ("TScrollbar", "Scrollbar"),
    ("TSpinbox", "Spinbox"),
    ("TFrame", "Frame"),
    ("TLabelframe", "Labelframe"),
    ("TMenubutton", "Menubutton"),
    ("TPanedwindow", "Panedwindow"),
]

_ONLY_IN_ONE_TOOLKIT = [
    ("Listbox", Role.LIST),
    ("Text", Role.TEXT),
    ("Message", Role.STATIC_TEXT),
    ("TCombobox", Role.COMBO_BOX),
    ("TProgressbar", Role.PROGRESS_BAR),
    ("TNotebook", Role.PAGE_TAB_LIST),
    ("Treeview", Role.OUTLINE),
    ("Canvas", Role.GRAPHIC),
    ("Menu", Role.MENU_POPUP),
    ("TSeparator", Role.SEPARATOR),
    ("TSizegrip", Role.GRIP),
]

# What the MSAA-to-UIA bridge was measured to make of each number. A role the
# bridge does not recognise comes through as PaneControl, which is what these
# widgets already were: the wrong number looks like success from inside this
# process and changes nothing a client can read.
_MEASURED_AGAINST_THE_BRIDGE = [
    (Role.GRAPHIC, 40, "ImageControl"),
    (Role.MENU_BUTTON, 62, "SplitButtonControl"),
    (Role.SEPARATOR, 21, "SeparatorControl"),
    (Role.GRIP, 4, "ThumbControl"),
    (Role.MENU_POPUP, 11, "MenuControl"),
    (Role.GROUPING, 20, "GroupControl"),
]


def test_a_button_widget_is_given_the_role_a_screen_reader_announces_for_a_push_button() -> (
    None
):
    # Given the class name Tk answers with for a classic button
    tk_class = "Button"

    # When the role table is asked what that class is
    role = ROLE_FOR_TK_CLASS[tk_class]

    # Then it is MSAA's push button, by the number oleacc defines, because the
    # bridge reads the number and nothing else
    assert role is Role.PUSH_BUTTON, f"a Button must be a push button, not {role}"
    assert role.value == _MSAA_PUSHBUTTON, (
        "the value is what reaches Windows: any other number announces a "
        f"different kind of control, got {role.value}"
    )


@pytest.mark.parametrize(("themed", "classic"), _THEMED_AND_CLASSIC)
def test_a_ttk_widget_maps_to_the_same_role_as_the_classic_widget_it_replaces(
    themed: str, classic: str
) -> None:
    # Given a themed widget and the classic widget it is a drop-in for
    # When each is looked up by the class name Tk answers with
    themed_role = ROLE_FOR_TK_CLASS.get(themed)
    classic_role = ROLE_FOR_TK_CLASS.get(classic)

    # Then they are announced identically, because swapping `tk` for `ttk` is a
    # visual decision and a user of a screen reader must not be able to tell
    assert themed_role is classic_role, (
        f"{themed} is announced as {themed_role} but {classic} as {classic_role}"
    )
    assert themed_role is not None, f"{themed} is not in the role table at all"


def test_a_label_and_an_entry_are_split_by_the_two_roles_that_mean_read_and_write() -> (
    None
):
    # Given the two classes that both hold text but differ in who may change it
    # When each is looked up
    label = ROLE_FOR_TK_CLASS["Label"]
    entry = ROLE_FOR_TK_CLASS["Entry"]

    # Then the label is static text and the entry is editable text. Measured: 41
    # turns the label from an `ImageControl` into a `TextControl`, and 42 turns
    # the entry into an `EditControl` carrying a ValuePattern that did not exist
    # before it.
    assert (label.value, entry.value) == (_MSAA_STATICTEXT, _MSAA_TEXT), (
        f"label is {label.value} and entry is {entry.value}; a client reads the "
        "number to decide whether a control can be written to"
    )


@pytest.mark.parametrize(
    ("role", "number", "control_type"), _MEASURED_AGAINST_THE_BRIDGE
)
def test_each_role_carries_the_number_that_was_measured_to_produce_its_control_type(
    role: Role, number: int, control_type: str
) -> None:
    # Then the number that reaches Windows is the measured one. `DIAGRAM`,
    # `CLIENT` and `PANE` were all tried for the canvas and every one came back
    # as the anonymous `PaneControl` the widget already was, with `S_OK` and no
    # complaint from anywhere.
    assert role.value == number, (
        f"{role.name} carries {role.value}; {number} is the number measured to "
        f"reach a client as {control_type}"
    )


@pytest.mark.parametrize(("tk_class", "expected"), _ONLY_IN_ONE_TOOLKIT)
def test_a_widget_that_exists_in_only_one_toolkit_is_still_announced_as_what_it_is(
    tk_class: str, expected: Role
) -> None:
    # Given a widget with no counterpart in the other toolkit
    # When it is looked up
    role = ROLE_FOR_TK_CLASS.get(tk_class)

    # Then it is announced as the thing it is, rather than left out of the table
    # and reaching a client as the anonymous pane Tk hands over by default
    assert role is expected, f"{tk_class} is announced as {role}, wanted {expected}"
