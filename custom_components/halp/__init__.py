"""Set up HALP!."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.storage import Store

from .const import (
    CONF_BLE_ENTITIES,
    CONF_GPS_ENTITIES,
    CONF_IGNORED_ENTITIES,
    CONF_PERSON_ENTITY,
    CONF_PRIORITIZE_SECOND_GPS_NOT_HOME,
    CONF_PRIORITIZE_SECOND_GPS_NOT_HOME_REVIEWED,
    CONF_ROUTER_ENTITIES,
    DEFAULT_PRIORITIZE_SECOND_GPS_NOT_HOME,
    GPS_NOT_HOME_PRIORITY_CONFIDENCE_FLOOR,
    DOMAIN,
    PLATFORMS,
    LOCATION_HOME,
    LOCATION_NOT_HOME,
    RUNTIME_GPS_NOT_HOME_ARMED,
    RUNTIME_GPS_NOT_HOME_CONFIDENCE_HIGH_WATER,
    RUNTIME_GPS_NOT_HOME_PRIORITY_ACTIVE,
    RUNTIME_GPS_NOT_HOME_TRIGGER_ENTITY,
)
from .helpers import (
    analyze_sources,
    calculate_base_confidence,
    calculate_confidence,
    calculate_consensus_score,
    calculate_source_health,
    calculate_vetted_location,
    normalize_location_state,
    resolve_person_entity_id,
)
from .history import async_record_history_sample

_LOGGER = logging.getLogger(__name__)

HISTORY_SAMPLE_INTERVAL = timedelta(minutes=5)

# HALP! already checks tracker mismatch during setup.
#
# This interval adds an automatic follow-up check so users do not need to
# reload HALP! or restart Home Assistant after changing the trackers assigned
# to a Home Assistant Person.
#
# A one minute interval is intentionally lightweight because the check only
# reads the Person storage file and compares small tracker lists.
TRACKER_MISMATCH_CHECK_INTERVAL = timedelta(minutes=1)

PERSON_STORAGE_KEY = "person"
PERSON_STORAGE_VERSION = 2


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HALP! from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    config = {
        **dict(entry.data),
        **dict(entry.options),
    }

    # Existing entries created before this option existed must review it.
    # Until Configure is saved, the new departure rule remains disabled.
    review_complete = bool(
        config.get(CONF_PRIORITIZE_SECOND_GPS_NOT_HOME_REVIEWED, False)
    )
    if not review_complete:
        config[CONF_PRIORITIZE_SECOND_GPS_NOT_HOME] = False

    # Runtime-only state for the optional second-GPS-update departure rule.
    # These values are deliberately not persisted across reloads or restarts.
    config[RUNTIME_GPS_NOT_HOME_ARMED] = set()
    config[RUNTIME_GPS_NOT_HOME_PRIORITY_ACTIVE] = False
    config[RUNTIME_GPS_NOT_HOME_TRIGGER_ENTITY] = None
    config[RUNTIME_GPS_NOT_HOME_CONFIDENCE_HIGH_WATER] = 0

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

    await _async_update_fast_departure_review_notification(hass, entry, config)

    if not config.get("person_missing", False):
        await _async_check_tracker_mismatch(hass, entry, config)

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    async def check_tracker_mismatch(now) -> None:
        """Re-check Person tracker assignments while HALP! is running.

        Home Assistant Person tracker assignments can be changed outside the
        HALP! Configure flow.

        Without this scheduled check, HALP! would only notice those changes
        after a reload or restart. This keeps the existing startup behavior
        while also making mismatch notifications appear and disappear
        automatically after Person tracker changes are saved.
        """
        current_config = hass.data.get(DOMAIN, {}).get(entry.entry_id)
        if not isinstance(current_config, dict):
            return

        if current_config.get("person_missing", False):
            return

        await _async_check_tracker_mismatch(hass, entry, current_config)
        await _async_update_fast_departure_review_notification(
            hass, entry, current_config
        )

    entry.async_on_unload(
        async_track_time_interval(
            hass,
            check_tracker_mismatch,
            TRACKER_MISMATCH_CHECK_INTERVAL,
        )
    )

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

    # Listen to every scored tracker so the GPS-specific rule can observe an
    # update whose state remains not_home, while normal arrival evidence can
    # clear a temporary priority override.
    tracked_entities = _configured_location_trackers(config)
    if tracked_entities:
        async def _async_location_source_event(event: Event) -> None:
            """Forward tracker state-change events to the async HALP handler."""
            await _async_handle_location_source_event(
                hass,
                entry,
                event,
            )

        entry.async_on_unload(
            async_track_state_change_event(
                hass,
                tracked_entities,
                _async_location_source_event,
            )
        )

    return True


async def _async_handle_location_source_event(
    hass: HomeAssistant,
    entry: ConfigEntry,
    event: Event,
) -> None:
    """Apply the optional second not_home GPS update rule.

    The rule is armed only when the vetted result immediately before the GPS
    home -> not_home transition was home. A later update from that same GPS
    entity, with both old and new states still not_home, activates the temporary
    priority override.

    While the override is active, confidence starts at no less than 80 percent
    and uses a runtime high-water mark so it may rise as other sources catch up
    but cannot fall. The override is cleared when normal voting independently
    reaches not_home or when a configured source produces a new positive Home
    transition.
    """
    config = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if not isinstance(config, dict):
        return

    if not bool(
        config.get(
            CONF_PRIORITIZE_SECOND_GPS_NOT_HOME,
            DEFAULT_PRIORITIZE_SECOND_GPS_NOT_HOME,
        )
    ):
        config[RUNTIME_GPS_NOT_HOME_ARMED] = set()
        config[RUNTIME_GPS_NOT_HOME_PRIORITY_ACTIVE] = False
        config[RUNTIME_GPS_NOT_HOME_TRIGGER_ENTITY] = None
        config[RUNTIME_GPS_NOT_HOME_CONFIDENCE_HIGH_WATER] = 0
        return

    entity_id = event.data.get("entity_id")
    old_state = event.data.get("old_state")
    new_state = event.data.get("new_state")

    if not isinstance(entity_id, str) or old_state is None or new_state is None:
        return

    old_normalized = normalize_location_state(old_state.state)
    new_normalized = normalize_location_state(new_state.state)
    gps_entities = set(config.get(CONF_GPS_ENTITIES, []))
    armed = config.get(RUNTIME_GPS_NOT_HOME_ARMED)
    if not isinstance(armed, set):
        armed = set()
        config[RUNTIME_GPS_NOT_HOME_ARMED] = armed

    # A fresh positive Home transition must remain able to restore Home using
    # the existing HALP! rules, even if an earlier GPS sequence forced Away.
    if new_normalized == LOCATION_HOME and old_normalized != LOCATION_HOME:
        config[RUNTIME_GPS_NOT_HOME_PRIORITY_ACTIVE] = False
        config[RUNTIME_GPS_NOT_HOME_TRIGGER_ENTITY] = None
        config[RUNTIME_GPS_NOT_HOME_CONFIDENCE_HIGH_WATER] = 0
        armed.clear()
        return

    if entity_id in gps_entities:
        if old_normalized == LOCATION_HOME and new_normalized == LOCATION_NOT_HOME:
            # Reconstruct the pre-event vote by analyzing current sources and
            # substituting this GPS entity's previous Home state.
            results = analyze_sources(hass, config)
            for result in results:
                if result.entity_id == entity_id:
                    result.raw_state = old_state.state
                    result.normalized_state = old_normalized
                    result.usable = True
                result.prioritize_second_gps_not_home_active = False
                result.gps_priority_confidence_floor = 0

            if calculate_vetted_location(results) == LOCATION_HOME:
                armed.add(entity_id)
            else:
                armed.discard(entity_id)

        elif (
            entity_id in armed
            and old_normalized == LOCATION_NOT_HOME
            and new_normalized == LOCATION_NOT_HOME
        ):
            config[RUNTIME_GPS_NOT_HOME_PRIORITY_ACTIVE] = True
            config[RUNTIME_GPS_NOT_HOME_TRIGGER_ENTITY] = entity_id
            config[RUNTIME_GPS_NOT_HOME_CONFIDENCE_HIGH_WATER] = (
                GPS_NOT_HOME_PRIORITY_CONFIDENCE_FLOOR
            )
            armed.discard(entity_id)

        elif new_normalized != LOCATION_NOT_HOME:
            armed.discard(entity_id)

    if config.get(RUNTIME_GPS_NOT_HOME_PRIORITY_ACTIVE, False):
        # Preserve a non-decreasing confidence value while the temporary
        # fast-departure override remains active.
        current_results = analyze_sources(hass, config)
        base_confidence = calculate_base_confidence(
            current_results,
            LOCATION_NOT_HOME,
        )
        current_high_water = int(
            config.get(
                RUNTIME_GPS_NOT_HOME_CONFIDENCE_HIGH_WATER,
                GPS_NOT_HOME_PRIORITY_CONFIDENCE_FLOOR,
            )
        )
        config[RUNTIME_GPS_NOT_HOME_CONFIDENCE_HIGH_WATER] = max(
            GPS_NOT_HOME_PRIORITY_CONFIDENCE_FLOOR,
            current_high_water,
            base_confidence,
        )

        # Once ordinary weighted voting independently says not_home, the
        # temporary override and its high-water mark are no longer needed.
        ordinary_results = analyze_sources(hass, config)
        for result in ordinary_results:
            result.prioritize_second_gps_not_home_active = False
            result.gps_priority_confidence_floor = 0

        if calculate_vetted_location(ordinary_results) == LOCATION_NOT_HOME:
            config[RUNTIME_GPS_NOT_HOME_PRIORITY_ACTIVE] = False
            config[RUNTIME_GPS_NOT_HOME_TRIGGER_ENTITY] = None
            config[RUNTIME_GPS_NOT_HOME_CONFIDENCE_HIGH_WATER] = 0


async def _async_check_tracker_mismatch(
    hass: HomeAssistant,
    entry: ConfigEntry,
    config: dict[str, Any],
) -> None:
    """Create a notification if Person trackers and HALP trackers differ."""
    person_entity = config.get(CONF_PERSON_ENTITY)
    if not isinstance(person_entity, str):
        return

    person_trackers = set(await _async_assigned_trackers_for_person(hass, person_entity))
    halp_location_trackers = set(_configured_location_trackers(config))
    ignored_trackers = set(_configured_ignored_trackers(config))

    # Ignore is intentionally different from Other.
    #
    # Location trackers are scored by HALP!.
    # Ignored trackers are not scored, but they are considered accounted for
    # when checking whether the Home Assistant Person still has extra assigned
    # trackers. This lets a user keep a tracker assigned to the Person while
    # deliberately excluding it from HALP! without receiving a mismatch warning.
    #
    # Other trackers are not included here. Other means "not a HALP location
    # source," but it does not suppress mismatch warnings.
    accounted_trackers = halp_location_trackers | ignored_trackers

    person_only = sorted(person_trackers - accounted_trackers)
    halp_only = sorted(halp_location_trackers - person_trackers)

    if not person_only and not halp_only:
        await _async_dismiss_tracker_mismatch_notification(hass, entry)
        return

    title = f"HALP! tracker mismatch for {entry.title}"

    message_parts = [
        "HALP! detected that this entry's configured trackers do not match "
        "the trackers currently assigned to the Home Assistant Person entity.",
        "",
        f"Person entity: `{person_entity}`",
        "",
    ]

    if person_only:
        message_parts.append("Trackers assigned to the Person but not used or ignored by HALP!:")
        message_parts.extend([f"- `{tracker}`" for tracker in person_only])
        message_parts.append("")

    if halp_only:
        message_parts.append("Trackers used by HALP! but not assigned to the Person:")
        message_parts.extend([f"- `{tracker}`" for tracker in halp_only])
        message_parts.append("")

    message_parts.append(
        "Open the HALP! integration entry and choose Configure to update "
        "the tracker assignments. Use Ignore for assigned Person trackers "
        "that should be intentionally excluded from HALP! analysis."
    )

    await hass.services.async_call(
        "persistent_notification",
        "create",
        {
            "title": title,
            "message": "\n".join(message_parts),
            "notification_id": _tracker_mismatch_notification_id(entry),
        },
        blocking=False,
    )


def _configured_location_trackers(config: dict[str, Any]) -> list[str]:
    """Return the device trackers configured as HALP! location sources."""
    trackers: list[str] = []

    for key in (CONF_GPS_ENTITIES, CONF_BLE_ENTITIES, CONF_ROUTER_ENTITIES):
        value = config.get(key, [])
        if isinstance(value, list):
            trackers.extend(
                tracker
                for tracker in value
                if isinstance(tracker, str) and tracker.startswith("device_tracker.")
            )

    return sorted(set(trackers))


def _configured_ignored_trackers(config: dict[str, Any]) -> list[str]:
    """Return device trackers intentionally ignored by HALP!."""
    value = config.get(CONF_IGNORED_ENTITIES, [])

    if not isinstance(value, list):
        return []

    return sorted(
        set(
            tracker
            for tracker in value
            if isinstance(tracker, str) and tracker.startswith("device_tracker.")
        )
    )


async def _async_assigned_trackers_for_person(
    hass: HomeAssistant,
    person_entity: str,
) -> list[str]:
    """Read the Person storage file and return assigned device_trackers."""
    registry = er.async_get(hass)
    person_registry_entry = registry.async_get(person_entity)

    if person_registry_entry is None:
        return []

    person_unique_id = person_registry_entry.unique_id

    store = Store(hass, PERSON_STORAGE_VERSION, PERSON_STORAGE_KEY)
    stored = await store.async_load()

    if not isinstance(stored, dict):
        return []

    items = stored.get("items", [])
    if not isinstance(items, list):
        items = stored.get("data", {}).get("items", [])

    if not isinstance(items, list):
        return []

    for item in items:
        if not isinstance(item, dict):
            continue

        if item.get("id") != person_unique_id:
            continue

        trackers = item.get("device_trackers", [])
        if not isinstance(trackers, list):
            return []

        return [
            tracker
            for tracker in trackers
            if isinstance(tracker, str) and tracker.startswith("device_tracker.")
        ]

    return []


async def _async_dismiss_tracker_mismatch_notification(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> None:
    """Dismiss an old mismatch notification when the entry is healthy again."""
    await hass.services.async_call(
        "persistent_notification",
        "dismiss",
        {
            "notification_id": _tracker_mismatch_notification_id(entry),
        },
        blocking=False,
    )


def _tracker_mismatch_notification_id(entry: ConfigEntry) -> str:
    """Return the stable persistent notification ID for one entry."""
    return f"{DOMAIN}_tracker_mismatch_{entry.entry_id}"


async def _async_update_fast_departure_review_notification(
    hass: HomeAssistant,
    entry: ConfigEntry,
    config: dict[str, Any],
) -> None:
    """Require upgraded entries to review the new GPS departure option."""
    reviewed = bool(
        config.get(CONF_PRIORITIZE_SECOND_GPS_NOT_HOME_REVIEWED, False)
    )
    notification_id = _fast_departure_review_notification_id(entry)

    if reviewed:
        await hass.services.async_call(
            "persistent_notification",
            "dismiss",
            {"notification_id": notification_id},
            blocking=False,
        )
        return

    await hass.services.async_call(
        "persistent_notification",
        "create",
        {
            "title": f"HALP! configuration review required for {entry.title}",
            "message": (
                "HALP! added the option **Speed up 'not_home' transition: "
                "prioritize second 'not_home' GPS update.**\n\n"
                "For existing HALP! entries, this option remains disabled until "
                "you review it. Open **Settings → Devices & services → HALP!**, "
                "choose **Configure** for this person, select the setting you "
                "want, and save the configuration.\n\n"
                "This notification will be recreated until the Configure flow "
                "has been saved."
            ),
            "notification_id": notification_id,
        },
        blocking=False,
    )


def _fast_departure_review_notification_id(entry: ConfigEntry) -> str:
    """Return the stable review-notification ID for one entry."""
    return f"{DOMAIN}_fast_departure_review_{entry.entry_id}"


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload HALP! when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a HALP! config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)

    return unload_ok