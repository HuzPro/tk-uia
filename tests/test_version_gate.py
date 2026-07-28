"""Behavioral spec for deciding whether this package should do anything at all."""

from __future__ import annotations

from tests.doubles import FakeInterpreter
from tk_uia.tkversion import Strategy, strategy_for, tcl_can_marshal_across_threads

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

    # And it got there without calling one of those commands, which are still in beta
    assert not any(_THE_NATIVE_API in str(call) for call in interpreter.calls), (
        f"the gate called into an untried native API to decide: {interpreter.calls}"
    )


def test_the_tk_that_ships_with_python_today_is_annotated_because_it_says_nothing() -> (
    None
):
    # Given the Tk that CPython 3.13 and 3.14 bundle, which has no accessibility
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

    # Then it is annotated: the version answers 9.1b1 for the whole beta either way
    assert strategy is Strategy.ANNOTATED, (
        f"deferred to accessibility commands this build does not have: {strategy}"
    )


def test_a_tk_that_is_not_talking_to_windows_is_left_entirely_alone() -> None:
    # Given the same application running on X11
    interpreter = FakeInterpreter("8.6.15", "x11", native=False)

    # When the gate is asked
    strategy = strategy_for(interpreter)

    # Then nothing happens, and nothing raises
    assert strategy is Strategy.UNSUPPORTED, (
        f"tried to reach an MSAA interface that is not on this machine: {strategy}"
    )


def test_the_tcl_python_ships_says_it_can_carry_a_call_between_threads() -> None:
    # Given the threaded Tcl every python.org build bundles
    interpreter = FakeInterpreter("8.6.15", "win32", native=False)

    # When the gate is asked whether a call can cross threads safely
    answer = tcl_can_marshal_across_threads(interpreter)

    # Then it can, which is what lets widgets answer clients that call from anywhere
    assert answer is True, (
        "the stock threaded Tcl was mistaken for one that cannot marshal, "
        "which would stand the provider layer down on every ordinary install"
    )


def test_a_tcl_built_without_threads_is_told_apart_so_providers_can_stand_down() -> (
    None
):
    # Given a Tcl someone compiled without thread support
    interpreter = FakeInterpreter("8.6.15", "win32", native=False, threaded=False)

    # When the gate is asked
    answer = tcl_can_marshal_across_threads(interpreter)

    # Then the build is told apart, so nothing ever answers a client from a
    # thread this interpreter cannot hear from
    assert answer is False, (
        "an unthreaded Tcl was waved through; a cross-thread call into one "
        "corrupts quietly, which no client would ever trace back here"
    )


def test_the_strategies_that_wrote_annotations_say_so_through_one_predicate() -> None:
    # Given the four ways enable() can answer
    # When each is asked whether MSAA annotations were written
    # Then the two writing strategies say yes and the two standing down say no
    assert Strategy.ANNOTATED.annotates and Strategy.PROVIDED.annotates, (
        "a strategy that wrote annotations denied it; every caller matching "
        "on ANNOTATED alone needs this predicate to survive PROVIDED"
    )
    assert not Strategy.NATIVE.annotates and not Strategy.UNSUPPORTED.annotates, (
        "a strategy that stood down claimed to have written annotations"
    )
