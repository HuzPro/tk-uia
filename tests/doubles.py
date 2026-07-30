"""Stand-ins for the two things the annotator talks to: Windows, and Tk."""

from __future__ import annotations

import threading
from collections.abc import Mapping, Sequence

from tk_uia.annotate import Ledger, PropId
from tk_uia.provide import Providers, WidgetWiring


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

    Deliberately stricter than Tk on foreign threads: real Tk answers and
    corrupts quietly, which is a failure a spec could never see.
    """

    def __init__(
        self,
        tk_class: str,
        hwnd: int,
        *,
        text: str | None = None,
        label: str | None = None,
        textvariable: str | None = None,
        mapped: bool = True,
        window: bool | None = None,
        children: Sequence[FakeWidget] = (),
        path: str | None = None,
        managed_by: str = "pack",
        grid_row: int | None = None,
        grid_column: int | None = None,
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
        # The Tcl *name* of a variable, which is all a widget carries. Only the
        # classes that really have the option get it: an entry does, a `tk.Text`
        # does not.
        if textvariable is not None:
            self._options["textvariable"] = textvariable
        self._mapped = mapped
        self._managed_by = managed_by
        self._grid_row = grid_row
        self._grid_column = grid_column
        self._children = list(children)
        # A real Tk path encodes ancestry: a dialog is `.!toplevel` and the
        # button in it is `.!toplevel.!button`. The default built here says
        # nothing about who holds it, so a spec that turns on that passes `path=`.
        self._path = path if path is not None else f".!{tk_class.lower()}{hwnd}"
        self._destroyed = False
        self._window = window if window is not None else tk_class in ("Tk", "Toplevel")
        self._parent: FakeWidget | None = None
        for child in self._children:
            child._parent = self

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
        # Answers rather than raises, as Tcl's `winfo exists` does.
        self._only_from_the_thread_that_owns_tk()
        return not self._destroyed

    def winfo_toplevel(self) -> object:
        self._only_from_the_thread_that_owns_tk()
        if self._window:
            return self
        holder = self._parent
        while holder is not None and not holder._window:
            holder = holder._parent
        # Real Tk always has a containing toplevel, so a parentless fake answers
        # with a stand-in rather than with itself.
        return holder if holder is not None else _A_WINDOW_SOMEWHERE_ABOVE

    def winfo_children(self) -> Sequence[FakeWidget]:
        self._only_from_the_thread_that_owns_tk()
        return tuple(self._children)

    def winfo_manager(self) -> str:
        self._only_from_the_thread_that_owns_tk()
        return self._managed_by

    def grid_info(self) -> Mapping[str, object]:
        self._only_from_the_thread_that_owns_tk()
        # Real Tk answers an empty mapping for a widget grid never managed.
        if self._managed_by != "grid":
            return {}
        return {"row": self._grid_row or 0, "column": self._grid_column or 0}

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
        """Stand in for Tk unmapping a widget that is still very much alive."""
        self._mapped = False

    def take_a_new_handle(self, hwnd: int) -> None:
        """Stand in for Tk rebuilding a widget at the same path on a fresh HWND."""
        self._hwnd = hwnd

    def says_something_else(self, text: str) -> None:
        """Stand in for a plain `config(text=...)`, which never re-announces."""
        self._options["text"] = text

    def declares_a_different_variable(self, name: str) -> None:
        """Stand in for `config(textvariable=...)` pointing the widget elsewhere."""
        self._options["textvariable"] = name

    def __str__(self) -> str:
        return self._path


_A_WINDOW_SOMEWHERE_ABOVE = object()


class FakeTclError(Exception):
    """What Tcl raises back through tkinter, without importing tkinter to say so."""


class FakeVariable:
    """A `tkinter.Variable` as the binding sees it: a value and write traces.

    Traces are held under the name `trace_add` hands back, as Tcl's are.
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


class VariablesByName:
    """The variables an application owns, reached the way a widget names them.

    A name nobody owns answers `None`, as a Tk with no such variable does.
    """

    def __init__(self, variables: Mapping[str, FakeVariable]) -> None:
        self._variables = dict(variables)

    def __call__(self, widget: object, name: str) -> FakeVariable | None:
        return self._variables.get(name)


