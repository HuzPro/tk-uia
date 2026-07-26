"""Whether this package should annotate a Tk, defer to it, or stand aside.

Where it plugs in: `enable()` asks this first and reports the answer back to its
caller, so a suite can assert which path it got rather than discovering months
later that the gate mis-fired and the whole thing quietly did nothing.

Everything is asked of the interpreter rather than of `sys.platform` or
`tkinter.TkVersion`: the interpreter is the thing whose behaviour is in
question, and asking it is what lets the gate be specified without a Tk.
"""

from __future__ import annotations

import re
from enum import Enum, auto
from typing import Protocol

# The release TIP 733 landed in. From here on Tk answers WM_GETOBJECT itself and
# the MSAA proxy this package annotates through is no longer in the picture.
_TK_ANSWERS_FOR_ITSELF_FROM = (9, 1)

_WINDOWS = "win32"

# Deliberately not a real subcommand. Tk answers a bad one by listing the good
# ones, which is how the accessibility commands can be found without running a
# single one of them.
_A_SUBCOMMAND_TK_WILL_NEVER_HAVE = "tk tk_uia_capability_probe"

_WHERE_TK_LEAVES_ITS_COMPLAINT = "::tk_uia_capability_probe_complaint"

_THE_ACCESSIBILITY_ENSEMBLE = "accessible"


class Strategy(Enum):
    """What `enable()` did, in the caller's terms."""

    ANNOTATED = auto()
    NATIVE = auto()
    UNSUPPORTED = auto()


class TkInterpreter(Protocol):
    """The Tcl interpreter, as the gate uses it."""

    def call(self, *args: object) -> object: ...


def strategy_for(interpreter: TkInterpreter) -> Strategy:
    if _windowing_system_of(interpreter) != _WINDOWS:
        return Strategy.UNSUPPORTED
    if _version_of(interpreter) < _TK_ANSWERS_FOR_ITSELF_FROM:
        return Strategy.ANNOTATED
    if _offers_its_own_accessibility(interpreter):
        return Strategy.NATIVE
    # New enough to have it, and does not: a build with the feature compiled
    # out still needs annotating, and guessing NATIVE here would leave it mute.
    return Strategy.ANNOTATED


def _windowing_system_of(interpreter: TkInterpreter) -> str:
    return str(interpreter.call("tk", "windowingsystem"))


def _version_of(interpreter: TkInterpreter) -> tuple[int, ...]:
    patchlevel = str(interpreter.call("info", "patchlevel"))
    # Major and minor only, and by digit runs rather than by splitting on dots:
    # a beta answers "9.1b1", and the gate has to hold for the betas because
    # that is what Tk 9.1 is right now.
    return tuple(int(number) for number in re.findall(r"\d+", patchlevel)[:2])


def _offers_its_own_accessibility(interpreter: TkInterpreter) -> bool:
    # Asked through Tcl's own `catch` rather than by letting the error cross
    # into Python, which would mean catching whatever tkinter chose to raise —
    # and this module cannot import tkinter to name it.
    #
    # The subcommand is one Tk cannot have, so what comes back is Tk's own list
    # of the subcommands it does have. That is how the accessibility ensemble
    # is found without running any part of it: these commands are new, still in
    # beta, and have never been executed here or anywhere else.
    interpreter.call(
        "catch", _A_SUBCOMMAND_TK_WILL_NEVER_HAVE, _WHERE_TK_LEAVES_ITS_COMPLAINT
    )
    complaint = str(interpreter.call("set", _WHERE_TK_LEAVES_ITS_COMPLAINT))
    interpreter.call("unset", _WHERE_TK_LEAVES_ITS_COMPLAINT)
    return _THE_ACCESSIBILITY_ENSEMBLE in complaint
