"""A Tk application whose widgets answer UIA for themselves, for the pattern specs."""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import tk_uia
from tk_uia import Strategy

NEW_TASK = "New Task"
OPEN_DIALOG = "Open Dialog"
SAVE = "Save"
PROXY_BUTTON = "Proxy Button"
NOTIFY = "Notify"
HIGH = "High"
TITLE_ENTRY = "Title"
VOLUME = "Volume"
CONFIRMATION = "Confirmation"
PRESSES = "plain tally"
TTK_PRESSES = "themed tally"
PROXY_PRESSES = "proxy tally"
THE_HELP = "the help the application chose"
THE_DESCRIPTION = "the description the application chose"
GENERAL_TAB = "General"
ADVANCED_TAB = "Advanced"
ON_THE_FIRST_PAGE = "the first page"
ON_THE_SECOND_PAGE = "the second page"
RED = "Red"
GREEN = "Green"
BLUE = "Blue"
SEARCH_RESULTS = "Search results"
THE_SELECTED_ROW = "Rust in production"
A_COLOUR_NOBODY_OFFERED = "Mauve"
NOTHING_YET = "-"


def chose(colour: str) -> str:
    """How the app reports the selection event it saw, where a spec can read it."""
    return f"the app heard {colour}"

_NEVER = 0


def presses(kind: str, count: int) -> str:
    return f"{kind} {count}"


def main(title: str, commands: Path) -> None:
    root = tk.Tk()
    root.title(title)
    root.geometry("420x560")

    tk.Label(root, text="Task list").pack(pady=6)

    pressed = tk.StringVar(value=presses(PRESSES, _NEVER))
    new_task = tk.Button(
        root, text=NEW_TASK, command=lambda: _count(pressed, PRESSES)
    )
    new_task.pack(pady=4)
    tk.Label(root, textvariable=pressed).pack()

    tk.Button(
        root,
        text=OPEN_DIALOG,
        command=lambda: messagebox.showinfo(CONFIRMATION, "created"),
    ).pack(pady=4)

    ttk_pressed = tk.StringVar(value=presses(TTK_PRESSES, _NEVER))
    ttk.Button(
        root, text=SAVE, command=lambda: _count(ttk_pressed, TTK_PRESSES)
    ).pack(pady=4)
    tk.Label(root, textvariable=ttk_pressed).pack()

    proxy_pressed = tk.StringVar(value=presses(PROXY_PRESSES, _NEVER))
    proxy_button = tk.Button(
        root, text=PROXY_BUTTON, command=lambda: _count(proxy_pressed, PROXY_PRESSES)
    )
    proxy_button.pack(pady=4)
    tk.Label(root, textvariable=proxy_pressed).pack()

    draft = tk.StringVar(value="")
    title_entry = tk.Entry(root, width=30, textvariable=draft)
    title_entry.pack(pady=4)

    notify = tk.IntVar(master=root, value=0)
    tk.Checkbutton(root, text=NOTIFY, variable=notify).pack(pady=4)

    priority = tk.IntVar(master=root, value=0)
    tk.Radiobutton(root, text=HIGH, value=1, variable=priority).pack(pady=4)

    scale = tk.Scale(root, from_=0, to=10, orient="horizontal", label=VOLUME)
    scale.pack(pady=4)

    ttk.Progressbar(root, value=40, maximum=100).pack(pady=4)

    colour = tk.StringVar(value=RED)
    combobox = ttk.Combobox(
        root, state="readonly", values=(RED, GREEN, BLUE), textvariable=colour
    )
    combobox.pack(pady=4)
    chosen = tk.StringVar(value=chose(NOTHING_YET))
    combobox.bind(
        "<<ComboboxSelected>>", lambda _event: chosen.set(chose(colour.get()))
    )
    tk.Label(root, textvariable=chosen).pack()

    notebook = ttk.Notebook(root)
    for page_name, page_words in ((GENERAL_TAB, ON_THE_FIRST_PAGE),
                                  (ADVANCED_TAB, ON_THE_SECOND_PAGE)):
        page = ttk.Frame(notebook)
        ttk.Label(page, text=page_words).pack(padx=8, pady=8)
        notebook.add(page, text=page_name)
    notebook.pack(pady=4)

    results = tk.Listbox(root, height=3)
    for row in ("Rust in production", "Go in anger", "Zig in doubt"):
        results.insert("end", row)
    results.pack(pady=4)

    root.update()

    strategy = tk_uia.enable(root)
    if strategy is not Strategy.PROVIDED:
        raise SystemExit(
            f"tk_uia.enable reported {strategy}, not {Strategy.PROVIDED}: "
            "these widgets would not be answering for themselves, so the "
            "pattern specs would be measuring the proxy"
        )

    tk_uia.set_acc_name(title_entry, TITLE_ENTRY)
    tk_uia.set_acc_name(results, SEARCH_RESULTS)
    tk_uia.set_acc_value(results, THE_SELECTED_ROW)
    tk_uia.set_acc_help(new_task, THE_HELP)
    tk_uia.set_acc_description(new_task, THE_DESCRIPTION)
    tk_uia.leave_to_the_proxy(proxy_button)

    root.mainloop()


def _count(tally: tk.StringVar, kind: str) -> None:
    already = int(tally.get().split()[-1])
    tally.set(presses(kind, already + 1))


if __name__ == "__main__":
    main(sys.argv[1], Path(sys.argv[2]))
