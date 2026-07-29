"""tk-uia: make Tkinter widgets visible to Windows accessibility clients.

Tk 8.6 gives every widget an empty accessible name and mostly the wrong control
type. `enable(root)` annotates each widget through MSAA, which Windows bridges
to UI Automation. Importing this reaches for neither `tkinter` nor
`ctypes.windll`, so the platform is untouched until `enable()` runs.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, ClassVar

from tk_uia.annotate import (
    AnnotationRefused,
    Annotator,
    InertAnnotator,
    Installation,
)
from tk_uia.describe import Description, Gap, WidgetDescription
from tk_uia.describe import describe as _describe
from tk_uia.layout import NamedByTheLayout
from tk_uia.layout import infer_names_from_layout as _names_the_layout_implies
from tk_uia.provide import Pattern, ProviderRefused, Providers, Trouble
from tk_uia.roles import ROLE_FOR_TK_CLASS, Role
from tk_uia.tkversion import Strategy

if TYPE_CHECKING:
    import tkinter

__version__ = "0.8.0"

__all__ = [
    "ROLE_FOR_TK_CLASS",
    "AnnotationRefused",
    "Description",
    "Gap",
    "NamedByTheLayout",
    "Pattern",
    "ProviderRefused",
    "Role",
    "Strategy",
    "WidgetDescription",
    "__version__",
    "add_acc_object",
    "annotate_only",
    "bind_text_variable",
    "bind_value_variable",
    "check_screenreader",
    "describe",
    "enable",
    "forget",
    "infer_names_from_layout",
    "label_for",
    "leave_to_the_proxy",
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
_providers: Providers | None = None
_trouble = Trouble()


def __dir__() -> list[str]:
    # The public surface and nothing else: without this, completion offers the
    # typing imports and every submodule.
    return sorted(__all__)


def enable(root: tkinter.Misc, *, roles: Mapping[str, Role] | None = None) -> Strategy:
    """Annotate this application's widgets and make them answer UIA themselves.

    Idempotent: a second call reports what the first one did and installs
    nothing further. One installation covers every window the application opens.
    """
    global _installed
    if _installed is not None:
        return _installed.strategy
    from tk_uia.tkversion import tcl_can_marshal_across_threads

    if not tcl_can_marshal_across_threads(root.tk):
        # Providers answer on whatever thread a client calls from, which an
        # unthreaded Tcl cannot hear from safely. Honest downgrade, with the
        # reason carried into the report.
        return _annotate_only(
            root,
            roles,
            providers_stood_down_because=(
                "this Tcl was built without thread support, so a widget could "
                "not answer a client safely; annotation alone was installed"
            ),
        )
    from tk_uia._subclass import WindowSubclasses
    from tk_uia._tkwiring import wiring_for
    from tk_uia._uiacore import ComProviderPlatform
    from tk_uia.provide import Providers

    global _providers
    from tk_uia.provide import ProvidedTabs

    platform = ComProviderPlatform(WindowSubclasses(_trouble.note), _trouble.note)
    providers = Providers(
        platform, wiring_for, roles, said=_WhateverTheInstallationChose()
    )
    _installed = _install_with(
        root,
        roles,
        providers=providers,
        notifier=_AnnouncesThroughTheProvider(root, platform),
        tab_activation=ProvidedTabs(platform),
    )
    _providers = providers
    return _installed.strategy


def annotate_only(
    root: tkinter.Misc, *, roles: Mapping[str, Role] | None = None
) -> Strategy:
    """Annotate without installing native providers, which is everything 0.6 did.

    The escape hatch: one line here returns an application to the proxy-only
    behaviour while keeping every annotation and every binding.
    """
    if _installed is not None:
        return _installed.strategy
    return _annotate_only(root, roles, providers_stood_down_because=None)


def _annotate_only(
    root: tkinter.Misc,
    roles: Mapping[str, Role] | None,
    providers_stood_down_because: str | None,
) -> Strategy:
    global _installed
    _installed = _install_with(
        root,
        roles,
        providers=None,
        providers_stood_down_because=providers_stood_down_because,
    )
    return _installed.strategy


def _install_with(
    root: tkinter.Misc,
    roles: Mapping[str, Role] | None,
    providers: object | None,
    notifier: object | None = None,
    tab_activation: object | None = None,
    providers_stood_down_because: str | None = None,
) -> Installation:
    from tk_uia._accprop import AccPropServicesStore
    from tk_uia._overlay import Win32Overlays
    from tk_uia._tkstrip import TkTabStrip, is_a_notebook
    from tk_uia._tkvars import a_variable_the_application_owns
    from tk_uia.annotate import install
    from tk_uia.tabs import Notebooks, TabHandles

    store = AccPropServicesStore()
    notebooks = Notebooks(
        TabHandles(store, Win32Overlays(), tab_activation),
        lambda widget: TkTabStrip(widget) if is_a_notebook(widget) else None,
    )
    return install(
        root,
        store,
        roles,
        notebooks,
        a_variable_the_application_owns,
        providers=providers,
        notifier=notifier,
        providers_stood_down_because=providers_stood_down_because,
        trouble=_trouble,
    )


class _WhateverTheInstallationChose:
    """The application's chosen properties, read from wherever they end up."""

    def chosen(self, hwnd: int, prop: object) -> str | int | None:
        if _installed is None:
            return None
        return _installed.annotator.ledger.chosen(hwnd, prop)


