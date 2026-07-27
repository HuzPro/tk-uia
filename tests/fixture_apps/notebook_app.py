"""A Tk application whose whole point is a notebook, for the tab specs to read.

The window titles itself from `argv` so that a window left behind by a crashed
run cannot be mistaken for this one.
"""

from __future__ import annotations

import sys
import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from tkinter import ttk

import tk_uia
from tk_uia import Strategy

FIRST = "General"
SECOND = "Paths"
THIRD = "Database"
ADDED_LATER = "Added Later"
RENAMED = "Renamed"

ADD_A_TAB = "add-a-tab"
REMOVE_THE_SELECTED_TAB = "remove-the-selected-tab"
RENAME_THE_FIRST_TAB = "rename-the-first-tab"
SELECT_THE_LAST_TAB = "select-the-last-tab"
WRITE_THE_DESCRIPTION = "write-the-description"

THE_REPORT = "report.txt"

_HOW_OFTEN_TO_CHECK_FOR_A_COMMAND_MS = 50


@dataclass
class Widgets:
    root: tk.Tk
    notebook: ttk.Notebook


def main(title: str, commands: Path) -> None:
    widgets = _a_window_with_a_notebook(title)
    # Painted first, so the tab strip has a geometry to scan.
    widgets.root.update_idletasks()
    _accessibility_switched_on(widgets.root)
    _watching_for_commands(widgets, commands)
    widgets.root.mainloop()


def _a_window_with_a_notebook(title: str) -> Widgets:
    root = tk.Tk()
    root.title(title)
    root.geometry("520x320")
    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True, padx=10, pady=10)
    for name in (FIRST, SECOND, THIRD):
        page = ttk.Frame(notebook)
        ttk.Label(page, text=f"the {name} page").pack(padx=20, pady=20)
        notebook.add(page, text=name)
    return Widgets(root=root, notebook=notebook)


def _accessibility_switched_on(root: tk.Tk) -> None:
    strategy = tk_uia.enable(root)
    if strategy is not Strategy.ANNOTATED:
        # Loudly: a mis-fired gate fails every spec below with "the tab is not there".
        raise SystemExit(
            f"tk_uia.enable reported {strategy}, not {Strategy.ANNOTATED}: "
            "there is nothing for the tab specs to read"
        )


def _add_a_tab(widgets: Widgets) -> None:
    page = ttk.Frame(widgets.notebook)
    ttk.Label(page, text=f"the {ADDED_LATER} page").pack(padx=20, pady=20)
    widgets.notebook.add(page, text=ADDED_LATER)
    # Adding beside the open tab moves no selection, so Tk fires nothing at all.
    tk_uia.add_acc_object(widgets.notebook)


def _remove_the_selected_tab(widgets: Widgets) -> None:
    # The *selected* one: removing it moves the selection, the one change Tk announces.
    widgets.notebook.forget(widgets.notebook.select())


def _rename_the_first_tab(widgets: Widgets) -> None:
    # A plain `tab(0, text=...)` fires no event at all.
    widgets.notebook.tab(0, text=RENAMED)
    tk_uia.add_acc_object(widgets.notebook)


def _select_the_last_tab(widgets: Widgets) -> None:
    widgets.notebook.select(len(widgets.notebook.tabs()) - 1)


def _write_the_description(widgets: Widgets, commands: Path) -> None:
    (commands / THE_REPORT).write_text(
        str(tk_uia.describe(widgets.root)), encoding="utf-8"
    )


def _watching_for_commands(widgets: Widgets, commands: Path) -> None:
    """Do what a spec asks, on Tk's own thread, where the annotator wants it."""
    handlers: dict[str, Callable[[], object]] = {
        ADD_A_TAB: lambda: _add_a_tab(widgets),
        REMOVE_THE_SELECTED_TAB: lambda: _remove_the_selected_tab(widgets),
        RENAME_THE_FIRST_TAB: lambda: _rename_the_first_tab(widgets),
        SELECT_THE_LAST_TAB: lambda: _select_the_last_tab(widgets),
        WRITE_THE_DESCRIPTION: lambda: _write_the_description(widgets, commands),
    }

    def look() -> None:
        for name, act in handlers.items():
            request = commands / name
            if request.exists():
                request.unlink()
                act()
        widgets.root.after(_HOW_OFTEN_TO_CHECK_FOR_A_COMMAND_MS, look)

    widgets.root.after(_HOW_OFTEN_TO_CHECK_FOR_A_COMMAND_MS, look)


if __name__ == "__main__":
    main(sys.argv[1], Path(sys.argv[2]))
