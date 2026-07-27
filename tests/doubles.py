"""Stand-ins for the two things the annotator talks to: Windows, and Tk.

Neither is available to a spec — one needs a desktop, the other a display — and
both are narrow enough to answer honestly in a dict. Everything the package
decides is decided above this line, so these doubles are the reason the whole
suite runs on a machine with no Tk, no display and no Windows.
"""

from __future__ import annotations

import threading
from collections.abc import Sequence

from tk_uia.annotate import PropId


class RecordingStore:
    """A store that keeps what was written to it, and can be asked to read back."""

    def __init__(self) -> None:
        self.writes: list[tuple[int, PropId, object]] = []
        self.cleared: list[int] = []
        self._properties: dict[int, dict[PropId, object]] = {}
        self._control_ids: dict[int, int] = {}

    def set_string(self, hwnd: int, prop: PropId, value: str) -> None:
        self._remember(hwnd, prop, value)

    def set_number(self, hwnd: int, prop: PropId, value: int) -> None:
        self._remember(hwnd, prop, value)

    def control_id(self, hwnd: int) -> int:
        return self._control_ids.get(hwnd, _NO_CONTROL_ID)

    def set_control_id(self, hwnd: int, control_id: int) -> None:
        self._control_ids[hwnd] = control_id

    def clear(self, hwnd: int) -> None:
        self.cleared.append(hwnd)
        self._properties.pop(hwnd, None)

    def properties(self, hwnd: int) -> dict[PropId, object]:
        return dict(self._properties.get(hwnd, {}))

    def _remember(self, hwnd: int, prop: PropId, value: object) -> None:
        self.writes.append((hwnd, prop, value))
        self._properties.setdefault(hwnd, {})[prop] = value


class FakeWidget:
    """A Tk widget as the annotator sees it, with no display behind it.

    `cget` refuses an option the real widget would not have, and `winfo_id`
    refuses once destroyed, because both are how Tk behaves and both are
    failures the annotator has to survive rather than propagate.

    Every method here goes through the Tcl interpreter in a real Tk, so every
    method here refuses a caller from another thread. That is *stricter* than Tk
    itself, deliberately: real Tk mostly answers, and corrupts the interpreter
    quietly instead — a failure a spec could never see. The rule under test is
    that the annotator turns a foreign caller away before touching Tk at all,
    and a double that answered would let a guard that fires afterwards pass.
    """

    def __init__(
        self,
        tk_class: str,
        hwnd: int,
        *,
        text: str | None = None,
        label: str | None = None,
        mapped: bool = True,
        children: Sequence[FakeWidget] = (),
    ) -> None:
        self._owning_thread = threading.get_ident()
        self._tk_class = tk_class
        self._hwnd = hwnd
        self._options: dict[str, str] = {}
        if text is not None:
            self._options["text"] = text
        # A classic `tk.Scale` has no `-text` at all; the words it shows sit in
        # `-label`, and it is the one widget in the toolkit built that way.
        if label is not None:
            self._options["label"] = label
        self._mapped = mapped
        self._children = list(children)
        self._path = f".!{tk_class.lower()}{hwnd}"
        self._destroyed = False

    def winfo_id(self) -> int:
        self._only_from_the_thread_that_owns_tk()
        if self._destroyed:
            raise FakeTclError(f'bad window path name "{self._path}"')
        return self._hwnd

    def winfo_class(self) -> str:
        self._only_from_the_thread_that_owns_tk()
        return self._tk_class

    def winfo_ismapped(self) -> bool:
        self._only_from_the_thread_that_owns_tk()
        return self._mapped

    def winfo_exists(self) -> bool:
        # Answers rather than raises, as Tcl's `winfo exists` does for a path it
        # no longer has — which is what makes it usable as a liveness check.
        self._only_from_the_thread_that_owns_tk()
        return not self._destroyed

    def winfo_children(self) -> Sequence[FakeWidget]:
        self._only_from_the_thread_that_owns_tk()
        return tuple(self._children)

    def keys(self) -> Sequence[str]:
        self._only_from_the_thread_that_owns_tk()
        return tuple(self._options)

    def cget(self, key: str) -> object:
        self._only_from_the_thread_that_owns_tk()
        if key not in self._options:
            raise FakeTclError(f'unknown option "-{key}"')
        return self._options[key]

    def _only_from_the_thread_that_owns_tk(self) -> None:
        if threading.get_ident() == self._owning_thread:
            return
        raise FakeTclError(
            f"thread {threading.get_ident()} reached into Tk, which belongs to "
            f"thread {self._owning_thread}"
        )

    def destroy(self) -> None:
        self._destroyed = True

    def is_taken_off_the_screen(self) -> None:
        """Stand in for Tk unmapping a widget that is still very much alive.

        An unselected notebook tab, a pane the geometry manager could not fit,
        a `pack_forget()`. The widget keeps its handle and everything written
        about it; UI Automation simply stops listing it.
        """
        self._mapped = False

    def take_a_new_handle(self, hwnd: int) -> None:
        """Stand in for Tk rebuilding a widget at the same path on a fresh HWND."""
        self._hwnd = hwnd

    def says_something_else(self, text: str) -> None:
        """Stand in for a plain `config(text=...)`, which never re-announces."""
        self._options["text"] = text

    def __str__(self) -> str:
        return self._path


