"""What this application has told Windows about its widgets, and what it has not.

`tk_uia.describe(root)` reads the annotator's ledger for what was written and
the live widget tree for what was never reached. It touches neither COM nor
`uiautomation`, so nothing here is evidence that a client can read any of it.
"""

from __future__ import annotations

import textwrap
from collections import Counter
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, replace
from enum import Enum

from tk_uia.annotate import (
    AnswersForItself,
    Installation,
    Ledger,
    PropId,
    TabbedWidgets,
    TkWidget,
    Written,
    Wrote,
    every_widget_under,
    is_a_window,
    words_the_widget_shows,
)
from tk_uia.patterns import Pattern
from tk_uia.roles import Role
from tk_uia.tkversion import Strategy


class Gap(Enum):
    """Something a client will not get from a widget, and why.

    The member name is the stable identity a client-side dump matches on; the
    value is the sentence the report prints.
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
    UNMAPPED_SINCE_ANNOTATED = (
        "written, and not on the screen now. Everything below is still on the "
        "widget's window and still correct, and a client can read none of it: "
        "UI Automation does not list an unmapped window. It comes back on its "
        "own when Tk maps the widget -- an unselected notebook tab is the "
        "everyday case, and nothing needs re-annotating."
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
    NAME_NOT_UNIQUE = (
        "shares its role and its accessible name with another widget in the "
        "same window, so a client asking for it reaches one of them at random "
        "and a screen reader announces both of them the same way. Qualify the "
        "caption -- 'Browse... for Export Folder' -- with set_acc_name, or let "
        "infer_names_from_layout(root) qualify the generic ones for a whole "
        "window at once."
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
        "its rows or items are not in the accessibility tree, so the widget "
        "is findable and its contents are not. A listbox or treeview "
        "answering UIA for itself serves its rows and is not reported here; "
        "annotation alone never serves them. A notebook is reported only "
        "when nothing could be found on its strip."
    )
    CANNOT_BE_PRESSED = (
        "a press through the tree does nothing here. Whatever the MSAA proxy "
        "offers for it (a DefaultAction, and on a real button class an Invoke) "
        "is a synthesised BM_CLICK an owner-drawn Tk widget ignores. A wired "
        "class with a -command answers UIA itself and genuinely presses; a "
        "button with no command has nothing to run, and a role assigned by "
        "hand brings no working pattern yet, so a client must click this one."
    )
    LEFT_TO_THE_PROXY = (
        "the application asked for this widget to be left to the MSAA proxy, so "
        "every pattern a client finds on it advertises and does nothing; the "
        "annotations above are all it has."
    )
    MENUS_ARE_NATIVE = (
        "a menu. Tk builds menubars and popup menus out of native Windows "
        "menus, which are accessible on their own: measured, a bare window "
        "already shows a MenuBarControl with named items. Nothing needs "
        "writing here, and nothing is."
    )
    NAMED_BY_ITS_TITLE = (
        "a window, and `wm title` already gives it a correct accessible name. "
        "Overriding it would break resolving the window by its title, which is "
        "where every other query starts."
    )


ON_PURPOSE: frozenset[Gap] = frozenset({Gap.NAMED_BY_ITS_TITLE, Gap.MENUS_ARE_NATIVE})


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
    # Not widgets, so they appear nowhere else in this report and there is
    # nothing to walk to.
    tabs: tuple[str, ...] = ()
    is_window: bool = False
    patterns: tuple[Pattern, ...] = ()
    answers_rows: bool = False


@dataclass(frozen=True)
class Description:
    """What tk-uia believes it wrote about every widget under one root."""

    strategy: Strategy
    root: str
    widgets: tuple[WidgetDescription, ...]
    orphans: tuple[str, ...]
    provider_trouble: tuple[str, ...] = ()
    providers_stood_down_because: str | None = None

    def __str__(self) -> str:
        return _report(self)


def describe(root: TkWidget, installation: Installation) -> Description:
    """Say what this application has told Windows about the widgets under `root`."""
    # Before anything crosses into the Tcl interpreter, which a foreign thread
    # corrupts quietly.
    installation.owner.refuse_any_other_caller()
    annotator = installation.annotator
    widgets = _and_whichever_of_them_a_client_cannot_tell_apart(
        tuple(
            _described(widget, annotator.ledger, annotator.roles, installation.tabs)
            for widget in _the_root_and_everything_under_it(root)
        )
    )
    widgets = tuple(
        _with_what_the_provider_answers(widget, installation.providers.ledger)
        for widget in widgets
    )
    return Description(
        installation.strategy,
        str(root),
        widgets,
        _annotations_this_walk_never_reached(annotator.ledger, widgets),
        installation.trouble.so_far(),
        installation.providers_stood_down_because,
    )


def _with_what_the_provider_answers(
    widget: WidgetDescription, answers: AnswersForItself
) -> WidgetDescription:
    """Fold what the provider layer says about a path into its row."""
    patterns = tuple(answers.patterns_on(widget.path))
    rows = answers.answers_rows_on(widget.path)
    cured = _whatever_answering_for_itself_cures(patterns, rows)
    gaps = tuple(gap for gap in widget.gaps if gap not in cured)
    if answers.is_left_to_the_proxy(widget.path):
        gaps = (*gaps, Gap.LEFT_TO_THE_PROXY)
    if patterns == widget.patterns and gaps == widget.gaps and not rows:
        return widget
    return replace(widget, patterns=patterns, gaps=gaps, answers_rows=rows)


def _whatever_answering_for_itself_cures(
    patterns: tuple[Pattern, ...], answers_rows: bool
) -> set[Gap]:
    """The gaps a real provider closes: a live pattern outranks the proxy's dead one."""
    cured = {
        _THE_GAP_EACH_PATTERN_CURES[pattern]
        for pattern in patterns
        if pattern in _THE_GAP_EACH_PATTERN_CURES
    }
    if answers_rows:
        cured.add(Gap.ITEMS_NOT_IN_THE_TREE)
    return cured


