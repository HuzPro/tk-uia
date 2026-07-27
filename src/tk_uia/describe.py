"""What this application has told Windows about its widgets, and what it has not.

Where it plugs in: `tk_uia.describe(root)` hands this module the installation
`enable()` made, and it reads two things — the annotator's ledger, for what was
written, and the live widget tree, for what was never reached. It talks to COM
not at all and to `uiautomation` not at all; nothing here is evidence that a
client can read what was written, and the report says so in as many words.

One known and accepted blind spot, which follows from that: `forget(widget)`
clears the recorded automation id, and nothing in Win32 resets `GWLP_ID`, so a
forgotten widget goes on carrying its control id while this stops reporting it.
`forget` and `describe` are a rare pairing, and inventing state to track it
would be inventing state to describe a window this module cannot read.
"""

from __future__ import annotations

import textwrap
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, replace
from enum import Enum

from tk_uia.annotate import (
    WINDOWS_THAT_ALREADY_NAME_THEMSELVES,
    Installation,
    Ledger,
    PropId,
    TabbedWidgets,
    TkWidget,
    Written,
    Wrote,
    every_widget_under,
    words_the_widget_shows,
)
from tk_uia.roles import Role
from tk_uia.tkversion import Strategy


class Gap(Enum):
    """Something a client will not get from a widget, and why.

    The member name is the stable identity — a client-side dump comparing what
    was written against what it can read matches on it. The value is the
    sentence the report prints, held here rather than in a lookup table beside
    it so that the reason cannot fall out of step with the member.

    Every member corresponds to a caveat the README already documents. That is
    what keeps this catalogue closed: the description is those caveats applied
    to one application, and it claims nothing the README does not.
    """

    NO_ROLE_FOR_ITS_CLASS = (
        "nothing was written at all: no role is mapped for this widget class, "
        "so a client still sees whatever bare Tk gave it. Pass roles={...} to "
        "enable() to add one."
    )
    NEVER_MAPPED = (
        "nothing was written: Tk has never mapped it, so <Map> never fired. A "
        "withdrawn window, an unshown notebook tab, or a widget the geometry "
        "manager could not fit."
    )
    NOTHING_WRITTEN = (
        "mapped, its class has a role, and still nothing was written. Either "
        "the strategy in the headline above is not ANNOTATED, in which case "
        "nothing in this window was annotated at all, or the application has "
        "called forget() on it, or something here has genuinely gone wrong."
    )
    ANNOTATED_ON_A_HANDLE_IT_NO_LONGER_HAS = (
        "everything written about this widget is on a window handle it no "
        "longer has: Tk rebuilt it at the same path. Nothing has re-annotated "
        "it since, so a client reads the new window, which carries nothing."
    )
    NAME_MAY_BE_STALE = (
        "the name written here is not what the widget's -text says now. A plain "
        "config(text=...) does not re-announce; call add_acc_object(widget), or "
        "drive it from a variable and bind_text_variable it."
    )
    NO_NAME = (
        "no accessible name, so a screen reader announces the control and not "
        "what it is for. set_acc_name(widget, ...), or bind_text_variable(...)."
    )
    NO_VALUE = (
        "no accessible value. The role gives this widget a ValuePattern it did "
        "not have before, and it reads '' until something writes one -- a "
        "confident wrong answer where bare Tk gave none. bind_value_variable()."
    )
    ITEMS_NOT_IN_THE_TREE = (
        "its rows or items are not in the accessibility tree at all. MSAA child "
        "ids are not implemented here, so the widget is findable and its "
        "contents are not. A notebook is the exception: its tabs are given "
        "window handles of their own, and this is reported only for one whose "
        "strip nothing could be found on."
    )
    CANNOT_BE_PRESSED = (
        "advertises an InvokePattern and a DefaultAction that press nothing. Tk "
        "buttons are owner-drawn, so the proxy's synthesised BM_CLICK goes into "
        "the void. Clients must click."
    )
    NAMED_BY_ITS_TITLE = (
        "a window, and `wm title` already gives it a correct accessible name. "
        "Overriding it would break resolving the window by its title, which is "
        "where every other query starts."
    )


# The one reason in the catalogue that is not a fault to fix. It is reported
# rather than left out because a description that silently dropped every window
# would read as having lost them.
ON_PURPOSE: frozenset[Gap] = frozenset({Gap.NAMED_BY_ITS_TITLE})


