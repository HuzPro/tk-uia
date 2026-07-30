"""The UIA pattern vocabulary, where the annotator's ports and the provider layer can both name it."""

from __future__ import annotations

from enum import Enum


class Pattern(Enum):
    """The UIA patterns a provider can honestly offer, by their pattern ids."""

    INVOKE = 10000
    VALUE = 10002
    RANGE_VALUE = 10003
    SELECTION_ITEM = 10010
    TOGGLE = 10015
