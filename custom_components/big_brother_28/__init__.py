"""Big Brother 28 integration."""
from __future__ import annotations

import os

import voluptuous as vol

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from . import logic
from .sensor import BB28HousemateSensor
from .const import (
    ATTR_DETAIL,
    ATTR_EVENT_TYPE,
    ATTR_IS_HAVE_NOT,
    ATTR_NAME,
    ATTR_SCHEDULED_TIME,
    ATTR_STATUS,
    CONF_HOUSEMATES,
    CONF_START_DATE,
    DOMAIN,
    EVENT_STATES,
    HOUSEMATE_STATUSES,
    ICON_STATIC_URL,
    SERVICE_ADD_HOUSEMATE,
    SERVICE_REMOVE_HOUSEMATE,
    SERVICE_SET_HAVE_NOT,
    SERVICE_SET_HOUSEMATE_STATUS,
    SERVICE_SET_NEXT_EVENT,
)

PLATFORMS = ["sensor"]

_NAME_OR_LIST = vol.All(cv.ensure_list, [cv.string])

ADD_HOUSEMATE_SCHEMA = vol.Schema({vol.Required(ATTR_NAME): _NAME_OR_LIST})
REMOVE_HOUSEMATE_SCHEMA = vol.Schema({vol.Required(ATTR_NAME): _NAME_OR_LIST})
SET_HOUSEMATE_STATUS_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_NAME): _NAME_OR_LIST,
        vol.Required(ATTR_STATUS): vol.In(HOUSEMATE_STATUSES),
    }
)
SET_NEXT_EVENT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_EVENT_TYPE): vol.In(EVENT_STATES),
        vol.Optional(ATTR_DETAIL, default=""): cv.string,
        vol.Optional(ATTR_SCHEDULED_TIME): cv.string,
    }
)
SET_HAVE_NOT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_NAME): _NAME_OR_LIST,
        vol.Required(ATTR_IS_HAVE_NOT): cv.boolean,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "housemate_entities": {},
        "next_event_entity": None,
        "house_day_entity": None,
        "week_number_entity": None,
        "aggregate_entities": [],
    }

    await _async_register_icon_path(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    _async_register_services(hass)

    return True


async def _async_register_icon_path(hass: HomeAssistant) -> None:
    if hass.data[DOMAIN].get("_icon_path_registered"):
        return
    icons_dir = os.path.join(os.path.dirname(__file__), "icons")
    await hass.http.async_register_static_paths(
        [StaticPathConfig("/big_brother_28/icons", icons_dir, cache_headers=False)]
    )
    hass.data[DOMAIN]["_icon_path_registered"] = True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


def _refresh_aggregates(hass: HomeAssistant, entry_id: str) -> None:
    for entity in hass.data[DOMAIN][entry_id]["aggregate_entities"]:
        entity.refresh()


def _ensure_housemate_entity(hass: HomeAssistant, entry: ConfigEntry, name: str):
    """Get the housemate sensor for `name`, auto-creating it (live + persisted) if new.

    Lets set_housemate_status/set_have_not/set_jury_status double as an implicit
    "add housemate" for callers (e.g. the daily-recap automation) that only know
    a name showed up in a confirmed fact and never call add_housemate themselves.
    """
    store = hass.data[DOMAIN][entry.entry_id]
    entities = store["housemate_entities"]
    entity = entities.get(name)
    if entity is not None:
        return entity

    entity = BB28HousemateSensor(entry, name)
    entities[name] = entity
    store["async_add_entities"]([entity])

    housemates = list(entry.options.get(CONF_HOUSEMATES, []))
    if name not in housemates:
        housemates.append(name)
        hass.config_entries.async_update_entry(
            entry, options={**entry.options, CONF_HOUSEMATES: housemates}
        )
    return entity


def _async_register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_ADD_HOUSEMATE):
        return

    async def _get_entry(call: ServiceCall) -> ConfigEntry:
        entries = hass.config_entries.async_entries(DOMAIN)
        if not entries:
            raise ValueError("Big Brother 28 is not configured")
        return entries[0]

    def _clean_names(raw_names) -> list[str]:
        seen: list[str] = []
        for raw in raw_names:
            name = raw.strip()
            if name and name not in seen:
                seen.append(name)
        return seen

    async def add_housemate(call: ServiceCall) -> None:
        entry = await _get_entry(call)
        names = _clean_names(call.data[ATTR_NAME])
        housemates = list(entry.options.get(CONF_HOUSEMATES, []))
        added = False
        for name in names:
            if name not in housemates:
                housemates.append(name)
                added = True
        if added:
            hass.config_entries.async_update_entry(
                entry,
                options={**entry.options, CONF_HOUSEMATES: housemates},
            )

    async def remove_housemate(call: ServiceCall) -> None:
        entry = await _get_entry(call)
        names = set(_clean_names(call.data[ATTR_NAME]))
        housemates = [h for h in entry.options.get(CONF_HOUSEMATES, []) if h not in names]
        hass.config_entries.async_update_entry(
            entry,
            options={**entry.options, CONF_HOUSEMATES: housemates},
        )

    async def set_housemate_status(call: ServiceCall) -> None:
        entry = await _get_entry(call)
        status = call.data[ATTR_STATUS]
        store = hass.data[DOMAIN][entry.entry_id]
        names = _clean_names(call.data[ATTR_NAME])
        if not names:
            return

        for name in names:
            entity = _ensure_housemate_entity(hass, entry, name)
            entity.set_status(status)

        updated_statuses = {
            housemate_name: housemate_entity.native_value
            for housemate_name, housemate_entity in store["housemate_entities"].items()
        }
        next_event_value = logic.next_event_after_status_change(
            status, updated_statuses
        )
        if next_event_value is not None:
            store["next_event_entity"].set_event(next_event_value)

        if logic.is_week_advancing_status(status):
            store["week_number_entity"].advance_week()

        _refresh_aggregates(hass, entry.entry_id)

    async def set_next_event(call: ServiceCall) -> None:
        entry = await _get_entry(call)
        entity = hass.data[DOMAIN][entry.entry_id]["next_event_entity"]
        if entity is None:
            raise ValueError("Next event sensor not ready")
        entity.set_event(
            call.data[ATTR_EVENT_TYPE],
            call.data.get(ATTR_DETAIL, ""),
            call.data.get(ATTR_SCHEDULED_TIME),
        )

    async def set_have_not(call: ServiceCall) -> None:
        entry = await _get_entry(call)
        is_have_not = call.data[ATTR_IS_HAVE_NOT]
        for name in _clean_names(call.data[ATTR_NAME]):
            entity = _ensure_housemate_entity(hass, entry, name)
            entity.set_have_not(is_have_not)
        _refresh_aggregates(hass, entry.entry_id)

    hass.services.async_register(
        DOMAIN, SERVICE_ADD_HOUSEMATE, add_housemate, schema=ADD_HOUSEMATE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_HOUSEMATE,
        remove_housemate,
        schema=REMOVE_HOUSEMATE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_HOUSEMATE_STATUS,
        set_housemate_status,
        schema=SET_HOUSEMATE_STATUS_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_NEXT_EVENT, set_next_event, schema=SET_NEXT_EVENT_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_HAVE_NOT, set_have_not, schema=SET_HAVE_NOT_SCHEMA
    )
