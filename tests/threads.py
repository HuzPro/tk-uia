"""Running a call on a thread that does not own the widgets, and catching what it says.

Two specs need this — one for annotating, one for describing — and both are
about a refusal that has to arrive as an exception on the calling thread rather
than as a traceback printed by a worker nobody is watching. It is a helper
rather than a double, so it lives beside them instead of in `doubles.py`.
"""

from __future__ import annotations

import threading
from collections.abc import Callable


def the_failure_raised_on_another_thread(work: Callable[[], object]) -> BaseException:
    """Run `work` on a fresh thread and hand back whatever it raised."""
    caught: list[BaseException] = []

    def run() -> None:
        try:
            work()
        except BaseException as failure:  # noqa: BLE001 - reported, not handled
            caught.append(failure)

    worker = threading.Thread(target=run)
    worker.start()
    worker.join()

    assert caught, "the call went through on a thread that does not own the widgets"
    return caught[0]
