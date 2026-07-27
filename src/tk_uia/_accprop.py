"""The `oleacc` calls an annotation is actually made of.

Two details here return `S_OK` and do nothing at all when they are wrong, so
neither is guessed at:

* every `PROPID_ACC_*` GUID is transcribed from `oleacc.h` in the Windows SDK
  (10.0.22621.0), not recalled. `PROPID_ACC_HELP` in particular is not the value
  intuition suggests;
* `MSAAPROPID` is `typedef GUID`, so `idProp` is passed **by value**. Passing a
  pointer compiles, runs, returns `S_OK`, and annotates nothing.

`ctypes.HRESULT` and `ctypes.WINFUNCTYPE` do not exist off Windows, so every
prototype is built on first use rather than at import.
"""

from __future__ import annotations

import ctypes
import sys
from typing import Any

from tk_uia.annotate import PropId

_S_OK = 0
_S_FALSE = 1
_RPC_E_CHANGED_MODE = 0x80010106
_COINIT_APARTMENTTHREADED = 0x2
_CLSCTX_INPROC_SERVER = 1

_OBJID_CLIENT = 0xFFFFFFFC
_CHILDID_SELF = 0

# IAccPropServices, after IUnknown's three: SetPropValue 3, SetPropServer 4,
# ClearProps 5, then these. Verified by calling them, because a wrong slot with
# these signatures is an access violation rather than a quiet no-op.
_SLOT_SET_HWND_PROP = 6
_SLOT_SET_HWND_PROP_STR = 7
_SLOT_CLEAR_HWND_PROPS = 9

_VT_I4 = 3

# GWLP_ID: the control id Win32 puts in WM_COMMAND.wParam and WM_DRAWITEM.idCtl.
_GWLP_ID = -12

_SPI_GETSCREENREADER = 0x0046

_WINDOWS = "win32"

# A plain number rather than `ctypes.HRESULT`, which looks like the honest
# choice and is the wrong one: ctypes raises an `OSError` of its own on any
# negative HRESULT *before* the caller sees the value, so `_checked` never runs
# and the application gets a bare "[WinError -2147024891] Access is denied" with
# no way to tell which of eleven annotation calls refused. Read as a number, the
# code reaches `_checked`, which also catches the positive non-`S_OK` answers
# `ctypes.HRESULT` lets through.
_HOWEVER_COM_ANSWERED = ctypes.c_long


class _Guid(ctypes.Structure):
    _fields_ = (
        ("Data1", ctypes.c_ulong),
        ("Data2", ctypes.c_ushort),
        ("Data3", ctypes.c_ushort),
        ("Data4", ctypes.c_ubyte * 8),
    )


class _Variant(ctypes.Structure):
    """VARIANT, in the only shape used here: 24 bytes, holding a long."""

    _fields_ = (
        ("vt", ctypes.c_ushort),
        ("reserved1", ctypes.c_ushort),
        ("reserved2", ctypes.c_ushort),
        ("reserved3", ctypes.c_ushort),
        ("value", ctypes.c_longlong),
        ("padding", ctypes.c_longlong),
    )


def _guid(first: int, second: int, third: int, *rest: int) -> _Guid:
    return _Guid(first, second, third, (ctypes.c_ubyte * 8)(*rest))


# Transcribed from oleacc.h, 10.0.22621.0.
_CLSID_ACC_PROP_SERVICES = _guid(
    0xB5F8350B, 0x0548, 0x48B1, 0xA6, 0xEE, 0x88, 0xBD, 0x00, 0xB4, 0xA5, 0xE7
)
_IID_IACC_PROP_SERVICES = _guid(
    0x6E26E776, 0x04F0, 0x495D, 0x80, 0xE4, 0x33, 0x30, 0x35, 0x2E, 0x31, 0x69
)

_GUID_FOR_PROP = {
    PropId.NAME: _guid(
        0x608D3DF8, 0x8128, 0x4AA7, 0xA4, 0x28, 0xF5, 0x5E, 0x49, 0x26, 0x72, 0x91
    ),
    PropId.VALUE: _guid(
        0x123FE443, 0x211A, 0x4615, 0x95, 0x27, 0xC4, 0x5A, 0x7E, 0x93, 0x71, 0x7A
    ),
    PropId.DESCRIPTION: _guid(
        0x4D48DFE4, 0xBD3F, 0x491F, 0xA6, 0x48, 0x49, 0x2D, 0x6F, 0x20, 0xC5, 0x88
    ),
    PropId.ROLE: _guid(
        0xCB905FF2, 0x7BD1, 0x4C05, 0xB3, 0xC8, 0xE6, 0xC2, 0x41, 0x36, 0x4D, 0x70
    ),
    PropId.STATE: _guid(
        0xA8D4D5B0, 0x0A21, 0x42D0, 0xA5, 0xC0, 0x51, 0x4E, 0x98, 0x4F, 0x45, 0x7B
    ),
    PropId.HELP: _guid(
        0xC831E11F, 0x44DB, 0x4A99, 0x97, 0x68, 0xCB, 0x8F, 0x97, 0x8B, 0x72, 0x31
    ),
    PropId.DEFAULT_ACTION: _guid(
        0x180C072B, 0xC27F, 0x43C7, 0x99, 0x22, 0xF6, 0x35, 0x62, 0xA4, 0x63, 0x2B
    ),
}


