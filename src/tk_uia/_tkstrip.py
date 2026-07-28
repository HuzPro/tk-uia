"""A real `ttk.Notebook`, answering the three questions the tab scan asks.

There is no public API for a tab's rectangle. `index @x,y` is the same question
Tk answers for a real mouse click, so scanning with it is the one measurement
that cannot disagree with where the tab actually is.
"""

from __future__ import annotations

import tkinter
from tkinter import ttk


class TkTabStrip:
    """One notebook's strip, as the scan sees it."""

    def __init__(self, notebook: ttk.Notebook) -> None:
        self._notebook = notebook

    def settle(self) -> None:
        """Let Tk finish laying the strip out before anything measures it.

        Idle tasks only, never `update()`, which would drain the event queue and
        re-enter whatever binding is asking for this.
        """
        self._notebook.update_idletasks()

    def tab_at(self, x: int, y: int) -> int | None:
        try:
            return int(self._notebook.index(f"@{x},{y}"))
        except (tkinter.TclError, ValueError):
            # Tk refuses rather than answers for a point that is not on a tab,
            # which is most of a notebook. Not an error here: it is the answer.
            return None

    def text_of(self, index: int) -> str:
        return str(self._notebook.tab(index, "text"))

    def size(self) -> tuple[int, int]:
        return (self._notebook.winfo_width(), self._notebook.winfo_height())


def is_a_notebook(widget: object) -> bool:
    """Whether this widget is one whose tabs need handles of their own.

    Asked of Tk, never `isinstance`: a host that re-imports `tkinter.ttk`
    makes a second Notebook class that fails the identity check.
    """
    winfo_class = getattr(widget, "winfo_class", None)
    return winfo_class is not None and winfo_class() == "TNotebook"
