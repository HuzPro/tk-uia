"""Measures what `enable()` on its own leaves a client able to read, and what it does not.

    python probes/what_enable_alone_gives_you.py

The script behind the README's caveats, read back from a separate process.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

HEADLINE = "Task list"
NEW_TASK = "New Task"
SHOPPING = "buy milk"
TICKED = "Ticked"
UNTICKED = "Unticked"
DISABLED = "Disabled"
RESTYLED = "in progress"

RESTYLE_THE_LABEL = "restyle"
RE_ADD_THE_LABEL = "readd"
UNTICK_THE_CHECKBOX = "untick"
SAY_THE_BUTTON_IS_DISABLED = "disable"

_THE_TK_CONTAINER = "TkChild"

# The patterns that decide whether a client can read a widget's contents, act on
# it, or tell whether it is ticked.
_THE_PATTERNS_WORTH_ASKING_FOR = (
    "Value",
    "Invoke",
    "Toggle",
    "SelectionItem",
    "LegacyIAccessible",
)

_TOP_LEVEL_WINDOWS = 1
_READY_TIMEOUT_SECONDS = 20.0
_HOW_OFTEN_TO_LOOK_AGAIN_SECONDS = 0.2
_LONG_ENOUGH_FOR_THE_APP_TO_REACT_SECONDS = 1.0
_HOW_OFTEN_TO_CHECK_FOR_A_COMMAND_MS = 50
_SHUTDOWN_GRACE_SECONDS = 10.0


def an_application_that_only_calls_enable(title: str, commands: Path) -> None:
    """The window under measurement: `enable(root)`, and not one call more."""
    import tkinter as tk

    import tk_uia

    root = tk.Tk()
    root.title(title)
    root.geometry("420x300")

    headline = tk.Label(root, text=HEADLINE)
    headline.pack(pady=10)
    tk.Button(root, text=NEW_TASK).pack(pady=10)
    tk.Entry(root, width=30, textvariable=tk.StringVar(value=SHOPPING)).pack(pady=10)
    # Two checkbuttons differing only in whether they are ticked, and one widget
    # that is disabled. A client that cannot tell these apart is not being told
    # about state.
    ticked = tk.IntVar(value=1)
    tk.Checkbutton(root, text=TICKED, variable=ticked).pack()
    tk.Checkbutton(root, text=UNTICKED, variable=tk.IntVar(value=0)).pack()
    greyed = tk.Button(root, text=DISABLED, state=tk.DISABLED)
    greyed.pack(pady=10)
    root.update()

    strategy = tk_uia.enable(root)
    if strategy is not tk_uia.Strategy.ANNOTATED:
        raise SystemExit(f"enable() reported {strategy}: nothing here is annotated")

    handlers = {
        # The widget changes its words the ordinary way, saying nothing here.
        RESTYLE_THE_LABEL: lambda: headline.config(text=RESTYLED),
        # The documented workaround: the annotator re-reads `-text`.
        RE_ADD_THE_LABEL: lambda: tk_uia.add_acc_object(headline),
        # Does a checkbox's ToggleState follow the variable, or was it only ever
        # right the first time a client happened to ask?
        UNTICK_THE_CHECKBOX: lambda: ticked.set(0),
        # And is there a way to say "disabled" at all? STATE_SYSTEM_UNAVAILABLE.
        SAY_THE_BUTTON_IS_DISABLED: lambda: tk_uia.set_acc_state(greyed, 0x1),
    }

    def look() -> None:
        for name, act in handlers.items():
            request = commands / name
            if request.exists():
                request.unlink()
                act()
        root.after(_HOW_OFTEN_TO_CHECK_FOR_A_COMMAND_MS, look)

    root.after(_HOW_OFTEN_TO_CHECK_FOR_A_COMMAND_MS, look)
    root.mainloop()


def measure() -> None:
    import uiautomation as auto

    title = f"tk-uia probe {uuid.uuid4()}"
    with tempfile.TemporaryDirectory() as commands:
        app = subprocess.Popen(
            [sys.executable, __file__, title, commands], stderr=subprocess.PIPE
        )
        try:
            window = auto.WindowControl(searchDepth=_TOP_LEVEL_WINDOWS, Name=title)
            if not window.Exists(
                _READY_TIMEOUT_SECONDS, _HOW_OFTEN_TO_LOOK_AGAIN_SECONDS
            ):
                raise SystemExit("no window appeared")
            _report(window, Path(commands))
        finally:
            _killed_with_its_children(app)


def _report(window: Any, commands: Path) -> None:
    print("What a client reads after enable() and nothing else:\n")
    print(
        f"{'ControlType':<16} {'Name':<11} {'Value':<9} {'Toggle':<9} "
        f"{'Enabled':<8} Patterns"
    )
    print("-" * 92)
    for control in _the_widgets_the_application_shows(window):
        print(
            f"{control.ControlTypeName:<16} {control.Name!r:<11} "
            f"{_value_of(control)!r:<9} {_toggle_state_of(control):<9} "
            f"{control.IsEnabled!s:<8} {', '.join(_patterns_of(control)) or '-'}"
        )

    print("\nA name going stale, and the documented way back:\n")
    print(f"  at rest                     Name={_name_of_the_headline(window)!r}")
    _ask_for(commands, RESTYLE_THE_LABEL)
    print(f"  after config(text=...)      Name={_name_of_the_headline(window)!r}")
    _ask_for(commands, RE_ADD_THE_LABEL)
    print(f"  after add_acc_object(label) Name={_name_of_the_headline(window)!r}")

    print("\nWhether state follows the application:\n")
    print(f"  {TICKED} at rest             Toggle={_toggle_of(window, TICKED)}")
    _ask_for(commands, UNTICK_THE_CHECKBOX)
    print(f"  {TICKED} after variable=0    Toggle={_toggle_of(window, TICKED)}")
    print(f"  {DISABLED} at rest           Enabled={_enabled(window, DISABLED)}")
    _ask_for(commands, SAY_THE_BUTTON_IS_DISABLED)
    print(f"  {DISABLED} after set_acc_state Enabled={_enabled(window, DISABLED)}")


def _named(window: Any, name: str) -> Any:
    for control in _the_widgets_the_application_shows(window):
        if control.Name == name:
            return control
    raise SystemExit(f"no widget named {name!r}")


def _toggle_of(window: Any, name: str) -> str:
    return _toggle_state_of(_named(window, name))


def _enabled(window: Any, name: str) -> str:
    return str(_named(window, name).IsEnabled)


def _name_of_the_headline(window: Any) -> str:
    for control in _the_widgets_the_application_shows(window):
        if control.ControlTypeName == "TextControl":
            return str(control.Name)
    return "<no text control in the window>"


def _the_widgets_the_application_shows(window: Any) -> list[Any]:
    import uiautomation as auto

    container = auto.PaneControl(
        searchFromControl=window, searchDepth=1, ClassName=_THE_TK_CONTAINER
    )
    return [control for control, _ in auto.WalkControl(container)]


def _pattern(control: Any, pattern: str) -> Any:
    """Whatever the control offers under this pattern, or nothing.

    Two ways of answering "no", and both are the measurement: `uiautomation`
    defines no accessor on a control class the pattern cannot apply to, and
    answers `None` where it applies and the provider does not offer it.
    """
    ask = getattr(control, f"Get{pattern}Pattern", None)
    return None if ask is None else ask()


def _value_of(control: Any) -> str:
    reads_its_value = _pattern(control, "Value")
    return "" if reads_its_value is None else str(reads_its_value.Value)


def _toggle_state_of(control: Any) -> str:
    can_be_ticked = _pattern(control, "Toggle")
    return "-" if can_be_ticked is None else str(can_be_ticked.ToggleState)


def _patterns_of(control: Any) -> list[str]:
    return [
        pattern
        for pattern in _THE_PATTERNS_WORTH_ASKING_FOR
        if _pattern(control, pattern) is not None
    ]


def _ask_for(commands: Path, command: str) -> None:
    (commands / command).write_text("", encoding="utf-8")
    time.sleep(_LONG_ENOUGH_FOR_THE_APP_TO_REACT_SECONDS)


def _killed_with_its_children(app: subprocess.Popen[bytes]) -> None:
    subprocess.run(
        ["taskkill", "/T", "/F", "/PID", str(app.pid)], capture_output=True, check=False
    )
    app.wait(timeout=_SHUTDOWN_GRACE_SECONDS)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        an_application_that_only_calls_enable(sys.argv[1], Path(sys.argv[2]))
    else:
        measure()
