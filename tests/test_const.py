"""Sanity checks for the updated status/event constant lists."""
from custom_components.big_brother_28 import const


def test_veto_competitor_and_veto_winner_are_distinct_statuses():
    assert const.STATUS_VETO_COMPETITOR == "Veto Competitor"
    assert const.STATUS_VETO_WINNER == "Veto Winner"
    assert const.STATUS_VETO_COMPETITOR in const.HOUSEMATE_STATUSES
    assert const.STATUS_VETO_WINNER in const.HOUSEMATE_STATUSES


def test_veto_picks_event_state_exists():
    assert const.EVENT_VETO_PICKS == "Veto Picks"
    assert const.EVENT_VETO_PICKS in const.EVENT_STATES


def test_have_not_attr_exists():
    assert const.ATTR_IS_HAVE_NOT == "is_have_not"


def test_have_not_service_exists():
    assert const.SERVICE_SET_HAVE_NOT == "set_have_not"


def test_jury_is_a_housemate_status():
    assert const.STATUS_JURY == "Jury"
    assert const.STATUS_JURY in const.HOUSEMATE_STATUSES
