"""Reaching a variable the application owns, by the name its widget declared.

Never a `tkinter.Variable`. `StringVar(master, name=whatever_the_widget_declared)`
is the obvious implementation and it destroys the application's data:
`Variable.__del__` unsets the Tcl variable it names, unconditionally, so the
moment that wrapper is collected the application's own variable is gone.
Measured: unreadable afterwards, with no exception and nothing in any log, and
removing the trace first makes no difference. So the three things the protocol
needs are raw Tcl calls, which read and trace a variable without claiming it.
"""

from __future__ import annotations

import tkinter
from collections.abc import Callable

from tk_uia.annotate import TkVariable


class _AVariableTheApplicationOwns:
    """One Tcl variable, read and traced by name and never taken over."""

    def __init__(self, widget: tkinter.Misc, name: str) -> None:
        self._interpreter = widget.tk
        # Registered against the window rather than the widget: Tk deletes a
        # widget's Tcl commands as it destroys it, and a trace still on the
        # variable would then fire at a command that is no longer there, once
        # per write for the life of the process.
        self._where_a_callback_becomes_a_command = widget.winfo_toplevel()
        self._name = name

    def get(self) -> object:
        try:
            return self._interpreter.call("set", self._name)
        except tkinter.TclError:
            # Tcl refuses to read a variable that is not there, and to a client
            # "not there" and "empty" are the same answer.
            return ""

    def trace_add(self, mode: str, callback: Callable[..., object]) -> str:
        command = self._where_a_callback_becomes_a_command.register(callback)
        self._interpreter.call("trace", "add", "variable", self._name, mode, command)
        return command

    def trace_remove(self, mode: str, callback_name: str) -> None:
        # The trace comes off first and the command second. The other order
        # leaves a window in which a write reaches a command that has gone.
        self._interpreter.call(
            "trace", "remove", "variable", self._name, mode, callback_name
        )
        self._where_a_callback_becomes_a_command.deletecommand(callback_name)


def a_variable_the_application_owns(widget: tkinter.Misc, name: str) -> TkVariable:
    """The variable this widget declared, reachable and still the application's."""
    return _AVariableTheApplicationOwns(widget, name)
