"""Behavioral spec for what a provider slot writes into the out parameter UIA hands it.

Drives the COM slot bodies directly against real buffers, with no window and no
client, because a wrong store there answers `S_OK` and writes nothing a client
can read.
"""

from __future__ import annotations

import ctypes
import sys
from collections.abc import Iterator
from typing import Any

import pytest

from tk_uia._uiacore import (
    _BY_ADDRESS,
    _S_OK,
    _UIA_E_INVALIDOPERATION,
    _VT_BSTR,
    _VT_I4,
    _ComLayer,
    _Hosted,
    _Shell,
    _UIA_ControlTypePropertyId,
    _UIA_NamePropertyId,
    _UiaRect,
    _Variant,
)
from tk_uia.patterns import Pattern
from tk_uia.provide import Blueprint, RangeAnswers, ToggleAnswers

pytestmark = pytest.mark.skipif(
    sys.platform != "win32",
    reason="SysAllocString and the ctypes call machinery exist only on Windows",
)

_A_CHECK_BUTTON_CONTROL = 50002
_WHATEVER_WAS_IN_THE_BUFFER_BEFORE = 999


@pytest.fixture
def slots() -> Iterator[Any]:
    """The slot bodies, with no COM layer loaded: none of these touch the vtables."""
    standing = dict(_BY_ADDRESS)
    yield object.__new__(_ComLayer)
    _BY_ADDRESS.clear()
    _BY_ADDRESS.update(standing)


def _a_widget_answering_with(**patterns: object) -> int:
    """One hosted widget, and the `this` pointer UIA would call its slots with."""
    blueprint = Blueprint(
        control_type=lambda: _A_CHECK_BUTTON_CONTROL,
        name=lambda: "Bold",
        help_text=lambda: None,
        description=lambda: None,
        is_enabled=lambda: True,
        **patterns,
    )
    hosted = _Hosted(0xABC, blueprint)
    shell = _Shell(ctypes.c_void_p(0))
    hosted.shells["simple"] = shell
    this = ctypes.addressof(shell)
    _BY_ADDRESS[this] = hosted
    return this


def test_a_toggle_state_is_written_as_the_four_byte_truth_a_client_reads(
    slots: Any,
) -> None:
    # Given a checkbutton whose variable is on
    on = [True]
    this = _a_widget_answering_with(
        patterns={Pattern.TOGGLE: ToggleAnswers(flip=lambda: None, is_on=lambda: on[0])}
    )
    answered = ctypes.c_int(_WHATEVER_WAS_IN_THE_BUFFER_BEFORE)

    # When a client asks for the toggle state, and again after the variable flips
    first = slots._toggle_state(this, ctypes.addressof(answered))
    was_on = answered.value
    on[0] = False
    slots._toggle_state(this, ctypes.addressof(answered))

    # Then the buffer carries the state at the moment of each ask
    assert (first, was_on, answered.value) == (_S_OK, 1, 0), (
        f"answered {first:#x} then {was_on} and {answered.value}; a client reads "
        "this buffer and nothing else"
    )


def test_a_name_reaches_the_variant_as_a_bstr_and_a_control_type_as_a_number(
    slots: Any,
) -> None:
    # Given a widget with a name and a control type to answer
    this = _a_widget_answering_with(patterns={})
    named = _Variant()
    typed = _Variant()

    # When a client asks for each property
    slots._property_value(this, _UIA_NamePropertyId, ctypes.addressof(named))
    slots._property_value(this, _UIA_ControlTypePropertyId, ctypes.addressof(typed))

    # Then each landed in the caller's VARIANT, tagged the way COM requires
    assert named.vt == _VT_BSTR, f"a name tagged {named.vt} is not a string to COM"
    assert named.pointer, "the BSTR pointer is null, so the name marshalled nowhere"
    assert typed.vt == _VT_I4, f"a control type tagged {typed.vt} is not a number"
    assert typed.number == _A_CHECK_BUTTON_CONTROL, (
        f"a client reads control type {typed.number}"
    )


def test_a_range_value_is_written_as_the_double_the_pattern_promises(
    slots: Any,
) -> None:
    # Given a scale sitting at a fractional value
    this = _a_widget_answering_with(
        patterns={
            Pattern.RANGE_VALUE: RangeAnswers(
                write=None,
                now=lambda: 40.5,
                low=lambda: 0.0,
                high=lambda: 100.0,
                step=lambda: None,
                is_read_only=lambda: True,
            )
        }
    )
    answered = ctypes.c_double(-1.0)

    # When a client asks what it holds
    result = slots._range_value(this, ctypes.addressof(answered))

    # Then the full double is there, not a truncated or reinterpreted one
    assert (result, answered.value) == (_S_OK, 40.5), (
        f"answered {result:#x} and {answered.value}, so the double did not land"
    )


def test_a_pattern_the_widget_does_not_carry_is_refused_and_the_buffer_left_alone(
    slots: Any,
) -> None:
    # Given a widget with no RangeValue at all
    this = _a_widget_answering_with(patterns={})
    answered = ctypes.c_double(-1.0)

    # When a client asks for one anyway
    result = slots._range_value(this, ctypes.addressof(answered))

    # Then it is the documented refusal, and nothing was written over
    assert result == _UIA_E_INVALIDOPERATION, (
        f"answered {result:#x}; a pattern that is not there must refuse rather "
        "than write a confident zero"
    )
    assert answered.value == -1.0, "the buffer was written to despite the refusal"


def test_a_rectangle_nobody_can_measure_is_written_as_four_zeroes(slots: Any) -> None:
    # Given a widget whose bounds are its window's to answer
    this = _a_widget_answering_with(patterns={})
    answered = _UiaRect(9.0, 9.0, 9.0, 9.0)

    # When a client asks the fragment for its rectangle
    slots._bounding_rectangle(this, ctypes.addressof(answered))

    # Then every field is cleared, not just the first
    assert (
        answered.left,
        answered.top,
        answered.width,
        answered.height,
    ) == (0.0, 0.0, 0.0, 0.0), "a partly-written rectangle is a garbage rectangle"
