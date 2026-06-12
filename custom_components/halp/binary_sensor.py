"""Binary sensor entities for HALP!."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_PERSON_ENTITY,
    CONF_RELIABLE_THRESHOLD,
    DEFAULT_RELIABLE_THRESHOLD,
    DOMAIN,
    NAME,
)
from .helpers import (
    analyze_sources,
    calculate_confidence,
    calculate_vetted_location,
    get_state,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HALP! binary sensors from a config entry."""
    config = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            HalpLocationReliableBinarySensor(hass, entry, config),
        ],
        True,
    )


def reliable_threshold(config: dict[str, Any]) -> int:
    """Return configured reliable threshold."""
    value = config.get(CONF_RELIABLE_THRESHOLD, DEFAULT_RELIABLE_THRESHOLD)

    try:
        return int(value)
    except (TypeError, ValueError):
        return DEFAULT_RELIABLE_THRESHOLD


class HalpLocationReliableBinarySensor(BinarySensorEntity):
    """Binary sensor indicating whether HALP! considers location reliable."""

    _attr_should_poll = True
    _attr_icon = "mdi:account-check-outline"

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        config: dict[str, Any],
    ) -> None:
        """Initialize the reliable binary sensor."""
        self.hass = hass
        self.entry = entry
        self.config = config

        self._attr_name = f"{NAME} {entry.title} Location Reliable"
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_location_reliable"

    @property
    def available(self) -> bool:
        """Return whether the configured Person still exists."""
        return not self.config.get("person_missing", False)

    @property
    def is_on(self) -> bool | None:
        """Return true when confidence meets the reliability threshold."""
        if not self.available:
            return None

        results = analyze_sources(self.hass, self.config)
        vetted_location = calculate_vetted_location(results)
        confidence = calculate_confidence(results, vetted_location)

        return confidence >= reliable_threshold(self.config)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return confidence and current comparison details."""
        if not self.available:
            return {
                "halp_status": "Configured Person entity could not be found.",
                "person_entity": self.config.get(CONF_PERSON_ENTITY),
            }

        results = analyze_sources(self.hass, self.config)
        vetted_location = calculate_vetted_location(results)
        confidence = calculate_confidence(results, vetted_location)
        threshold = reliable_threshold(self.config)

        return {
            "confidence": confidence,
            "threshold": threshold,
            "vetted_location": vetted_location,
            "person_entity": self.config.get(CONF_PERSON_ENTITY),
            "ha_person_state": get_state(
                self.hass,
                self.config.get(CONF_PERSON_ENTITY),
            ),
        }

    @property
    def device_info(self) -> dict[str, Any]:
        """Group all HALP! entities for a person under one device."""
        return {
            "identifiers": {
                (DOMAIN, self.entry.entry_id),
            },
            "name": f"{NAME} {self.entry.title}",
            "manufacturer": "HALP!",
            "model": "Location Reliability Analyzer",
        }