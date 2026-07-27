"""tk-uia: make Tkinter widgets visible to Windows accessibility clients.

Tk 8.6 gives every widget an empty accessible name and mostly the wrong control
type, so a screen reader announces nothing and UI Automation sees a window full
of anonymous panes. `enable(root)` annotates each widget through MSAA, which
Windows bridges to UI Automation, and the tree starts telling the truth.

The names re-exported here are the whole public surface, and they deliberately
mirror TIP 733 — Tk 9.1's own accessibility API — so that moving to it later is
close to a rename. `enable()` returns which of the three things it did, because
"annotated" and "the version gate mis-fired and this did nothing at all" are
otherwise the same silence.

Importing this module reaches for neither `tkinter` nor `ctypes.windll`: the
type names below are only needed by a type checker, and the platform is not
touched until `enable()` runs. That is what lets the whole spec suite run on a
machine with no Tk, no display and no Windows — which matters practically too,
since a Linux CPython is not guaranteed to carry `_tkinter` at all.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from tk_uia.annotate import (
    AnnotationRefused,
    Annotator,
    InertAnnotator,
    Installation,
)
from tk_uia.describe import Description, Gap, WidgetDescription
from tk_uia.describe import describe as _describe
from tk_uia.roles import ROLE_FOR_TK_CLASS, Role
from tk_uia.tkversion import Strategy

if TYPE_CHECKING:
    import tkinter

__version__ = "0.5.0"

__all__ = [
    "ROLE_FOR_TK_CLASS",
    "AnnotationRefused",
    "Description",
    "Gap",
    "Role",
    "Strategy",
    "WidgetDescription",
    "__version__",
    "add_acc_object",
    "bind_text_variable",
    "bind_value_variable",
    "check_screenreader",
    "describe",
    "enable",
    "forget",
    "set_acc_action",
    "set_acc_description",
    "set_acc_help",
    "set_acc_name",
    "set_acc_role",
    "set_acc_state",
    "set_acc_value",
    "set_automation_id",
]

_installed: Installation | None = None


def enable(root: tkinter.Misc, *, roles: Mapping[str, Role] | None = None) -> Strategy:
    """Annotate this application's widgets, and say which way it went.

    Idempotent: a second call reports what the first one did and installs
    nothing further. `bind_all` binds on the `all` bindtag, so one installation
    already covers every window the application will ever open — where a second
    would stack another pair of `<Map>`/`<Destroy>` bindings, leave a stale
    annotator auto-annotating widgets that `forget()` can no longer reach, and
    leak one more `IAccPropServices` that nothing releases.
    """
    global _installed
    if _installed is not None:
        return _installed.strategy
    from tk_uia._accprop import AccPropServicesStore
    from tk_uia._overlay import Win32Overlays
    from tk_uia._tkstrip import TkTabStrip, is_a_notebook
    from tk_uia.annotate import install
    from tk_uia.tabs import Notebooks, TabHandles

    store = AccPropServicesStore()
    notebooks = Notebooks(
        TabHandles(store, Win32Overlays()),
        lambda widget: TkTabStrip(widget) if is_a_notebook(widget) else None,
    )
    _installed = install(root, store, roles, notebooks)
    return _installed.strategy


def add_acc_object(widget: tkinter.Misc) -> None:
    """Annotate one widget now, re-reading its class, its `-text` and its tabs.

    `enable()` already does this for everything Tk maps. Call it by hand after
    changing a widget's `-text`, which otherwise leaves the accessible name
    saying whatever the widget said when it was first mapped.

    A notebook needs it after a tab is added, removed or renamed. Tk fires
    `<<NotebookTabChanged>>` when the *selection* moves and at no other time, so
    a tab added beside the open one, or a tab renamed in place, announces itself
    exactly as a `config(text=...)` does: not at all, until this is called.
    """
    _annotator().add(widget)
    _the_installation().tabs.refresh(widget)


def set_acc_role(widget: tkinter.Misc, role: Role) -> None:
    """Say what kind of control this is, overriding the inferred role.

    A role is not a label on an existing object: it decides which patterns the
    MSAA-to-UIA bridge offers for the widget at all.
    """
    _annotator().set_role(widget, role)


def set_acc_name(widget: tkinter.Misc, name: str) -> None:
    """Say what a screen reader should call this widget.

    Needed for anything with no `-text` to infer a name from. Raises
    `AnnotationRefused` for a toplevel, which is named by `wm title` instead.
    """
    _annotator().set_name(widget, name)


def set_acc_value(widget: tkinter.Misc, value: str) -> None:
    """Say what a client reads out of this widget, as an edit control's contents.

    Written once, where `bind_value_variable` keeps it true from then on.
    """
    _annotator().set_value(widget, value)


def set_acc_description(widget: tkinter.Misc, description: str) -> None:
    """Say more about this widget than its name has room for."""
    _annotator().set_description(widget, description)


def set_acc_action(widget: tkinter.Misc, action: str) -> None:
    """Say what activating this widget would do, as a verb ("Press").

    Advertising it does not make it activatable: `InvokePattern` on a Tk button
    returns cleanly and presses nothing. See the README's central caveat.
    """
    _annotator().set_action(widget, action)


def set_acc_help(widget: tkinter.Misc, help_text: str) -> None:
    """Say what a client should offer as this widget's help text."""
    _annotator().set_help(widget, help_text)


def set_acc_state(widget: tkinter.Misc, state: int) -> None:
    """Say what state this widget is in, as `oleacc.h`'s `STATE_SYSTEM_*` bits.

    Written once and never tracked: nothing here notices a widget being
    disabled or re-enabled, so an application that says this has to keep
    saying it.
    """
    _annotator().set_state(widget, state)


def bind_text_variable(widget: tkinter.Misc, variable: tkinter.Variable) -> None:
    """Keep a widget's accessible name in step with the variable it displays."""
    _annotator().bind_text_variable(widget, variable)


def bind_value_variable(widget: tkinter.Misc, variable: tkinter.Variable) -> None:
    """Keep a widget's accessible value in step with the variable it holds."""
    _annotator().bind_value_variable(widget, variable)


def set_automation_id(widget: tkinter.Misc, automation_id: int) -> None:
    """Give this widget a stable id for a test suite to pin a locator to.

    Explicit only, and never invented. Writes `GWLP_ID`, the control id Win32
    puts in `WM_COMMAND.wParam` and `WM_DRAWITEM.idCtl`; a non-zero existing id
    raises `AnnotationRefused` rather than being overwritten.
    """
    _annotator().set_automation_id(widget, automation_id)


def forget(widget: tkinter.Misc | str) -> None:
    """Take every annotation back off a widget, and stop following its variables.

    Takes the widget or its Tk path, since `<Destroy>` carries only the path
    once the widget object has gone.
    """
    _annotator().forget(widget)


def describe(root: tkinter.Misc) -> Description:
    """Say what this application has told Windows about the widgets under `root`.

    Reports what tk-uia believes it wrote, which is not evidence that a client
    can read it — see the caveat the report closes with. `print()` it for the
    report; read `.widgets` for the same thing as data.
    """
    return _describe(root, _the_installation())


def check_screenreader() -> bool:
    """Whether Windows believes something is reading the screen aloud."""
    from tk_uia._accprop import screen_reader_running

    return screen_reader_running()


def _annotator() -> Annotator | InertAnnotator:
    return _the_installation().annotator


def _the_installation() -> Installation:
    if _installed is None:
        raise AnnotationRefused(
            "tk_uia.enable(root) has not been called, so there is nothing to "
            "annotate through; call it once after building the window and "
            "before saying anything about the widgets in it"
        )
    return _installed
