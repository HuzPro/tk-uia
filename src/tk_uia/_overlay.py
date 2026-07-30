"""The window handles a notebook's tabs borrow, made with four Win32 calls.

Both styles are load-bearing: `WS_EX_TRANSPARENT` lets clicks fall through to
the notebook, `SS_OWNERDRAW` leaves painting to a parent that never paints,
so the tab strip shows through.
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
        made = _user32().CreateWindowExW(
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
        _user32().MoveWindow(
            ctypes.c_void_p(hwnd), left, top, width, height, _REPAINT_IT
        )

    def destroy(self, hwnd: int) -> None:
        _user32().DestroyWindow(ctypes.c_void_p(hwnd))


_USER32: Any = None


def _user32() -> Any:
    # Built on first use rather than at import: `ctypes.WinDLL` cannot be built
    # off Windows, and this module still has to import there.
    global _USER32
    if _USER32 is None:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.CreateWindowExW.restype = ctypes.c_void_p
        user32.CreateWindowExW.argtypes = (
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
        user32.MoveWindow.restype = ctypes.c_int
        user32.MoveWindow.argtypes = (
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
        )
        user32.DestroyWindow.restype = ctypes.c_int
        user32.DestroyWindow.argtypes = (ctypes.c_void_p,)
        _USER32 = user32
    return _USER32
