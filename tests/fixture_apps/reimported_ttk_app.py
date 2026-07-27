"""Fixture app: a notebook built from a re-imported `tkinter.ttk`.

IDLE's `idlelib/run.py` deletes seven tkinter submodules from `sys.modules` as
a workaround it has carried for a decade; any later `import tkinter.ttk`
re-executes the module and makes a second, distinct `Notebook` class. This app
performs that dance after `enable()`, then builds its notebook from the second
class. A gate that asks Python's type system instead of Tk fails it silently:
the notebook keeps its role and loses its tabs.
"""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path

import tk_uia
from tk_uia import Strategy

FIRST = "Fonts"
SECOND = "Keys"


def main(title: str, _commands: Path) -> None:
    root = tk.Tk()
    root.title(title)
    root.geometry("420x240")
    root.update_idletasks()

    strategy = tk_uia.enable(root)
    if strategy is not Strategy.ANNOTATED:
        raise SystemExit(f"tk_uia.enable reported {strategy}, not ANNOTATED")

    import tkinter.ttk  # noqa: F401  (bind the first copy, as any app would)

    del sys.modules["tkinter.ttk"]
    delattr(tk, "ttk")
    from tkinter import ttk  # a second execution: a distinct Notebook class

    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True, padx=10, pady=10)
    for name in (FIRST, SECOND):
        page = ttk.Frame(notebook)
        ttk.Label(page, text=f"the {name} page").pack(padx=20, pady=20)
        notebook.add(page, text=name)

    root.mainloop()


if __name__ == "__main__":
    main(sys.argv[1], Path(sys.argv[2]))
