"""One window holding every widget `ttk` has, for the survey to read.

    python probes/every_ttk_widget.py "ttk zoo" .

`ttk.LabeledScale` and `ttk.OptionMenu` are composites; the survey reports the
container's class.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from _widget_zoo import (
    follow_the_values,
    laid_out_in_a_grid,
    main_for,
    name_everything,
)

TITLE = "tk-uia ttk widget zoo"

NEVER_SHOWS = frozenset({"ttk.Menu (on a Menubutton)"})


# See the classic zoo for why the decorative two are named here and should not
# be in a real application.
WHAT_TO_CALL_THEM = {
    "ttk.Entry": "Task title",
    "ttk.Combobox": "Priority",
    "ttk.Spinbox": "Quantity",
    "ttk.Scale": "Volume",
    "ttk.Scrollbar": "Scroll the results",
    "ttk.Progressbar": "Upload progress",
    "ttk.Separator": "Divider",
    "ttk.Sizegrip": "Resize this window",
    "ttk.Frame": "Details",
    "ttk.Panedwindow": "Split view",
    "ttk.Notebook": "Settings",
    "ttk.Treeview": "Task list",
    "ttk.LabeledScale": "Brightness",
}

_HELD_IN = {}


def say_everything(built: dict[str, tk.Misc]) -> None:
    name_everything(built, WHAT_TO_CALL_THEM)
    follow_the_values(built, _HELD_IN)


def build(root: tk.Tk) -> dict[str, tk.Misc]:
    built: dict[str, tk.Misc] = {}

    built["ttk.Label"] = ttk.Label(root, text="a Label")
    built["ttk.Button"] = ttk.Button(root, text="a Button")
    _HELD_IN["ttk.Entry"] = tk.StringVar(master=root, value="write the report")
    built["ttk.Entry"] = ttk.Entry(root, textvariable=_HELD_IN["ttk.Entry"])
    built["ttk.Checkbutton"] = ttk.Checkbutton(root, text="a Checkbutton")
    built["ttk.Radiobutton"] = ttk.Radiobutton(
        root, text="a Radiobutton", value=1, variable=tk.IntVar(master=root, value=1)
    )
    _HELD_IN["ttk.Combobox"] = tk.StringVar(master=root, value="high")
    built["ttk.Combobox"] = ttk.Combobox(
        root, values=["high", "low"], textvariable=_HELD_IN["ttk.Combobox"]
    )
    _HELD_IN["ttk.Spinbox"] = tk.StringVar(master=root, value="3")
    built["ttk.Spinbox"] = ttk.Spinbox(
        root, from_=0, to=10, textvariable=_HELD_IN["ttk.Spinbox"]
    )
    built["ttk.Scale"] = ttk.Scale(root, from_=0, to=10, orient="horizontal")
    built["ttk.Scrollbar"] = ttk.Scrollbar(root, orient="vertical")
    built["ttk.Progressbar"] = ttk.Progressbar(root, value=40)
    built["ttk.Separator"] = ttk.Separator(root, orient="horizontal")
    built["ttk.Sizegrip"] = ttk.Sizegrip(root)
    built["ttk.Frame"] = _a_frame(root)
    built["ttk.Labelframe"] = _a_label_frame(root)
    built["ttk.Panedwindow"] = _a_paned_window(root)
    built["ttk.Notebook"] = _a_notebook(root)
    built["ttk.Treeview"] = _a_treeview(root)
    built["ttk.LabeledScale"] = ttk.LabeledScale(root, from_=0, to=10)
    built["ttk.Menubutton"] = _a_menubutton(root, built)
    built["ttk.OptionMenu"] = ttk.OptionMenu(
        root, tk.StringVar(master=root, value="one"), "one", "one", "two"
    )

    laid_out_in_a_grid(root, built, NEVER_SHOWS)
    return built


def _a_frame(root: tk.Tk) -> ttk.Frame:
    frame = ttk.Frame(root, borderwidth=2, relief="groove")
    ttk.Label(frame, text="inside a Frame").pack(padx=4, pady=4)
    return frame


def _a_label_frame(root: tk.Tk) -> ttk.Labelframe:
    frame = ttk.Labelframe(root, text="a Labelframe")
    ttk.Label(frame, text="inside it").pack(padx=4, pady=4)
    return frame


def _a_paned_window(root: tk.Tk) -> ttk.Panedwindow:
    paned = ttk.Panedwindow(root, orient="horizontal")
    paned.add(ttk.Label(paned, text="left pane"))
    paned.add(ttk.Label(paned, text="right pane"))
    return paned


def _a_notebook(root: tk.Tk) -> ttk.Notebook:
    notebook = ttk.Notebook(root)
    for name in ("First", "Second"):
        page = ttk.Frame(notebook)
        ttk.Label(page, text=f"the {name} page").pack(padx=10, pady=10)
        notebook.add(page, text=name)
    return notebook


def _a_treeview(root: tk.Tk) -> ttk.Treeview:
    tree = ttk.Treeview(root, columns=("value",), height=3)
    tree.heading("#0", text="a Treeview")
    for label in ("first row", "second row"):
        tree.insert("", "end", text=label, values=("a value",))
    return tree


def _a_menubutton(root: tk.Tk, built: dict[str, tk.Misc]) -> ttk.Menubutton:
    menubutton = ttk.Menubutton(root, text="a Menubutton")
    menu = tk.Menu(menubutton, tearoff=False)
    for label in ("first item", "second item"):
        menu.add_command(label=label)
    menubutton.configure(menu=menu)
    built["ttk.Menu (on a Menubutton)"] = menu
    return menubutton


if __name__ == "__main__":
    main_for(TITLE, build, NEVER_SHOWS, say_everything)
