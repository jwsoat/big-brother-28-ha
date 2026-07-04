"""Pure, Home-Assistant-independent game-state logic for Big Brother 28."""
from __future__ import annotations

from .const import (
    DEFAULT_HOUSEMATE_STATUS,
    EVENT_HOH,
    EVENT_LIVE_SHOW,
    EVENT_NOMINATIONS,
    EVENT_VETO,
    EVENT_VETO_PICKS,
    HOUSEMATE_STATUSES,
    STATUS_ELIMINATED,
    STATUS_HOH,
    STATUS_NOMINATED,
    STATUS_VETO_COMPETITOR,
    STATUS_VETO_WINNER,
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


def next_event_after_status_change(
    new_status: str, statuses_after_change: dict[str, str]
) -> str | None:
    """Return the next_event value triggered by this status change, or None."""
    if new_status == STATUS_HOH:
        return EVENT_NOMINATIONS
    if new_status == STATUS_NOMINATED:
        if len(compute_nominees(statuses_after_change)) >= 2:
            return EVENT_VETO_PICKS
        return None
    if new_status == STATUS_VETO_COMPETITOR:
        return EVENT_VETO
    if new_status == STATUS_VETO_WINNER:
        return EVENT_LIVE_SHOW
    if new_status == STATUS_ELIMINATED:
        return EVENT_HOH
    return None


def is_week_advancing_status(new_status: str) -> bool:
    """True if this status change closes out a BB week (eviction)."""
    return new_status == STATUS_ELIMINATED


def normalize_restored_status(raw_status: str) -> str:
    """Map a status restored from a prior release to a currently-valid one."""
    if raw_status == "Veto Player":
        return STATUS_VETO_WINNER
    if raw_status in HOUSEMATE_STATUSES:
        return raw_status
    return DEFAULT_HOUSEMATE_STATUS
