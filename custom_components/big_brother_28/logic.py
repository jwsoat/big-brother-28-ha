"""Pure, Home-Assistant-independent game-state logic for Big Brother 28."""
from __future__ import annotations

from .const import (
    STATUS_ELIMINATED,
    STATUS_HOH,
    STATUS_NOMINATED,
    STATUS_VETO_COMPETITOR,
)


def join_names_or_none(names: list[str]) -> str:
    return ", ".join(names) if names else "None"


def compute_current_hoh(statuses: dict[str, str]) -> str:
    for name, status in statuses.items():
        if status == STATUS_HOH:
            return name
    return "None"


def compute_nominees(statuses: dict[str, str]) -> list[str]:
    return [name for name, status in statuses.items() if status == STATUS_NOMINATED]


def compute_veto_competitors(statuses: dict[str, str]) -> list[str]:
    return [
        name
        for name, status in statuses.items()
        if status == STATUS_VETO_COMPETITOR
    ]


def compute_have_nots(have_not_flags: dict[str, bool]) -> list[str]:
    return [name for name, is_have_not in have_not_flags.items() if is_have_not]


def compute_jury_members(
    statuses: dict[str, str], jury_flags: dict[str, bool]
) -> list[str]:
    return [
        name
        for name, status in statuses.items()
        if status == STATUS_ELIMINATED and jury_flags.get(name, False)
    ]
