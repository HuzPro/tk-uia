"""Fixture app: one of every widget class whose role was chosen by measurement.

`test_gui_new_roles.py` reads this back from another process and checks each one
arrives as the control type the role was *measured* to produce. Each widget is
named explicitly, because most of these have no words of their own.
"""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk

import tk_uia
from tk_uia import Strategy

A_CANVAS = "a canvas"
A_CLASSIC_MENUBUTTON = "a classic menubutton"
A_THEMED_MENUBUTTON = "a themed menubutton"
A_CLASSIC_PANEDWINDOW = "a classic panedwindow"
A_THEMED_PANEDWINDOW = "a themed panedwindow"
A_SEPARATOR = "a separator"
A_SIZEGRIP = "a sizegrip"
A_LABELLED_SCALE = "Volume"


def main(title: str, _commands: Path) -> None:
    root = tk.Tk()
    root.title(title)

    named = {
        A_CANVAS: tk.Canvas(root, width=120, height=40, bg="white"),
        A_CLASSIC_MENUBUTTON: tk.Menubutton(root, text="classic", relief="raised"),
        A_THEMED_MENUBUTTON: ttk.Menubutton(root, text="themed"),
        A_CLASSIC_PANEDWINDOW: tk.PanedWindow(root, width=120, height=40),
        A_THEMED_PANEDWINDOW: ttk.Panedwindow(root, width=120, height=40),
        A_SEPARATOR: ttk.Separator(root, orient="horizontal"),
        A_SIZEGRIP: ttk.Sizegrip(root),
    }
    for widget in named.values():
        widget.pack(padx=10, pady=6, fill="x")

    # Not in `named`: its name has to come from Tk rather than from a call here.
    tk.Scale(root, from_=0, to=10, orient="horizontal", label=A_LABELLED_SCALE).pack(
        padx=10, pady=6, fill="x"
    )

    root.update_idletasks()
    strategy = tk_uia.enable(root)
    if strategy is not Strategy.ANNOTATED:
        raise SystemExit(f"tk_uia.enable reported {strategy}, not {Strategy.ANNOTATED}")

    for name, widget in named.items():
        tk_uia.set_acc_name(widget, name)

    root.mainloop()


if __name__ == "__main__":
    main(sys.argv[1], Path(sys.argv[2]))
