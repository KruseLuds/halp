"""Validation of HALP! fixed-location assignments.

The current global zone inventory is not itself a configuration error.
Only a configured fixed tracker pointing to a missing/inactive zone needs
attention. GPS and explicitly mobile router sources remain dynamic.
"""

from __future__ import annotations

from typing import Any


def invalid_fixed_zone_assignments(
    config: dict[str, Any],
    active_zones: set[str],
    *,
    ble_entities_key: str,
    router_entities_key: str,
    ble_zones_key: str,
    router_zones_key: str,
    mobile_marker: str,
) -> tuple[list[str], list[str]]:
    """Return BLE and WiFi/router sources lacking valid fixed zone IDs."""
    ble_entities = [
        value
        for value in config.get(ble_entities_key, [])
        if isinstance(value, str)
    ]
    router_entities = [
        value
        for value in config.get(router_entities_key, [])
        if isinstance(value, str)
    ]
    ble_zones = config.get(ble_zones_key, {})
    if not isinstance(ble_zones, dict):
        ble_zones = {}
    router_zones = config.get(router_zones_key, {})
    if not isinstance(router_zones, dict):
        router_zones = {}

    missing_ble = [
        entity_id for entity_id in ble_entities
        if ble_zones.get(entity_id) not in active_zones
    ]
    missing_router = [
        entity_id for entity_id in router_entities
        if router_zones.get(entity_id) != mobile_marker
        and router_zones.get(entity_id) not in active_zones
    ]
    return missing_ble, missing_router