@dataclass(frozen=True)
class WidgetDescription:
    """One widget, and what tk-uia believes it wrote about it."""

    path: str
    tk_class: str
    role: Role | None
    name: str | None
    value: str | None
    automation_id: int | None
    shows_now: str | None
    kept_in_step: tuple[PropId, ...]
    also_written: Mapping[PropId, str | int]
    gaps: tuple[Gap, ...]
    # A notebook's tabs, which are not widgets and appear nowhere else in this
    # report — they have window handles of their own and nothing to walk to.
    tabs: tuple[str, ...] = ()


@dataclass(frozen=True)
class Description:
    """What tk-uia believes it wrote about every widget under one root."""

    strategy: Strategy
    root: str
    widgets: tuple[WidgetDescription, ...]
    orphans: tuple[str, ...]

    def __str__(self) -> str:
        return _report(self)


def describe(root: TkWidget, installation: Installation) -> Description:
    """Say what this application has told Windows about the widgets under `root`."""
    # Before the walk asks its first widget anything: describing crosses into
    # the Tcl interpreter six ways per widget, and doing that from a foreign
    # thread corrupts it quietly rather than raising.
    installation.owner.refuse_any_other_caller()
    annotator = installation.annotator
    widgets = tuple(
        _described(widget, annotator.ledger, annotator.roles, installation.tabs)
        for widget in _the_root_and_everything_under_it(root)
    )
    return Description(
        installation.strategy,
        str(root),
        widgets,
        _annotations_this_walk_never_reached(annotator.ledger, widgets),
    )


def _annotations_this_walk_never_reached(
    ledger: Ledger, widgets: tuple[WidgetDescription, ...]
) -> tuple[str, ...]:
    described = {widget.path for widget in widgets}
    return tuple(path for path in ledger.paths() if path not in described)


def _report(description: Description) -> str:
    """Render a description as the text an author reads. Not a method: see the module."""
    return "\n".join(
        [
            *_the_headline(description),
            "",
            *_the_table(description.widgets),
            *_the_reasons(description.widgets),
            *_whatever_this_walk_never_reached(description),
            "",
            _THE_CAVEAT_THIS_REPORT_CARRIES,
        ]
    )


def _the_headline(description: Description) -> Iterator[str]:
    # Imported here rather than at module scope, where it would be a cycle: the
    # package imports this module in order to re-export `describe`.
    from tk_uia import __version__

    yield f"tk-uia {__version__} -- {_WHAT_THIS_IS}"
    yield from _how_it_went(description)


def _how_it_went(description: Description) -> Iterator[str]:
    written_to = sum(1 for widget in description.widgets if widget.role is not None)
    how_many = len(description.widgets)
    if description.strategy is not Strategy.ANNOTATED:
        # First, and before a single row: a window where the gate stood down
        # renders as a page of blanks, and an author who read that as a clean
        # bill of health would be exactly wrong.
        yield textwrap.fill(
            f"enable() reported {description.strategy.name}, so nothing here was "
            f"annotated: every one of the {how_many} widgets under "
            f"{description.root} is exactly as bare Tk left it.",
            width=_HOW_WIDE_THE_REASONS_READ,
        )
        return
    yield (
        f"enable() reported {description.strategy.name}. {how_many} widgets under "
        f"{description.root}: {written_to} written to, {how_many - written_to} not."
    )


def _the_reasons(widgets: tuple[WidgetDescription, ...]) -> Iterator[str]:
    carrying = _the_widgets_behind_each_gap(widgets)
    yield from _a_section(
        _WHAT_A_CLIENT_WILL_NOT_GET,
        {gap: found for gap, found in carrying.items() if gap not in ON_PURPOSE},
    )
    yield from _a_section(
        _LEFT_ALONE_ON_PURPOSE,
        {gap: found for gap, found in carrying.items() if gap in ON_PURPOSE},
    )


def _whatever_this_walk_never_reached(description: Description) -> Iterator[str]:
    if not description.orphans:
        return
    yield ""
    yield _ANNOTATED_AND_NOT_UNDER_THIS_ROOT
    yield ""
    yield textwrap.fill(
        f"annotations are in place for these, and no widget under "
        f"{description.root} answers to them. Either this is not the "
        "application's real root, or the widget went away by a route that never "
        "reached forget().",
        width=_HOW_WIDE_THE_REASONS_READ,
        initial_indent=_UNDER_THE_ROW,
        subsequent_indent=_UNDER_THE_ROW,
    )
    for path in description.orphans:
        yield f"{_UNDER_THE_REASON}{path}"