def _and_whichever_of_them_a_client_cannot_tell_apart(
    widgets: tuple[WidgetDescription, ...],
) -> tuple[WidgetDescription, ...]:
    """Add NAME_NOT_UNIQUE to every widget another widget answers to as well.

    A pass of its own because nothing about a widget on its own says this: both
    "Browse..." buttons are correct, and the fault is that they are the same.
    """
    windows = _the_windows_a_client_scopes_a_query_to(widgets)
    asked_for = tuple(
        _how_a_client_would_ask_for(widget, windows) for widget in widgets
    )
    shared = _the_queries_more_than_one_widget_answers_to(asked_for)
    return tuple(
        _carrying_the_ambiguity_as_well(widget) if query in shared else widget
        for widget, query in zip(widgets, asked_for)
    )


def _carrying_the_ambiguity_as_well(widget: WidgetDescription) -> WidgetDescription:
    # Appended, not replacing: two buttons a client cannot tell apart are still
    # two buttons it cannot press.
    return replace(widget, gaps=(*widget.gaps, Gap.NAME_NOT_UNIQUE))


@dataclass(frozen=True)
class _WhatAClientWouldAskFor:
    """A window, a control type and a name: the whole of an ordinary query.

    The window is part of it because a client scopes a query to one, so a
    dialog's "Confirm" and the main window's are not a collision.
    """

    window: str
    role: Role
    name: str


def _how_a_client_would_ask_for(
    widget: WidgetDescription, windows: tuple[str, ...]
) -> _WhatAClientWouldAskFor | None:
    # A widget with no role or no name cannot be asked for at all, and is
    # already reported as whichever of those it is missing.
    if widget.role is None or widget.name is None:
        return None
    return _WhatAClientWouldAskFor(
        _the_window_holding(widget.path, windows), widget.role, widget.name
    )


def _the_queries_more_than_one_widget_answers_to(
    asked_for: tuple[_WhatAClientWouldAskFor | None, ...],
) -> frozenset[_WhatAClientWouldAskFor]:
    return frozenset(
        query
        for query, how_many in Counter(asked_for).items()
        if query is not None and how_many > _ONE_WIDGET_IS_NEVER_AMBIGUOUS
    )


def _the_windows_a_client_scopes_a_query_to(
    widgets: tuple[WidgetDescription, ...],
) -> tuple[str, ...]:
    return tuple(widget.path for widget in widgets if widget.is_window)


def _the_window_holding(path: str, windows: tuple[str, ...]) -> str:
    # The nearest one, so a dialog opened from a dialog scopes to itself rather
    # than to the window behind it.
    return max(
        (window for window in windows if _is_inside(path, window)),
        key=len,
        default=_WHATEVER_WINDOW_THIS_WALK_STARTED_IN,
    )


def _is_inside(path: str, window: str) -> bool:
    # On the segment boundary and not on the characters: `.!toplevel22.!button`
    # begins with the whole of `.!toplevel2` and is a different window.
    within = (
        window
        if window.endswith(_HOW_TK_SEPARATES_A_PATH)
        else window + _HOW_TK_SEPARATES_A_PATH
    )
    return path != window and path.startswith(within)


