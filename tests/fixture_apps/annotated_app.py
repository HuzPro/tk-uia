"""A Tk application that annotates itself, for the gui specs to read back.

Where it plugs in: launched as a subprocess by `tests/conftest.py`, then read
through UI Automation from the pytest process. Being in a separate process is
the whole point — an annotation is written into this process's MSAA store, and
only a client outside it can prove Windows really bridged it to UI Automation.

Classic `tk` throughout, never `ttk`: measured against every ttk widget type,
each one is an anonymous `PaneControl` and `ttk.Button` has no InvokePattern at
all, so ttk is strictly the worse starting point.

The window titles itself from `argv`, so several runs — or a window left behind
by a crashed one — can never be mistaken for each other.

It also takes a directory to watch. A spec that needs the application to *do*
something asks by dropping a named file there, because the one thing a client
cannot do to a Tk window is press its buttons — which is the honest limitation
this package documents, and which one of these specs exists to pin down.
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
DRAFT = "Write the report"
REVISION = "Write the quarterly report"
DISPOSABLE = "Disposable"
SCRATCH = "Scratch"
READY = "ready"
TASK_CREATED = "task created"
PRESSES = "presses"
TRACES = "traces"

# Chosen by this application, never by the package: an id derived from a widget
# path would make every repack a breaking change for whoever locates by it.
NEW_TASK_NUMBER = 4207

FORGET_THE_DISPOSABLE_WIDGETS = "forget"
ADVANCE_THE_STATUS = "advance"
REVISE_THE_DRAFT = "revise"
PRESS_THE_BUTTON = "press"
DESTROY_THE_STATUS_LABEL = "destroy"

_HOW_OFTEN_TO_CHECK_FOR_A_COMMAND_MS = 50

_NEVER = 0


def presses(count: int) -> str:
    """How the button's own tally reads, in the one place both sides agree."""
    return f"{PRESSES} {count}"


def traces(count: int) -> str:
    """How many write traces are still registered on the status variable.

    Reported into the window rather than asserted in-process, because the whole
    point of the gui specs is that the claim is read from outside. A trace is
    registered on the *variable*, which outlives every widget that displays it,
    so this is the number that says whether a destroyed widget let go.
    """
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


def main(title: str, commands: Path) -> None:
    widgets = _a_window_of_classic_tk_widgets(title)
    # Realised and mapped before accessibility is switched on, so that the
    # sweep over what is already on screen is the path under test here — which
    # is the path an application that calls `enable()` late will take.
    widgets.root.update()

    _accessibility_switched_on(widgets.root)
    _the_things_no_widget_can_say_for_itself(widgets)
    _watching_for_commands(widgets, commands)

    widgets.root.mainloop()


def _a_window_of_classic_tk_widgets(title: str) -> Widgets:
    root = tk.Tk()
    root.title(title)
    root.geometry("420x420")

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

    # The control group, and the reason it is a canvas: `ROLE_FOR_TK_CLASS` has
    # no entry for one, so `enable()` walks straight past it. It stays exactly
    # as bare Tk left it, in the same window, in the same process, reached by
    # the same call that annotated everything around it.
    tk.Canvas(root, width=200, height=40).pack(pady=10)

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
    )


def _an_entry_holding_a_draft(root: tk.Tk, draft: tk.StringVar) -> tk.Entry:
    # A frame deep on purpose: `enable()`'s sweep of what is already on screen
    # has to descend, and a widget only reachable by recursion is the one that
    # proves it does.
    frame = tk.Frame(root)
    frame.pack(pady=10)
    entry = tk.Entry(frame, width=30, textvariable=draft)
    entry.pack()
    return entry


def _accessibility_switched_on(root: tk.Tk) -> None:
    strategy = tk_uia.enable(root)
    if strategy is not Strategy.ANNOTATED:
        # Loudly, and before the window is worth reading: a gate that mis-fires
        # leaves every widget exactly as bare Tk left it, and a suite that only
        # asserted "the name is right" would report that as an ordinary miss.
        raise SystemExit(
            f"tk_uia.enable reported {strategy}, not {Strategy.ANNOTATED}: "
            "nothing in this window has been annotated, so the gui specs "
            "would be measuring bare Tk"
        )


def _the_things_no_widget_can_say_for_itself(widgets: Widgets) -> None:
    # An entry has no `-text` to be named from, and a name invented from its Tk
    # path would be worse than none, so this is the application's job.
    tk_uia.set_acc_name(widgets.title_entry, TITLE)
    tk_uia.set_acc_name(widgets.disposable_entry, SCRATCH)
    # A widget showing a `textvariable` has no `-text` either, so the two
    # widgets whose whole job is to report what just happened are the two that
    # would otherwise never say anything at all.
    tk_uia.bind_text_variable(widgets.status_label, widgets.status)
    tk_uia.bind_text_variable(widgets.tally, widgets.pressed)
    tk_uia.bind_text_variable(widgets.trace_tally, widgets.still_traced)
    _report_what_is_still_traced(widgets)
    # And what a client reads out of the entry is what is in the variable
    # behind it, from now on rather than only at startup.
    tk_uia.bind_value_variable(widgets.title_entry, widgets.draft)
    tk_uia.set_automation_id(widgets.new_task, NEW_TASK_NUMBER)


def _report_what_is_still_traced(widgets: Widgets) -> None:
    widgets.still_traced.set(traces(len(widgets.status.trace_info())))


def _destroy_the_status_label(widgets: Widgets) -> None:
    """Kill a bound widget, then write the variable it was following.

    The order is the whole spec. If the binding did not let go, the write below
    fires a trace at a window path Tk no longer has, and the `TclError` that
    raises inside Tcl's own callback stops this handler before it can report —
    so the count a client reads never moves, and the spec says why.
    """
    widgets.status_label.destroy()
    widgets.status.set(TASK_CREATED)
    _report_what_is_still_traced(widgets)


def _count_a_press(pressed: tk.StringVar) -> None:
    # The displayed tally is the count, rather than a second copy of it kept
    # alongside: two numbers that have to agree are one more thing to get wrong
    # in a fixture whose whole job is to be believed.
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
        # Tk's own invoke, which really does run the command — the control that
        # stops "the counter never moved" being mistaken for "the counter could
        # never have moved".
        PRESS_THE_BUTTON: widgets.new_task.invoke,
    }

    def look() -> None:
        for name, act in handlers.items():
            request = commands / name
            if request.exists():
                # Removed before acting, so the command runs exactly once
                # however long the act takes.
                request.unlink()
                act()
        widgets.root.after(_HOW_OFTEN_TO_CHECK_FOR_A_COMMAND_MS, look)

    widgets.root.after(_HOW_OFTEN_TO_CHECK_FOR_A_COMMAND_MS, look)


def _forget(*widgets: tk.Misc) -> None:
    for widget in widgets:
        tk_uia.forget(widget)


if __name__ == "__main__":
    main(sys.argv[1], Path(sys.argv[2]))
