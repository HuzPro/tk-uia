"""How much of Tkinter a Windows accessibility client can actually see.

Nothing imports this. It launches the two widget zoos beside it, reads each
window through UI Automation twice, once as bare Tk and once after `enable()`,
and writes a table saying what a client gets for every widget class Tk has.

    python probes/coverage_matrix.py

The two views are joined **by rectangle**, not by name. Matching on a name
collapses exactly where the interesting answers are: a widget whose class has no
role is never annotated, so it has no name to match on, and those are the rows
this exists to find. Every widget has a rectangle.

The `a test writes` column is read by shelling out to a sibling `pytest-uia`
checkout, because asking it directly is the only way to be sure the answer is
not this file's own copy of a table that could drift. Without one the column is
left out and the report says so.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

from _widget_zoo import (
    GO_ANNOTATE,
    GO_SAY_EVERYTHING,
    QUIT,
    READY_ANNOTATED,
    READY_BARE,
    READY_FULL,
    THE_FACTS,
    THE_REPORT,
)

HERE = Path(__file__).parent
OUT = HERE.parent / "COVERAGE.md"

# Where a sibling checkout of the other half usually is. Only ever used to run
# its dump; nothing here imports it, and the report is written either way.
A_SIBLING_PYTEST_UIA = (
    HERE.parent.parent / "pytest-uia" / ".venv" / "Scripts" / "python.exe"
)

_HOW_LONG_TO_WAIT_SECONDS = 40.0
_HOW_OFTEN_TO_LOOK = 0.1
# Tk and UI Automation agree on rectangles to the pixel when the process is DPI
# aware; this is slack for a border, not for a guess.
_CLOSE_ENOUGH_PIXELS = 3

_THE_PATTERNS_WORTH_ASKING_ABOUT = (
    "Value",
    "Toggle",
    "SelectionItem",
    "Selection",
    "RangeValue",
    "Invoke",
    "ExpandCollapse",
    "Scroll",
    "Grid",
)

_ASK_PYTEST_UIA = """
import json, sys
from pytest_uia.application.session import session_on_this_desktop
from pytest_uia.domain.tree import DumpLimits
app = session_on_this_desktop().attach(title=sys.argv[1], timeout=30.0)
dump = app.dump(limits=DumpLimits(max_nodes=4000, budget=120.0))
print(json.dumps({
    "queries": list(dump.queries),
    "nodes": [
        {"control_type": n.control_type, "name": n.name, "role": None if n.role is None else n.role.name}
        for n in dump.nodes
    ],
}))
"""


@dataclass(frozen=True)
class Seen:
    """One control as a client reads it."""

    control_type: str
    name: str
    left: int
    top: int
    right: int
    bottom: int
    patterns: tuple[str, ...]
    children: int

    def matches(self, fact: dict[str, Any]) -> bool:
        return all(
            abs(getattr(self, side) - fact[side]) <= _CLOSE_ENOUGH_PIXELS
            for side in ("left", "top", "right", "bottom")
        )

    @property
    def area(self) -> int:
        return max(0, self.right - self.left) * max(0, self.bottom - self.top)


def main() -> int:
    reports = []
    for script, label in (
        ("every_classic_tk_widget.py", "classic tk"),
        ("every_ttk_widget.py", "ttk"),
    ):
        print(f"surveying {label} ...", flush=True)
        reports.append((label, _survey(script)))
    OUT.write_text(_written(reports), encoding="utf-8")
    print(f"\nwrote {OUT}")
    return 0


def _survey(script: str) -> dict[str, Any]:
    title = f"tk-uia zoo {uuid.uuid4()}"
    with tempfile.TemporaryDirectory() as raw:
        workdir = Path(raw)
        app = subprocess.Popen(
            [sys.executable, str(HERE / script), title, str(workdir)],
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            _wait_for(workdir / READY_BARE, app)
            facts = json.loads((workdir / THE_FACTS).read_text(encoding="utf-8"))
            bare = _what_a_client_sees(title)

            (workdir / GO_ANNOTATE).write_text("", encoding="utf-8")
            _wait_for(workdir / READY_ANNOTATED, app)
            annotated = _what_a_client_sees(title)
            annotated_facts = json.loads(
                (workdir / f"annotated-{THE_FACTS}").read_text(encoding="utf-8")
            )
            (workdir / GO_SAY_EVERYTHING).write_text("", encoding="utf-8")
            _wait_for(workdir / READY_FULL, app)
            full = _what_a_client_sees(title)
            full_facts = json.loads(
                (workdir / f"full-{THE_FACTS}").read_text(encoding="utf-8")
            )
            queries = _what_pytest_uia_offers(title)
            report = (workdir / f"full-{THE_REPORT}").read_text(encoding="utf-8")
        finally:
            (workdir / QUIT).write_text("", encoding="utf-8")
            _closed(app)
    return {
        "facts": full_facts or annotated_facts or facts,
        "bare": bare,
        "annotated": annotated,
        "full": full,
        "queries": queries,
        "gaps": _gaps_from(report),
    }


def _wait_for(flag: Path, app: subprocess.Popen[str]) -> None:
    ran_out_at = time.monotonic() + _HOW_LONG_TO_WAIT_SECONDS
    while time.monotonic() < ran_out_at:
        if flag.exists():
            return
        if app.poll() is not None:
            raise SystemExit(f"the zoo exited {app.returncode}:\n{app.stderr.read()}")
        time.sleep(_HOW_OFTEN_TO_LOOK)
    raise SystemExit(f"the zoo never wrote {flag.name}")


def _closed(app: subprocess.Popen[str]) -> None:
    try:
        app.wait(timeout=10.0)
    except subprocess.TimeoutExpired:
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(app.pid)],
            capture_output=True,
            check=False,
        )


def _what_a_client_sees(title: str) -> list[Seen]:
    """Every control under this survey's windows, both of them where there are two.

    A `Toplevel` is a window of its own rather than a control inside the first,
    so a reader that walked only the main window would report it as absent and
    the row would read as unsupported.
    """
    import uiautomation as auto

    window = auto.WindowControl(searchDepth=1, Name=title)
    if not window.Exists(10, 0.2):
        raise SystemExit(f"no window titled {title!r}")
    seen = [_read(control) for control, _ in auto.WalkControl(window, includeTop=True)]

    beside_it = auto.WindowControl(searchDepth=1, Name=f"{title} (Toplevel)")
    if beside_it.Exists(2, 0.2):
        seen += [
            _read(control)
            for control, _ in auto.WalkControl(beside_it, includeTop=True)
        ]
    return seen


def _read(control: Any) -> Seen:
    rect = control.BoundingRectangle
    return Seen(
        control_type=control.ControlTypeName,
        name=control.Name or "",
        left=rect.left,
        top=rect.top,
        right=rect.right,
        bottom=rect.bottom,
        patterns=_patterns_on(control),
        children=len(control.GetChildren()),
    )


def _patterns_on(control: Any) -> tuple[str, ...]:
    import uiautomation as auto

    offered = []
    for name in _THE_PATTERNS_WORTH_ASKING_ABOUT:
        pattern_id = getattr(auto.PatternId, f"{name}Pattern", None)
        if pattern_id is None:
            continue
        try:
            if control.GetPattern(pattern_id) is not None:
                offered.append(name)
        except Exception:  # noqa: BLE001, S112 -- see below
            # A provider that raises when asked is one that does not offer the
            # pattern, and comtypes reports that as any of half a dozen
            # HRESULTs.
            continue
    return tuple(offered)


def _what_pytest_uia_offers(title: str) -> dict[str, Any] | None:
    if not A_SIBLING_PYTEST_UIA.exists():
        return None
    done = subprocess.run(
        [str(A_SIBLING_PYTEST_UIA), "-c", _ASK_PYTEST_UIA, title],
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode != 0:
        print(f"  (pytest-uia column unavailable: {done.stderr.strip()[:200]})")
        return None
    return json.loads(done.stdout)


def _gaps_from(report: str) -> dict[str, list[str]]:
    """The gap names `describe()` reported, per Tk path."""
    gaps: dict[str, list[str]] = {}
    current = ""
    for line in report.splitlines():
        stripped = line.strip()
        if stripped and stripped.split()[0].isupper() and "(" in stripped:
            current = stripped.split()[0]
        elif current and stripped.startswith("."):
            gaps.setdefault(stripped.split()[0], []).append(current)
    return gaps


def _written(reports: list[tuple[str, dict[str, Any]]]) -> str:
    lines = [
        "# What a Windows accessibility client sees in Tkinter",
        "",
        "Measured, not asserted: every row below is one widget in a real window,",
        "read back through UI Automation from another process. Regenerate with",
        "`python probes/coverage_matrix.py`.",
        "",
        "The two views are joined by rectangle rather than by name, because a",
        "widget whose class has no role is never annotated and so has no name to",
        "join on — and those are the rows worth having.",
        "",
    ]
    for label, survey in reports:
        lines += _a_table(label, survey)
    return "\n".join(lines) + "\n"


def _a_table(label: str, survey: dict[str, Any]) -> list[str]:
    queries = survey["queries"]
    lines = [
        f"## {label}",
        "",
        "| widget | `winfo_class` | bare Tk | after `enable()` | + what the app says | patterns | `describe()` says | a test writes |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for fact in survey["facts"]:
        bare = _best_match(survey["bare"], fact)
        now = _best_match(survey["annotated"], fact)
        full = _best_match(survey["full"], fact)
        lines.append(
            "| `{kind}` | `{tk_class}` | {bare} | {now} | {full} | {patterns} | {gaps} | {query} |".format(
                kind=fact["kind"],
                tk_class=fact["tk_class"],
                bare=_as_cell(bare),
                now=_as_cell(now),
                full=_as_cell(full),
                patterns=", ".join(full.patterns) if full else "—",
                gaps=", ".join(survey["gaps"].get(fact["path"], [])) or "—",
                query=_query_for(full, queries),
            )
        )
    lines += [
        "",
        *_the_tally(label, survey),
        "",
        _how_the_query_column_was_filled(queries),
        "",
    ]
    return lines


def _the_tally(label: str, survey: dict[str, Any]) -> list[str]:
    """The counts, so nobody has to add up a table to answer 'how much of it'."""
    on_screen = [fact for fact in survey["facts"] if fact["mapped"]]
    queries = survey["queries"]
    how_many = len(on_screen)
    never = len(survey["facts"]) - how_many

    def at(state: str) -> list[Any]:
        return [_best_match(survey[state], fact) for fact in on_screen]

    def typed(seen: list[Any]) -> int:
        return sum(1 for one in seen if one and one.control_type != _ANONYMOUS)

    def named(seen: list[Any]) -> int:
        return sum(1 for one in seen if one and one.name)

    def queryable(seen: list[Any]) -> str:
        if queries is None:
            return "unknown"
        return str(sum(1 for one in seen if _query_for(one, queries).startswith("`")))

    full = at("full")
    return [
        f"**{len(survey['facts'])} widget classes surveyed, {never} never on screen.**",
        "",
        f"| of {how_many} on screen | typed | named | queryable |",
        "|---|---|---|---|",
        f"| bare Tk | {typed(at('bare'))} | {named(at('bare'))} | — |",
        f"| after `enable()` | {typed(at('annotated'))} | {named(at('annotated'))} | — |",
        f"| **+ what the app says** | **{typed(full)}** | **{named(full)}** | **{queryable(full)}** |",
    ]


_ANONYMOUS = "PaneControl"


def _best_match(seen: list[Seen], fact: dict[str, Any]) -> Seen | None:
    if not fact["mapped"]:
        return None
    matching = [one for one in seen if one.matches(fact)]
    if not matching:
        return None
    # A frame and the single widget filling it can share a rectangle to the
    # pixel. The smaller one is the widget; the larger is what it sits in.
    return min(matching, key=lambda one: one.area)


def _as_cell(seen: Seen | None) -> str:
    if seen is None:
        return "*not on screen*"
    return (
        f"`{seen.control_type}` {seen.name!r}"
        if seen.name
        else f"`{seen.control_type}` —"
    )


def _query_for(seen: Seen | None, queries: dict[str, Any] | None) -> str:
    """The line a test would really write, taken from the list pytest-uia offers.

    Built from the offered list rather than from the node's role, which is not
    the same question: a control can carry `Role.TEXTBOX` and still authorise
    nothing, because it has no accessible name to match on. Deriving the query
    from the role would print `app.textbox("")` for every unnamed entry.
    """
    if queries is None:
        return "*n/a*"
    if seen is None:
        return "—"
    offered = set(queries["queries"])
    for node in queries["nodes"]:
        if node["control_type"] != seen.control_type or node["name"] != seen.name:
            continue
        if not node["role"]:
            return "**no query**"
        written = f'app.{node["role"].lower()}("{seen.name}")'
        return f"`{written}`" if written in offered else "**no query**"
    return "**no query**"


def _how_the_query_column_was_filled(queries: dict[str, Any] | None) -> str:
    if queries is None:
        return (
            "*The `a test writes` column needs a sibling `pytest-uia` checkout with "
            "its virtualenv; without one it is left blank rather than guessed.*"
        )
    return f"*{len(queries['queries'])} queries offered for this window.*"


if __name__ == "__main__":
    raise SystemExit(main())
