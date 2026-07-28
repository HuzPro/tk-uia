"""How a live Tk widget becomes the callables a provider drives it through.

Thin by design, like `_tkvars.py`: every reader answers nothing once the
widget is mid-teardown, and its truth is proven by the gui specs.
"""

from __future__ import annotations

from tkinter import TclError
from typing import TYPE_CHECKING

from tk_uia.annotate import words_the_widget_shows
from tk_uia.provide import WidgetWiring, answers_nothing_once_the_widget_is_gone

if TYPE_CHECKING:
    from collections.abc import Callable

    from tk_uia.annotate import TkWidget

_NO_COMMAND = ""


def wiring_for(widget: TkWidget) -> WidgetWiring:
    build = _THE_PATTERNS_OF_EACH_CLASS.get(widget.winfo_class(), _nothing_more)
    return WidgetWiring(
        words=_guarded(lambda: words_the_widget_shows(widget)),
        is_enabled=_guarded(lambda: _is_enabled(widget), nothing=True),
        post=widget.after_idle,
        still_there=_guarded(widget.winfo_exists, nothing=False),
        **build(widget),
    )


class _APress:
    def __init__(self, widget: TkWidget) -> None:
        self._widget = widget
        self.press = widget.invoke
        self.offered = _guarded(
            lambda: str(widget.cget("command")) != _NO_COMMAND, nothing=False
        )


class _AFlip:
    def __init__(self, widget: TkWidget) -> None:
        self._widget = widget
        self.flip = widget.invoke
        self.is_on = _guarded(lambda: _holds_its_on_value(widget), nothing=False)


class _AChoice:
    def __init__(self, widget: TkWidget) -> None:
        self._widget = widget
        self.select = widget.invoke
        self.is_selected = _guarded(
            lambda: _holds_its_own_value(widget), nothing=False
        )


class _TheTextOfAnEntry:
    def __init__(self, widget: TkWidget) -> None:
        self._widget = widget
        self.read = _guarded(lambda: str(widget.get()), nothing="")
        self.is_read_only = _guarded(lambda: _cannot_be_typed_in(widget), nothing=True)

    def write(self, text: str) -> None:
        self._widget.delete(0, "end")
        self._widget.insert(0, text)


class _TheTextOfACombobox:
    """A combobox is select-only under `readonly`, not unchangeable: a user
    still picks from the dropdown, so UIA read-only counts `disabled` alone."""

    def __init__(self, widget: TkWidget) -> None:
        self._widget = widget
        self.read = _guarded(lambda: str(widget.get()), nothing="")
        self.is_read_only = _guarded(lambda: _is_disabled(widget), nothing=True)

    def write(self, text: str) -> None:
        widget = self._widget
        if _selects_rather_than_types(widget):
            offered = _the_values_it_offers(widget)
            if text not in offered:
                raise ValueError(
                    f"{text!r} is not among the values this combobox offers "
                    f"({', '.join(repr(value) for value in offered)}); a "
                    "readonly combobox takes only a choice a user could make"
                )
            widget.set(text)
            # The one action a user has here is a dropdown choice, and a
            # dropdown choice fires this event.
            widget.event_generate("<<ComboboxSelected>>")
            return
        widget.set(text)


class _TheTextOfAText:
    def __init__(self, widget: TkWidget) -> None:
        self._widget = widget
        self.read = _guarded(lambda: str(widget.get("1.0", "end-1c")), nothing="")
        self.is_read_only = _guarded(
            lambda: str(widget.cget("state")) == "disabled", nothing=True
        )

    def write(self, text: str) -> None:
        self._widget.delete("1.0", "end")
        self._widget.insert("1.0", text)


class _TheNumberOfAScale:
    def __init__(self, widget: TkWidget) -> None:
        self.write = widget.set
        self.now = _guarded(lambda: float(widget.get()), nothing=0.0)
        self.low = _guarded(lambda: min(_the_ends_of(widget)), nothing=0.0)
        self.high = _guarded(lambda: max(_the_ends_of(widget)), nothing=0.0)
        self.step = _guarded(lambda: _the_resolution_of(widget))
        self.is_read_only = _guarded(lambda: _is_disabled(widget), nothing=True)


