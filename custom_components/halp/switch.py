"""Switch entities for HALP!."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_GPS_ENTITIES,
    CONF_PRIORITIZE_SECOND_GPS_NOT_HOME,
    CONF_PRIORITIZE_SECOND_GPS_NOT_HOME_REVIEWED,
    DEFAULT_PRIORITIZE_SECOND_GPS_NOT_HOME,
    DOMAIN,
    NAME,
)

SETTING_LABEL = "Speed up location transitions"
NO_GPS_COMMENT = (
    "Unavailable (there is no GPS tracker sensor configured for this person)"
)
REVIEW_REQUIRED_COMMENT = (
    "Unavailable (review and save this new option in the HALP! Configure flow)"
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HALP! switches from a config entry."""
    config = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([HalpPrioritizeSecondGpsNotHomeSwitch(hass, entry, config)])


class HalpPrioritizeSecondGpsNotHomeSwitch(SwitchEntity):
    """Enable the second matching GPS location update transition rule."""

    _attr_icon = "mdi:map-marker-fast"
    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        config: dict[str, Any],
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.config = config
        self._attr_name = f"{NAME} {entry.title} Speed Up Location Transitions"
        self._attr_unique_id = (
            f"{DOMAIN}_{entry.entry_id}_prioritize_second_gps_not_home"
        )

    @property
    def device_info(self) -> dict[str, Any]:
        """Group this switch with the other HALP! entities for the Person."""
        return {
            "identifiers": {
                (DOMAIN, self.entry.entry_id),
            },
            "name": f"{NAME} {self.entry.title}",
            "manufacturer": "HALP!",
            "model": "Location Reliability Analyzer",
        }

    @property
    def available(self) -> bool:
        """Return whether the setting can currently be used."""
        has_gps = bool(self.config.get(CONF_GPS_ENTITIES, []))
        reviewed = bool(
            self.config.get(
                CONF_PRIORITIZE_SECOND_GPS_NOT_HOME_REVIEWED,
                False,
            )
        )
        return has_gps and reviewed

    @property
    def is_on(self) -> bool:
        """Return whether the fast-transition rule is enabled."""
        return bool(
            self.config.get(
                CONF_PRIORITIZE_SECOND_GPS_NOT_HOME,
                DEFAULT_PRIORITIZE_SECOND_GPS_NOT_HOME,
            )
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the full setting label and behavior."""
        has_gps = bool(self.config.get(CONF_GPS_ENTITIES, []))
        reviewed = bool(
            self.config.get(
                CONF_PRIORITIZE_SECOND_GPS_NOT_HOME_REVIEWED,
                False,
            )
        )

        if not has_gps:
            status_comment = NO_GPS_COMMENT
        elif not reviewed:
            status_comment = REVIEW_REQUIRED_COMMENT
        else:
            status_comment = "Available"

        return {
            "setting_label": SETTING_LABEL,
            "status_comment": status_comment,
            "behavior": (
                "When a configured GPS tracker changes to a location different "
                "from the current Vetted Location and then updates again while "
                "still reporting that same new location, HALP! can prioritize "
                "the confirmed location. This applies to Home, named zones, "
                "and not_home."
            ),
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the setting and reload the config entry."""
        await self._async_set_enabled(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the setting and reload the config entry."""
        await self._async_set_enabled(False)

    async def _async_set_enabled(self, enabled: bool) -> None:
        new_data = dict(self.entry.data)
        new_data[CONF_PRIORITIZE_SECOND_GPS_NOT_HOME] = enabled
        self.config[CONF_PRIORITIZE_SECOND_GPS_NOT_HOME] = enabled
        self.hass.config_entries.async_update_entry(self.entry, data=new_data)
