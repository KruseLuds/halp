"""Shared helper functions for HALP!.

This file contains the reusable analysis logic for HALP!.

Important design rule:
No person-specific or installation-specific entity IDs belong here.
Everything must come from config entry data.

The sensors should mostly call functions in this file rather than each sensor
inventing its own scoring logic. That keeps HALP!'s behavior consistent.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from homeassistant.components.person import DOMAIN as PERSON_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_BLE_ENTITIES,
    CONF_BLE_ZONES,
    CONF_BLE_WEIGHT,
    CONF_GPS_ENTITIES,
    CONF_GPS_WEIGHT,
    CONF_PERSON_ENTITY,
    CONF_PERSON_UNIQUE_ID,
    CONF_PRIORITIZE_SECOND_GPS_NOT_HOME,
    CONF_ROUTER_ENTITIES,
    CONF_ROUTER_ZONES,
    CONF_ROUTER_WEIGHT,
    DEFAULT_BLE_WEIGHT,
    DEFAULT_GPS_WEIGHT,
    DEFAULT_ROUTER_WEIGHT,
    DEFAULT_PRIORITIZE_SECOND_GPS_NOT_HOME,
    GPS_NOT_HOME_PRIORITY_CONFIDENCE_FLOOR,
    FRESHNESS_EXCELLENT_MINUTES,
    FRESHNESS_FAIR_MINUTES,
    FRESHNESS_GOOD_MINUTES,
    FRESHNESS_POOR_MINUTES,
    LOCATION_NOT_HOME,
    LOCATION_HOME,
    LOCATION_MISSING,
    LOCATION_UNAVAILABLE,
    LOCATION_UNKNOWN,
    SOURCE_TYPE_BLE,
    SOURCE_TYPE_GPS,
    SOURCE_TYPE_NAMES,
    SOURCE_TYPE_ROUTER,
    RUNTIME_GPS_NOT_HOME_PRIORITY_ACTIVE,
    RUNTIME_GPS_PRIORITY_LOCATION,
    RUNTIME_GPS_NOT_HOME_CONFIDENCE_HIGH_WATER,
    ROUTER_ZONE_NONE_MOBILE,
)


@dataclass(slots=True)
class SourceResult:
    """Calculated status for one configured location source.

    One SourceResult represents one configured tracker, such as one GPS tracker,
    one BLE tracker, or one router tracker.

    HALP! keeps both raw and normalized states:
    - raw_state is what Home Assistant reports.
    - normalized_state is HALP!'s Home Assistant-compatible location value.
    """

    source_type: str
    source_type_name: str
    entity_id: str
    raw_state: str
    normalized_state: str
    weight: int
    freshness_factor: float
    last_updated_minutes: float
    last_changed_minutes: float
    usable: bool
    prioritize_second_gps_not_home_active: bool = False
    gps_priority_confidence_floor: int = 0
    gps_priority_location: str | None = None
    fixed_zone_entity_id: str | None = None


def resolve_person_entity_id(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> str | None:
    """Resolve the current Person entity ID for a HALP! config entry.

    HALP! stores both the readable Person entity ID and, when available, the
    registry unique ID. The unique ID gives us a more stable lookup if the
    entity ID is renamed later.

    If resolution fails, callers can mark the HALP! entities unavailable
    without crashing the whole integration.
    """
    stored_entity_id = entry.data.get(CONF_PERSON_ENTITY)
    stored_unique_id = entry.data.get(CONF_PERSON_UNIQUE_ID)

    registry = er.async_get(hass)

    if isinstance(stored_unique_id, str) and stored_unique_id:
        entity_id = registry.async_get_entity_id(
            PERSON_DOMAIN,
            PERSON_DOMAIN,
            stored_unique_id,
        )
        if entity_id:
            return entity_id

    if isinstance(stored_entity_id, str) and hass.states.get(stored_entity_id):
        return stored_entity_id

    return None


def get_state(hass: HomeAssistant, entity_id: str | None) -> str:
    """Return an entity state or 'missing' if the entity does not exist."""
    if not entity_id:
        return LOCATION_MISSING

    state = hass.states.get(entity_id)
    if state is None:
        return LOCATION_MISSING

    return state.state


def minutes_since_updated(hass: HomeAssistant, entity_id: str | None) -> float:
    """Return minutes since an entity last updated.

    last_updated answers:
    'When did this source last report anything?'

    HALP! uses this for freshness because a tracker can remain in the same
    state for a long time but still be actively reporting updates.
    """
    if not entity_id:
        return 999999.0

    state = hass.states.get(entity_id)
    if state is None:
        return 999999.0

    return max(0.0, (datetime.now(timezone.utc) - state.last_updated).total_seconds() / 60)


def minutes_since_changed(hass: HomeAssistant, entity_id: str | None) -> float:
    """Return minutes since an entity last changed state.

    last_changed answers:
    'How long has this source been saying the same thing?'

    HALP! uses this for explanation and diagnostics, not freshness.
    """
    if not entity_id:
        return 999999.0

    state = hass.states.get(entity_id)
    if state is None:
        return 999999.0

    return max(0.0, (datetime.now(timezone.utc) - state.last_changed).total_seconds() / 60)


def format_age(minutes: float) -> str:
    """Return a compact human-readable age string for attributes/explanations."""
    if minutes >= 999999:
        return "missing"
    if minutes < 1:
        return "less than 1 min"
    if minutes < 60:
        return f"{round(minutes)} min"
    if minutes < 1440:
        return f"{round(minutes / 60, 1)} hr"
    return f"{round(minutes / 1440, 1)} days"


def normalize_location_state(raw_state: str) -> str:
    """Normalize common Home Assistant location states.

    Home Assistant GPS-capable trackers may report ``home``, ``not_home``, or
    the name of any configured zone. Named zones are deliberately preserved.
    Legacy ``away`` is normalized to Home Assistant's native ``not_home``.
    """
    if raw_state == LOCATION_HOME:
        return LOCATION_HOME
    if raw_state in ("away", LOCATION_NOT_HOME):
        return LOCATION_NOT_HOME
    if raw_state == LOCATION_UNKNOWN:
        return LOCATION_UNKNOWN
    if raw_state == LOCATION_UNAVAILABLE:
        return LOCATION_UNAVAILABLE
    if raw_state == LOCATION_MISSING:
        return LOCATION_MISSING
    return raw_state


def is_valid_location_state(value: str) -> bool:
    """Return whether a normalized value can represent a real location."""
    return value not in (LOCATION_UNKNOWN, LOCATION_UNAVAILABLE, LOCATION_MISSING, "")


def zone_location_state(hass: HomeAssistant, zone_entity_id: str | None) -> str | None:
    """Return the Home Assistant location state represented by a zone entity.

    The Home zone uses the special state ``home``. Other zones use their
    friendly name, matching the state vocabulary produced by GPS trackers.
    Passive zones are not accepted as fixed HALP! voting locations.
    """
    if not zone_entity_id or zone_entity_id == ROUTER_ZONE_NONE_MOBILE:
        return None
    state = hass.states.get(zone_entity_id)
    if state is None or not zone_entity_id.startswith("zone."):
        return None
    if bool(state.attributes.get("passive", False)):
        return None
    if zone_entity_id == "zone.home":
        return LOCATION_HOME
    friendly_name = state.attributes.get("friendly_name")
    if isinstance(friendly_name, str) and friendly_name:
        return friendly_name
    return zone_entity_id.split(".", 1)[1]


def canonical_dynamic_location_state(hass: HomeAssistant, raw_state: str) -> str:
    """Canonicalize a dynamic tracker state against current active HA zones."""
    normalized = normalize_location_state(raw_state)
    if not is_valid_location_state(normalized) or normalized in (LOCATION_HOME, LOCATION_NOT_HOME):
        return normalized

    folded = normalized.casefold()
    for state in hass.states.async_all("zone"):
        if bool(state.attributes.get("passive", False)):
            continue
        entity_id = state.entity_id
        friendly_name = state.attributes.get("friendly_name")
        object_id = entity_id.split(".", 1)[1] if "." in entity_id else entity_id
        candidates = [object_id]
        if isinstance(friendly_name, str):
            candidates.append(friendly_name)
        if any(folded == candidate.casefold() for candidate in candidates):
            return zone_location_state(hass, entity_id) or normalized
    return normalized

def freshness_factor(age_minutes: float) -> float:
    """Convert source age into a confidence multiplier.

    A fresh source receives full strength.
    A stale source gradually loses voting strength.
    A very stale source contributes nothing to the current decision.
    """
    if age_minutes <= FRESHNESS_EXCELLENT_MINUTES:
        return 1.0
    if age_minutes <= FRESHNESS_GOOD_MINUTES:
        return 0.9
    if age_minutes <= FRESHNESS_FAIR_MINUTES:
        return 0.75
    if age_minutes <= FRESHNESS_POOR_MINUTES:
        return 0.5
    return 0.0


def source_weight(config: dict[str, Any], source_type: str) -> int:
    """Return configured voting weight for a source type.

    Source weight is not a percentage. It is voting strength.

    Example:
    - GPS weight 100
    - BLE weight 70
    - Router weight 55

    This means fresh GPS evidence has more influence than fresh BLE or router
    evidence, unless the user changes the weights in Configure.
    """
    if source_type == SOURCE_TYPE_GPS:
        value = config.get(CONF_GPS_WEIGHT, DEFAULT_GPS_WEIGHT)
    elif source_type == SOURCE_TYPE_BLE:
        value = config.get(CONF_BLE_WEIGHT, DEFAULT_BLE_WEIGHT)
    elif source_type == SOURCE_TYPE_ROUTER:
        value = config.get(CONF_ROUTER_WEIGHT, DEFAULT_ROUTER_WEIGHT)
    else:
        value = 50

    try:
        return int(value)
    except (TypeError, ValueError):
        return 50


def iter_configured_sources(config: dict[str, Any]) -> list[tuple[str, str]]:
    """Return all configured primary location sources.

    The config model supports multiple entities per source type:
    - zero or more GPS entities
    - zero or more BLE entities
    - zero or more router/WiFi entities
    """
    sources: list[tuple[str, str]] = []

    for entity_id in config.get(CONF_GPS_ENTITIES, []):
        sources.append((SOURCE_TYPE_GPS, entity_id))

    for entity_id in config.get(CONF_BLE_ENTITIES, []):
        sources.append((SOURCE_TYPE_BLE, entity_id))

    for entity_id in config.get(CONF_ROUTER_ENTITIES, []):
        sources.append((SOURCE_TYPE_ROUTER, entity_id))

    return sources


def analyze_sources(hass: HomeAssistant, config: dict[str, Any]) -> list[SourceResult]:
    """Analyze all configured location sources for multi-zone voting.

    GPS is dynamic and may vote for any active Home Assistant zone or
    ``not_home``. BLE is fixed to exactly one configured zone per tracker.
    Router/WiFi is fixed to one zone unless explicitly configured as
    None/Mobile, in which case its Home Assistant state is treated dynamically.

    A fixed source's positive detection is strong location evidence. Its
    ``not_home`` state only means that the device is not detected by that fixed
    source, so it does not vote for the global ``not_home`` location.
    """
    results: list[SourceResult] = []
    ble_zones = config.get(CONF_BLE_ZONES, {})
    if not isinstance(ble_zones, dict):
        ble_zones = {}
    router_zones = config.get(CONF_ROUTER_ZONES, {})
    if not isinstance(router_zones, dict):
        router_zones = {}

    priority_active = bool(config.get(RUNTIME_GPS_NOT_HOME_PRIORITY_ACTIVE, False))
    priority_location = config.get(RUNTIME_GPS_PRIORITY_LOCATION)
    if not isinstance(priority_location, str) or not is_valid_location_state(priority_location):
        priority_location = None

    for source_type, entity_id in iter_configured_sources(config):
        raw_state = get_state(hass, entity_id)
        raw_normalized = canonical_dynamic_location_state(hass, raw_state)
        updated_minutes = minutes_since_updated(hass, entity_id)
        changed_minutes = minutes_since_changed(hass, entity_id)
        factor = freshness_factor(updated_minutes)
        weight = source_weight(config, source_type)
        fixed_zone_entity_id: str | None = None
        usable = False
        normalized = raw_normalized

        if source_type == SOURCE_TYPE_GPS:
            usable = is_valid_location_state(normalized) and factor > 0

        elif source_type == SOURCE_TYPE_BLE:
            configured_zone = ble_zones.get(entity_id, "zone.home")
            fixed_zone_entity_id = configured_zone if isinstance(configured_zone, str) else "zone.home"
            fixed_location = zone_location_state(hass, fixed_zone_entity_id)
            if raw_normalized not in (LOCATION_NOT_HOME, LOCATION_UNKNOWN, LOCATION_UNAVAILABLE, LOCATION_MISSING):
                if fixed_location is not None:
                    normalized = fixed_location
                    usable = factor > 0
            else:
                normalized = raw_normalized

        elif source_type == SOURCE_TYPE_ROUTER:
            configured_zone = router_zones.get(entity_id, "zone.home")
            fixed_zone_entity_id = configured_zone if isinstance(configured_zone, str) else "zone.home"
            if fixed_zone_entity_id == ROUTER_ZONE_NONE_MOBILE:
                # A mobile/unassigned router can confirm connectivity but not an
                # absolute geographic zone, so it remains visible in diagnostics
                # without voting for location.
                fixed_zone_entity_id = None
                usable = False
            else:
                fixed_location = zone_location_state(hass, fixed_zone_entity_id)
                if raw_normalized not in (LOCATION_NOT_HOME, LOCATION_UNKNOWN, LOCATION_UNAVAILABLE, LOCATION_MISSING):
                    if fixed_location is not None:
                        normalized = fixed_location
                        usable = factor > 0
                else:
                    normalized = raw_normalized

        results.append(
            SourceResult(
                source_type=source_type,
                source_type_name=SOURCE_TYPE_NAMES.get(source_type, source_type),
                entity_id=entity_id,
                raw_state=raw_state,
                normalized_state=normalized,
                weight=weight,
                freshness_factor=factor,
                last_updated_minutes=updated_minutes,
                last_changed_minutes=changed_minutes,
                usable=usable,
                prioritize_second_gps_not_home_active=(
                    bool(config.get(CONF_PRIORITIZE_SECOND_GPS_NOT_HOME, DEFAULT_PRIORITIZE_SECOND_GPS_NOT_HOME))
                    and priority_active
                ),
                gps_priority_confidence_floor=(
                    int(config.get(RUNTIME_GPS_NOT_HOME_CONFIDENCE_HIGH_WATER, GPS_NOT_HOME_PRIORITY_CONFIDENCE_FLOOR))
                    if priority_active else 0
                ),
                gps_priority_location=priority_location if priority_active else None,
                fixed_zone_entity_id=fixed_zone_entity_id,
            )
        )

    return results


def calculate_vetted_location(results: list[SourceResult]) -> str:
    """Calculate HALP!'s best current location across any number of zones."""
    for result in results:
        if result.prioritize_second_gps_not_home_active and result.gps_priority_location:
            return result.gps_priority_location

    scores: dict[str, float] = {}
    for result in results:
        if not result.usable or not is_valid_location_state(result.normalized_state):
            continue
        scores[result.normalized_state] = scores.get(result.normalized_state, 0.0) + (
            result.weight * result.freshness_factor
        )

    if not scores:
        return LOCATION_UNKNOWN

    highest = max(scores.values())
    leaders = [location for location, score in scores.items() if score == highest]
    if len(leaders) == 1:
        return leaders[0]

    # Preserve the original safety bias toward Home when Home is tied. For a
    # tie between two non-Home locations, do not invent an arbitrary winner.
    if LOCATION_HOME in leaders:
        return LOCATION_HOME
    return LOCATION_UNKNOWN