def _annotations_this_walk_never_reached(
    ledger: Ledger, widgets: tuple[WidgetDescription, ...]
) -> tuple[str, ...]:
    described = {widget.path for widget in widgets}
    return tuple(path for path in ledger.paths() if path not in described)


def _report(description: Description) -> str:
    """Render a description as the text an author reads."""
    return "\n".join(
        [
            *_the_headline(description),
            "",
            *_the_table(description.widgets),
            *_the_reasons(description.widgets),
            *_whatever_this_walk_never_reached(description),
            *_what_the_provider_machinery_swallowed(description),
            "",
            _THE_CAVEAT_THIS_REPORT_CARRIES,
        ]
    )


def _the_headline(description: Description) -> Iterator[str]:
    # Imported here rather than at module scope, where it would be a cycle: the
    # package imports this module to re-export `describe`.
    from tk_uia import __version__

    yield f"tk-uia {__version__} -- {_WHAT_THIS_IS}"
    yield from _how_it_went(description)


def _how_it_went(description: Description) -> Iterator[str]:
    written_to = sum(1 for widget in description.widgets if widget.role is not None)
    how_many = len(description.widgets)
    if not description.strategy.annotates:
        # Before a single row: a window where the gate stood down renders as a
        # page of blanks, which reads as a clean bill of health.
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
    if description.strategy is Strategy.PROVIDED:
        answering = sum(1 for widget in description.widgets if widget.patterns)
        yield (
            f"{answering} of them answer UIA themselves with working patterns; "
            "the rest are typed and named through the proxy."
        )
    if description.providers_stood_down_because is not None:
        yield textwrap.fill(
            "No widget answers UIA itself: "
            f"{description.providers_stood_down_because}.",
            width=_HOW_WIDE_THE_REASONS_READ,
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


def _what_the_provider_machinery_swallowed(description: Description) -> Iterator[str]:
    if not description.provider_trouble:
        return
    yield ""
    yield _WHAT_THE_CALLBACKS_SWALLOWED
    yield ""
    yield textwrap.fill(
        "the window procedure and the COM callbacks are forbidden to raise, so "
        "whatever failed inside them landed here instead of anywhere louder.",
        width=_HOW_WIDE_THE_REASONS_READ,
        initial_indent=_UNDER_THE_ROW,
        subsequent_indent=_UNDER_THE_ROW,
    )
    for line in description.provider_trouble:
        yield f"{_UNDER_THE_REASON}{line}"


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
    # Declaration order is the reading order: total failures first, then wrong
    # answers, then missing ones, then the limits that are inherent.
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
    if gap is not Gap.NAME_MAY_BE_STALE:
        return ""
    return f"   -text now says {widget.shows_now!r}"


def _the_table(widgets: tuple[WidgetDescription, ...]) -> Iterator[str]:
    rows = [_the_cells_of(widget) for widget in widgets]
    # Never truncated: a shortened Tk path cannot be grepped for.
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
    if widget.patterns:
        working = ", ".join(
            pattern.name.replace("_", " ").title() for pattern in widget.patterns
        )
        yield f"{_UNDER_THE_ROW}answers UIA itself, with working: {working}"
    if widget.answers_rows:
        yield f"{_UNDER_THE_ROW}its rows answer UIA themselves"
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
    # Quoted, so a name that is empty or all spaces is visibly different from
    # one that was never written.
    return _NOTHING if written is None else repr(written)


def _the_root_and_everything_under_it(root: TkWidget) -> Iterator[TkWidget]:
    yield root
    yield from every_widget_under(root)


@dataclass(frozen=True)
class _AsTheWalkFoundIt:
    """One widget, as the trip round the tree left it: asked once, passed on."""

    widget: TkWidget
    path: str
    tk_class: str
    is_window: bool
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
        is_window=is_a_window(widget),
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
        is_window=found.is_window,
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
        is_window=found.is_window,
        kept_in_step=_whatever_a_variable_is_keeping_true(said),
        also_written=_whatever_the_columns_have_no_room_for(said),
        gaps=(),
        tabs=carrying,
    )
    if not found.widget.winfo_ismapped():
        # Instead of every per-property reason, which has the opposite fix.
        return replace(written, gaps=(Gap.UNMAPPED_SINCE_ANNOTATED,))
    if found.widget.winfo_id() != hwnd:
        # Instead of every other reason, each of which is true of a window
        # handle nobody is reading any more.
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
    # A notebook given handles is not hollow; one whose strip yielded nothing
    # still is, which the scan reports for a notebook Tk has not laid out yet.
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
    # Only a name this package read off the widget can have gone stale: one the
    # application chose over a shorter caption is meant to differ.
    return said[PropId.NAME].source is Wrote.INFERRED and name != shows_now


