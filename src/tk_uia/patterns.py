"""The UIA pattern vocabulary, where the annotator's ports and the provider layer can both name it."""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from types import MappingProxyType


class Pattern(Enum):
    """The UIA patterns a provider can honestly offer, by their pattern ids."""

    INVOKE = 10000
    VALUE = 10002
    RANGE_VALUE = 10003
    SELECTION_ITEM = 10010
    TOGGLE = 10015


# A table because `Pattern(10099)` raises for an id no member carries.
THE_PATTERN_WITH_EACH_ID: Mapping[int, Pattern] = MappingProxyType(
    {pattern.value: pattern for pattern in Pattern}
)
