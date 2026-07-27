"""Behavioral spec for the widget classes whose role was chosen by measurement.

A role the MSAA-to-UIA bridge does not recognise is accepted, returns `S_OK`,
and leaves the widget as the anonymous `PaneControl` it already was. `DIAGRAM`,
`CLIENT` and `PANE` were all tried for the canvas and all three did that.

So the numbers cannot be held by a unit spec, which would only prove the table
says what the table says. These read the widgets back from another process and
check each arrives as the control type its number was measured to produce.
"""

from __future__ import annotations

import sys
from typing import Any

import pytest

from tests.conftest import RunningApp, the_widgets_the_application_shows
from tests.fixture_apps.newly_roled_app import (
    A_CANVAS,
    A_CLASSIC_MENUBUTTON,
    A_CLASSIC_PANEDWINDOW,
    A_LABELLED_SCALE,
    A_SEPARATOR,
    A_SIZEGRIP,
    A_THEMED_MENUBUTTON,
    A_THEMED_PANEDWINDOW,
)

pytestmark = [
    pytest.mark.gui,
    pytest.mark.skipif(
        sys.platform != "win32", reason="UI Automation is a Windows API"
    ),
]

# What each role was measured to reach a client as, read back from another
# process while the numbers were being chosen.
WHAT_EACH_ONE_SHOULD_REACH_A_CLIENT_AS = [
    (A_CANVAS, "ImageControl"),
    (A_CLASSIC_MENUBUTTON, "SplitButtonControl"),
    (A_THEMED_MENUBUTTON, "SplitButtonControl"),
    (A_CLASSIC_PANEDWINDOW, "GroupControl"),
    (A_THEMED_PANEDWINDOW, "GroupControl"),
    (A_SEPARATOR, "SeparatorControl"),
    (A_SIZEGRIP, "ThumbControl"),
]

_STILL_ANONYMOUS = "PaneControl"


def what_a_client_reads(window: Any) -> dict[str, str]:
    return {
        control.Name: control.ControlTypeName
        for control in the_widgets_the_application_shows(window)
        if control.Name
    }


@pytest.mark.parametrize(
    ("name", "control_type"), WHAT_EACH_ONE_SHOULD_REACH_A_CLIENT_AS
)
def test_a_widget_that_gained_a_role_reaches_a_client_as_the_control_it_was_measured_to_be(
    newly_roled_app: RunningApp, name: str, control_type: str
) -> None:
    # Given one of these widgets, when a client reads the window it is in
    read = what_a_client_reads(newly_roled_app.window)

    # Then it arrives as the control type its number was measured to produce,
    # and as something other than an anonymous pane. A number the bridge does
    # not know leaves it a pane, so the second assertion is the one that catches
    # a wrong choice.
    assert read.get(name) == control_type, (
        f"{name!r} reaches a client as {read.get(name)}, not {control_type}"
    )
    assert read.get(name) != _STILL_ANONYMOUS, (
        f"{name!r} is still the anonymous pane bare Tk hands over"
    )


def test_a_scale_carries_the_name_tk_keeps_in_its_label_option(
    newly_roled_app: RunningApp,
) -> None:
    # Given a Scale given its caption the only way Tk allows, `-label`, since a
    # classic Scale has no `-text` option at all
    # When a client reads the window
    read = what_a_client_reads(newly_roled_app.window)

    # Then the caption is its accessible name, inferred rather than set by hand.
    # Nothing in the fixture names this widget, so an inference that only read
    # `-text` would leave it announced as an unnamed slider.
    assert read.get(A_LABELLED_SCALE) == "SliderControl", (
        f"a labelled Scale reaches a client as {read.get(A_LABELLED_SCALE)}"
    )
