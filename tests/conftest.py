"""Keeps the specs independent of each other, and launches the one real window."""

from __future__ import annotations

import subprocess
import sys
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

import tk_uia

FIXTURE_APPS = Path(__file__).parent / "fixture_apps"

# Not `skipif`: the gui modules import Windows-only packages at module scope,
# so off Windows they must not be collected at all.
collect_ignore_glob = [] if sys.platform == "win32" else ["test_gui_*.py"]

# Tk paints in well under a second here; the rest is the interpreter starting.
_READY_TIMEOUT_SECONDS = 20.0
_HOW_OFTEN_TO_LOOK_FOR_THE_WINDOW = 0.2

_TOP_LEVEL_WINDOWS = 1

_SHUTDOWN_GRACE_SECONDS = 10.0

# Tk gives its toplevel one container child, under which every widget lives.
# Everything else directly under the window is chrome Windows drew.
_THE_TK_CONTAINER = "TkChild"

# In a venv this is a launcher whose pid owns no window: hence the tree kill
# at teardown, and windows found by unique title rather than by pid.
_INTERPRETER = sys.executable


@dataclass(frozen=True)
class RunningApp:
    """The fixture application on screen, as a spec talks to it."""

    # `uiautomation.WindowControl`, untyped here because this module is imported
    # on platforms where there is no `uiautomation` to name.
    window: Any
    commands: Path

    def ask_for(self, command: str) -> None:
        """Have the application do something to itself, and say when it did.

        A dropped file rather than a click, because a click is the one thing a
        UI Automation client cannot make a Tk button feel.
        """
        (self.commands / command).write_text("", encoding="utf-8")


def the_widgets_the_application_shows(window: Any) -> list[Any]:
    """Every control under Tk's own container, and none of Windows' chrome."""
    # Imported inside the function: this module is imported on platforms with no
    # `uiautomation`.
    import uiautomation as auto

    container = auto.PaneControl(
        searchFromControl=window, searchDepth=1, ClassName=_THE_TK_CONTAINER
    )
    return [control for control, _ in auto.WalkControl(container)]


@pytest.fixture(autouse=True)
def a_package_that_has_not_been_enabled_yet() -> Iterator[None]:
    yield
    tk_uia._installed = None


@pytest.fixture
def annotated_app(tmp_path: Path) -> Iterator[RunningApp]:
    """The self-annotating Tk app, up and painted, in a process of its own."""
    yield from _the_app_in("annotated_app.py", tmp_path)


@pytest.fixture
def newly_roled_app(tmp_path: Path) -> Iterator[RunningApp]:
    """One of every widget class whose role was chosen by measurement."""
    yield from _the_app_in("newly_roled_app.py", tmp_path)


@pytest.fixture
def reimported_ttk_app(tmp_path: Path) -> Iterator[RunningApp]:
    """A notebook built from a re-imported tkinter.ttk, the way IDLE ends up with one."""
    yield from _the_app_in("reimported_ttk_app.py", tmp_path)


@pytest.fixture
def notebook_app(tmp_path: Path) -> Iterator[RunningApp]:
    """The app whose window is a notebook, for the specs about its tabs."""
    yield from _the_app_in("notebook_app.py", tmp_path)


def _the_app_in(fixture_app: str, commands: Path) -> Iterator[RunningApp]:
    import uiautomation as auto

    title = f"tk-uia fixture {uuid.uuid4()}"
    app = subprocess.Popen(
        [_INTERPRETER, str(FIXTURE_APPS / fixture_app), title, str(commands)],
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        window = auto.WindowControl(searchDepth=_TOP_LEVEL_WINDOWS, Name=title)
        if not window.Exists(_READY_TIMEOUT_SECONDS, _HOW_OFTEN_TO_LOOK_FOR_THE_WINDOW):
            pytest.fail(_why_no_window_appeared(app, title))
        yield RunningApp(window, commands)
    finally:
        _killed_with_its_children(app)


def _why_no_window_appeared(app: subprocess.Popen[str], title: str) -> str:
    if app.poll() is None:
        return (
            f"no window titled {title!r} appeared within "
            f"{_READY_TIMEOUT_SECONDS:.0f}s, and the fixture app is still running"
        )
    # It refused to start, and the reason it printed is the only useful thing
    # left. Most likely `enable()` reported a strategy other than ANNOTATED.
    return (
        f"the fixture app exited {app.returncode} before painting:\n{app.stderr.read()}"
    )


def _killed_with_its_children(app: subprocess.Popen[str]) -> None:
    subprocess.run(
        ["taskkill", "/T", "/F", "/PID", str(app.pid)],
        capture_output=True,
        check=False,
    )
    app.wait(timeout=_SHUTDOWN_GRACE_SECONDS)