def _the_widgets_behind_each_gap(
    widgets: tuple[WidgetDescription, ...],
) -> dict[Gap, list[WidgetDescription]]:
    # Keyed by `Gap` in declaration order, which is the reading order: total
    # failures first, then wrong answers, then missing ones, then the limits
    # that are inherent. Top to bottom it goes from broken to how it is.
    behind = {gap: [w for w in widgets if gap in w.gaps] for gap in Gap}
    return {gap: found for gap, found in behind.items() if found}


def _a_section(
    heading: str, carrying: dict[Gap, list[WidgetDescription]]
) -> Iterator[str]:
    if not carrying:
        return
    yield ""
    yield heading
    for gap, found in carrying.items():
        yield ""
        yield f"{_UNDER_THE_HEADING}{gap.name}  ({len(found)})"
        yield textwrap.fill(
            gap.value,
            width=_HOW_WIDE_THE_REASONS_READ,
            initial_indent=_UNDER_THE_ROW,
            subsequent_indent=_UNDER_THE_ROW,
        )
        for widget in found:
            yield (
                f"{_UNDER_THE_REASON}{widget.path}  ({widget.tk_class})"
                f"{_and_what_the_widget_shows_now(gap, widget)}"
            )


def _and_what_the_widget_shows_now(gap: Gap, widget: WidgetDescription) -> str:
    # Only worth saying where the two disagreeing is the complaint: a reader
    # deciding whether a name went stale needs both halves on one line.
    if gap is not Gap.NAME_MAY_BE_STALE:
        return ""
    return f"   -text now says {widget.shows_now!r}"


def _the_table(widgets: tuple[WidgetDescription, ...]) -> Iterator[str]:
    rows = [_the_cells_of(widget) for widget in widgets]
    # Sized to content and never truncated: a shortened Tk path cannot be
    # grepped for, and finding the widget in your own source is the point.
    widths = [len(max(column, key=len)) for column in zip(_COLUMNS, *rows)]
    yield _laid_out(_COLUMNS, widths)
    yield _laid_out(tuple("-" * width for width in widths), widths)
    for widget, cells in zip(widgets, rows):
        yield _laid_out(cells, widths)
        yield from _whatever_the_row_had_no_room_for(widget)


def _the_cells_of(widget: WidgetDescription) -> tuple[str, ...]:
    return (
        widget.path,
        widget.tk_class,
        _NOTHING
        if widget.role is None
        else f"{widget.role.name} ({widget.role.value})",
        _as_it_reads(widget.name),
        _as_it_reads(widget.value),
        _NOTHING if widget.automation_id is None else str(widget.automation_id),
    )


def _whatever_the_row_had_no_room_for(widget: WidgetDescription) -> Iterator[str]:
    if widget.kept_in_step:
        following = ", ".join(prop.name.lower() for prop in widget.kept_in_step)
        yield f"{_UNDER_THE_ROW}kept in step with a variable: {following}"
    if widget.tabs:
        yield f"{_UNDER_THE_ROW}tabs a client can reach: {', '.join(widget.tabs)}"
    if widget.also_written:
        also = ", ".join(
            f"{prop.name}={value!r}" for prop, value in widget.also_written.items()
        )
        yield f"{_UNDER_THE_ROW}also written: {also}"


def _laid_out(cells: tuple[str, ...], widths: list[int]) -> str:
    return _BETWEEN_COLUMNS.join(
        cell.ljust(width) for cell, width in zip(cells, widths)
    ).rstrip()


def _as_it_reads(written: str | None) -> str:
    # Quoted rather than bare, so that a name which is empty, or which is all
    # spaces, is visibly different from one that was never written.
    return _NOTHING if written is None else repr(written)


def _the_root_and_everything_under_it(root: TkWidget) -> Iterator[TkWidget]:
    # The root is described alongside its children rather than treated as a
    # frame around them: it is a widget an author put on screen, and one whose
    # accessible name comes from somewhere else entirely.
    yield root
    yield from every_widget_under(root)


