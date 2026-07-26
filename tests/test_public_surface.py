"""Behavioral spec for the module an application actually imports.

The surface deliberately reads like TIP 733, Tk 9.1's own accessibility API, so
that moving to it later is close to a rename rather than a rewrite.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

import tk_uia
from tests.doubles import FakeInterpreter, FakeRoot, FakeVariable, FakeWidget
from tk_uia import Strategy
from tk_uia.annotate import AnnotationRefused

_A_LABEL_HANDLE = 0x000407A5
_AN_ID_THE_APPLICATION_CHOSE = 4207

_A_WIDGET_APPEARED = "<Map>"
_A_WIDGET_DIED = "<Destroy>"
_ALONGSIDE = "+"


def test_switching_accessibility_on_where_there_is_none_says_so_and_stays_callable() -> (
    None
):
    # Given the same application, running somewhere MSAA does not exist
    root = FakeRoot(FakeInterpreter("8.6.15", "x11", native=False))
    label = FakeWidget("Label", _A_LABEL_HANDLE, text="ready")
    status = FakeVariable("ready")

    # When it switches accessibility on and then says everything it would say
    strategy = tk_uia.enable(root)
    tk_uia.add_acc_object(label)
    tk_uia.set_acc_name(label, "status")
    tk_uia.set_acc_value(label, "ready")
    tk_uia.bind_text_variable(label, status)
    tk_uia.bind_value_variable(label, status)
    tk_uia.set_automation_id(label, _AN_ID_THE_APPLICATION_CHOSE)
    tk_uia.forget(label)

    # Then it is told plainly that nothing was annotated, and not one of those
    # calls raised. The return value is the whole point: without it, "annotated"
    # and "the gate mis-fired and this did nothing" are the same silence.
    assert strategy is Strategy.UNSUPPORTED, (
        f"claimed {strategy} on a machine with no MSAA to annotate through"
    )


def test_switching_accessibility_on_a_second_time_hands_back_the_installation_already_there() -> (
    None
):
    # Given an application that has already switched accessibility on
    root = FakeRoot(FakeInterpreter("8.6.15", "win32", native=False))
    the_first_time = tk_uia.enable(root)

    # When something switches it on again — a library being defensive, a dialog
    # module enabling for its own window, a restarted startup path
    the_second_time = tk_uia.enable(root)

    # Then Tk was told once. A second pair of bindings leaves a stale annotator
    # auto-annotating widgets that `forget()` — which reaches only the newest —
    # can no longer take back, and every call leaks an `IAccPropServices` that
    # nothing ever releases. `bind_all` binds on the `all` bindtag, so the first
    # installation already covers every window this application will open.
    assert root.class_bindings == [
        (_A_WIDGET_APPEARED, _ALONGSIDE),
        (_A_WIDGET_DIED, _ALONGSIDE),
    ], (
        f"bound {root.class_bindings}; a repeat enable() stacked a second pair "
        "of bindings over the first"
    )
    assert the_second_time is the_first_time, (
        f"the second call reported {the_second_time}, the first {the_first_time}"
    )


def test_saying_something_before_accessibility_is_switched_on_is_refused() -> None:
    # Given an application that has not called `enable()` yet
    label = FakeWidget("Label", _A_LABEL_HANDLE, text="ready")

    # When it tries to name a widget anyway
    with pytest.raises(AnnotationRefused) as refusal:
        tk_uia.set_acc_name(label, "status")

    # Then it is told. Doing nothing quietly is the failure mode this whole
    # package exists to refuse, and it would be indistinguishable from a Tk that
    # is simply not annotatable.
    assert "enable" in str(refusal.value), (
        f"the refusal has to say what was skipped: {refusal.value}"
    )


def test_every_call_an_application_makes_says_what_it_does_when_asked() -> None:
    # Given the names the package publishes as its whole public surface
    published = [getattr(tk_uia, name) for name in tk_uia.__all__]

    # When an editor's hover, or `help()`, asks each callable what it is for
    silent = [
        call.__name__ for call in published if callable(call) and not call.__doc__
    ]

    # Then every one of them answers. This surface is the only documentation
    # most callers will ever see — a library about making things announce
    # themselves cannot have a public API that says nothing about itself.
    assert silent == [], f"no docstring on {silent}, so hover and help() show nothing"


def test_importing_the_package_reaches_for_neither_tkinter_nor_windows() -> None:
    # Given a Python with every Tk and every Windows-only name taken away
    # When the package, and the module that talks to COM, are imported anyway
    attempt = subprocess.run(
        [sys.executable, "-c", _A_PYTHON_WITH_NEITHER_TK_NOR_WINDOWS],
        capture_output=True,
        text=True,
        check=False,
    )

    # Then both import, and a store can be built without reaching for any of it.
    # This is not housekeeping: it is what lets every spec above run on Linux,
    # where the CPython that CI installs is not guaranteed to carry `_tkinter`
    # at all, and it is why an application can call `enable()` unconditionally.
    assert attempt.returncode == 0, (
        f"the package cannot be imported without Tk or Windows:\n{attempt.stderr}"
    )


_A_PYTHON_WITH_NEITHER_TK_NOR_WINDOWS = """
import ctypes
import sys

sys.modules["tkinter"] = None
sys.modules["_tkinter"] = None
for windows_only in ("windll", "oledll", "WinDLL", "OleDLL", "WINFUNCTYPE", "HRESULT"):
    if hasattr(ctypes, windows_only):
        delattr(ctypes, windows_only)

try:
    import tkinter
except ImportError:
    pass
else:
    raise SystemExit("tkinter still imported, so this proves nothing")

import tk_uia
import tk_uia._accprop

tk_uia._accprop.AccPropServicesStore()
"""
