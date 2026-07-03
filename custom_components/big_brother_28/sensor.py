"""Sensor platform for Big Brother 28."""
from __future__ import annotations

from datetime import date, timedelta

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    async_track_point_in_time,
    async_track_time_interval,
)
from homeassistant.helpers.restore_state import RestoreEntity
import homeassistant.util.dt as dt_util

from .const import (
    CONF_HOUSEMATES,
    CONF_START_DATE,
    CONF_TIMEZONE,
    DEFAULT_EVENT_STATE,
    DEFAULT_HOUSEMATE_STATUS,
    DEFAULT_TIMEZONE,
    DOMAIN,
    ICON_STATIC_URL,
)


def _get_tz(entry: ConfigEntry):
    name = entry.options.get(CONF_TIMEZONE, DEFAULT_TIMEZONE)
    return dt_util.get_time_zone(name) or dt_util.get_time_zone(DEFAULT_TIMEZONE)


def _device_info(entry: ConfigEntry) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="Big Brother 28",
        manufacturer="CBS",
        model="Big Brother House",
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    store = hass.data[DOMAIN][entry.entry_id]

    house_day = BB28HouseDaySensor(entry)
    house_time = BB28HouseTimeSensor(entry)
    next_event = BB28NextEventSensor(entry)

    store["house_day_entity"] = house_day
    store["next_event_entity"] = next_event

    entities: list[SensorEntity] = [house_day, house_time, next_event]

    for name in entry.options.get(CONF_HOUSEMATES, []):
        housemate = BB28HousemateSensor(entry, name)
        store["housemate_entities"][name] = housemate
        entities.append(housemate)

    async_add_entities(entities)


class BB28HouseDaySensor(SensorEntity):
    """Day number of the season, counted from start_date (day 1)."""

    _attr_icon = "mdi:calendar-star"
    _attr_entity_picture = ICON_STATIC_URL
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_house_day"
        self._attr_name = "House Day"
        self._attr_device_info = _device_info(entry)
        self._unsub = None

    @property
    def native_value(self) -> int | None:
        start = self._start_date()
        if start is None:
            return None
        delta = dt_util.now(_get_tz(self._entry)).date() - start
        return max(delta.days + 1, 0)

    def _start_date(self) -> date | None:
        raw = self._entry.options.get(CONF_START_DATE)
        if not raw:
            return None
        try:
            return date.fromisoformat(raw)
        except ValueError:
            return None

    async def async_added_to_hass(self) -> None:
        self._schedule_next_midnight()

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub:
            self._unsub()

    def _schedule_next_midnight(self) -> None:
        now = dt_util.now(_get_tz(self._entry))
        next_midnight = (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        self._unsub = async_track_point_in_time(
            self.hass, self._handle_midnight, next_midnight
        )

    def _handle_midnight(self, _now) -> None:
        self.async_write_ha_state()
        self._schedule_next_midnight()


class BB28HouseTimeSensor(SensorEntity):
    """Current live-feed clock time in the house."""

    _attr_icon = "mdi:clock-outline"
    _attr_entity_picture = ICON_STATIC_URL
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_house_time"
        self._attr_name = "House Time"
        self._attr_device_info = _device_info(entry)
        self._unsub = None

    @property
    def native_value(self) -> str:
        return dt_util.now(_get_tz(self._entry)).strftime("%H:%M")

    async def async_added_to_hass(self) -> None:
        self._unsub = async_track_time_interval(
            self.hass, self._handle_tick, timedelta(minutes=1)
        )

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub:
            self._unsub()

    def _handle_tick(self, _now) -> None:
        self.async_write_ha_state()


class BB28NextEventSensor(RestoreEntity, SensorEntity):
    """Next upcoming event: HOH, Veto, Live Show, Eviction, Nominations, Other."""

    _attr_icon = "mdi:calendar-clock"
    _attr_entity_picture = ICON_STATIC_URL
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_next_event"
        self._attr_name = "Next Event"
        self._attr_device_info = _device_info(entry)
        self._state = DEFAULT_EVENT_STATE
        self._detail = ""
        self._scheduled_time: str | None = None

    @property
    def native_value(self) -> str:
        return self._state

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "detail": self._detail,
            "scheduled_time": self._scheduled_time,
        }

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None:
            self._state = last_state.state
            self._detail = last_state.attributes.get("detail", "")
            self._scheduled_time = last_state.attributes.get("scheduled_time")

    def set_event(
        self, event_type: str, detail: str = "", scheduled_time: str | None = None
    ) -> None:
        self._state = event_type
        self._detail = detail
        self._scheduled_time = scheduled_time
        self.async_write_ha_state()


class BB28HousemateSensor(RestoreEntity, SensorEntity):
    """Status of a single housemate."""

    _attr_icon = "mdi:account"
    _attr_entity_picture = ICON_STATIC_URL
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, name: str) -> None:
        self._entry = entry
        self._name_value = name
        slug = name.lower().replace(" ", "_")
        self._attr_unique_id = f"{entry.entry_id}_housemate_{slug}"
        self._attr_name = name
        self._attr_device_info = _device_info(entry)
        self._state = DEFAULT_HOUSEMATE_STATUS

    @property
    def native_value(self) -> str:
        return self._state

    @property
    def extra_state_attributes(self) -> dict:
        return {"housemate": self._name_value}

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state is not None:
            self._state = last_state.state

    def set_status(self, status: str) -> None:
        self._state = status
        self.async_write_ha_state()
