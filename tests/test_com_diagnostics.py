"""Behavioral spec for what an application is told when a COM call refuses.

`_accprop.py` holds one decision worth a unit test: when `oleacc` answers with a
failure, which of the eleven calls it was has to survive into the message. Every
one of them looks identical from the outside, and the symptom is a widget that
quietly never announced itself.

A stand-in built from the module's own prototype factory answers the way a
refusing COM method does, so the question is only whether the answer reaches
`_checked`. The prototypes need `ctypes.WINFUNCTYPE`, which does not exist off
Windows, so this file skips there rather than being collected away: the question
only has a meaning on Windows.
"""

from __future__ import annotations

import sys

import pytest

from tk_uia._accprop import _GUID_FOR_PROP, _checked, _set_hwnd_prop_str
from tk_uia.annotate import PropId

# E_ACCESSDENIED: a plausible refusal, and negative, which is the half that
# matters. ctypes treats a negative HRESULT as its own business.
_AN_ACCESS_DENIED = 0x80070005

_NO_INTERFACE = None
_NO_WINDOW = None
_OBJID_CLIENT = 0xFFFFFFFC
_CHILDID_SELF = 0

pytestmark = pytest.mark.skipif(
    sys.platform != "win32",
    reason="ctypes.WINFUNCTYPE and ctypes.HRESULT exist only on Windows",
)


def test_a_com_call_that_refuses_is_reported_with_the_name_of_the_call_that_refused() -> (
    None
):
    # Given the prototype `SetHwndPropStr` is really called through, standing in
    # for an `oleacc` that refuses the annotation
    an_oleacc_that_refuses = _set_hwnd_prop_str()(lambda *_: _AN_ACCESS_DENIED)

    # When the store makes that call and checks what came back, as it does
    with pytest.raises(OSError) as failure:
        _checked(
            an_oleacc_that_refuses(
                _NO_INTERFACE,
                _NO_WINDOW,
                _OBJID_CLIENT,
                _CHILDID_SELF,
                _GUID_FOR_PROP[PropId.NAME],
                "New Task",
            ),
            f"SetHwndPropStr({PropId.NAME.name})",
        )

    # Then the application is told which call failed and what it answered. A
    # prototype declaring `ctypes.HRESULT` never gets here: ctypes raises a bare
    # `[WinError -2147024891] Access is denied` of its own on any negative
    # HRESULT, before `_checked` runs, throwing away the one piece of
    # information that distinguishes eleven identical-looking calls.
    assert "SetHwndPropStr(NAME)" in str(failure.value), (
        f"the message names no call, so nothing says which annotation was "
        f"refused: {failure.value}"
    )
    assert "0x80070005" in str(failure.value), (
        f"the message drops the code oleacc answered with: {failure.value}"
    )
