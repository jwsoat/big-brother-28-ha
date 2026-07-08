"""Unit tests for pure BB28 game-state logic (no Home Assistant dependency)."""
from custom_components.big_brother_28 import logic
from custom_components.big_brother_28.const import (
    DEFAULT_HOUSEMATE_STATUS,
    EVENT_HOH,
    EVENT_LIVE_SHOW,
    EVENT_NOMINATIONS,
    EVENT_VETO,
    EVENT_VETO_PICKS,
    STATUS_ELIMINATED,
    STATUS_HOH,
    STATUS_JURY,
    STATUS_NOMINATED,
    STATUS_SAFE,
    STATUS_VETO_COMPETITOR,
    STATUS_VETO_WINNER,
)


def test_join_names_or_none_empty():
    assert logic.join_names_or_none([]) == "None"


def test_join_names_or_none_joins_with_comma():
    assert logic.join_names_or_none(["Alex", "Jordan"]) == "Alex, Jordan"


def test_compute_current_hoh_finds_the_hoh():
    statuses = {"Alex": STATUS_HOH, "Jordan": STATUS_SAFE}
    assert logic.compute_current_hoh(statuses) == "Alex"


def test_compute_current_hoh_returns_none_string_when_no_hoh():
    statuses = {"Alex": STATUS_SAFE, "Jordan": STATUS_SAFE}
    assert logic.compute_current_hoh(statuses) == "None"


def test_compute_nominees_returns_all_nominated():
    statuses = {
        "Alex": STATUS_NOMINATED,
        "Jordan": STATUS_NOMINATED,
        "Sam": STATUS_SAFE,
    }
    assert sorted(logic.compute_nominees(statuses)) == ["Alex", "Jordan"]


def test_compute_veto_competitors_returns_only_that_status():
    statuses = {
        "Alex": STATUS_VETO_COMPETITOR,
        "Jordan": STATUS_HOH,
        "Sam": STATUS_SAFE,
    }
    assert logic.compute_veto_competitors(statuses) == ["Alex"]


def test_compute_have_nots_returns_flagged_names():
    flags = {"Alex": True, "Jordan": False, "Sam": True}
    assert sorted(logic.compute_have_nots(flags)) == ["Alex", "Sam"]


def test_compute_jury_members_returns_only_jury_status():
    statuses = {
        "Alex": STATUS_JURY,
        "Jordan": STATUS_ELIMINATED,
        "Sam": STATUS_SAFE,
    }
    assert logic.compute_jury_members(statuses) == ["Alex"]


def test_hoh_status_advances_to_nominations():
    result = logic.next_event_after_status_change(STATUS_HOH, {"Alex": STATUS_HOH})
    assert result == EVENT_NOMINATIONS


def test_single_nominee_does_not_advance_yet():
    statuses = {"Alex": STATUS_NOMINATED, "Jordan": STATUS_SAFE}
    assert logic.next_event_after_status_change(STATUS_NOMINATED, statuses) is None


def test_second_nominee_advances_to_veto_picks():
    statuses = {"Alex": STATUS_NOMINATED, "Jordan": STATUS_NOMINATED}
    result = logic.next_event_after_status_change(STATUS_NOMINATED, statuses)
    assert result == EVENT_VETO_PICKS


def test_veto_competitor_status_advances_to_veto():
    statuses = {"Alex": STATUS_VETO_COMPETITOR}
    result = logic.next_event_after_status_change(STATUS_VETO_COMPETITOR, statuses)
    assert result == EVENT_VETO


def test_veto_winner_status_advances_to_live_show():
    statuses = {"Alex": STATUS_VETO_WINNER}
    result = logic.next_event_after_status_change(STATUS_VETO_WINNER, statuses)
    assert result == EVENT_LIVE_SHOW


def test_eliminated_status_advances_to_hoh():
    statuses = {"Alex": STATUS_ELIMINATED}
    result = logic.next_event_after_status_change(STATUS_ELIMINATED, statuses)
    assert result == EVENT_HOH


def test_safe_status_does_not_advance():
    statuses = {"Alex": STATUS_SAFE}
    assert logic.next_event_after_status_change(STATUS_SAFE, statuses) is None


def test_eliminated_status_advances_the_week():
    assert logic.is_week_advancing_status(STATUS_ELIMINATED) is True


def test_hoh_status_does_not_advance_the_week():
    assert logic.is_week_advancing_status(STATUS_HOH) is False


def test_jury_status_does_not_advance_event_or_week():
    statuses = {"Alex": STATUS_JURY}
    assert logic.next_event_after_status_change(STATUS_JURY, statuses) is None
    assert logic.is_week_advancing_status(STATUS_JURY) is False


def test_normalize_restored_status_maps_legacy_veto_player():
    assert logic.normalize_restored_status("Veto Player") == STATUS_VETO_WINNER


def test_normalize_restored_status_passes_through_valid_status():
    assert logic.normalize_restored_status(STATUS_SAFE) == STATUS_SAFE


def test_normalize_restored_status_falls_back_for_unrecognized_string():
    assert logic.normalize_restored_status("garbage") == DEFAULT_HOUSEMATE_STATUS
