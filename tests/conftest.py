"""Keeps the specs independent of each other despite one module-level variable.

`enable()` records what it installed on the package, because the surface an
application calls is `tk_uia.set_acc_name(widget, ...)` and not a handle it has
to carry around. That state is the one thing in the package a spec can leave
behind for the next one, so it is put back after every one of them.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

import tk_uia


@pytest.fixture(autouse=True)
def a_package_that_has_not_been_enabled_yet() -> Iterator[None]:
    yield
    tk_uia._installed = None