class _TheNumberOfAProgressbar:
    """Readable and never writable, and it says so."""

    write = None

    def __init__(self, widget: TkWidget) -> None:
        self.now = _guarded(lambda: float(str(widget.cget("value"))), nothing=0.0)
        self.low = _guarded(lambda: 0.0, nothing=0.0)
        self.high = _guarded(lambda: float(str(widget.cget("maximum"))), nothing=0.0)
        self.step = _guarded(lambda: None)

    def is_read_only(self) -> bool:
        return True


def _a_press(widget: TkWidget) -> dict[str, object]:
    return {"invoke": _APress(widget)}


def _a_flip(widget: TkWidget) -> dict[str, object]:
    return {"toggle": _AFlip(widget)}


def _a_choice(widget: TkWidget) -> dict[str, object]:
    return {"selection": _AChoice(widget)}


def _entry_text(widget: TkWidget) -> dict[str, object]:
    return {"value": _TheTextOfAnEntry(widget)}


def _combobox_text(widget: TkWidget) -> dict[str, object]:
    return {"value": _TheTextOfACombobox(widget)}


def _text_text(widget: TkWidget) -> dict[str, object]:
    return {"value": _TheTextOfAText(widget)}


def _scale_number(widget: TkWidget) -> dict[str, object]:
    return {"range_value": _TheNumberOfAScale(widget)}


def _progressbar_number(widget: TkWidget) -> dict[str, object]:
    return {"range_value": _TheNumberOfAProgressbar(widget)}


def _nothing_more(widget: TkWidget) -> dict[str, object]:
    return {}


_THE_PATTERNS_OF_EACH_CLASS: dict[str, Callable[[TkWidget], dict[str, object]]] = {
    "Button": _a_press,
    "TButton": _a_press,
    "Checkbutton": _a_flip,
    "TCheckbutton": _a_flip,
    "Radiobutton": _a_choice,
    "TRadiobutton": _a_choice,
    "Entry": _entry_text,
    "TEntry": _entry_text,
    "Spinbox": _entry_text,
    "TSpinbox": _entry_text,
    "TCombobox": _combobox_text,
    "Text": _text_text,
    "Scale": _scale_number,
    "TScale": _scale_number,
    "TProgressbar": _progressbar_number,
}


def _guarded(read, nothing=None):
    return answers_nothing_once_the_widget_is_gone(read, TclError, nothing)


def _is_enabled(widget: TkWidget) -> bool:
    return not _is_disabled(widget)


def _is_disabled(widget: TkWidget) -> bool:
    instate = getattr(widget, "instate", None)
    if instate is not None:
        return bool(instate(["disabled"]))
    if "state" not in widget.keys():  # noqa: SIM118 - Tk options, not a dict
        return False
    return str(widget.cget("state")) == "disabled"


def _cannot_be_typed_in(widget: TkWidget) -> bool:
    instate = getattr(widget, "instate", None)
    if instate is not None:
        return bool(instate(["disabled"])) or bool(instate(["readonly"]))
    return str(widget.cget("state")) in ("disabled", "readonly")


def _selects_rather_than_types(widget: TkWidget) -> bool:
    instate = getattr(widget, "instate", None)
    return bool(instate(["readonly"])) if instate is not None else False


def _the_values_it_offers(widget: TkWidget) -> tuple[str, ...]:
    values = widget.cget("values")
    if isinstance(values, (list, tuple)):
        return tuple(str(value) for value in values)
    return tuple(str(value) for value in widget.tk.splitlist(values))


def _holds_its_on_value(widget: TkWidget) -> bool:
    variable = str(widget.cget("variable"))
    if variable:
        try:
            return str(widget.getvar(variable)) == str(widget.cget("onvalue"))
        except TclError:
            # An inline variable nobody held gets collected and unset, which
            # a checkbutton displays as off.
            return False
    instate = getattr(widget, "instate", None)
    return bool(instate(["selected"])) if instate is not None else False


def _holds_its_own_value(widget: TkWidget) -> bool:
    variable = str(widget.cget("variable"))
    if not variable:
        return False
    try:
        return str(widget.getvar(variable)) == str(widget.cget("value"))
    except TclError:
        return False


def _the_ends_of(widget: TkWidget) -> tuple[float, float]:
    return (
        float(str(widget.cget("from"))),
        float(str(widget.cget("to"))),
    )


def _the_resolution_of(widget: TkWidget) -> float | None:
    if "resolution" not in widget.keys():  # noqa: SIM118 - Tk options, not a dict
        return None
    return float(str(widget.cget("resolution")))
