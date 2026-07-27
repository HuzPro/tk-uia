"""Behavioral spec for the description, against a real Tk and a real client.

Two things the doubles cannot reach. The first is contact with real tkinter:
`keys()` really returns a list, `cget` really hands back a Tcl object, and
`winfo_children()` on a root really includes the toplevels and menus Tk put
there. A description specified only against `FakeWidget` would be specified
against a widget somebody wrote to make it pass.

The second is the point of the feature. The description says what tk-uia
*believes* it wrote, and every failure mode this package has returns `S_OK` and
does nothing. So the second spec reads the description out of a live
application, reads the same window back through UI Automation from this process,
and checks the claim against what a client can actually see.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

from tests.conftest import RunningApp, the_widgets_the_application_shows
from tests.fixture_apps.annotated_app import (
    NEW_TASK,
    NEW_TASK_NUMBER,
    THE_NAMES_IT_CLAIMS,
    THE_REPORT,
    WRITE_THE_DESCRIPTION,
)

# The application checks for a command a few times a second; anything near this
# means it stopped checking.
_A_REACTION_TIMEOUT_SECONDS = 5.0
_HOW_OFTEN_TO_LOOK_AGAIN_SECONDS = 0.1

_BETWEEN_A_PATH_AND_ITS_NAME = "\t"

pytestmark = [
    pytest.mark.gui,
    pytest.mark.skipif(
        sys.platform != "win32",
        reason="MSAA and UI Automation are Windows APIs",
    ),
]


def test_describing_a_real_tk_window_names_its_widgets_by_their_real_tk_classes_and_paths(
    annotated_app: RunningApp,
) -> None:
    # Given the fixture application, which annotated itself at startup
    annotated_app.ask_for(WRITE_THE_DESCRIPTION)

    # When it is asked to say what it has told Windows, from inside its own
    # process, where the widgets and the ledger both are
    report = _whatever_the_application_wrote(annotated_app, THE_REPORT)

    # Then the widgets are named by their real Tk classes and their real paths
    assert " SparklineChart " in report, (
        f"no widget in the report is a real SparklineChart, so this ran against "
        f"something other than a live Tk:\n{report}"
    )

    # And the one class the role table has never heard of is reported as
    # carrying nothing, with the reason
    assert "NO_ROLE_FOR_ITS_CLASS" in report, (
        f"the unknown_class_widget this application deliberately leaves unannotated is not "
        f"reported as unwritten:\n{report}"
    )

    # And the button carries both the name it was given and the number the
    # application chose, which is what a suite pins its locators to
    button_row = _the_row_carrying(report, NEW_TASK)

    assert str(NEW_TASK_NUMBER) in button_row, (
        f"the button's row does not carry its automation id: {button_row!r}"
    )


def test_every_name_the_description_says_it_wrote_is_a_name_a_client_in_another_process_can_read(
    annotated_app: RunningApp,
) -> None:
    # Given the description the application wrote about itself, listing every
    # widget it believes it named
    annotated_app.ask_for(WRITE_THE_DESCRIPTION)
    claimed = _the_names_the_description_claims(annotated_app)

    assert claimed, "the application claims to have named nothing at all"

    # When the same window is read back through UI Automation from here
    readable = {
        control.Name
        for control in the_widgets_the_application_shows(annotated_app.window)
    }

    # Then every name the description claims is one a client really sees. This
    # is the only thing that catches the failure this package is built around:
    # `IAccPropServices` accepts a write to a window handle nobody owns, answers
    # `S_OK`, and changes nothing, after which the description goes on reporting
    # a name no client will ever read.
    unread = {path: name for path, name in claimed.items() if name not in readable}

    assert unread == {}, (
        f"the description claims names a client cannot read: {unread}. Either "
        f"the annotation returned S_OK and went nowhere, or the description is "
        f"reporting something that was never written. A client sees {readable}"
    )


def _the_names_the_description_claims(app: RunningApp) -> dict[str, str]:
    written = _whatever_the_application_wrote(app, THE_NAMES_IT_CLAIMS)
    return dict(
        line.split(_BETWEEN_A_PATH_AND_ITS_NAME, maxsplit=1)
        for line in written.splitlines()
    )


def _whatever_the_application_wrote(app: RunningApp, filename: str) -> str:
    """Wait for the file the application drops, which it writes on its own loop."""
    left_behind = app.commands / filename
    deadline = time.monotonic() + _A_REACTION_TIMEOUT_SECONDS
    while not _there_and_complete(left_behind):
        if time.monotonic() >= deadline:
            pytest.fail(
                f"the application never wrote {filename} "
                f"(waited {_A_REACTION_TIMEOUT_SECONDS:.0f}s)"
            )
        time.sleep(_HOW_OFTEN_TO_LOOK_AGAIN_SECONDS)
    return left_behind.read_text(encoding="utf-8")


def _there_and_complete(left_behind: Path) -> bool:
    # Non-empty as well as present: `write_text` creates the file before it
    # fills it, so a reader that only checked existence would race it.
    return left_behind.exists() and left_behind.stat().st_size > 0


def _the_row_carrying(report: str, name: str) -> str:
    for line in report.splitlines():
        if repr(name) in line:
            return line
    raise AssertionError(f"no row in the report mentions {name!r}:\n{report}")
