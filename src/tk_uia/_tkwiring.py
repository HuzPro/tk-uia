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
    named = _THE_PATTERN_OF_EACH_CLASS.get(widget.winfo_class())
    drives: dict[str, object] = {}
    if named is not None:
        slot, drive = named
        drives[slot] = drive(widget)
    return WidgetWiring(
        words=_guarded(lambda: words_the_widget_shows(widget)),
        is_enabled=_guarded(lambda: _is_enabled(widget), nothing=True),
        post=widget.after_idle,
        still_there=_guarded(widget.winfo_exists, nothing=False),
        **drives,
    )


class _APress:
    def __init__(self, widget: TkWidget) -> None:
        self.press = widget.invoke
        self.offered = _guarded(
            lambda: str(widget.cget("command")) != _NO_COMMAND, nothing=False
        )


class _AFlip:
    def __init__(self, widget: TkWidget) -> None:
        self.flip = widget.invoke
        self.is_on = _guarded(lambda: _holds_its_on_value(widget), nothing=False)


class _AChoice:
    def __init__(self, widget: TkWidget) -> None:
        self.select = widget.invoke
        self.is_selected = _guarded(lambda: _holds_its_own_value(widget), nothing=False)


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
        self.high = _guarded(lambda: float(str(widget.cget("maximum"))), nothing=0.0)

    def low(self) -> float:
        return 0.0

    def step(self) -> float | None:
        return None

    def is_read_only(self) -> bool:
        return True


class _TheRowsOfAListbox:
    """A listbox's rows: keys are indexes as words, and there are no branches.

    A pattern select fires `<<ListboxSelect>>`, because the user gesture it
    stands in for would have.
    """

    def __init__(self, widget: TkWidget) -> None:
        self._widget = widget
        self._how_many = _guarded(lambda: int(widget.size()), nothing=0)

    def roots(self) -> tuple[str, ...]:
        return tuple(str(index) for index in range(self._how_many()))

    def children(self, key: str) -> tuple[str, ...]:
        return ()

    def parent(self, key: str) -> str | None:
        return None

    def exists(self, key: str) -> bool:
        # By arithmetic, never by building the whole run: a client walking a
        # large listbox asks this before every single answer.
        return key.isdigit() and int(key) < self._how_many()

    def words(self, key: str) -> str | None:
        return _or_nothing(lambda: str(self._widget.get(int(key))))

    def select(self, key: str) -> None:
        widget = self._widget
        widget.selection_clear(0, "end")
        widget.selection_set(int(key))
        widget.activate(int(key))
        widget.event_generate("<<ListboxSelect>>")

    def is_selected(self, key: str) -> bool:
        return bool(
            _or_nothing(
                lambda: self._widget.selection_includes(int(key)), nothing=False
            )
        )

    def show(self, key: str) -> None:
        self._widget.see(int(key))

    def rectangle(self, key: str) -> tuple[int, int, int, int] | None:
        return _or_nothing(
            lambda: _painted_at(self._widget, self._widget.bbox(int(key)))
        )

    def is_open(self, key: str) -> bool:
        return False

    def open(self, key: str) -> None: ...

    def close(self, key: str) -> None: ...

    def takes_more_than_one(self) -> bool:
        return bool(
            _or_nothing(
                lambda: (
                    str(self._widget.cget("selectmode")) in ("multiple", "extended")
                ),
                nothing=False,
            )
        )

    def add_to_selection(self, key: str) -> None:
        self._widget.selection_set(int(key))
        self._widget.event_generate("<<ListboxSelect>>")

    def remove_from_selection(self, key: str) -> None:
        self._widget.selection_clear(int(key))
        self._widget.event_generate("<<ListboxSelect>>")

    def announce_selection_to(self, say: Callable[[tuple[str, ...]], None]) -> None:
        widget = self._widget
        selected_now = _guarded(
            lambda: tuple(str(index) for index in widget.curselection()),
            nothing=(),
        )
        widget.bind("<<ListboxSelect>>", lambda _event: say(selected_now()), add="+")


class _TheItemsOfATreeview:
    """A treeview's items, by the item ids the widget itself assigns.

    Tk raises `<<TreeviewSelect>>` on any selection change of its own accord,
    so a pattern select only has to select and focus.
    """

    def __init__(self, widget: TkWidget) -> None:
        self._widget = widget

    def roots(self) -> tuple[str, ...]:
        return self.children("")

    def children(self, key: str) -> tuple[str, ...]:
        held = _or_nothing(lambda: self._widget.get_children(key), nothing=())
        return tuple(str(child) for child in held)

    def parent(self, key: str) -> str | None:
        holder = _or_nothing(lambda: str(self._widget.parent(key)))
        return holder or None

    def exists(self, key: str) -> bool:
        return bool(_or_nothing(lambda: self._widget.exists(key), nothing=False))

    def words(self, key: str) -> str | None:
        return _or_nothing(lambda: str(self._widget.item(key, "text"))) or None

    def select(self, key: str) -> None:
        self._widget.selection_set(key)
        self._widget.focus(key)

    def is_selected(self, key: str) -> bool:
        return bool(_or_nothing(lambda: key in self._widget.selection(), nothing=False))

    def show(self, key: str) -> None:
        self._widget.see(key)

    def rectangle(self, key: str) -> tuple[int, int, int, int] | None:
        # An item scrolled or folded out of view answers an empty bbox.
        return _or_nothing(
            lambda: _painted_at(self._widget, self._widget.bbox(key) or None)
        )

    def is_open(self, key: str) -> bool:
        return bool(
            _or_nothing(lambda: str(self._widget.item(key, "open")) in ("1", "True"))
        )

    def open(self, key: str) -> None:
        self._widget.item(key, open=True)

    def close(self, key: str) -> None:
        self._widget.item(key, open=False)

    def takes_more_than_one(self) -> bool:
        return bool(
            _or_nothing(
                lambda: str(self._widget.cget("selectmode")) == "extended",
                nothing=False,
            )
        )

    def add_to_selection(self, key: str) -> None:
        self._widget.selection_add(key)

    def remove_from_selection(self, key: str) -> None:
        self._widget.selection_remove(key)

    def announce_selection_to(self, say: Callable[[tuple[str, ...]], None]) -> None:
        widget = self._widget
        selected_now = _guarded(
            lambda: tuple(str(key) for key in widget.selection()), nothing=()
        )
        widget.bind("<<TreeviewSelect>>", lambda _event: say(selected_now()), add="+")