class FakeTclError(Exception):
    """What Tcl raises back through tkinter, without importing tkinter to say so."""


class FakeVariable:
    """A `tkinter.Variable` as the binding sees it: a value and write traces.

    Traces are held under the name `trace_add` hands back, as Tcl's are, because
    a trace outlives the widget it was registered for and the name is the only
    thing that can take it off again.
    """

    def __init__(self, value: str) -> None:
        self._value = value
        self._traces: dict[str, object] = {}

    def get(self) -> str:
        return self._value

    def set(self, value: str) -> None:
        self._value = value
        for observer in list(self._traces.values()):
            observer(_A_TRACED_VARIABLE, _NO_INDEX, _A_WRITE)

    def trace_add(self, mode: str, callback: object) -> str:
        assert mode == "write", f"only writes need re-announcing, not {mode}"
        callback_name = f"{_HOW_TCL_NAMES_A_TRACE}{len(self._traces)}"
        self._traces[callback_name] = callback
        return callback_name

    def trace_remove(self, mode: str, callback_name: str) -> None:
        assert mode == "write", f"only writes need re-announcing, not {mode}"
        del self._traces[callback_name]

    def traces_left(self) -> int:
        """How many registrations are still on the variable, leak and all."""
        return len(self._traces)


class FakeInterpreter:
    """The Tcl interpreter, answering the handful of things the gate asks it.

    `catch`, `set` and `unset` behave as Tcl's do, because that is how the gate
    asks whether a subcommand exists without letting the refusal reach Python.
    The wording of the complaint is the wording Tk 8.6.15 actually produced.
    """

    def __init__(self, patchlevel: str, windowing_system: str, *, native: bool) -> None:
        self._answers = {
            ("info", "patchlevel"): patchlevel,
            ("tk", "windowingsystem"): windowing_system,
        }
        self._native = native
        self._variables: dict[str, str] = {}
        self.calls: list[tuple[object, ...]] = []

    def call(self, *args: object) -> object:
        self.calls.append(args)
        if args in self._answers:
            return self._answers[args]
        return self._run(args)

    def _run(self, args: tuple[object, ...]) -> object:
        command, rest = args[0], args[1:]
        if command == "catch":
            return self._catch(str(rest[0]), str(rest[1]))
        if command == "set":
            return self._variables[str(rest[0])]
        if command == "unset":
            del self._variables[str(rest[0])]
            return ""
        raise FakeTclError(f'invalid command name "{command}"')

    def _catch(self, script: str, complaint_goes_to: str) -> int:
        self._variables[complaint_goes_to] = self._how_tk_rejects(script)
        return _THE_SCRIPT_RAISED

    def _how_tk_rejects(self, script: str) -> str:
        offered = _TK_SUBCOMMANDS + (("accessible",) if self._native else ())
        asked_for = script.split()[-1]
        return (
            f'unknown or ambiguous subcommand "{asked_for}": '
            f"must be {', '.join(sorted(offered))}"
        )


class FakeRoot(FakeWidget):
    """A Tk root: a widget that also owns the interpreter and the class bindings."""

    def __init__(
        self,
        interpreter: FakeInterpreter,
        *,
        children: Sequence[FakeWidget] = (),
    ) -> None:
        super().__init__("Tk", _A_ROOT_HANDLE, children=children)
        self.tk = interpreter
        self.class_bindings: list[tuple[str, str]] = []
        self._handlers: dict[str, object] = {}

    def bind_all(self, sequence: str, func: object, add: str) -> None:
        self.class_bindings.append((sequence, add))
        self._handlers[sequence] = func

    def announce(self, sequence: str, widget: object) -> None:
        """Fire a bound event the way Tk would, once a widget maps or dies."""
        self._handlers[sequence](FakeEvent(widget))

    def __str__(self) -> str:
        return "."


class FakeEvent:
    """A `tkinter.Event`, of which only the widget it happened to matters here."""

    def __init__(self, widget: object) -> None:
        self.widget = widget


_NO_CONTROL_ID = 0
_A_ROOT_HANDLE = 1
_A_TRACED_VARIABLE = "PY_VAR0"
# What tkinter really calls the Tcl command it registers a trace under.
_HOW_TCL_NAMES_A_TRACE = "0x1a2b3c4d5e6f"
_NO_INDEX = ""
_A_WRITE = "write"
_THE_SCRIPT_RAISED = 1

# What `tk` really lists when it is handed a subcommand it does not have,
# transcribed from Tk 8.6.15 on this machine.
_TK_SUBCOMMANDS = (
    "appname",
    "busy",
    "caret",
    "fontchooser",
    "inactive",
    "scaling",
    "useinputmethods",
    "windowingsystem",
)
