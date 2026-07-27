"""Scaffolding the two widget-zoo apps share: layout, facts, and the handshake.

`every_classic_tk_widget.py` and `every_ttk_widget.py` each build their own
widgets and hand them here; `coverage_matrix.py` drives both.

Two things in here are load-bearing.

**The window is never given a fixed geometry.** A `geometry()` call makes the Tk
packer silently drop whatever will not fit, `<Map>` never fires for those
widgets, and nothing raises anywhere. In this survey that would read as
"unsupported" for a reason that has nothing to do with support, so the window
asks for the room it needs and `every_widget_is_up` refuses to go on if Tk
dropped one anyway.

**The process is made DPI-aware before Tk starts.** UI Automation reports
rectangles in physical pixels and a Tk that is not DPI-aware reports logical
ones, so on a scaled display every rectangle recorded here would miss the
control it belongs to. Correlation is by rectangle, so this is not cosmetic.
"""

from __future__ import annotations

import ctypes
import json
import sys
import tkinter as tk
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

READY_BARE = "ready-bare"
GO_ANNOTATE = "go-annotate"
READY_ANNOTATED = "ready-annotated"
GO_SAY_EVERYTHING = "go-say-everything"
READY_FULL = "ready-full"
QUIT = "quit"

THE_FACTS = "tk-facts.json"
THE_REPORT = "describe.txt"

_HOW_OFTEN_TO_LOOK_MS = 50
_HOW_MANY_COLUMNS = 4


@dataclass(frozen=True)
class WidgetFact:
    """One widget, as Tk itself describes it. The left-hand side of the matrix."""

    kind: str
    tk_class: str
    path: str
    mapped: bool
    # Screen coordinates, which is what UI Automation answers in too, and the
    # only thing the two views of this window can be joined on.
    left: int
    top: int
    right: int
    bottom: int

    @property
    def on_screen(self) -> bool:
        return self.mapped and self.right > self.left and self.bottom > self.top


