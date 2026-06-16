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
    CONF_IGNORED_ENTITIES,
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
    ignored_entities = config.get(CONF_IGNORED_ENTITIES, [])

    # Ignored entities are reported separately because they are intentionally
    # excluded from HALP! scoring. They are still useful diagnostics because
    # they explain why an assigned Person tracker does not appear as a source.
    scored_total = len(gps_entities) + len(ble_entities) + len(router_entities)

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
            "ignored": len(ignored_entities),
            "total": scored_total,
            "accounted_total": scored_total + len(ignored_entities),
        },
        "configured_sources": {
            "gps": gps_entities,
            "ble": ble_entities,
            "router": router_entities,
            "ignored": ignored_entities,
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
