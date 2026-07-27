"""One window holding every widget classic Tkinter has, for the survey to read.

Where it plugs in: `coverage_matrix.py` launches this, reads the window through
UI Automation before and after `enable()`, and joins the two by rectangle. It is
also runnable on its own if you just want to look at it:

    python probes/every_classic_tk_widget.py "classic tk zoo" .

Every widget class `tkinter` exposes is here, including the three that do not
behave like ordinary children and are the likeliest to come out unsupported:

- `Menu` is not a child widget at all — it is posted. One is attached to the
  window as its menubar and one to the `Menubutton`, and neither ever maps.
- `Toplevel` is a window of its own, which tk-uia deliberately refuses to
  annotate because `wm title` already names it correctly.
- `Canvas` draws its own contents, so there is nothing under it to expose.

`OptionMenu` is included even though it is a `Menubutton` underneath, because
what an application writes is `tk.OptionMenu` and the survey is read by people
who write that.
"""

from __future__ import annotations

import tkinter as tk

from _widget_zoo import (
    follow_the_values,
    laid_out_in_a_grid,
    main_for,
    name_everything,
)

TITLE = "tk-uia classic widget zoo"

# The widgets that legitimately never map, so that anything *else* going missing
# fails the run instead of quietly becoming a row that reads "unreachable".
NEVER_SHOWS = frozenset(
    {"tk.Menu (menubar)", "tk.Menu (on a Menubutton)", "tk.Toplevel"}
)


# What only the application knows. `enable()` names a widget from its own words,
# and most of these have none: an entry's caption is a *sibling* label and Tk
# records no relationship between them, so inferring one would be this package
# guessing at a layout convention.
#
# The two decorative widgets are named too, which a real application should not
# do — a separator exists to be looked at, not announced, and naming it makes a
# screen reader read out furniture. They are named here because the survey's job
# is to show every widget *can* be reached.
WHAT_TO_CALL_THEM = {
    "tk.Entry": "Task title",
    "tk.Text": "Notes",
    "tk.Scale": "Volume",
    "tk.Scrollbar": "Scroll the results",
    "tk.Spinbox": "Quantity",
    "tk.Listbox": "Search results",
    "tk.Canvas": "Activity sparkline",
    "tk.Frame": "Details",
    "tk.PanedWindow": "Split view",
}

_HELD_IN = {}


def say_everything(built: dict[str, tk.Misc]) -> None:
    name_everything(built, WHAT_TO_CALL_THEM)
    follow_the_values(built, _HELD_IN)


def build(root: tk.Tk) -> dict[str, tk.Misc]:
    built: dict[str, tk.Misc] = {}

    built["tk.Label"] = tk.Label(root, text="a Label")
    built["tk.Button"] = tk.Button(root, text="a Button")
    _HELD_IN["tk.Entry"] = tk.StringVar(master=root, value="write the report")
    built["tk.Entry"] = tk.Entry(root, textvariable=_HELD_IN["tk.Entry"])
    built["tk.Text"] = tk.Text(root, width=18, height=3)
    built["tk.Checkbutton"] = tk.Checkbutton(root, text="a Checkbutton")
    built["tk.Radiobutton"] = tk.Radiobutton(
        root, text="a Radiobutton", value=1, variable=tk.IntVar(master=root, value=1)
    )
    built["tk.Scale"] = tk.Scale(root, from_=0, to=10, orient="horizontal")
    built["tk.Scrollbar"] = tk.Scrollbar(root, orient="vertical")
    _HELD_IN["tk.Spinbox"] = tk.StringVar(master=root, value="3")
    built["tk.Spinbox"] = tk.Spinbox(
        root, from_=0, to=10, textvariable=_HELD_IN["tk.Spinbox"]
    )
    built["tk.Message"] = tk.Message(root, text="a Message", width=120)
    built["tk.Listbox"] = _a_listbox(root)
    built["tk.Canvas"] = _a_canvas(root)
    built["tk.Frame"] = _a_frame(root)
    built["tk.LabelFrame"] = _a_label_frame(root)
    built["tk.PanedWindow"] = _a_paned_window(root)
    built["tk.Menubutton"] = _a_menubutton(root, built)
    built["tk.OptionMenu"] = tk.OptionMenu(
        root, tk.StringVar(master=root, value="one"), "one", "two"
    )

    _laid_out(root, built)

    # After the layout, because neither of these is laid out at all.
    built["tk.Menu (menubar)"] = _a_menubar(root)
    built["tk.Toplevel"] = _a_toplevel(root)
    return built


def _laid_out(root: tk.Tk, built: dict[str, tk.Misc]) -> None:
    laid_out_in_a_grid(root, built, NEVER_SHOWS)


def _a_listbox(root: tk.Tk) -> tk.Listbox:
    listbox = tk.Listbox(root, height=3, width=16)
    for row in ("first row", "second row", "third row"):
        listbox.insert("end", row)
    return listbox


def _a_canvas(root: tk.Tk) -> tk.Canvas:
    canvas = tk.Canvas(root, width=120, height=60, bg="white")
    # Drawn rather than packed: a canvas's contents are paint, which is the
    # whole reason it is the one fixture the pixel fallback still exists for.
    canvas.create_text(60, 30, text="painted words")
    return canvas


def _a_frame(root: tk.Tk) -> tk.Frame:
    frame = tk.Frame(root, borderwidth=2, relief="groove")
    tk.Label(frame, text="inside a Frame").pack(padx=4, pady=4)
    return frame


def _a_label_frame(root: tk.Tk) -> tk.LabelFrame:
    frame = tk.LabelFrame(root, text="a LabelFrame")
    tk.Label(frame, text="inside it").pack(padx=4, pady=4)
    return frame


def _a_paned_window(root: tk.Tk) -> tk.PanedWindow:
    paned = tk.PanedWindow(root, orient="horizontal")
    paned.add(tk.Label(paned, text="left pane"))
    paned.add(tk.Label(paned, text="right pane"))
    return paned


def _a_menubutton(root: tk.Tk, built: dict[str, tk.Misc]) -> tk.Menubutton:
    menubutton = tk.Menubutton(root, text="a Menubutton", relief="raised")
    menu = tk.Menu(menubutton, tearoff=False)
    for label in ("first item", "second item"):
        menu.add_command(label=label)
    menubutton.configure(menu=menu)
    built["tk.Menu (on a Menubutton)"] = menu
    return menubutton


def _a_menubar(root: tk.Tk) -> tk.Menu:
    menubar = tk.Menu(root, tearoff=False)
    file_menu = tk.Menu(menubar, tearoff=False)
    file_menu.add_command(label="Open")
    file_menu.add_command(label="Quit")
    menubar.add_cascade(label="File", menu=file_menu)
    root.configure(menu=menubar)
    return menubar


def _a_toplevel(root: tk.Tk) -> tk.Toplevel:
    window = tk.Toplevel(root)
    window.title(f"{root.title()} (Toplevel)")
    tk.Label(window, text="inside a Toplevel").pack(padx=20, pady=20)
    # Beside the main window rather than over it, so that neither covers the
    # other while a client is reading rectangles off both.
    window.geometry(f"+{root.winfo_rootx()}+{root.winfo_rooty() + 620}")
    return window


if __name__ == "__main__":
    main_for(TITLE, build, NEVER_SHOWS, say_everything)
