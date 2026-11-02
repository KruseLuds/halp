"""Set up HALP!."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.storage import Store

from .const import (
    CONF_BLE_ENTITIES,
    CONF_BLE_ZONES,
    CONF_GPS_ENTITIES,
    CONF_IGNORED_ENTITIES,
    CONF_IDLE_REFRESH_MINUTES,
    CONF_PERSON_ENTITY,
    CONF_PRIORITIZE_SECOND_GPS_NOT_HOME,
    CONF_PRIORITIZE_SECOND_GPS_NOT_HOME_REVIEWED,
    CONF_ROUTER_ENTITIES,
    CONF_ROUTER_ZONES,
    DEFAULT_PRIORITIZE_SECOND_GPS_NOT_HOME,
    DEFAULT_IDLE_REFRESH_MINUTES,
    GPS_NOT_HOME_PRIORITY_CONFIDENCE_FLOOR,
    DOMAIN,
    PLATFORMS,
    LOCATION_HOME,
    LOCATION_NOT_HOME,
    RUNTIME_GPS_NOT_HOME_ARMED,
    RUNTIME_GPS_TRANSITION_CANDIDATES,
    RUNTIME_GPS_TRANSITION_ORIGINS,
    RUNTIME_GPS_DEPARTED_ZONE_CONTEXTS,
    RUNTIME_FIXED_ARRIVAL_PRIORITY_ACTIVE,
    RUNTIME_FIXED_ARRIVAL_PRIORITY_LOCATION,
    RUNTIME_FIXED_ARRIVAL_PRIORITY_ENTITY,
    RUNTIME_GPS_NOT_HOME_CONFIDENCE_HIGH_WATER,
    RUNTIME_GPS_NOT_HOME_PRIORITY_ACTIVE,
    RUNTIME_GPS_NOT_HOME_TRIGGER_ENTITY,
    RUNTIME_GPS_PRIORITY_LOCATION,
    RUNTIME_HISTORY_REFRESH_CALLBACKS,
    RUNTIME_IDLE_REFRESH_CANCEL,
    RUNTIME_SENSOR_REFRESH_CALLBACKS,
    ROUTER_ZONE_NONE_MOBILE,
)
from .helpers import (
    analyze_sources,
    calculate_base_confidence,
    calculate_confidence,
    calculate_consensus_score,
    calculate_source_health,
    calculate_vetted_location,
    canonical_dynamic_location_state,
    is_valid_location_state,
    normalize_location_state,
    resolve_person_entity_id,
    zone_entity_id_for_location,
    zone_location_state,
)
from .history import async_record_history_sample
from .notifications import NotificationPublisher
from .zone_validation import invalid_fixed_zone_assignments

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

# Per-entry, in-memory notification state. Never store as ConfigEntry options.
RUNTIME_NOTIFICATION_PUBLISHER = "_notification_publisher"


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

    # Runtime-only state for the optional second matching GPS update rule.
    # These values are deliberately not persisted across reloads or restarts.
    config[RUNTIME_GPS_NOT_HOME_ARMED] = set()  # legacy compatibility only
    config[RUNTIME_GPS_TRANSITION_CANDIDATES] = {}
    config[RUNTIME_GPS_TRANSITION_ORIGINS] = {}
    config[RUNTIME_GPS_DEPARTED_ZONE_CONTEXTS] = {}
    config[RUNTIME_FIXED_ARRIVAL_PRIORITY_ACTIVE] = False
    config[RUNTIME_FIXED_ARRIVAL_PRIORITY_LOCATION] = None
    config[RUNTIME_FIXED_ARRIVAL_PRIORITY_ENTITY] = None
    config[RUNTIME_GPS_NOT_HOME_PRIORITY_ACTIVE] = False
    config[RUNTIME_GPS_NOT_HOME_TRIGGER_ENTITY] = None
    config[RUNTIME_GPS_PRIORITY_LOCATION] = None
    config[RUNTIME_GPS_NOT_HOME_CONFIDENCE_HIGH_WATER] = 0
    config[RUNTIME_SENSOR_REFRESH_CALLBACKS] = set()
    config[RUNTIME_HISTORY_REFRESH_CALLBACKS] = set()
    config[RUNTIME_IDLE_REFRESH_CANCEL] = None
    config[RUNTIME_NOTIFICATION_PUBLISHER] = NotificationPublisher(hass)

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
        await _async_check_fixed_zone_configuration(hass, entry, config)

    # Issue #4: the old inventory-mismatch warning was triggered by every
    # unrelated zone addition/removal. Retire it and clear any existing notice
    # once when an entry starts. Actual fixed-zone assignments are still checked.
    await config[RUNTIME_NOTIFICATION_PUBLISHER].async_dismiss(
        f"{DOMAIN}_zone_mismatch_{entry.entry_id}"
    )

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
        await _async_check_fixed_zone_configuration(hass, entry, current_config)
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

        await _async_refresh_registered_entities(
            current_config,
            RUNTIME_HISTORY_REFRESH_CALLBACKS,
        )

    # History sampling is idle-based, not an independent periodic poll.
    # Any relevant source event restarts this per-person timer, so a history
    # sample is written only after the person has had no source activity for
    # the full history interval.
    history_timer_key = "_halp_history_sample_cancel"
    history_generation_key = "_halp_history_sample_generation"
    config[history_generation_key] = 0

    def _cancel_history_sample() -> None:
        cancel = config.get(history_timer_key)
        if callable(cancel):
            cancel()
        config[history_timer_key] = None

    def _schedule_history_sample() -> None:
        # Advance a generation on every reset.  Cancellation normally removes the
        # old callback, but the generation guard also makes an already-dispatched
        # callback harmless if a source event arrives at the timer boundary.
        _cancel_history_sample()
        generation = int(config.get(history_generation_key, 0)) + 1
        config[history_generation_key] = generation

        async def _async_idle_history_sample(now) -> None:
            current_config = hass.data.get(DOMAIN, {}).get(entry.entry_id)
            if not isinstance(current_config, dict):
                return

            if current_config.get(history_generation_key) != generation:
                return

            current_config[history_timer_key] = None
            await record_history_sample(now)

            # If the entry remains quiet, take another sample after another
            # complete history interval. Any source event will invalidate this
            # generation and restart the full interval immediately.
            _schedule_history_sample()

        config[history_timer_key] = async_call_later(
            hass,
            HISTORY_SAMPLE_INTERVAL,
            _async_idle_history_sample,
        )

    _schedule_history_sample()
    entry.async_on_unload(_cancel_history_sample)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Listen to every scored tracker. The existing transition handler preserves
    # HALP!'s GPS/fixed-source behavior, then the same event drives an immediate
    # refresh of the current-state HALP! sensors and resets the idle timer.
    tracked_entities = _configured_location_trackers(config)
    if tracked_entities:
        async def _async_location_source_event(event: Event) -> None:
            """Process one source event and refresh HALP! immediately."""
            # Reset history at the instant source activity is observed, before
            # awaiting any processing. Otherwise a history timer due a second
            # later can fire while this event is still being handled.
            _schedule_history_sample()

            await _async_handle_location_source_event(
                hass,
                entry,
                event,
            )

            current_config = hass.data.get(DOMAIN, {}).get(entry.entry_id)
            if not isinstance(current_config, dict):
                return

            await _async_refresh_registered_entities(
                current_config,
                RUNTIME_SENSOR_REFRESH_CALLBACKS,
            )
            _schedule_idle_refresh(hass, entry, current_config)

        entry.async_on_unload(
            async_track_state_change_event(
                hass,
                tracked_entities,
                _async_location_source_event,
            )
        )

    # Start the one-shot idle timer even before the first source event so a
    # completely quiet tracker set still gets freshness reevaluation.
    _schedule_idle_refresh(hass, entry, config)
    entry.async_on_unload(lambda: _cancel_idle_refresh(config))

    return True


async def _async_refresh_registered_entities(
    config: dict[str, Any],
    registry_key: str,
) -> None:
    """Refresh entities registered for one HALP! refresh group."""
    callbacks = config.get(registry_key)
    if not isinstance(callbacks, set):
        return

    for refresh_callback in list(callbacks):
        await refresh_callback()


def _cancel_idle_refresh(config: dict[str, Any]) -> None:
    """Cancel the active idle refresh timer for one HALP! entry."""
    cancel = config.get(RUNTIME_IDLE_REFRESH_CANCEL)
    if callable(cancel):
        cancel()
    config[RUNTIME_IDLE_REFRESH_CANCEL] = None


def _schedule_idle_refresh(
    hass: HomeAssistant,
    entry: ConfigEntry,
    config: dict[str, Any],
) -> None:
    """Reset the per-entry idle freshness reevaluation timer."""
    cancel = config.get(RUNTIME_IDLE_REFRESH_CANCEL)
    if callable(cancel):
        cancel()

    try:
        idle_minutes = int(
            config.get(CONF_IDLE_REFRESH_MINUTES, DEFAULT_IDLE_REFRESH_MINUTES)
        )
    except (TypeError, ValueError):
        idle_minutes = DEFAULT_IDLE_REFRESH_MINUTES

    idle_minutes = max(1, idle_minutes)

    async def _async_idle_refresh(now) -> None:
        current_config = hass.data.get(DOMAIN, {}).get(entry.entry_id)
        if not isinstance(current_config, dict):
            return

        current_config[RUNTIME_IDLE_REFRESH_CANCEL] = None

        if not current_config.get("person_missing", False):
            await _async_refresh_registered_entities(
                current_config,
                RUNTIME_SENSOR_REFRESH_CALLBACKS,
            )

        # Stay quiet while sources are active, but continue reevaluating
        # freshness at the configured cadence for as long as the entry is idle.
        _schedule_idle_refresh(hass, entry, current_config)

    cancel = async_call_later(
        hass,
        timedelta(minutes=idle_minutes),
        _async_idle_refresh,
    )
    config[RUNTIME_IDLE_REFRESH_CANCEL] = cancel


async def _async_handle_location_source_event(
    hass: HomeAssistant,
    entry: ConfigEntry,
    event: Event,
) -> None:
    """Handle fixed-source arrivals and the optional GPS transition rule.

    A real fixed BLE/router transition from ``not_home`` to positive presence
    is fresh arrival evidence. HALP! temporarily prioritizes that fixed Zone
    until GPS publishes its next update.

    Separately, the existing optional second-matching-GPS rule confirms a GPS
    transition. When that confirmation proves departure from a concrete Zone,
    HALP! remembers the departure at runtime so old fixed evidence from that
    Zone cannot later create a geographically impossible snap-back.
    """
    config = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if not isinstance(config, dict):
        return

    entity_id = event.data.get("entity_id")
    old_state = event.data.get("old_state")
    new_state = event.data.get("new_state")
    if not isinstance(entity_id, str) or old_state is None or new_state is None:
        return

    gps_entities = set(config.get(CONF_GPS_ENTITIES, []))
    ble_entities = set(config.get(CONF_BLE_ENTITIES, []))
    router_entities = set(config.get(CONF_ROUTER_ENTITIES, []))

    def clear_gps_priority() -> None:
        config[RUNTIME_GPS_NOT_HOME_PRIORITY_ACTIVE] = False
        config[RUNTIME_GPS_NOT_HOME_TRIGGER_ENTITY] = None
        config[RUNTIME_GPS_PRIORITY_LOCATION] = None
        config[RUNTIME_GPS_NOT_HOME_CONFIDENCE_HIGH_WATER] = 0

    def clear_fixed_arrival_priority() -> None:
        config[RUNTIME_FIXED_ARRIVAL_PRIORITY_ACTIVE] = False
        config[RUNTIME_FIXED_ARRIVAL_PRIORITY_LOCATION] = None
        config[RUNTIME_FIXED_ARRIVAL_PRIORITY_ENTITY] = None

    # Fixed-source positive arrival is intentionally independent of the GPS
    # speedup switch. A genuine not_home -> positive transition is new arrival
    # evidence, not a continuation of an old sticky fixed-location state.
    if entity_id in ble_entities or entity_id in router_entities:
        if entity_id in ble_entities:
            zone_map = config.get(CONF_BLE_ZONES, {})
        else:
            zone_map = config.get(CONF_ROUTER_ZONES, {})

        if not isinstance(zone_map, dict):
            zone_map = {}

        zone_entity_id = zone_map.get(entity_id, "zone.home")
        if (
            not isinstance(zone_entity_id, str)
            or zone_entity_id == ROUTER_ZONE_NONE_MOBILE
        ):
            zone_entity_id = None

        old_normalized = normalize_location_state(old_state.state)
        new_normalized = normalize_location_state(new_state.state)
        new_is_positive = new_normalized not in (
            LOCATION_NOT_HOME,
            "unknown",
            "unavailable",
            "missing",
        )

        if (
            gps_entities
            and zone_entity_id is not None
            and old_normalized == LOCATION_NOT_HOME
            and new_is_positive
        ):
            fixed_location = zone_location_state(hass, zone_entity_id)
            if fixed_location is not None:
                config[RUNTIME_FIXED_ARRIVAL_PRIORITY_ACTIVE] = True
                config[RUNTIME_FIXED_ARRIVAL_PRIORITY_LOCATION] = fixed_location
                config[RUNTIME_FIXED_ARRIVAL_PRIORITY_ENTITY] = entity_id
            return

        if (
            config.get(RUNTIME_FIXED_ARRIVAL_PRIORITY_ACTIVE, False)
            and config.get(RUNTIME_FIXED_ARRIVAL_PRIORITY_ENTITY) == entity_id
            and not new_is_positive
        ):
            clear_fixed_arrival_priority()

        return

    if entity_id not in gps_entities:
        return

    # Any GPS update ends a temporary fixed-source arrival priority. The fixed
    # source remains normal positive evidence after that; only the temporary
    # "GPS has not updated yet" precedence ends here.
    clear_fixed_arrival_priority()

    old_location = canonical_dynamic_location_state(hass, old_state.state)
    new_location = canonical_dynamic_location_state(hass, new_state.state)

    # Re-entering a concrete Zone removes any older confirmed-departure context
    # for that Zone. A future departure must be confirmed again before old
    # fixed evidence can be geographically suppressed.
    departed_contexts = config.get(RUNTIME_GPS_DEPARTED_ZONE_CONTEXTS)
    if not isinstance(departed_contexts, dict):
        departed_contexts = {}
        config[RUNTIME_GPS_DEPARTED_ZONE_CONTEXTS] = departed_contexts

    entered_zone_entity_id = zone_entity_id_for_location(hass, new_location)
    if entered_zone_entity_id is not None:
        departed_contexts.pop(entered_zone_entity_id, None)

    if not bool(
        config.get(
            CONF_PRIORITIZE_SECOND_GPS_NOT_HOME,
            DEFAULT_PRIORITIZE_SECOND_GPS_NOT_HOME,
        )
    ):
        config[RUNTIME_GPS_TRANSITION_CANDIDATES] = {}
        config[RUNTIME_GPS_TRANSITION_ORIGINS] = {}
        config[RUNTIME_GPS_DEPARTED_ZONE_CONTEXTS] = {}
        config[RUNTIME_GPS_NOT_HOME_ARMED] = set()
        clear_gps_priority()
        return

    candidates = config.get(RUNTIME_GPS_TRANSITION_CANDIDATES)
    if not isinstance(candidates, dict):
        candidates = {}
        config[RUNTIME_GPS_TRANSITION_CANDIDATES] = candidates

    origins = config.get(RUNTIME_GPS_TRANSITION_ORIGINS)
    if not isinstance(origins, dict):
        origins = {}
        config[RUNTIME_GPS_TRANSITION_ORIGINS] = origins

    active_target = config.get(RUNTIME_GPS_PRIORITY_LOCATION)

    # If GPS itself moves away from an active priority target, that target is
    # no longer current. The separate departed-Zone context remains available
    # to prevent an older fixed source from resurrecting a Zone already proven
    # to have been left.
    if (
        config.get(RUNTIME_GPS_NOT_HOME_PRIORITY_ACTIVE, False)
        and isinstance(active_target, str)
        and new_location != active_target
    ):
        clear_gps_priority()

    if not is_valid_location_state(new_location):
        candidates.pop(entity_id, None)
        origins.pop(entity_id, None)
        return

    if old_location != new_location:
        # Reconstruct the ordinary vote immediately before this GPS transition.
        results = analyze_sources(hass, config)
        for result in results:
            result.prioritize_second_gps_not_home_active = False
            result.gps_priority_confidence_floor = 0
            result.gps_priority_location = None
            result.fixed_arrival_priority_active = False
            result.fixed_arrival_priority_location = None
            if result.entity_id == entity_id:
                result.raw_state = old_state.state
                result.normalized_state = old_location
                result.usable = is_valid_location_state(old_location)

        previous_vetted = calculate_vetted_location(results)

        # A new location different from the previously vetted result becomes
        # the candidate. Remember the Zone the GPS itself actually left so the
        # second matching update can confirm that departure.
        if new_location != previous_vetted:
            candidates[entity_id] = new_location
            origins[entity_id] = old_location
        else:
            candidates.pop(entity_id, None)
            origins.pop(entity_id, None)

    elif candidates.get(entity_id) == new_location:
        departed_location = origins.get(entity_id)
        departed_zone_entity_id = zone_entity_id_for_location(
            hass,
            departed_location,
        )

        # The second matching GPS update confirms departure. Record only a
        # concrete departed Zone. not_home is not itself a Zone that fixed
        # location sources can be assigned to.
        if (
            departed_zone_entity_id is not None
            and departed_location != new_location
        ):
            departed_contexts[departed_zone_entity_id] = {
                "gps_entity_id": entity_id,
                "confirmed_at": new_state.last_updated.timestamp(),
                "departed_location": departed_location,
                "confirmed_location": new_location,
            }

        config[RUNTIME_GPS_NOT_HOME_PRIORITY_ACTIVE] = True
        config[RUNTIME_GPS_NOT_HOME_TRIGGER_ENTITY] = entity_id
        config[RUNTIME_GPS_PRIORITY_LOCATION] = new_location
        config[RUNTIME_GPS_NOT_HOME_CONFIDENCE_HIGH_WATER] = (
            GPS_NOT_HOME_PRIORITY_CONFIDENCE_FLOOR
        )
        candidates.pop(entity_id, None)
        origins.pop(entity_id, None)

    if config.get(RUNTIME_GPS_NOT_HOME_PRIORITY_ACTIVE, False):
        target = config.get(RUNTIME_GPS_PRIORITY_LOCATION)
        if not isinstance(target, str) or not is_valid_location_state(target):
            clear_gps_priority()
            return

        current_results = analyze_sources(hass, config)
        base_confidence = calculate_base_confidence(current_results, target)
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

        ordinary_results = analyze_sources(hass, config)
        for result in ordinary_results:
            result.prioritize_second_gps_not_home_active = False
            result.gps_priority_confidence_floor = 0
            result.gps_priority_location = None
            result.fixed_arrival_priority_active = False
            result.fixed_arrival_priority_location = None

        if calculate_vetted_location(ordinary_results) == target:
            clear_gps_priority()


async def _async_check_fixed_zone_configuration(
    hass: HomeAssistant,
    entry: ConfigEntry,
    config: dict[str, Any],
) -> None:
    """Notify until every fixed BLE/router source has a valid zone mapping.

    v2.0.0 introduced explicit fixed-zone assignments. Existing HALP! entries
    therefore need to open Configure once after upgrade and assign each BLE
    tracker to exactly one active zone and each fixed WiFi/router tracker to
    exactly one active zone. A router source explicitly configured as
    None / Mobile is valid without a zone.

    Only *assigned* fixed zones matter here. Adding, renaming, or removing
    unrelated Home Assistant zones does not require reconfiguration.
    """
    active_zones = {
        state.entity_id
        for state in hass.states.async_all("zone")
        if not bool(state.attributes.get("passive", False))
    }

    missing_ble, missing_router = invalid_fixed_zone_assignments(
        config,
        active_zones,
        ble_entities_key=CONF_BLE_ENTITIES,
        router_entities_key=CONF_ROUTER_ENTITIES,
        ble_zones_key=CONF_BLE_ZONES,
        router_zones_key=CONF_ROUTER_ZONES,
        mobile_marker=ROUTER_ZONE_NONE_MOBILE,
    )

    notification_id = f"{DOMAIN}_fixed_zone_configuration_{entry.entry_id}"

    publisher = config[RUNTIME_NOTIFICATION_PUBLISHER]
    if not missing_ble and not missing_router:
        await publisher.async_dismiss(notification_id)
        return

    lines = [
        "HALP! multi-zone configuration is incomplete for this Person.",
        "Open Settings → Devices & services → HALP!, then click the gear icon for this Person to review/update the fixed-location zone assignments.",
        "GPS trackers do not need a zone assignment because Home Assistant reports their current zone dynamically.",
    ]
    if missing_ble:
        lines.append(
            "BLE trackers requiring exactly one active zone: "
            + ", ".join(sorted(missing_ble))
        )
    if missing_router:
        lines.append(
            "WiFi/router trackers requiring one active zone or None / Mobile: "
            + ", ".join(sorted(missing_router))
        )

    await publisher.async_publish(
        notification_id,
        f"HALP! zone assignment required for {entry.title}",
        "\n\n".join(lines),
    )


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
        await _async_dismiss_tracker_mismatch_notification(hass, entry, config)
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
        "Open Settings → Devices & services → HALP!, then click the gear icon "
        "for this Person to review/update the tracker assignments. Use Ignore "
        "for assigned Person trackers that should be intentionally excluded "
        "from HALP! analysis."
    )

    await config[RUNTIME_NOTIFICATION_PUBLISHER].async_publish(
        _tracker_mismatch_notification_id(entry),
        title,
        "\n".join(message_parts),
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
    config: dict[str, Any],
) -> None:
    """Clear a resolved mismatch notification only once."""
    await config[RUNTIME_NOTIFICATION_PUBLISHER].async_dismiss(
        _tracker_mismatch_notification_id(entry)
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

    publisher = config[RUNTIME_NOTIFICATION_PUBLISHER]
    if reviewed:
        await publisher.async_dismiss(notification_id)
        return

    await publisher.async_publish(
        notification_id,
        f"HALP! configuration review required for {entry.title}",
        (
            "HALP! added the option **Speed up location transitions: "
            "prioritize second matching GPS location update.**\n\n"
            "For existing HALP! entries, this option remains disabled until "
            "you review it. Open **Settings → Devices & services → HALP!**, "
            "then click the **gear icon for this Person**, review the setting "
            "you want, and save the configuration.\n\n"
            "This reminder clears after you save the Configure flow."
        ),
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