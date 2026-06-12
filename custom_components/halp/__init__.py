"""Set up HALP!."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval

from .const import CONF_PERSON_ENTITY, DOMAIN, PLATFORMS
from .helpers import (
    analyze_sources,
    calculate_confidence,
    calculate_consensus_score,
    calculate_source_health,
    calculate_vetted_location,
    resolve_person_entity_id,
)
from .history import async_record_history_sample

_LOGGER = logging.getLogger(__name__)

HISTORY_SAMPLE_INTERVAL = timedelta(minutes=5)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HALP! from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    config = {
        **dict(entry.data),
        **dict(entry.options),
    }

    resolved_person_entity = resolve_person_entity_id(hass, entry)

    if resolved_person_entity is not None:
        stored_person_entity = entry.data.get(CONF_PERSON_ENTITY)

        if stored_person_entity != resolved_person_entity:
            _LOGGER.info(
                "Resolved HALP! Person entity changed from %s to %s",
                stored_person_entity,
                resolved_person_entity,
            )

            new_data = dict(entry.data)
            new_data[CONF_PERSON_ENTITY] = resolved_person_entity
            hass.config_entries.async_update_entry(entry, data=new_data)

            config[CONF_PERSON_ENTITY] = resolved_person_entity
    else:
        _LOGGER.warning(
            "HALP! could not resolve the configured Person entity for entry %s",
            entry.entry_id,
        )

        config[CONF_PERSON_ENTITY] = None
        config["person_missing"] = True

    hass.data[DOMAIN][entry.entry_id] = config

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    async def record_history_sample(now) -> None:
        """Record one rolling history sample for this HALP! entry."""
        current_config = hass.data.get(DOMAIN, {}).get(entry.entry_id)
        if not isinstance(current_config, dict):
            return

        if current_config.get("person_missing", False):
            return

        results = analyze_sources(hass, current_config)
        vetted_location = calculate_vetted_location(results)
        confidence = calculate_confidence(results, vetted_location)
        consensus_score = calculate_consensus_score(results, vetted_location)
        source_health = calculate_source_health(
            results,
            vetted_location,
            confidence,
            consensus_score,
        )

        await async_record_history_sample(
            hass=hass,
            entry_id=entry.entry_id,
            entry_title=entry.title,
            person_entity=current_config.get(CONF_PERSON_ENTITY),
            vetted_location=vetted_location,
            confidence=confidence,
            consensus_score=consensus_score,
            source_health=source_health,
            results=results,
        )

    entry.async_on_unload(
        async_track_time_interval(
            hass,
            record_history_sample,
            HISTORY_SAMPLE_INTERVAL,
        )
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload HALP! when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a HALP! config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)

    return unload_ok