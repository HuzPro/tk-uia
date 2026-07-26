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

from tk_uia.annotate import AnnotationRefused, Annotator, InertAnnotator
from tk_uia.roles import ROLE_FOR_TK_CLASS, Role
from tk_uia.tkversion import Strategy

if TYPE_CHECKING:
    import tkinter

__version__ = "0.2.0"

__all__ = [
    "ROLE_FOR_TK_CLASS",
    "AnnotationRefused",
    "Role",
    "Strategy",
    "__version__",
    "add_acc_object",
    "bind_text_variable",
    "bind_value_variable",
    "check_screenreader",
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

_installed: Annotator | InertAnnotator | None = None


def enable(root: tkinter.Misc, *, roles: Mapping[str, Role] | None = None) -> Strategy:
    """Annotate this application's widgets, and say which way it went."""
    global _installed
    from tk_uia._accprop import AccPropServicesStore
    from tk_uia.annotate import install

    installation = install(root, AccPropServicesStore(), roles)
    _installed = installation.annotator
    return installation.strategy


def add_acc_object(widget: tkinter.Misc) -> None:
    _annotator().add(widget)


def set_acc_role(widget: tkinter.Misc, role: Role) -> None:
    _annotator().set_role(widget, role)


def set_acc_name(widget: tkinter.Misc, name: str) -> None:
    _annotator().set_name(widget, name)


def set_acc_value(widget: tkinter.Misc, value: str) -> None:
    _annotator().set_value(widget, value)


def set_acc_description(widget: tkinter.Misc, description: str) -> None:
    _annotator().set_description(widget, description)


def set_acc_action(widget: tkinter.Misc, action: str) -> None:
    _annotator().set_action(widget, action)


def set_acc_help(widget: tkinter.Misc, help_text: str) -> None:
    _annotator().set_help(widget, help_text)


def set_acc_state(widget: tkinter.Misc, state: int) -> None:
    _annotator().set_state(widget, state)


def bind_text_variable(widget: tkinter.Misc, variable: tkinter.Variable) -> None:
    """Keep a widget's accessible name in step with the variable it displays."""
    _annotator().bind_text_variable(widget, variable)


def bind_value_variable(widget: tkinter.Misc, variable: tkinter.Variable) -> None:
    """Keep a widget's accessible value in step with the variable it holds."""
    _annotator().bind_value_variable(widget, variable)


def set_automation_id(widget: tkinter.Misc, automation_id: int) -> None:
    _annotator().set_automation_id(widget, automation_id)


def forget(widget: tkinter.Misc | str) -> None:
    _annotator().forget(widget)


def check_screenreader() -> bool:
    """Whether Windows believes something is reading the screen aloud."""
    from tk_uia._accprop import screen_reader_running

    return screen_reader_running()


def _annotator() -> Annotator | InertAnnotator:
    if _installed is None:
        raise AnnotationRefused(
            "tk_uia.enable(root) has not been called, so there is nothing to "
            "annotate through; call it once after building the window and "
            "before saying anything about the widgets in it"
        )
    return _installed
