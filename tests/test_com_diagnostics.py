"""Behavioral spec for what an application is told when a COM call refuses."""

from __future__ import annotations

import sys

import pytest

from tk_uia._accprop import _GUID_FOR_PROP, _checked, _set_hwnd_prop_str
from tk_uia._uiacore import (
    _E_FAIL,
    _S_OK,
    _UIA_E_INVALIDOPERATION,
    _never_raising,
)
from tk_uia.annotate import PropId

# E_ACCESSDENIED: negative, which is the half that matters to ctypes.
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
    # Given the real prototype standing in for an `oleacc` that refuses the annotation
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

    # Then it is told which call failed. A `ctypes.HRESULT` prototype never gets here
    assert "SetHwndPropStr(NAME)" in str(failure.value), (
        f"the message names no call, so nothing says which annotation was "
        f"refused: {failure.value}"
    )
    assert "0x80070005" in str(failure.value), (
        f"the message drops the code oleacc answered with: {failure.value}"
    )


def test_a_provider_slot_that_raises_answers_e_fail() -> None:
    # Given a slot implementation that blows up the way a mid-teardown widget can
    def raises_the_way_a_widget_mid_teardown_does(_this: int) -> int:
        raise RuntimeError("the widget went while UIA was asking")

    # When UIA calls it through the guard every HRESULT slot is bound behind
    answered = _never_raising(raises_the_way_a_widget_mid_teardown_does)(0)

    # Then UIA is told the call failed, and nothing propagates into the message loop
    assert answered == _E_FAIL, (
        f"a raising slot answered {answered:#x} rather than E_FAIL, so the "
        f"exception crosses back into COM"
    )


def test_a_provider_slot_that_answers_is_left_to_answer() -> None:
    # Given a slot implementation that refuses in the documented way, without raising
    # When it is called through the same guard
    refused = _never_raising(lambda _this: _UIA_E_INVALIDOPERATION)(0)
    succeeded = _never_raising(lambda _this: _S_OK)(0)

    # Then the guard hands back what the slot said, unchanged
    assert (refused, succeeded) == (_UIA_E_INVALIDOPERATION, _S_OK), (
        "the guard rewrote an HRESULT the slot chose deliberately"
    )
