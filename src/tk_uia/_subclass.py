"""SetWindowSubclass, and the one window procedure that never raises."""

from __future__ import annotations

import ctypes
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

WM_GETOBJECT = 0x003D
WM_DESTROY = 0x0002

_OUR_SUBCLASS_ID = 1

Responder = Callable[[int, int, int], int | None]
"""Answers a WM_GETOBJECT, or None to let the message fall through."""


@dataclass(frozen=True)
class _WhoAnswersFor:
    """Who answers for one window, and who hears that it has gone."""

    respond: Responder
    gone: Callable[[int], None]


class WindowSubclasses:
    """Puts a responder in each handle's message path, and takes it out again."""

    def __init__(self, note_trouble: Callable[[str], None]) -> None:
        self._answering: dict[int, _WhoAnswersFor] = {}
        self._note = note_trouble
        # Built on first use (WINFUNCTYPE does not exist off Windows) and then
        # never released: a collected callback is a crash on the next message.
        self._proc: Any = None

    def put_in_the_path_of(
        self, hwnd: int, respond: Responder, gone: Callable[[int], None]
    ) -> None:
        self._answering[hwnd] = _WhoAnswersFor(respond, gone)
        if not _comctl32().SetWindowSubclass(
            hwnd, self._the_one_proc(), _OUR_SUBCLASS_ID, 0
        ):
            self._answering.pop(hwnd, None)
            raise ctypes.WinError(ctypes.get_last_error())

    def step_out_of(self, hwnd: int) -> None:
        self._answering.pop(hwnd, None)
        _comctl32().RemoveWindowSubclass(hwnd, self._the_one_proc(), _OUR_SUBCLASS_ID)

    def _the_one_proc(self) -> Any:
        if self._proc is None:
            self._proc = _a_subclass_proc_type()(self._handle)
        return self._proc

    def _handle(self, hwnd, msg, wparam, lparam, _subclass_id, _reference):
        try:
            if msg == WM_GETOBJECT:
                answering = self._answering.get(hwnd)
                if answering is not None:
                    answer = answering.respond(hwnd, wparam, lparam)
                    if answer is not None:
                        return answer
            elif msg == WM_DESTROY:
                answering = self._answering.pop(hwnd, None)
                if answering is not None:
                    answering.gone(hwnd)
                _comctl32().RemoveWindowSubclass(
                    hwnd, self._the_one_proc(), _OUR_SUBCLASS_ID
                )
        except Exception as trouble:  # noqa: BLE001 - an exception here corrupts the message loop
            self._note(f"window {hwnd:#x}, message {msg:#x}: {trouble!r}")
        return _comctl32().DefSubclassProc(hwnd, msg, wparam, lparam)


def _a_subclass_proc_type() -> Any:
    global _PROC_TYPE
    if _PROC_TYPE is None:
        from ctypes import wintypes

        _PROC_TYPE = ctypes.WINFUNCTYPE(
            wintypes.LPARAM,
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
            ctypes.c_size_t,
            ctypes.c_size_t,
        )
    return _PROC_TYPE


def _comctl32() -> Any:
    global _COMCTL32
    if _COMCTL32 is None:
        from ctypes import wintypes

        # Full argtypes throughout: a handle passed through the c_int default
        # is truncated on 64-bit Windows.
        comctl32 = ctypes.WinDLL("comctl32.dll", use_last_error=True)
        comctl32.SetWindowSubclass.restype = wintypes.BOOL
        comctl32.SetWindowSubclass.argtypes = [
            wintypes.HWND,
            _a_subclass_proc_type(),
            ctypes.c_size_t,
            ctypes.c_size_t,
        ]
        comctl32.RemoveWindowSubclass.restype = wintypes.BOOL
        comctl32.RemoveWindowSubclass.argtypes = [
            wintypes.HWND,
            _a_subclass_proc_type(),
            ctypes.c_size_t,
        ]
        comctl32.DefSubclassProc.restype = wintypes.LPARAM
        comctl32.DefSubclassProc.argtypes = [
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
        ]
        _COMCTL32 = comctl32
    return _COMCTL32


_PROC_TYPE: Any = None
_COMCTL32: Any = None
