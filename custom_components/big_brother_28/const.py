"""Constants for Big Brother 28 integration."""

DOMAIN = "big_brother_28"

CONF_START_DATE = "start_date"
CONF_HOUSEMATES = "housemates"

STORAGE_VERSION = 1
STORAGE_KEY_HOUSEMATES = "housemates"

# Housemate statuses
STATUS_HOH = "HOH"
STATUS_NOMINATED = "Nominated"
STATUS_VETO_PLAYER = "Veto Player"
STATUS_SAFE = "Safe"
STATUS_ELIMINATED = "Eliminated"

HOUSEMATE_STATUSES = [
    STATUS_HOH,
    STATUS_NOMINATED,
    STATUS_VETO_PLAYER,
    STATUS_SAFE,
    STATUS_ELIMINATED,
]

DEFAULT_HOUSEMATE_STATUS = STATUS_SAFE

# Next-event states
EVENT_HOH = "HOH"
EVENT_VETO = "Veto"
EVENT_LIVE_SHOW = "Live Show"
EVENT_EVICTION = "Eviction"
EVENT_NOMINATIONS = "Nominations"
EVENT_OTHER = "Other"

EVENT_STATES = [
    EVENT_HOH,
    EVENT_VETO,
    EVENT_LIVE_SHOW,
    EVENT_EVICTION,
    EVENT_NOMINATIONS,
    EVENT_OTHER,
]

DEFAULT_EVENT_STATE = EVENT_OTHER

SERVICE_ADD_HOUSEMATE = "add_housemate"
SERVICE_REMOVE_HOUSEMATE = "remove_housemate"
SERVICE_SET_HOUSEMATE_STATUS = "set_housemate_status"
SERVICE_SET_NEXT_EVENT = "set_next_event"

ATTR_NAME = "name"
ATTR_STATUS = "status"
ATTR_EVENT_TYPE = "event_type"
ATTR_DETAIL = "detail"
ATTR_SCHEDULED_TIME = "scheduled_time"

SIGNAL_HOUSEMATES_UPDATED = f"{DOMAIN}_housemates_updated"

ICON_STATIC_URL = "/big_brother_28/icons/logo.jpg"