_COLUMNS = ("WIDGET", "CLASS", "ROLE", "NAME", "VALUE", "ID")
_BETWEEN_COLUMNS = "  "
_UNDER_THE_HEADING = "  "
_UNDER_THE_ROW = "    "
_UNDER_THE_REASON = "      "
_NOTHING = "-"

# `.`, then `.!toplevel`, then `.!toplevel.!button`.
_HOW_TK_SEPARATES_A_PATH = "."

# What a walk that began below every toplevel scopes to, shared by everything
# it reached.
_WHATEVER_WINDOW_THIS_WALK_STARTED_IN = ""

_ONE_WIDGET_IS_NEVER_AMBIGUOUS = 1

_WHAT_THIS_IS = "what this application has told Windows it is showing"
_WHAT_A_CLIENT_WILL_NOT_GET = "WHAT A CLIENT WILL NOT GET, AND WHY"
_LEFT_ALONE_ON_PURPOSE = "LEFT ALONE ON PURPOSE"
_ANNOTATED_AND_NOT_UNDER_THIS_ROOT = "ANNOTATED, AND NOT UNDER THIS ROOT"
_WHAT_THE_CALLBACKS_SWALLOWED = "WHAT THE PROVIDER MACHINERY SWALLOWED"

# Narrower than the table, which sizes itself to the longest Tk path: prose
# does not read at 200 columns.
_HOW_WIDE_THE_REASONS_READ = 74

# The last word, always, and there is a spec that fails if it ever goes.
_THE_CAVEAT_THIS_REPORT_CARRIES = textwrap.fill(
    "Everything above is what tk-uia believes it wrote. It is not evidence "
    "that a client can read it: IAccPropServices accepts a write to a window "
    "handle nobody owns, answers S_OK, and changes nothing. Reading the same "
    "window back from another process is the only thing that proves the bridge "
    "carried it.",
    width=_HOW_WIDE_THE_REASONS_READ,
)

_THE_PROPERTIES_THE_TABLE_HAS_A_COLUMN_FOR = frozenset(
    {PropId.ROLE, PropId.NAME, PropId.VALUE}
)

# The roles a missing name is not worth reporting for: flagging every container
# would bury the one entry that genuinely needs `set_acc_name`.
# Decoration included: naming a separator or a sizegrip makes a screen reader
# read out furniture, which accessibility guidance says not to do.
_ROLES_NOBODY_ANNOUNCES = frozenset(
    {Role.GROUPING, Role.SCROLL_BAR, Role.SEPARATOR, Role.GRIP}
)

# The roles the MSAA-to-UIA bridge hands a ValuePattern to, which answers `''`
# until the application says otherwise (COVERAGE.md, `patterns` column).
# `ttk.Progressbar`'s stays `''` even after its own `-value` moves.
_ROLES_A_CLIENT_WILL_ASK_THE_VALUE_OF = frozenset(
    {Role.TEXT, Role.COMBO_BOX, Role.SPIN_BUTTON, Role.PROGRESS_BAR}
)

# Rows and items have no window handle of their own; they would need MSAA's
# child-id model, which annotation on handles cannot reach.
_ROLES_WHOSE_CONTENTS_ARE_A_WIDGET_OF_THEIR_OWN = frozenset({Role.LIST, Role.OUTLINE})

# Each gap asserted from the role table alone, and the working pattern that
# takes it back. `_what_is_missing_from` reads the role; this reads the provider.
_THE_GAP_EACH_PATTERN_CURES: Mapping[Pattern, Gap] = {
    Pattern.INVOKE: Gap.CANNOT_BE_PRESSED,
    Pattern.VALUE: Gap.NO_VALUE,
}


def _why_nothing_was_written(
    found: _AsTheWalkFoundIt, roles: Mapping[str, Role]
) -> tuple[Gap, ...]:
    # The order is the answer: a widget is routinely both role-less and never
    # mapped, as every `tk.Menu` is, and only the first is worth acting on.
    if found.is_window:
        return (Gap.NAMED_BY_ITS_TITLE,)
    if found.tk_class == "Menu":
        return (Gap.MENUS_ARE_NATIVE,)
    if found.tk_class not in roles:
        return (Gap.NO_ROLE_FOR_ITS_CLASS,)
    if not found.widget.winfo_ismapped():
        return (Gap.NEVER_MAPPED,)
    return (Gap.NOTHING_WRITTEN,)