class _AnnouncesThroughTheProvider:
    """Carries a changed property to UIA clients, off the write that changed it.

    The raise itself is posted: raising from inside a trace that a client's
    own synchronous call fired is a deadlock window.
    """

    _THE_UIA_PROPERTY_FOR: ClassVar[Mapping[str, int]] = {
        "NAME": 30005,
        "VALUE": 30045,
    }

    def __init__(self, root: tkinter.Misc, platform: object) -> None:
        self._root = root
        self._platform = platform

    def changed(self, hwnd: int, prop: object, now: str | int) -> None:
        uia_property = self._THE_UIA_PROPERTY_FOR.get(getattr(prop, "name", ""))
        if uia_property is None:
            return
        from tkinter import TclError

        try:
            self._root.after_idle(
                lambda: self._platform.announce_change(hwnd, uia_property, now)
            )
        except TclError:
            # The application is tearing down; there is nobody left to tell.
            return


def add_acc_object(widget: tkinter.Misc) -> None:
    """Annotate one widget now, re-reading its class, its `-text` and its tabs.

    Needed after `config(text=...)`, and after a tab is added, removed or
    renamed: Tk announces neither, so nothing re-annotates without this call.
    """
    _annotator().add(widget)
    _the_installation().tabs.refresh(widget)


def set_acc_role(widget: tkinter.Misc, role: Role) -> None:
    """Say what kind of control this is, overriding the inferred role."""
    _annotator().set_role(widget, role)


def set_acc_name(widget: tkinter.Misc, name: str) -> None:
    """Say what a screen reader should call this widget.

    Raises `AnnotationRefused` for a toplevel, which `wm title` names instead.
    """
    _annotator().set_name(widget, name)


def label_for(label: tkinter.Misc, widget: tkinter.Misc) -> None:
    """Say that this label is the caption for that widget, and name it accordingly.

    `label_for(tk.Label(text="Host:"), entry)` names the entry `'Host'`, and
    follows the label's `-textvariable` where it declares one. A label showing
    nothing at all raises `AnnotationRefused`.
    """
    _annotator().label_for(label, widget)


def infer_names_from_layout(root: tkinter.Misc) -> tuple[NamedByTheLayout, ...]:
    """Name what the layout of this window says its controls are, and report what it did.

    A guess read off the widgets *around* each control, which is why `enable()`
    does not do it. Nothing an application named itself is touched.
    """
    return _names_the_layout_implies(root, _the_installation())


def set_acc_value(widget: tkinter.Misc, value: str) -> None:
    """Say what a client reads out of this widget, as an edit control's contents."""
    _annotator().set_value(widget, value)


def set_acc_description(widget: tkinter.Misc, description: str) -> None:
    """Say more about this widget than its name has room for."""
    _annotator().set_description(widget, description)


def set_acc_action(widget: tkinter.Misc, action: str) -> None:
    """Say what activating this widget would do, as a verb ("Press").

    This reaches the MSAA view only, and it is an announcement, not a wiring:
    on a widget whose class carries no working pattern (a role assigned by
    hand included), the advertised action does nothing when a client calls it.
    """
    _annotator().set_action(widget, action)


def set_acc_help(widget: tkinter.Misc, help_text: str) -> None:
    """Say what a client should offer as this widget's help text."""
    _annotator().set_help(widget, help_text)


def set_acc_state(widget: tkinter.Misc, state: int) -> None:
    """Say what state this widget is in, as `oleacc.h`'s `STATE_SYSTEM_*` bits.

    Written once and never tracked: nothing here notices a widget being
    disabled or re-enabled.
    """
    _annotator().set_state(widget, state)


def bind_text_variable(widget: tkinter.Misc, variable: tkinter.Variable) -> None:
    """Keep a widget's accessible name in step with a variable of your choosing.

    Replaces the binding `enable()` made from the widget's own `-textvariable`
    rather than joining it.
    """
    _annotator().bind_text_variable(widget, variable)


def bind_value_variable(widget: tkinter.Misc, variable: tkinter.Variable) -> None:
    """Keep a widget's accessible value in step with a variable of your choosing."""
    _annotator().bind_value_variable(widget, variable)


def set_automation_id(widget: tkinter.Misc, automation_id: int) -> None:
    """Give this widget a stable id for a test suite to pin a locator to.

    Writes `GWLP_ID`, the control id Win32 puts in `WM_COMMAND.wParam`; a
    non-zero existing id raises `AnnotationRefused` rather than being overwritten.
    """
    _annotator().set_automation_id(widget, automation_id)


def leave_to_the_proxy(widget: tkinter.Misc) -> None:
    """Take this widget's native provider back off, leaving the MSAA proxy and its annotations.

    Under NATIVE and UNSUPPORTED nothing was provided; the choice is recorded
    and nothing else happens.
    """
    _the_installation()
    if _providers is not None:
        _providers.leave_to_the_proxy(widget)


def forget(widget: tkinter.Misc | str) -> None:
    """Take every annotation back off a widget, and stop following its variables.

    Takes the widget or its Tk path, since `<Destroy>` carries only the path
    once the widget object has gone.
    """
    _annotator().forget(widget)
    if _providers is not None:
        _providers.detach(str(widget))


def describe(root: tkinter.Misc) -> Description:
    """Say what this application has told Windows about the widgets under `root`.

    Reports what tk-uia believes it wrote, which is not evidence that a client
    can read it. `print()` it for the report, or read `.widgets` for the same
    thing as data. Raises `AnnotationRefused` where `enable()` has never run.
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