class FakeInterpreter:
    """The Tcl interpreter, answering the handful of things the gate asks it.

    The wording of the complaint is the wording Tk 8.6.15 actually produced.
    """

    def __init__(
        self,
        patchlevel: str,
        windowing_system: str,
        *,
        native: bool,
        threaded: bool = True,
    ) -> None:
        self._answers = {
            ("info", "patchlevel"): patchlevel,
            ("tk", "windowingsystem"): windowing_system,
            ("set", "tcl_platform(threaded)"): "1" if threaded else "0",
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
        tk_class: str = "Tk",
    ) -> None:
        super().__init__(tk_class, _A_ROOT_HANDLE, window=True, children=children)
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


class RecordingPlatform:
    """A provider platform that keeps every blueprint it was handed."""

    def __init__(self) -> None:
        self.hosted: dict[int, object] = {}
        self.unhosted: list[int] = []
        self.announced: list[tuple[int, object, object]] = []
        self.selection_heard: list[tuple[int, tuple[str, ...]]] = []

    def host(self, hwnd: int, blueprint: object) -> None:
        self.hosted[hwnd] = blueprint

    def unhost(self, hwnd: int) -> None:
        self.unhosted.append(hwnd)
        self.hosted.pop(hwnd, None)

    def announces(self, prop: object) -> bool:
        return True

    def announce_change(self, hwnd: int, prop: object, now: object) -> None:
        self.announced.append((hwnd, prop, now))

    def announce_selection(self, hwnd: int, now: tuple[str, ...]) -> None:
        self.selection_heard.append((hwnd, now))


class HeldPoster:
    """A poster that holds what was posted, so a spec can run it later."""

    def __init__(self) -> None:
        self.held: list = []

    def __call__(self, action) -> None:
        self.held.append(action)

    def run_everything_posted(self) -> None:
        while self.held:
            self.held.pop(0)()


class RecordingNotifier:
    """A notifier that keeps every change it was told about."""

    def __init__(self) -> None:
        self.heard: list[tuple[int, object, object]] = []

    def changed(self, hwnd: int, prop: object, now: object) -> None:
        self.heard.append((hwnd, prop, now))


class RecordingProvidedWidgets:
    """A provider layer that keeps what install() handed it."""

    def __init__(self) -> None:
        self.attached: list[object] = []
        self.forgotten: list[str] = []

    def attach(self, widget: object) -> None:
        self.attached.append(widget)

    def forget(self, path: str) -> None:
        self.forgotten.append(path)


class AnInvoke:
    """An invoke wiring, counting presses and answering for the command it has now."""

    def __init__(self, command: str = "the command the application wired") -> None:
        self.command = command
        self.pressed = 0

    def press(self) -> None:
        self.pressed += 1

    def offered(self) -> bool:
        return bool(self.command)


class AToggle:
    def __init__(self) -> None:
        self.on = False

    def flip(self) -> None:
        self.on = not self.on

    def is_on(self) -> bool:
        return self.on


class AValue:
    def __init__(self, text: str = "") -> None:
        self.text = text

    def read(self) -> str:
        return self.text

    def write(self, text: str) -> None:
        self.text = text

    def is_read_only(self) -> bool:
        return False


class ASelection:
    def __init__(self) -> None:
        self.selected = False

    def select(self) -> None:
        self.selected = True

    def is_selected(self) -> bool:
        return self.selected


def a_wiring_with(
    widget, *, words=None, is_enabled=None, post=None, **patterns
) -> WidgetWiring:
    """One widget's wiring: the four every class carries, plus the patterns named."""
    return WidgetWiring(
        words=words if words is not None else lambda: None,
        is_enabled=is_enabled if is_enabled is not None else lambda: True,
        post=post if post is not None else HeldPoster(),
        still_there=widget.winfo_exists,
        **patterns,
    )


def attached(widget, platform=None, said=None, **wiring):
    """Attach one widget through a Providers, and hand back the blueprint hosted for it."""
    platform = platform if platform is not None else RecordingPlatform()
    providers = Providers(
        platform,
        lambda _each: a_wiring_with(widget, **wiring),
        said=said if said is not None else Ledger(),
    )
    providers.attach(widget)
    return platform.hosted[widget.winfo_id()]
