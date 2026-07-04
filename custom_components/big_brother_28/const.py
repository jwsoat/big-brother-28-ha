"""Constants for Big Brother 28 integration."""

DOMAIN = "big_brother_28"

CONF_START_DATE = "start_date"
CONF_HOUSEMATES = "housemates"
CONF_TIMEZONE = "timezone"

DEFAULT_START_DATE = "2026-07-09"
DEFAULT_TIMEZONE = "America/Los_Angeles"

STORAGE_VERSION = 1
STORAGE_KEY_HOUSEMATES = "housemates"

# Housemate statuses
STATUS_HOH = "HOH"
STATUS_NOMINATED = "Nominated"
STATUS_VETO_COMPETITOR = "Veto Competitor"
STATUS_VETO_WINNER = "Veto Winner"
STATUS_SAFE = "Safe"
STATUS_ELIMINATED = "Eliminated"

HOUSEMATE_STATUSES = [
    STATUS_HOH,
    STATUS_NOMINATED,
    STATUS_VETO_COMPETITOR,
    STATUS_VETO_WINNER,
    STATUS_SAFE,
    STATUS_ELIMINATED,
]

DEFAULT_HOUSEMATE_STATUS = STATUS_SAFE

# Next-event states, in cycle order
EVENT_HOH = "HOH"
EVENT_NOMINATIONS = "Nominations"
EVENT_VETO_PICKS = "Veto Picks"
EVENT_VETO = "Veto"
EVENT_LIVE_SHOW = "Live Show"
EVENT_EVICTION = "Eviction"
EVENT_OTHER = "Other"

EVENT_STATES = [
    EVENT_HOH,
    EVENT_NOMINATIONS,
    EVENT_VETO_PICKS,
    EVENT_VETO,
    EVENT_LIVE_SHOW,
    EVENT_EVICTION,
    EVENT_OTHER,
]

DEFAULT_EVENT_STATE = EVENT_OTHER

SERVICE_ADD_HOUSEMATE = "add_housemate"
SERVICE_REMOVE_HOUSEMATE = "remove_housemate"
SERVICE_SET_HOUSEMATE_STATUS = "set_housemate_status"
SERVICE_SET_NEXT_EVENT = "set_next_event"
SERVICE_SET_HAVE_NOT = "set_have_not"
SERVICE_SET_JURY_STATUS = "set_jury_status"

ATTR_NAME = "name"
ATTR_STATUS = "status"
ATTR_EVENT_TYPE = "event_type"
ATTR_DETAIL = "detail"
ATTR_SCHEDULED_TIME = "scheduled_time"
ATTR_IS_HAVE_NOT = "is_have_not"
ATTR_IS_JURY_MEMBER = "is_jury_member"

SIGNAL_HOUSEMATES_UPDATED = f"{DOMAIN}_housemates_updated"

ICON_STATIC_URL = "/big_brother_28/icons/logo.jpg"
