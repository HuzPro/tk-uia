"""A Tk application that annotates itself, for the gui specs to read back.

Classic `tk` throughout, never `ttk`: measured against every ttk widget type,
each one is an anonymous `PaneControl` and `ttk.Button` has no InvokePattern at
all. It titles itself from `argv`, so a window left behind by a crashed run can
never be mistaken for this one, and takes a directory to watch, because the one
thing a client cannot do to a Tk window is press its buttons.
"""

from __future__ import annotations

import sys
import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import tk_uia
from tk_uia import Strategy

NEW_TASK = "New Task"
HEADLINE = "Task list"
TITLE = "Title"

# The colon is on the label and not on the name.
HOST_CAPTION = "Host:"
HOST = "Host"
DRAFT = "Write the report"
REVISION = "Write the quarterly report"
DISPOSABLE = "Disposable"
SCRATCH = "Scratch"
A_CLASS_NOBODY_HAS_A_ROLE_FOR = "SparklineChart"
READY = "ready"
TASK_CREATED = "task created"
PRESSES = "presses"
TRACES = "traces"

# The two widgets nothing here binds: what a client reads came from `enable()` alone.
UNBOUND_STATUS = "nobody bound this"
UNBOUND_STATUS_MOVED = "and it followed anyway"
UNBOUND_DRAFT = "typed into an unbound entry"
UNBOUND_DRAFT_REVISED = "retyped, still unbound"
UNBOUND_ENTRY_NAME = "Unbound"

# Chosen by this application: an id from a widget path would break on every repack.
NEW_TASK_NUMBER = 4207

FORGET_THE_DISPOSABLE_WIDGETS = "forget"
ADVANCE_THE_STATUS = "advance"
REVISE_THE_DRAFT = "revise"
MOVE_WHAT_NOBODY_BOUND = "unbound"
PRESS_THE_BUTTON = "press"
DESTROY_THE_STATUS_LABEL = "destroy"
WRITE_THE_DESCRIPTION = "describe"

# What the description is left in, for a spec outside this process to read.
THE_REPORT = "description.txt"
THE_NAMES_IT_CLAIMS = "claimed-names.txt"

_BETWEEN_A_PATH_AND_ITS_NAME = "\t"

_HOW_OFTEN_TO_CHECK_FOR_A_COMMAND_MS = 50

_NEVER = 0


def presses(count: int) -> str:
    """How the button's own tally reads, in the one place both sides agree."""
    return f"{PRESSES} {count}"


def traces(count: int) -> str:
    """How many write traces are still registered on the status variable."""
    return f"{TRACES} {count}"


@dataclass(frozen=True)
class Widgets:
    """The widgets the specs read, held together while they are wired up."""

    root: tk.Tk
    new_task: tk.Button
    pressed: tk.StringVar
    tally: tk.Label
    draft: tk.StringVar
    title_entry: tk.Entry
    status: tk.StringVar
    status_label: tk.Label
    still_traced: tk.StringVar
    trace_tally: tk.Label
    disposable_label: tk.Label
    disposable_entry: tk.Entry
    host_caption: tk.Label
    host: tk.Entry
    unbound_status: tk.StringVar
    unbound_draft: tk.StringVar
    unbound_entry: tk.Entry


def main(title: str, commands: Path) -> None:
    widgets = _a_window_of_classic_tk_widgets(title)
    # Mapped before accessibility is switched on: the path under test is the sweep.
    widgets.root.update()

    _accessibility_switched_on(widgets.root)
    _the_things_no_widget_can_say_for_itself(widgets)
    _watching_for_commands(widgets, commands)

    widgets.root.mainloop()


def _a_window_of_classic_tk_widgets(title: str) -> Widgets:
    root = tk.Tk()
    root.title(title)
    # Tall enough for every widget below: the Tk packer drops what it cannot fit.
    root.geometry("420x520")

    tk.Label(root, text=HEADLINE).pack(pady=10)

    pressed = tk.StringVar(value=presses(_NEVER))
    new_task = tk.Button(root, text=NEW_TASK, command=lambda: _count_a_press(pressed))
    new_task.pack(pady=10)
    tally = tk.Label(root, textvariable=pressed)
    tally.pack()

    status = tk.StringVar(value=READY)
    status_label = tk.Label(root, textvariable=status)
    status_label.pack(pady=10)

    still_traced = tk.StringVar(value=traces(_NEVER))
    trace_tally = tk.Label(root, textvariable=still_traced)
    trace_tally.pack()

    disposable_label = tk.Label(root, text=DISPOSABLE)
    disposable_label.pack()
    disposable_entry = tk.Entry(root, width=20)
    disposable_entry.pack()

    # Nothing in Tk records that a caption and its entry are related.
    row = tk.Frame(root)
    row.pack(pady=10)
    host_caption = tk.Label(row, text=HOST_CAPTION)
    host_caption.pack(side=tk.LEFT)
    host = tk.Entry(row, width=20)
    host.pack(side=tk.LEFT)

    unbound_status = tk.StringVar(value=UNBOUND_STATUS)
    tk.Label(root, textvariable=unbound_status).pack()
    unbound_draft = tk.StringVar(value=UNBOUND_DRAFT)
    unbound_entry = tk.Entry(root, width=30, textvariable=unbound_draft)
    unbound_entry.pack()

    # The control group: a class `enable()` walks past, left exactly as bare Tk left it.
    tk.Frame(root, class_=A_CLASS_NOBODY_HAS_A_ROLE_FOR, width=200, height=40).pack(
        pady=10
    )

    draft = tk.StringVar(value=DRAFT)

    return Widgets(
        root=root,
        new_task=new_task,
        pressed=pressed,
        tally=tally,
        draft=draft,
        title_entry=_an_entry_holding_a_draft(root, draft),
        status=status,
        status_label=status_label,
        still_traced=still_traced,
        trace_tally=trace_tally,
        disposable_label=disposable_label,
        disposable_entry=disposable_entry,
        host_caption=host_caption,
        host=host,
        unbound_status=unbound_status,
        unbound_draft=unbound_draft,
        unbound_entry=unbound_entry,
    )