@dataclass(frozen=True)
class _AsTheWalkFoundIt:
    """One widget, as the trip round the tree left it: asked once, passed on."""

    widget: TkWidget
    path: str
    tk_class: str
    shows_now: str | None


def _described(
    widget: TkWidget,
    ledger: Ledger,
    roles: Mapping[str, Role],
    tabs: TabbedWidgets,
) -> WidgetDescription:
    found = _AsTheWalkFoundIt(
        widget=widget,
        path=str(widget),
        tk_class=widget.winfo_class(),
        shows_now=words_the_widget_shows(widget),
    )
    hwnd = ledger.handle_of(found.path)
    if hwnd is None:
        return _nothing_was_written_about(found, roles)
    return _what_was_written_about(found, hwnd, ledger, tabs)


def _nothing_was_written_about(
    found: _AsTheWalkFoundIt, roles: Mapping[str, Role]
) -> WidgetDescription:
    return WidgetDescription(
        path=found.path,
        tk_class=found.tk_class,
        role=None,
        name=None,
        value=None,
        automation_id=None,
        shows_now=found.shows_now,
        kept_in_step=(),
        also_written={},
        gaps=_why_nothing_was_written(found, roles),
    )


def _what_was_written_about(
    found: _AsTheWalkFoundIt, hwnd: int, ledger: Ledger, tabs: TabbedWidgets
) -> WidgetDescription:
    said = ledger.about(hwnd)
    carrying = tuple(str(tab.text) for tab in tabs.on(found.path))
    role = None if PropId.ROLE not in said else Role(said[PropId.ROLE].value)
    written = WidgetDescription(
        path=found.path,
        tk_class=found.tk_class,
        role=role,
        name=_whatever_was_written(said, PropId.NAME),
        value=_whatever_was_written(said, PropId.VALUE),
        automation_id=ledger.automation_id_of(hwnd),
        shows_now=found.shows_now,
        kept_in_step=_whatever_a_variable_is_keeping_true(said),
        also_written=_whatever_the_columns_have_no_room_for(said),
        gaps=(),
        tabs=carrying,
    )
    if found.widget.winfo_id() != hwnd:
        # Asked once the ledger has answered, and reported instead of every
        # other reason rather than alongside them: each of those is true of a
        # window handle nobody is reading any more.
        return replace(written, gaps=(Gap.ANNOTATED_ON_A_HANDLE_IT_NO_LONGER_HAS,))
    return replace(written, gaps=_what_is_missing_from(written, said))


def _whatever_the_columns_have_no_room_for(
    said: Mapping[PropId, Written],
) -> Mapping[PropId, str | int]:
    return {
        prop: written.value
        for prop, written in said.items()
        if prop not in _THE_PROPERTIES_THE_TABLE_HAS_A_COLUMN_FOR
    }


def _whatever_a_variable_is_keeping_true(
    said: Mapping[PropId, Written],
) -> tuple[PropId, ...]:
    return tuple(
        prop for prop, written in said.items() if written.source is Wrote.KEPT_IN_STEP
    )


def _whatever_was_written(said: Mapping[PropId, Written], prop: PropId) -> str | None:
    written = said.get(prop)
    return None if written is None else str(written.value)


def _what_is_missing_from(
    written: WidgetDescription, said: Mapping[PropId, Written]
) -> tuple[Gap, ...]:
    missing = []
    if _the_name_no_longer_matches_the_caption_it_came_from(written, said):
        missing.append(Gap.NAME_MAY_BE_STALE)
    if written.name is None and written.role not in _ROLES_NOBODY_ANNOUNCES:
        missing.append(Gap.NO_NAME)
    if written.role in _ROLES_A_CLIENT_WILL_ASK_THE_VALUE_OF and written.value is None:
        missing.append(Gap.NO_VALUE)
    if written.role in _ROLES_WHOSE_CONTENTS_ARE_A_WIDGET_OF_THEIR_OWN:
        missing.append(Gap.ITEMS_NOT_IN_THE_TREE)
    # A notebook whose tabs were found and given handles is not hollow. One
    # whose strip yielded nothing still is, and saying so is the whole point:
    # the scan can come up empty on a notebook Tk has not laid out yet.
    if written.role is Role.PAGE_TAB_LIST and not written.tabs:
        missing.append(Gap.ITEMS_NOT_IN_THE_TREE)
    if written.role is Role.PUSH_BUTTON:
        missing.append(Gap.CANNOT_BE_PRESSED)
    return tuple(missing)


