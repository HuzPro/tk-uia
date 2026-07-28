"""Whether this package should annotate a Tk, defer to it, or stand aside.

`enable()` asks this first and reports the answer back to its caller. Everything
is asked of the interpreter rather than of `sys.platform` or
`tkinter.TkVersion`, which is what lets the gate be specified without a Tk.
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
# ones, which is how the accessibility commands are found without running any.
_A_SUBCOMMAND_TK_WILL_NEVER_HAVE = "tk tk_uia_capability_probe"

_WHERE_TK_LEAVES_ITS_COMPLAINT = "::tk_uia_capability_probe_complaint"

_THE_ACCESSIBILITY_ENSEMBLE = "accessible"


class Strategy(Enum):
    """What `enable()` did, in the caller's terms."""

    ANNOTATED = auto()
    PROVIDED = auto()
    NATIVE = auto()
    UNSUPPORTED = auto()

    @property
    def annotates(self) -> bool:
        """Whether MSAA annotations were written, whichever member says so."""
        return self in _THE_STRATEGIES_THAT_WRITE


_THE_STRATEGIES_THAT_WRITE = frozenset({Strategy.ANNOTATED, Strategy.PROVIDED})


class TkInterpreter(Protocol):
    """The Tcl interpreter, as the gate uses it."""

    def call(self, *args: object) -> object: ...


_WHERE_TCL_SAYS_IF_IT_IS_THREADED = "tcl_platform(threaded)"


def tcl_can_marshal_across_threads(interpreter: TkInterpreter) -> bool:
    """Whether a call from a foreign thread reaches this interpreter safely.

    Providers answer clients on whatever thread the request arrives on, which
    only a threaded Tcl carries back to the interpreter's own thread.
    """
    try:
        return str(interpreter.call("set", _WHERE_TCL_SAYS_IF_IT_IS_THREADED)) == "1"
    except Exception:  # noqa: BLE001 - this module cannot import tkinter to name TclError
        # Old enough to have never heard the question is old enough to refuse.
        return False


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
    # Digit runs, not dot-splitting: a beta answers "9.1b1" and must still gate.
    return tuple(int(number) for number in re.findall(r"\d+", patchlevel)[:2])


def _offers_its_own_accessibility(interpreter: TkInterpreter) -> bool:
    # Through Tcl's own `catch`: this module cannot import tkinter to name
    # whatever it would raise.
    interpreter.call(
        "catch", _A_SUBCOMMAND_TK_WILL_NEVER_HAVE, _WHERE_TK_LEAVES_ITS_COMPLAINT
    )
    complaint = str(interpreter.call("set", _WHERE_TK_LEAVES_ITS_COMPLAINT))
    interpreter.call("unset", _WHERE_TK_LEAVES_ITS_COMPLAINT)
    return _THE_ACCESSIBILITY_ENSEMBLE in complaint
