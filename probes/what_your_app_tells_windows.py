"""Prints the description of a deliberately mixed Tk window, gaps and all.

Where it plugs in: nothing imports this. It is the script behind the report in
the README's *"What your own application tells Windows"* section, so that a
reader who doubts a line of it can re-run it rather than take it on trust.

The window is built to contain one of everything worth reporting: a label named
from its own caption, a button named and numbered by hand, an entry nobody
named, an entry whose value follows a variable, a label driven by a
`textvariable`, a canvas no role table has heard of, a listbox whose rows are
invisible, ttk widgets, a notebook whose second tab has never been shown, a
frame that is never packed, a label whose caption moved on after annotation, and
a second window.

It reads nothing back from Windows and asks no UI Automation client anything.
That is the point, and the report says so in its own last paragraph.

    python probes/what_your_app_tells_windows.py
"""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk

import tk_uia

HEADLINE = "Task list"
NEW_TASK = "New Task"
WHAT_THE_BUTTON_DOES = "creates a task and clears the form"
TITLE = "Title"
DRAFT = "Write the report"
READY = "ready"
IN_PROGRESS = "in progress"

# Chosen by the application, never by the package.
NEW_TASK_NUMBER = 4207

# Small on purpose. The packer drops whatever it cannot fit and `<Map>` never
# fires for it — the failure this whole report exists to make visible, and one
# that raises nothing anywhere.
_A_WINDOW_TOO_SMALL_FOR_EVERYTHING_IN_IT = "360x420"


@dataclass(frozen=True)
class Widgets:
    """The widgets the probe says something about, held while they are wired up."""

    root: tk.Tk
    new_task: tk.Button
    title_entry: tk.Entry
    draft: tk.StringVar
    status_label: tk.Label
    status: tk.StringVar
    restyled: tk.Label


def main() -> None:
    widgets = _a_window_with_one_of_everything_worth_reporting()
    # Realised and mapped before accessibility is switched on, so that the sweep
    # over what is already on screen is the path taken — and so that whatever
    # the geometry manager could not fit has already failed to map.
    widgets.root.update()

    tk_uia.enable(widgets.root)
    _the_things_no_widget_can_say_for_itself(widgets)
    # After annotation, and with no re-announcement: this is the caveat the
    # README documents, and the report should catch it by path.
    widgets.restyled.config(text=IN_PROGRESS)

    print(tk_uia.describe(widgets.root))
    widgets.root.destroy()


def _a_window_with_one_of_everything_worth_reporting() -> Widgets:
    root = tk.Tk()
    root.title("Tasks")
    root.geometry(_A_WINDOW_TOO_SMALL_FOR_EVERYTHING_IN_IT)

    tk.Label(root, text=HEADLINE).pack()
    new_task = tk.Button(root, text=NEW_TASK)
    new_task.pack()

    tk.Entry(root, width=20).pack()
    draft = tk.StringVar(value=DRAFT)
    title_entry = tk.Entry(root, width=20, textvariable=draft)
    title_entry.pack()

    status = tk.StringVar(value=READY)
    status_label = tk.Label(root, textvariable=status)
    status_label.pack()

    tk.Canvas(root, width=120, height=30).pack()

    listbox = tk.Listbox(root, height=3)
    for row in ("first", "second", "third"):
        listbox.insert(tk.END, row)
    listbox.pack()

    ttk.Button(root, text="Save").pack()
    ttk.Combobox(root, values=("high", "low")).pack()
    _a_notebook_whose_second_tab_nobody_has_opened(root)

    # Built and never packed, so Tk never maps it and neither it nor anything
    # inside it ever fires `<Map>`.
    never_packed = tk.Frame(root)
    tk.Label(never_packed, text="never shown").pack()

    restyled = tk.Label(root, text=HEADLINE)
    restyled.pack()

    _a_second_window(root)

    return Widgets(
        root=root,
        new_task=new_task,
        title_entry=title_entry,
        draft=draft,
        status_label=status_label,
        status=status,
        restyled=restyled,
    )


def _a_notebook_whose_second_tab_nobody_has_opened(root: tk.Tk) -> None:
    notebook = ttk.Notebook(root, height=40)
    for caption in ("Open", "Done"):
        notebook.add(ttk.Frame(notebook), text=caption)
    notebook.pack()


def _a_second_window(root: tk.Tk) -> None:
    dialog = tk.Toplevel(root)
    dialog.title("About")
    dialog.geometry("200x80")
    tk.Label(dialog, text="version 1").pack()


def _the_things_no_widget_can_say_for_itself(widgets: Widgets) -> None:
    tk_uia.set_acc_name(widgets.title_entry, TITLE)
    tk_uia.bind_value_variable(widgets.title_entry, widgets.draft)
    tk_uia.bind_text_variable(widgets.status_label, widgets.status)
    tk_uia.set_acc_description(widgets.new_task, WHAT_THE_BUTTON_DOES)
    tk_uia.set_automation_id(widgets.new_task, NEW_TASK_NUMBER)


if __name__ == "__main__":
    main()
