"""The MSAA role numbers Tk widget classes are announced as.

The annotator looks a widget's ``winfo_class()`` up here and writes the number
it finds as `PROPID_ACC_ROLE`.
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
    # Absent from ROLE_FOR_TK_CLASS: a tab is not a widget; `tabs.py` writes
    # this onto a window handle made for it.
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
    # SPLITBUTTON in `oleacc.h`; reaches a client as `SplitButtonControl`.
    # BUTTONMENU (0x39) reaches it as a menu *item* instead.
    MENU_BUTTON = 62


ROLE_FOR_TK_CLASS: Mapping[str, Role] = MappingProxyType(
    {
        # Listed, not derived: `ttk.Treeview` answers "Treeview", so the
        # leading T is a convention and not a rule.
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
        # `GRAPHIC` is the one number measured to reach a client as anything
        # other than the anonymous pane a canvas already was.
        "Canvas": Role.GRAPHIC,
        "Menubutton": Role.MENU_BUTTON,
        "TMenubutton": Role.MENU_BUTTON,
        "Panedwindow": Role.GROUPING,
        "TPanedwindow": Role.GROUPING,
        "TSeparator": Role.SEPARATOR,
        "TSizegrip": Role.GRIP,
        # A menu never maps, so this is never written; the entry exists so
        # `describe()` reports NEVER_MAPPED instead of a missing role.
        "Menu": Role.MENU_POPUP,
    }
)
