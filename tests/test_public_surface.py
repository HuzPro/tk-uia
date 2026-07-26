"""Behavioral spec for the module an application actually imports.

The surface deliberately reads like TIP 733, Tk 9.1's own accessibility API, so
that moving to it later is close to a rename rather than a rewrite.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

import tk_uia
from tests.doubles import FakeInterpreter, FakeRoot, FakeWidget
from tk_uia import Strategy
from tk_uia.annotate import AnnotationRefused

_A_LABEL_HANDLE = 0x000407A5
_AN_ID_THE_APPLICATION_CHOSE = 4207


def test_switching_accessibility_on_where_there_is_none_says_so_and_stays_callable() -> (
    None
):
    # Given the same application, running somewhere MSAA does not exist
    root = FakeRoot(FakeInterpreter("8.6.15", "x11", native=False))
    label = FakeWidget("Label", _A_LABEL_HANDLE, text="ready")

    # When it switches accessibility on and then says everything it would say
    strategy = tk_uia.enable(root)
    tk_uia.add_acc_object(label)
    tk_uia.set_acc_name(label, "status")
    tk_uia.set_acc_value(label, "ready")
    tk_uia.set_automation_id(label, _AN_ID_THE_APPLICATION_CHOSE)
    tk_uia.forget(label)

    # Then it is told plainly that nothing was annotated, and not one of those
    # calls raised. The return value is the whole point: without it, "annotated"
    # and "the gate mis-fired and this did nothing" are the same silence.
    assert strategy is Strategy.UNSUPPORTED, (
        f"claimed {strategy} on a machine with no MSAA to annotate through"
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
