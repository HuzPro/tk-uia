"""The MSAA role numbers Tk widget classes are announced as.

The annotator looks a widget's ``winfo_class()`` up here and writes the number
it finds as `PROPID_ACC_ROLE`. Nothing else in the package knows what a "button"
is.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from types import MappingProxyType


class Role(Enum):
    """MSAA roles, by the numbers `oleacc.h` defines for them."""

    SCROLL_BAR = 3
    GRIP = 4
    MENU_POPUP = 11
    GROUPING = 20
    SEPARATOR = 21
    LIST = 33
    OUTLINE = 35
    # Deliberately absent from ROLE_FOR_TK_CLASS below: a tab is not a widget
    # and has no `winfo_class()` to look up. It is written by `tabs.py` onto a
    # window handle made for it, which is the only reason one exists at all.
    PAGE_TAB = 37
    GRAPHIC = 40
    STATIC_TEXT = 41
    TEXT = 42
    PUSH_BUTTON = 43
    CHECK_BUTTON = 44
    RADIO_BUTTON = 45
    COMBO_BOX = 46
    PROGRESS_BAR = 48
    SLIDER = 51
    SPIN_BUTTON = 52
    PAGE_TAB_LIST = 60
    # `oleacc.h` calls this SPLITBUTTON. BUTTONMENU (0x39) reads as the more
    # obviously named thing and measures as a `MenuItemControl`, which would
    # have a screen reader announce a menu *item* for a button that is not in a
    # menu at all. This one reads as `SplitButtonControl`: a button with a menu
    # attached, which is what a Menubutton is.
    MENU_BUTTON = 62


ROLE_FOR_TK_CLASS: Mapping[str, Role] = MappingProxyType(
    {
        # Classic tk and themed ttk are listed side by side rather than derived
        # from one another: `ttk.Treeview` answers "Treeview", not "TTreeview",
        # so the leading T is a convention and not a rule.
        "Button": Role.PUSH_BUTTON,
        "TButton": Role.PUSH_BUTTON,
        "Label": Role.STATIC_TEXT,
        "TLabel": Role.STATIC_TEXT,
        "Entry": Role.TEXT,
        "TEntry": Role.TEXT,
        "Checkbutton": Role.CHECK_BUTTON,
        "TCheckbutton": Role.CHECK_BUTTON,
        "Radiobutton": Role.RADIO_BUTTON,
        "TRadiobutton": Role.RADIO_BUTTON,
        "Scale": Role.SLIDER,
        "TScale": Role.SLIDER,
        "Scrollbar": Role.SCROLL_BAR,
        "TScrollbar": Role.SCROLL_BAR,
        "Spinbox": Role.SPIN_BUTTON,
        "TSpinbox": Role.SPIN_BUTTON,
        "Frame": Role.GROUPING,
        "TFrame": Role.GROUPING,
        "Labelframe": Role.GROUPING,
        "TLabelframe": Role.GROUPING,
        "Listbox": Role.LIST,
        "Text": Role.TEXT,
        "Message": Role.STATIC_TEXT,
        "TCombobox": Role.COMBO_BOX,
        "TProgressbar": Role.PROGRESS_BAR,
        "TNotebook": Role.PAGE_TAB_LIST,
        "Treeview": Role.OUTLINE,
        # A drawing surface, and honestly so: what a canvas shows is paint, and
        # `GRAPHIC` is the one number measured to reach a client as anything
        # other than the anonymous pane it already was.
        "Canvas": Role.GRAPHIC,
        "Menubutton": Role.MENU_BUTTON,
        "TMenubutton": Role.MENU_BUTTON,
        "Panedwindow": Role.GROUPING,
        "TPanedwindow": Role.GROUPING,
        "TSeparator": Role.SEPARATOR,
        "TSizegrip": Role.GRIP,
        # A menu is never mapped, so nothing here is ever written to one, which
        # is the point of the entry. Without it `describe()` blames the missing
        # role, reading as "add one and this will work"; with it the report says
        # NEVER_MAPPED, which is the truth and is not fixable.
        "Menu": Role.MENU_POPUP,
    }
)