def paint_at_physical_pixel_resolution() -> None:
    """Before Tk exists, or the rectangles it reports cannot be joined."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


def laid_out_in_a_grid(
    parent: tk.Misc,
    built: dict[str, tk.Misc],
    never_shows: frozenset[str] = frozenset(),
) -> None:
    """Every widget on screen at once, in the order they were declared.

    Skips the ones that cannot be laid out at all: a `Menu` is a top-level
    window Tk posts rather than a child a geometry manager can place, and
    handing one to `grid` raises rather than being ignored.
    """
    placeable = [widget for kind, widget in built.items() if kind not in never_shows]
    for index, widget in enumerate(placeable):
        widget.grid(
            row=index // _HOW_MANY_COLUMNS,
            column=index % _HOW_MANY_COLUMNS,
            padx=6,
            pady=6,
            sticky="w",
        )


def facts_about(built: dict[str, tk.Misc]) -> list[WidgetFact]:
    return [_fact_about(kind, widget) for kind, widget in built.items()]


def _fact_about(kind: str, widget: tk.Misc) -> WidgetFact:
    mapped = bool(widget.winfo_ismapped())
    left, top = widget.winfo_rootx(), widget.winfo_rooty()
    return WidgetFact(
        kind=kind,
        tk_class=widget.winfo_class(),
        path=str(widget),
        mapped=mapped,
        left=left,
        top=top,
        right=left + widget.winfo_width(),
        bottom=top + widget.winfo_height(),
    )


def every_widget_is_up(facts: list[WidgetFact], never_shows: frozenset[str]) -> None:
    """Refuse to survey a window Tk has quietly dropped widgets from.

    `never_shows` is the short list of widgets that legitimately do not map, a
    menu being posted rather than laid out. Every one of them is named rather
    than inferred, so a widget going missing for any *other* reason fails here
    instead of becoming a row that reads "unsupported".
    """
    missing = [
        fact.kind
        for fact in facts
        if not fact.on_screen and fact.kind not in never_shows
    ]
    if missing:
        raise SystemExit(
            f"Tk never put {missing} on screen, so this survey would record them "
            "as unreachable for a reason that is nothing to do with "
            "accessibility. Give the window more room."
        )


def run(
    title: str,
    workdir: Path,
    build: Callable[[tk.Tk], dict[str, tk.Misc]],
    never_shows: frozenset[str],
    say_everything: Callable[[dict[str, tk.Misc]], None],
) -> None:
    """Build the window, then walk it through the two passes the driver wants."""
    paint_at_physical_pixel_resolution()
    root = tk.Tk()
    root.title(title)
    built = build(root)
    root.update_idletasks()
    root.update()

    facts = facts_about(built)
    every_widget_is_up(facts, never_shows)
    (workdir / THE_FACTS).write_text(
        json.dumps([asdict(fact) for fact in facts], indent=2), encoding="utf-8"
    )
    _say(workdir, READY_BARE)

    _when_asked(
        root,
        workdir,
        GO_ANNOTATE,
        lambda: _annotate(root, workdir, built, say_everything),
    )
    root.mainloop()


def _annotate(
    root: tk.Tk,
    workdir: Path,
    built: dict[str, tk.Misc],
    say_everything: Callable[[dict[str, tk.Misc]], None],
) -> None:
    import tk_uia
    from tk_uia import Strategy

    strategy = tk_uia.enable(root)
    if strategy is not Strategy.ANNOTATED:
        raise SystemExit(f"enable() reported {strategy}; there is nothing to survey")
    root.update_idletasks()
    (workdir / THE_REPORT).write_text(str(tk_uia.describe(root)), encoding="utf-8")
    # Re-measured after annotating, because the tab overlays a notebook gets are
    # real windows and the strip is laid out again on the way through.
    (workdir / f"annotated-{THE_FACTS}").write_text(
        json.dumps([asdict(fact) for fact in facts_about(built)], indent=2),
        encoding="utf-8",
    )
    _say(workdir, READY_ANNOTATED)
    _when_asked(
        root,
        workdir,
        GO_SAY_EVERYTHING,
        lambda: _say_everything(root, workdir, built, say_everything),
    )


def _say_everything(
    root: tk.Tk,
    workdir: Path,
    built: dict[str, tk.Misc],
    say_everything: Callable[[dict[str, tk.Misc]], None],
) -> None:
    """The third state: what a well-behaved application adds on top of enable().

    `enable()` names a widget from its own words, and most widgets have none.
    Everything applied here is the application saying what only the application
    knows, so the gap between this state and the one before it is the work
    adopting this asks of you.
    """
    import tk_uia

    say_everything(built)
    root.update_idletasks()
    (workdir / f"full-{THE_REPORT}").write_text(
        str(tk_uia.describe(root)), encoding="utf-8"
    )
    (workdir / f"full-{THE_FACTS}").write_text(
        json.dumps([asdict(fact) for fact in facts_about(built)], indent=2),
        encoding="utf-8",
    )
    _say(workdir, READY_FULL)
    _when_asked(root, workdir, QUIT, root.quit)


def _when_asked(
    root: tk.Tk, workdir: Path, name: str, then: Callable[[], None]
) -> None:
    def look() -> None:
        asked = workdir / name
        if asked.exists():
            asked.unlink()
            then()
            return
        root.after(_HOW_OFTEN_TO_LOOK_MS, look)

    root.after(_HOW_OFTEN_TO_LOOK_MS, look)


def _say(workdir: Path, name: str) -> None:
    (workdir / name).write_text("", encoding="utf-8")


def started_from(argv: list[str]) -> tuple[str, Path]:
    return argv[1], Path(argv[2])


def name_everything(built: dict[str, tk.Misc], names: dict[str, str]) -> None:
    """Give each widget the name only the application could know.

    Refusals are swallowed on purpose: a window is named by `wm title` and says
    so, and a widget that never mapped was never annotated. Both are the package
    answering correctly.
    """
    import tk_uia
    from tk_uia import AnnotationRefused

    for kind, name in names.items():
        widget = built.get(kind)
        if widget is None:
            continue
        try:
            tk_uia.set_acc_name(widget, name)
        except AnnotationRefused:
            continue


def follow_the_values(
    built: dict[str, tk.Misc], variables: dict[str, tk.Variable]
) -> None:
    """Keep each editable widget's accessible value true from now on."""
    import tk_uia

    for kind, variable in variables.items():
        widget = built.get(kind)
        if widget is not None:
            tk_uia.bind_value_variable(widget, variable)


def main_for(
    title: str,
    build: Callable[[tk.Tk], dict[str, tk.Misc]],
    never_shows: frozenset[str] = frozenset(),
    say_everything: Callable[[dict[str, tk.Misc]], None] = lambda _built: None,
) -> None:
    given_title, workdir = started_from(sys.argv)
    run(given_title or title, workdir, build, never_shows, say_everything)
