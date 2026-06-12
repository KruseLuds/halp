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
    CONF_BLE_WEIGHT,
    CONF_GPS_ENTITIES,
    CONF_GPS_WEIGHT,
    CONF_PERSON_ENTITY,
    CONF_PERSON_UNIQUE_ID,
    CONF_ROUTER_ENTITIES,
    CONF_ROUTER_WEIGHT,
    DEFAULT_BLE_WEIGHT,
    DEFAULT_GPS_WEIGHT,
    DEFAULT_ROUTER_WEIGHT,
    FRESHNESS_EXCELLENT_MINUTES,
    FRESHNESS_FAIR_MINUTES,
    FRESHNESS_GOOD_MINUTES,
    FRESHNESS_POOR_MINUTES,
    LOCATION_AWAY,
    LOCATION_HOME,
    LOCATION_MISSING,
    LOCATION_UNAVAILABLE,
    LOCATION_UNKNOWN,
    SOURCE_TYPE_BLE,
    SOURCE_TYPE_GPS,
    SOURCE_TYPE_NAMES,
    SOURCE_TYPE_ROUTER,
)


@dataclass(slots=True)
class SourceResult:
    """Calculated status for one configured location source.

    One SourceResult represents one configured tracker, such as one GPS tracker,
    one BLE tracker, or one router tracker.

    HALP! keeps both raw and normalized states:
    - raw_state is what Home Assistant reports.
    - normalized_state is HALP!'s simplified home/away/unknown style value.
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

    Home Assistant trackers may report:
    - home
    - not_home
    - unavailable
    - unknown
    - named zones

    For the first version, HALP! treats home and away as the main reliable
    states. Named zones are preserved so they can be improved later.
    """
    if raw_state == LOCATION_HOME:
        return LOCATION_HOME

    if raw_state in ("not_home", LOCATION_AWAY):
        return LOCATION_AWAY

    if raw_state == LOCATION_UNKNOWN:
        return LOCATION_UNKNOWN

    if raw_state == LOCATION_UNAVAILABLE:
        return LOCATION_UNAVAILABLE

    if raw_state == LOCATION_MISSING:
        return LOCATION_MISSING

    return raw_state


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
    """Analyze all configured location sources.

    This is the main entry point for current-state analysis.

    It does not decide the final location by itself. Instead, it builds a list
    of SourceResult objects that other functions can use to calculate:
    - vetted location
    - confidence
    - consensus
    - source health
    - explanations
    """
    results: list[SourceResult] = []

    for source_type, entity_id in iter_configured_sources(config):
        raw_state = get_state(hass, entity_id)
        normalized = normalize_location_state(raw_state)
        updated_minutes = minutes_since_updated(hass, entity_id)
        changed_minutes = minutes_since_changed(hass, entity_id)
        factor = freshness_factor(updated_minutes)
        weight = source_weight(config, source_type)

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
                usable=normalized in (LOCATION_HOME, LOCATION_AWAY) and factor > 0,
            )
        )

    return results


def calculate_vetted_location(results: list[SourceResult]) -> str:
    """Calculate HALP!'s best current location conclusion.

    This is a weighted vote between usable home evidence and usable away
    evidence. Unusable, missing, unknown, and very stale sources do not vote.
    """
    home_score = 0.0
    away_score = 0.0

    for result in results:
        if not result.usable:
            continue

        score = result.weight * result.freshness_factor

        if result.normalized_state == LOCATION_HOME:
            home_score += score
        elif result.normalized_state == LOCATION_AWAY:
            away_score += score

    if home_score == 0 and away_score == 0:
        return LOCATION_UNKNOWN

    return LOCATION_HOME if home_score >= away_score else LOCATION_AWAY


def calculate_confidence(results: list[SourceResult], vetted_location: str) -> int:
    """Calculate confidence for the current vetted location.

    Philosophy:
    - Strong agreeing evidence should increase confidence.
    - Additional agreeing sources help, but not as much as the strongest source.
    - Conflicting fresh evidence reduces confidence.
    - Confidence is capped at 99 because location certainty is never perfect.
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
            if result.normalized_state in (LOCATION_HOME, LOCATION_AWAY)
            and not result.usable
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
    }