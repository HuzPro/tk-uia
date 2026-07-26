"""Behavioral spec for deciding whether this package should do anything at all.

Tk 9.1 answers `WM_GETOBJECT` itself (TIP 733), and once it does, the oleacc
proxy this package annotates through is no longer in the picture. The gate is
written and tested now rather than retrofitted later, because the alternative is
debugging it in the field on somebody else's Python.

Driven entirely by a fake interpreter: a spec that needed a real Tk 9.1 to run
could not be written today, and one that needed a real Tk at all would not run
on the lane that proves this package is import-clean off Windows.
"""

from __future__ import annotations

from tests.doubles import FakeInterpreter
from tk_uia.tkversion import Strategy, strategy_for

_THE_NATIVE_API = "tk accessible"


def test_a_tk_that_answers_for_itself_is_left_alone_rather_than_annotated_over() -> (
    None
):
    # Given a Tk new enough to carry its own accessibility commands
    interpreter = FakeInterpreter("9.1.0", "win32", native=True)

    # When the gate is asked what to do with it
    strategy = strategy_for(interpreter)

    # Then it stands aside
    assert strategy is Strategy.NATIVE, (
        f"annotating over a Tk that already answers for itself, chose {strategy}"
    )

    # And it got there without running a single one of those commands. They have
    # never been executed on this machine or any other, against a Tk that is
    # still in beta; deferring to them is a decision, calling them is a guess.
    assert not any(_THE_NATIVE_API in str(call) for call in interpreter.calls), (
        f"the gate called into an untried native API to decide: {interpreter.calls}"
    )


def test_the_tk_that_ships_with_python_today_is_annotated_because_it_says_nothing() -> (
    None
):
    # Given the Tk that CPython 3.13 and 3.14 bundle, which has no accessibility
    # commands at all
    interpreter = FakeInterpreter("8.6.15", "win32", native=False)

    # When the gate is asked
    strategy = strategy_for(interpreter)

    # Then this package does the work, which is the case it exists for
    assert strategy is Strategy.ANNOTATED, (
        f"the only Tk anyone can install today was passed over: {strategy}"
    )


def test_a_tk_new_enough_for_accessibility_but_built_without_it_is_annotated_anyway() -> (
    None
):
    # Given a 9.1 whose accessibility support was compiled out
    interpreter = FakeInterpreter("9.1b1", "win32", native=False)

    # When the gate is asked
    strategy = strategy_for(interpreter)

    # Then it is annotated. Reading the version number alone would defer to an
    # implementation that is not there and leave the window mute, and the
    # version answers "9.1b1" during the whole beta, so the digits after the
    # minor cannot be relied on either.
    assert strategy is Strategy.ANNOTATED, (
        f"deferred to accessibility commands this build does not have: {strategy}"
    )


def test_a_tk_that_is_not_talking_to_windows_is_left_entirely_alone() -> None:
    # Given the same application running on X11
    interpreter = FakeInterpreter("8.6.15", "x11", native=False)

    # When the gate is asked
    strategy = strategy_for(interpreter)

    # Then nothing happens, and nothing raises. MSAA is a Windows interface;
    # this answer is what lets a cross-platform application call `enable()`
    # unconditionally instead of wrapping it in a platform check of its own.
    assert strategy is Strategy.UNSUPPORTED, (
        f"tried to reach an MSAA interface that is not on this machine: {strategy}"
    )