def calculate_base_confidence(
    results: list[SourceResult],
    vetted_location: str,
) -> int:
    """Calculate confidence from ordinary weighted source evidence.

    This function intentionally ignores the optional GPS fast-transition
    confidence floor. It is useful for diagnostics and for maintaining the
    temporary confidence high-water mark while that rule is active.
    """
    if vetted_location == LOCATION_UNKNOWN:
        return 0

    agree = 0.0
    conflict = 0.0
    strongest = 0.0

    for result in results:
        if not result.usable:
            continue

        score = result.weight * result.freshness_factor

        if result.normalized_state == vetted_location:
            agree += score
            strongest = max(strongest, score)
        else:
            conflict += score

    raw = strongest + ((agree - strongest) * 0.25) - (conflict * 0.4)

    return int(max(0, min(99, round(raw))))


def calculate_confidence(results: list[SourceResult], vetted_location: str) -> int:
    """Calculate confidence for the current vetted location.

    Ordinary confidence is based on weighted agreeing and conflicting evidence.

    When the optional second-matching-GPS-update rule is actively prioritizing
    a newly confirmed location, HALP! applies a temporary confidence floor. The
    floor starts at 80 percent because two consecutive matching GPS location
    updates are deliberate evidence even while slower fixed sources lag.

    The runtime listener maintains a high-water mark so confidence can rise as
    other sources agree, but cannot fall while the temporary GPS-priority state
    remains active.
    """
    base_confidence = calculate_base_confidence(results, vetted_location)

    active_floors = [
        result.gps_priority_confidence_floor
        for result in results
        if result.prioritize_second_gps_not_home_active
    ]

    if active_floors and vetted_location != LOCATION_UNKNOWN:
        return max(
            base_confidence,
            GPS_NOT_HOME_PRIORITY_CONFIDENCE_FLOOR,
            max(active_floors),
        )

    return base_confidence