def _an_entry_holding_a_draft(root: tk.Tk, draft: tk.StringVar) -> tk.Entry:
    # A frame deep on purpose: only recursion reaches this entry.
    frame = tk.Frame(root)
    frame.pack(pady=10)
    entry = tk.Entry(frame, width=30, textvariable=draft)
    entry.pack()
    return entry


def _accessibility_switched_on(root: tk.Tk) -> None:
    strategy = tk_uia.enable(root)
    if strategy is not Strategy.ANNOTATED:
        # Loudly: a mis-fired gate leaves every widget as bare Tk left it.
        raise SystemExit(
            f"tk_uia.enable reported {strategy}, not {Strategy.ANNOTATED}: "
            "nothing in this window has been annotated, so the gui specs "
            "would be measuring bare Tk"
        )


def _the_things_no_widget_can_say_for_itself(widgets: Widgets) -> None:
    # An entry has no `-text` to be named from, so this is the application's job.
    tk_uia.set_acc_name(widgets.title_entry, TITLE)
    tk_uia.set_acc_name(widgets.disposable_entry, SCRATCH)
    # Its *name* and nothing else: what is in it comes from the variable it declares.
    tk_uia.set_acc_name(widgets.unbound_entry, UNBOUND_ENTRY_NAME)
    tk_uia.label_for(widgets.host_caption, widgets.host)
    # A widget showing a `textvariable` has no `-text` to be named from either.
    tk_uia.bind_text_variable(widgets.status_label, widgets.status)
    tk_uia.bind_text_variable(widgets.tally, widgets.pressed)
    tk_uia.bind_text_variable(widgets.trace_tally, widgets.still_traced)
    _report_what_is_still_traced(widgets)
    # From now on rather than only at startup.
    tk_uia.bind_value_variable(widgets.title_entry, widgets.draft)
    tk_uia.set_automation_id(widgets.new_task, NEW_TASK_NUMBER)


def _report_what_is_still_traced(widgets: Widgets) -> None:
    widgets.still_traced.set(traces(len(widgets.status.trace_info())))


def _destroy_the_status_label(widgets: Widgets) -> None:
    """Kill a bound widget, then write the variable it was following."""
    widgets.status_label.destroy()
    widgets.status.set(TASK_CREATED)
    _report_what_is_still_traced(widgets)


def _move_what_nobody_bound(widgets: Widgets) -> None:
    """Write the two variables this application declared and never bound."""
    widgets.unbound_status.set(UNBOUND_STATUS_MOVED)
    widgets.unbound_draft.set(UNBOUND_DRAFT_REVISED)


def _write_the_description(widgets: Widgets, commands: Path) -> None:
    """Leave what tk-uia believes it wrote where a client outside can read it."""
    description = tk_uia.describe(widgets.root)
    (commands / THE_REPORT).write_text(str(description), encoding="utf-8")
    (commands / THE_NAMES_IT_CLAIMS).write_text(
        "\n".join(
            f"{widget.path}{_BETWEEN_A_PATH_AND_ITS_NAME}{widget.name}"
            for widget in description.widgets
            if widget.name is not None
        ),
        encoding="utf-8",
    )


def _count_a_press(pressed: tk.StringVar) -> None:
    # The displayed tally is the count, rather than a second copy kept alongside it.
    already = int(pressed.get().split()[-1])
    pressed.set(presses(already + 1))


def _watching_for_commands(widgets: Widgets, commands: Path) -> None:
    """Do what a spec asks, on Tk's own thread, where the annotator wants it."""
    handlers: dict[str, Callable[[], object]] = {
        FORGET_THE_DISPOSABLE_WIDGETS: lambda: _forget(
            widgets.disposable_label, widgets.disposable_entry
        ),
        ADVANCE_THE_STATUS: lambda: widgets.status.set(TASK_CREATED),
        DESTROY_THE_STATUS_LABEL: lambda: _destroy_the_status_label(widgets),
        REVISE_THE_DRAFT: lambda: widgets.draft.set(REVISION),
        MOVE_WHAT_NOBODY_BOUND: lambda: _move_what_nobody_bound(widgets),
        # Tk's own invoke, which really does run the command.
        PRESS_THE_BUTTON: widgets.new_task.invoke,
        WRITE_THE_DESCRIPTION: lambda: _write_the_description(widgets, commands),
    }

    def look() -> None:
        for name, act in handlers.items():
            request = commands / name
            if request.exists():
                # Removed before acting, so the command runs exactly once.
                request.unlink()
                act()
        widgets.root.after(_HOW_OFTEN_TO_CHECK_FOR_A_COMMAND_MS, look)

    widgets.root.after(_HOW_OFTEN_TO_CHECK_FOR_A_COMMAND_MS, look)


def _forget(*widgets: tk.Misc) -> None:
    for widget in widgets:
        tk_uia.forget(widget)


if __name__ == "__main__":
    main(sys.argv[1], Path(sys.argv[2]))
