"""Diagnostics support for HALP!."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_BLE_ENTITIES,
    CONF_BLE_WEIGHT,
    CONF_GPS_ENTITIES,
    CONF_GPS_WEIGHT,
    CONF_PERSON_ENTITY,
    CONF_RELIABLE_THRESHOLD,
    CONF_ROUTER_ENTITIES,
    CONF_ROUTER_WEIGHT,
    DEFAULT_BLE_WEIGHT,
    DEFAULT_GPS_WEIGHT,
    DEFAULT_RELIABLE_THRESHOLD,
    DEFAULT_ROUTER_WEIGHT,
    DOMAIN,
)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    config = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})

    gps_entities = config.get(CONF_GPS_ENTITIES, [])
    ble_entities = config.get(CONF_BLE_ENTITIES, [])
    router_entities = config.get(CONF_ROUTER_ENTITIES, [])

    return {
        "halp_entry": {
            "title": entry.title,
            "entry_id": entry.entry_id,
            "person_entity": config.get(CONF_PERSON_ENTITY),
            "person_missing": config.get("person_missing", False),
        },
        "source_counts": {
            "gps": len(gps_entities),
            "ble": len(ble_entities),
            "router": len(router_entities),
            "total": len(gps_entities) + len(ble_entities) + len(router_entities),
        },
        "configured_sources": {
            "gps": gps_entities,
            "ble": ble_entities,
            "router": router_entities,
        },
        "tuning": {
            "reliable_threshold": config.get(
                CONF_RELIABLE_THRESHOLD,
                DEFAULT_RELIABLE_THRESHOLD,
            ),
            "gps_weight": config.get(CONF_GPS_WEIGHT, DEFAULT_GPS_WEIGHT),
            "ble_weight": config.get(CONF_BLE_WEIGHT, DEFAULT_BLE_WEIGHT),
            "router_weight": config.get(CONF_ROUTER_WEIGHT, DEFAULT_ROUTER_WEIGHT),
        },
    }