class AccPropServicesStore:
    """Annotations, written where the MSAA-to-UIA bridge reads them."""

    def __init__(self) -> None:
        # Nothing is reached for here: `enable()` builds one of these before the
        # version gate has run, and on a machine with no MSAA it is never used.
        self._services: ctypes.c_void_p | None = None

    def set_string(self, hwnd: int, prop: PropId, value: str) -> None:
        services = self._reached()
        call = _method(services, _SLOT_SET_HWND_PROP_STR, _set_hwnd_prop_str())
        _checked(
            call(
                services,
                ctypes.c_void_p(hwnd),
                _OBJID_CLIENT,
                _CHILDID_SELF,
                _GUID_FOR_PROP[prop],
                value,
            ),
            f"SetHwndPropStr({prop.name})",
        )

    def set_number(self, hwnd: int, prop: PropId, value: int) -> None:
        holder = _Variant()
        holder.vt = _VT_I4
        holder.value = value
        services = self._reached()
        call = _method(services, _SLOT_SET_HWND_PROP, _set_hwnd_prop())
        _checked(
            call(
                services,
                ctypes.c_void_p(hwnd),
                _OBJID_CLIENT,
                _CHILDID_SELF,
                _GUID_FOR_PROP[prop],
                holder,
            ),
            f"SetHwndProp({prop.name})",
        )

    def control_id(self, hwnd: int) -> int:
        return int(_window_long()(ctypes.c_void_p(hwnd), _GWLP_ID))

    def set_control_id(self, hwnd: int, control_id: int) -> None:
        _set_window_long()(ctypes.c_void_p(hwnd), _GWLP_ID, control_id)

    def clear(self, hwnd: int) -> None:
        props = list(_GUID_FOR_PROP.values())
        everything = (_Guid * len(props))(*props)
        services = self._reached()
        call = _method(services, _SLOT_CLEAR_HWND_PROPS, _clear_hwnd_props())
        _checked(
            call(
                services,
                ctypes.c_void_p(hwnd),
                _OBJID_CLIENT,
                _CHILDID_SELF,
                everything,
                len(props),
            ),
            "ClearHwndProps",
        )

    def _reached(self) -> ctypes.c_void_p:
        if self._services is None:
            self._services = _acc_prop_services()
        return self._services


def screen_reader_running() -> bool:
    """Whether Windows believes something is reading the screen aloud."""
    if sys.platform != _WINDOWS:
        return False
    listening = ctypes.c_int(0)
    _user32().SystemParametersInfoW(_SPI_GETSCREENREADER, 0, ctypes.byref(listening), 0)
    return bool(listening.value)


def _acc_prop_services() -> ctypes.c_void_p:
    ole32 = ctypes.windll.ole32
    started = ole32.CoInitializeEx(None, _COINIT_APARTMENTTHREADED)
    # S_FALSE means this thread was already in an apartment and
    # RPC_E_CHANGED_MODE means it is in a different one. Both are somebody
    # else's apartment to close, which is why CoUninitialize is never called.
    if started not in (_S_OK, _S_FALSE) and (started & 0xFFFFFFFF) != (
        _RPC_E_CHANGED_MODE
    ):
        raise OSError(f"CoInitializeEx failed 0x{started & 0xFFFFFFFF:08X}")
    services = ctypes.c_void_p()
    _checked(
        ole32.CoCreateInstance(
            ctypes.byref(_CLSID_ACC_PROP_SERVICES),
            None,
            _CLSCTX_INPROC_SERVER,
            ctypes.byref(_IID_IACC_PROP_SERVICES),
            ctypes.byref(services),
        ),
        "CoCreateInstance(AccPropServices)",
    )
    return services


def _method(services: ctypes.c_void_p, slot: int, prototype: Any) -> Any:
    vtable = ctypes.cast(services, ctypes.POINTER(ctypes.c_void_p))[0]
    return prototype(ctypes.cast(vtable, ctypes.POINTER(ctypes.c_void_p))[slot])


def _checked(result: int, what: str) -> None:
    if result != _S_OK:
        raise OSError(f"{what} failed 0x{result & 0xFFFFFFFF:08X}")


def _set_hwnd_prop() -> Any:
    return ctypes.WINFUNCTYPE(
        _HOWEVER_COM_ANSWERED,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_ulong,
        _Guid,
        _Variant,
    )


def _set_hwnd_prop_str() -> Any:
    return ctypes.WINFUNCTYPE(
        _HOWEVER_COM_ANSWERED,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_ulong,
        _Guid,
        ctypes.c_wchar_p,
    )


def _clear_hwnd_props() -> Any:
    return ctypes.WINFUNCTYPE(
        _HOWEVER_COM_ANSWERED,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.POINTER(_Guid),
        ctypes.c_int,
    )


def _window_long() -> Any:
    user32 = _user32()
    # GetWindowLongPtrW exists only in the 64-bit user32; on 32-bit Python the
    # non-Ptr name is the whole of the API and is already pointer-sized.
    read = getattr(user32, "GetWindowLongPtrW", None) or user32.GetWindowLongW
    read.restype = ctypes.c_ssize_t
    read.argtypes = (ctypes.c_void_p, ctypes.c_int)
    return read


def _set_window_long() -> Any:
    user32 = _user32()
    write = getattr(user32, "SetWindowLongPtrW", None) or user32.SetWindowLongW
    write.restype = ctypes.c_ssize_t
    write.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t)
    return write


def _user32() -> Any:
    # Per call rather than at import: `ctypes.windll` does not exist off
    # Windows, and this module still has to import there.
    return ctypes.windll.user32