def calculate_consensus_score(
    results: list[SourceResult],
    vetted_location: str,
) -> int:
    """Calculate how strongly usable sources agree with the final decision.

    Consensus is different from confidence.

    Confidence asks:
    'How sure is HALP! about the final location?'

    Consensus asks:
    'How much do the usable sources agree with each other?'

    A setup can have high confidence but imperfect consensus if one weak source
    disagrees. A setup can also have high consensus but low confidence if only
    one weak source is usable.
    """
    if vetted_location == LOCATION_UNKNOWN:
        return 0

    usable_results = [result for result in results if result.usable]
    if not usable_results:
        return 0

    total_score = 0.0
    agreeing_score = 0.0

    for result in usable_results:
        score = result.weight * result.freshness_factor
        total_score += score

        if result.normalized_state == vetted_location:
            agreeing_score += score

    if total_score <= 0:
        return 0

    return int(max(0, min(100, round((agreeing_score / total_score) * 100))))


def calculate_source_health(
    results: list[SourceResult],
    vetted_location: str,
    confidence: int,
    consensus_score: int,
) -> str:
    """Return a simple health label for the current source set.

    Source Health is intentionally dashboard-friendly.

    It combines:
    - whether any usable sources exist
    - how many configured sources are stale or unavailable
    - whether usable sources are conflicting
    - how strong the final confidence is
    - how strong source consensus is

    This is not meant to replace the detailed attributes. It is a quick summary
    users can put on a dashboard.
    """
    total_count = len(results)
    usable_results = [result for result in results if result.usable]
    usable_count = len(usable_results)

    stale_count = len(
        [
            result
            for result in results
            if is_valid_location_state(result.normalized_state)
            and result.freshness_factor <= 0
        ]
    )

    missing_or_unknown_count = len(
        [
            result
            for result in results
            if result.normalized_state
            in (LOCATION_MISSING, LOCATION_UNAVAILABLE, LOCATION_UNKNOWN)
        ]
    )

    conflict_count = len(
        [
            result
            for result in usable_results
            if result.normalized_state != vetted_location
        ]
    )

    if total_count == 0 or usable_count == 0:
        return "Critical"

    if missing_or_unknown_count == total_count:
        return "Critical"

    if stale_count > total_count / 2:
        return "Poor"

    if confidence < 40:
        return "Poor"

    if conflict_count >= 2:
        return "Fair"

    if consensus_score < 70:
        return "Fair"

    if stale_count > 0 or missing_or_unknown_count > 0 or conflict_count == 1:
        return "Good"

    if confidence >= 80 and consensus_score >= 90:
        return "Excellent"

    return "Good"


def source_result_to_attribute(result: SourceResult) -> dict[str, Any]:
    """Convert a SourceResult into safe entity attributes.

    This keeps attributes consistent across all HALP! sensors.
    """
    return {
        "source_type": result.source_type,
        "source_type_name": result.source_type_name,
        "entity_id": result.entity_id,
        "state": result.raw_state,
        "normalized_state": result.normalized_state,
        "weight": result.weight,
        "freshness_factor": result.freshness_factor,
        "updated_minutes": round(result.last_updated_minutes, 2),
        "changed_minutes": round(result.last_changed_minutes, 2),
        "updated": format_age(result.last_updated_minutes),
        "unchanged": format_age(result.last_changed_minutes),
        "usable": result.usable,
        "gps_fast_transition_active": (
            result.prioritize_second_gps_not_home_active
        ),
        "gps_fast_departure_active": (
            result.prioritize_second_gps_not_home_active
        ),
        "gps_priority_location": result.gps_priority_location,
        "fixed_zone_entity_id": result.fixed_zone_entity_id,
    }