def _painted_at(
    widget: TkWidget, painted: tuple[int, int, int, int] | None
) -> tuple[int, int, int, int] | None:
    if painted is None:
        return None
    x, y, width, height = painted
    return (widget.winfo_rootx() + x, widget.winfo_rooty() + y, width, height)


# Which `WidgetWiring` slot each class fills, and what fills it. A class absent
# here carries no pattern, and a provider offers it none.
_THE_PATTERN_OF_EACH_CLASS: dict[str, tuple[str, Callable[[TkWidget], object]]] = {
    "Button": ("invoke", _APress),
    "TButton": ("invoke", _APress),
    "Checkbutton": ("toggle", _AFlip),
    "TCheckbutton": ("toggle", _AFlip),
    "Radiobutton": ("selection", _AChoice),
    "TRadiobutton": ("selection", _AChoice),
    "Entry": ("value", _TheTextOfAnEntry),
    "TEntry": ("value", _TheTextOfAnEntry),
    "Spinbox": ("value", _TheTextOfAnEntry),
    "TSpinbox": ("value", _TheTextOfAnEntry),
    "TCombobox": ("value", _TheTextOfACombobox),
    "Text": ("value", _TheTextOfAText),
    "Listbox": ("items", _TheRowsOfAListbox),
    "Treeview": ("items", _TheItemsOfATreeview),
    "Scale": ("range_value", _TheNumberOfAScale),
    "TScale": ("range_value", _TheNumberOfAScale),
    "TProgressbar": ("range_value", _TheNumberOfAProgressbar),
}


def _guarded(read, nothing=None):
    return answers_nothing_once_the_widget_is_gone(read, TclError, nothing)


def _or_nothing(read, nothing=None):
    """`_guarded`, for a read answered once rather than kept as a callable."""
    try:
        return read()
    except TclError:
        return nothing


def _ttk_state_of(widget: TkWidget):
    """How a ttk widget answers its state; None for a classic Tk widget, which has no `instate`."""
    return getattr(widget, "instate", None)


def _is_enabled(widget: TkWidget) -> bool:
    return not _is_disabled(widget)


def _is_disabled(widget: TkWidget) -> bool:
    instate = _ttk_state_of(widget)
    if instate is not None:
        return bool(instate(["disabled"]))
    if "state" not in widget.keys():  # noqa: SIM118 - Tk options, not a dict
        return False
    return str(widget.cget("state")) == "disabled"


def _cannot_be_typed_in(widget: TkWidget) -> bool:
    instate = _ttk_state_of(widget)
    if instate is not None:
        return bool(instate(["disabled"])) or bool(instate(["readonly"]))
    return str(widget.cget("state")) in ("disabled", "readonly")


def _selects_rather_than_types(widget: TkWidget) -> bool:
    instate = _ttk_state_of(widget)
    return bool(instate(["readonly"])) if instate is not None else False


def _the_values_it_offers(widget: TkWidget) -> tuple[str, ...]:
    values = widget.cget("values")
    if isinstance(values, (list, tuple)):
        return tuple(str(value) for value in values)
    return tuple(str(value) for value in widget.tk.splitlist(values))


def _holds(widget: TkWidget, wanted: str) -> bool | None:
    """Whether the widget's `-variable` holds its `wanted` option, None if it declares none."""
    variable = str(widget.cget("variable"))
    if not variable:
        return None
    try:
        return str(widget.getvar(variable)) == str(widget.cget(wanted))
    except TclError:
        # An inline variable nobody held gets collected and unset, which
        # a checkbutton displays as off.
        return False


def _holds_its_on_value(widget: TkWidget) -> bool:
    held = _holds(widget, "onvalue")
    if held is not None:
        return held
    instate = _ttk_state_of(widget)
    return bool(instate(["selected"])) if instate is not None else False


def _holds_its_own_value(widget: TkWidget) -> bool:
    return bool(_holds(widget, "value"))


def _the_ends_of(widget: TkWidget) -> tuple[float, float]:
    return (
        float(str(widget.cget("from"))),
        float(str(widget.cget("to"))),
    )


def _the_resolution_of(widget: TkWidget) -> float | None:
    if "resolution" not in widget.keys():  # noqa: SIM118 - Tk options, not a dict
        return None
    return float(str(widget.cget("resolution")))