def _the_name_no_longer_matches_the_caption_it_came_from(
    written: WidgetDescription, said: Mapping[PropId, Written]
) -> bool:
    name, shows_now = written.name, written.shows_now
    if name is None or shows_now is None:
        return False
    # Only a name this package read off the widget can have gone stale. A name
    # the application chose over a shorter caption — `Button(text="OK")` named
    # "Confirm order", which the README encourages — is meant to differ, and
    # calling it stale is how a diagnostic teaches its reader to ignore it.
    return said[PropId.NAME].source is Wrote.INFERRED and name != shows_now


_COLUMNS = ("WIDGET", "CLASS", "ROLE", "NAME", "VALUE", "ID")
_BETWEEN_COLUMNS = "  "
_UNDER_THE_HEADING = "  "
_UNDER_THE_ROW = "    "
_UNDER_THE_REASON = "      "
_NOTHING = "-"

_WHAT_THIS_IS = "what this application has told Windows it is showing"
_WHAT_A_CLIENT_WILL_NOT_GET = "WHAT A CLIENT WILL NOT GET, AND WHY"
_LEFT_ALONE_ON_PURPOSE = "LEFT ALONE ON PURPOSE"
_ANNOTATED_AND_NOT_UNDER_THIS_ROOT = "ANNOTATED, AND NOT UNDER THIS ROOT"

# Narrower than the table, which sizes itself to the longest Tk path: the table
# is scanned and the reasons are read, and prose does not read at 200 columns.
_HOW_WIDE_THE_REASONS_READ = 74

# The last word, always, and there is a spec that fails if it ever goes: every
# row above it is what this package believes it wrote, and the difference
# between that and what a client reads is the whole class of bug it has.
_THE_CAVEAT_THIS_REPORT_CARRIES = textwrap.fill(
    "Everything above is what tk-uia believes it wrote. It is not evidence "
    "that a client can read it: IAccPropServices accepts a write to a window "
    "handle nobody owns, answers S_OK, and changes nothing. Reading the same "
    "window back from another process is the only thing that proves the bridge "
    "carried it.",
    width=_HOW_WIDE_THE_REASONS_READ,
)

# Everything else a widget can be annotated with — description, help, default
# action and state — goes on an indented sub-line instead, so that the table
# stays narrow enough for the paths in it never to need truncating.
_THE_PROPERTIES_THE_TABLE_HAS_A_COLUMN_FOR = frozenset(
    {PropId.ROLE, PropId.NAME, PropId.VALUE}
)

# The roles a missing name is not worth reporting for. A frame never has one and
# does not need one, and flagging every container in a window would bury the one
# entry that genuinely needs `set_acc_name` under a list nobody will read.
_ROLES_NOBODY_ANNOUNCES = frozenset({Role.GROUPING, Role.SCROLL_BAR})

# The roles the MSAA-to-UIA bridge hands a ValuePattern to. Annotating one of
# these is what turns Tk's anonymous pane into a control a client will ask the
# contents of — and it answers `''` until an application says otherwise.
_ROLES_A_CLIENT_WILL_ASK_THE_VALUE_OF = frozenset({Role.TEXT, Role.COMBO_BOX})

# The roles whose whole point is what is inside them. Tk gives one window handle
# per widget and annotation works on handles, so the rows, items and tabs need
# MSAA's child-id model — a different piece of machinery, and not this one.
_ROLES_WHOSE_CONTENTS_ARE_A_WIDGET_OF_THEIR_OWN = frozenset({Role.LIST, Role.OUTLINE})


def _why_nothing_was_written(
    found: _AsTheWalkFoundIt, roles: Mapping[str, Role]
) -> tuple[Gap, ...]:
    # Ordered, and the order is the answer: a widget is routinely both role-less
    # and never mapped — every `tk.Menu` is — and "no role for class 'Menu'" is
    # what a reader can act on where "never mapped" is trivia.
    if found.tk_class in WINDOWS_THAT_ALREADY_NAME_THEMSELVES:
        return (Gap.NAMED_BY_ITS_TITLE,)
    if found.tk_class not in roles:
        return (Gap.NO_ROLE_FOR_ITS_CLASS,)
    if not found.widget.winfo_ismapped():
        return (Gap.NEVER_MAPPED,)
    return (Gap.NOTHING_WRITTEN,)
