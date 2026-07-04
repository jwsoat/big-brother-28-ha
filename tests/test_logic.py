"""Unit tests for pure BB28 game-state logic (no Home Assistant dependency)."""
from custom_components.big_brother_28 import logic
from custom_components.big_brother_28.const import (
    STATUS_ELIMINATED,
    STATUS_HOH,
    STATUS_NOMINATED,
    STATUS_SAFE,
    STATUS_VETO_COMPETITOR,
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


def test_compute_jury_members_requires_eliminated_and_flag():
    statuses = {
        "Alex": STATUS_ELIMINATED,
        "Jordan": STATUS_ELIMINATED,
        "Sam": STATUS_SAFE,
    }
    jury_flags = {"Alex": True, "Jordan": False, "Sam": True}
    assert logic.compute_jury_members(statuses, jury_flags) == ["Alex"]
