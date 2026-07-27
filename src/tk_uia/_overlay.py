"""The window handles a notebook's tabs borrow, made with four Win32 calls.

Both window styles are load-bearing. `WS_EX_TRANSPARENT` keeps the window out of
hit-testing, so the click a client aims at a tab reaches the notebook underneath
and Tk selects it. `SS_OWNERDRAW` makes the static ask its parent to paint it by
way of `WM_DRAWITEM`; Tk has never heard of this window and ignores the message,
so nothing is painted and the tab strip shows through. A plain static would
paint its background over the tab it is standing in for.
"""

from __future__ import annotations

import ctypes
from typing import Any

# The generic control class every Windows install has. A class of this
# package's own would leave a stale atom behind on every reload.
_A_PLAIN_STATIC = "STATIC"

_WS_CHILD = 0x40000000
_WS_VISIBLE = 0x10000000
_SS_OWNERDRAW = 0x0000000D
_WS_EX_TRANSPARENT = 0x00000020

_NO_MENU = None
_NO_MODULE = None
_NO_PARAMETER = None
_REPAINT_IT = True


class Win32Overlays:
    """Real child windows over a real notebook's real tabs."""

    def create(self, parent: int, left: int, top: int, width: int, height: int) -> int:
        made = _create_window()(
            _WS_EX_TRANSPARENT,
            _A_PLAIN_STATIC,
            None,
            _WS_CHILD | _WS_VISIBLE | _SS_OWNERDRAW,
            left,
            top,
            width,
            height,
            ctypes.c_void_p(parent),
            _NO_MENU,
            _NO_MODULE,
            _NO_PARAMETER,
        )
        if not made:
            raise OSError(
                f"could not make a window for a tab of {parent:#x}: "
                f"CreateWindowExW failed with {ctypes.get_last_error()}"
            )
        return int(made)

    def move(self, hwnd: int, left: int, top: int, width: int, height: int) -> None:
        _move_window()(ctypes.c_void_p(hwnd), left, top, width, height, _REPAINT_IT)

    def destroy(self, hwnd: int) -> None:
        _destroy_window()(ctypes.c_void_p(hwnd))


def _create_window() -> Any:
    make = _user32().CreateWindowExW
    make.restype = ctypes.c_void_p
    make.argtypes = (
        ctypes.c_uint32,
        ctypes.c_wchar_p,
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
    )
    return make


def _move_window() -> Any:
    move = _user32().MoveWindow
    move.restype = ctypes.c_int
    move.argtypes = (
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
    )
    return move


def _destroy_window() -> Any:
    close = _user32().DestroyWindow
    close.restype = ctypes.c_int
    close.argtypes = (ctypes.c_void_p,)
    return close


def _user32() -> Any:
    # Per call rather than at import: `ctypes.WinDLL` cannot be built off
    # Windows, and this module still has to import there.
    return ctypes.WinDLL("user32", use_last_error=True)
