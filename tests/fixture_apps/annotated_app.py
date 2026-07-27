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

# The form row: what the caption says, and what the entry beside it is therefore
# called. The colon is on the label and not on the name — every caption in a
# real dialog ends with one, and none of them is part of a control's name.
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

# The two widgets nothing in this application says one word about. Both are
# built with a `textvariable` and neither is ever passed to `bind_text_variable`
# or `bind_value_variable`, which is the whole point of them: what a client
# reads back is what `enable()` alone worked out from what the widget declared.
UNBOUND_STATUS = "nobody bound this"
UNBOUND_STATUS_MOVED = "and it followed anyway"
UNBOUND_DRAFT = "typed into an unbound entry"
UNBOUND_DRAFT_REVISED = "retyped, still unbound"
UNBOUND_ENTRY_NAME = "Unbound"

# Chosen by this application, never by the package: an id derived from a widget
# path would make every repack a breaking change for whoever locates by it.
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
    host_caption: tk.Label
    host: tk.Entry
    unbound_status: tk.StringVar
    unbound_draft: tk.StringVar
    unbound_entry: tk.Entry


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
    # Tall enough for every widget below to be laid out: the Tk packer silently
    # drops whatever it cannot fit, `<Map>` never fires for those, and a spec
    # measuring one would be measuring a widget accessibility never reached.
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

    # A form row exactly as Tk lays one out: a caption, and the entry it
    # captions, side by side. Nothing in the toolkit records that the two have
    # anything to do with each other — the application says so, once, below.
    row = tk.Frame(root)
    row.pack(pady=10)
    host_caption = tk.Label(row, text=HOST_CAPTION)
    host_caption.pack(side=tk.LEFT)
    host = tk.Entry(row, width=20)
    host.pack(side=tk.LEFT)

    # The pair nothing below ever mentions again: an ordinary Tk label and an
    # ordinary Tk entry, each built the way the tutorials build them, and
    # neither bound to anything by this application. Whatever a client reads out
    # of these two came from the widget's own `-textvariable` and from nowhere
    # else, which is the only way to prove that half is real.
    unbound_status = tk.StringVar(value=UNBOUND_STATUS)
    tk.Label(root, textvariable=unbound_status).pack()
    unbound_draft = tk.StringVar(value=UNBOUND_DRAFT)
    unbound_entry = tk.Entry(root, width=30, textvariable=unbound_draft)
    unbound_entry.pack()

    # The control group, and it is a widget of somebody's own class: every class
    # both toolkits ship has a role now, so the only thing `enable()` walks past
    # is one it has never heard of. It stays exactly as bare Tk left it, in the
    # same window, in the same process, reached by the same call that annotated
    # everything around it.
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
    # Its *name* and nothing else. What is in this entry is what is in the
    # variable it declares, and saying who it is must not stop that being read:
    # the two are different questions a client asks separately.
    tk_uia.set_acc_name(widgets.unbound_entry, UNBOUND_ENTRY_NAME)
    # The one thing an entry's caption cannot say for itself: in Tk it is a
    # sibling label, and nothing in the toolkit records which widget it speaks
    # for. Said once, about the pair, rather than by copying its words across.
    tk_uia.label_for(widgets.host_caption, widgets.host)
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


def _move_what_nobody_bound(widgets: Widgets) -> None:
    """Write the two variables this application declared and never bound.

    Ordinary `StringVar.set` calls, of the kind an application makes all day.
    Nothing here mentions tk-uia, which is exactly what a client reading the new
    words back has to be evidence of.
    """
    widgets.unbound_status.set(UNBOUND_STATUS_MOVED)
    widgets.unbound_draft.set(UNBOUND_DRAFT_REVISED)


def _write_the_description(widgets: Widgets, commands: Path) -> None:
    """Leave what tk-uia believes it wrote where a client outside can read it.

    Two files, both the same description: the report a reader would print, and
    the names it claims, as data. The second is what the spec comparing every
    claimed name against the real UI Automation tree consumes — re-parsing a
    table this process has just formatted would test the formatter twice and
    the claim not at all.
    """
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
        MOVE_WHAT_NOBODY_BOUND: lambda: _move_what_nobody_bound(widgets),
        # Tk's own invoke, which really does run the command — the control that
        # stops "the counter never moved" being mistaken for "the counter could
        # never have moved".
        PRESS_THE_BUTTON: widgets.new_task.invoke,
        WRITE_THE_DESCRIPTION: lambda: _write_the_description(widgets, commands),
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
