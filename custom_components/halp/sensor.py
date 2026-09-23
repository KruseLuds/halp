"""Sensor entities for HALP!.

Each HALP! config entry represents one Home Assistant Person analysis instance.

This file exposes HALP!'s current-state and recent-history sensors.

Current-state sensors answer questions such as:
- Where does HALP! think the person is?
- How confident is HALP!?
- Do the sources agree?
- Which trackers are usable, stale, missing, or conflicting?

History sensors answer questions such as:
- Is short-term history being recorded?
- How many samples have been collected?
- What are recent average confidence and consensus values?

No installation-specific person names or entity IDs belong in this file.
Everything is driven by config entry data.
"""

from __future__ import annotations

from datetime import datetime
import logging
import re
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from .history import async_get_entry_daily_summaries, async_get_entry_history

from .const import (
    CONF_BATTERY_LEVEL_ENTITY,
    CONF_BATTERY_STATE_ENTITY,
    CONF_BSSID_ENTITY,
    CONF_CONNECTION_TYPE_ENTITY,
    CONF_LOCATION_PERMISSION_ENTITY,
    CONF_PERSON_ENTITY,
    CONF_RELIABLE_THRESHOLD,
    CONF_SSID_ENTITY,
    DEFAULT_RELIABLE_THRESHOLD,
    DOMAIN,
    LOCATION_HOME,
    LOCATION_NOT_HOME,
    RUNTIME_GPS_NOT_HOME_PRIORITY_ACTIVE,
    RUNTIME_GPS_NOT_HOME_TRIGGER_ENTITY,
    RUNTIME_GPS_PRIORITY_LOCATION,
    RUNTIME_HISTORY_REFRESH_CALLBACKS,
    RUNTIME_SENSOR_REFRESH_CALLBACKS,
    NAME,
)
_LOGGER = logging.getLogger(__name__)

from .helpers import (
    analyze_sources,
    calculate_base_confidence,
    calculate_confidence,
    calculate_consensus_score,
    calculate_source_health,
    calculate_vetted_location,
    get_state,
    is_valid_location_state,
    source_result_to_attribute,
)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HALP! sensors from a config entry.

    One config entry represents one configured Person.
    Every configured Person gets the same set of HALP! sensors.
    """
    config = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            HalpVettedLocationSensor(hass, entry, config),
            HalpLocationConfidenceSensor(hass, entry, config),
            HalpConsensusScoreSensor(hass, entry, config),
            HalpSourceHealthSensor(hass, entry, config),
            HalpSourceDetailsSensor(hass, entry, config),
            HalpTrackerReliabilityTableSensor(hass, entry, config),
            HalpConfidenceTrendSensor(hass, entry, config),
            HalpConsensusTrendSensor(hass, entry, config),
            HalpLocationExplanationSensor(hass, entry, config),
            HalpSourceSummarySensor(hass, entry, config),
            HalpConflictingSourcesSensor(hass, entry, config),
            HalpConflictDetailsSensor(hass, entry, config),
            HalpStaleSourcesSensor(hass, entry, config),
            HalpLastReliableChangeSensor(hass, entry, config),
        ],
        True,
    )


def reliable_threshold(config: dict[str, Any]) -> int:
    """Return the configured reliable threshold.

    The threshold controls when the binary Location Reliable sensor turns on.
    It is a confidence percentage from 0 to 100.
    """
    value = config.get(CONF_RELIABLE_THRESHOLD, DEFAULT_RELIABLE_THRESHOLD)

    try:
        return int(value)
    except (TypeError, ValueError):
        return DEFAULT_RELIABLE_THRESHOLD


def display_location_state(value: str) -> str:
    """Return a human-friendly location label for dashboard text.

    HALP! exposes Home Assistant's native ``not_home`` state for automation
    compatibility, while human-facing explanations continue to say ``away``.
    """
    return "away" if value == LOCATION_NOT_HOME else value


def source_health_reason(
    results: list[Any],
    confidence: int,
    consensus_score: int,
    health: str,
) -> str:
    """Return a plain-English explanation for the Source Health state.

    This text is intended for dashboards and troubleshooting.
    Keep it short, readable, and non-technical.
    """
    total_count = len(results)

    usable_results = [result for result in results if result.usable]

    stale_results = [
        result
        for result in results
        if is_valid_location_state(result.normalized_state) and result.freshness_factor <= 0
    ]

    missing_results = [
        result
        for result in results
        if result.normalized_state in ("missing", "unavailable", "unknown")
    ]

    if total_count == 0:
        return "Critical because no location sources are configured."

    if not usable_results:
        return "Critical because no configured source is currently usable."

    if health == "Excellent":
        return "Excellent because all usable sources agree and no sources are stale."

    if health == "Good":
        return (
            "Good because the location is reliable, but at least one source is "
            "stale, missing, unknown, or conflicting."
        )

    gps_fast_transition_active = any(
        result.prioritize_second_gps_not_home_active for result in results
    )

    if health == "Fair" and gps_fast_transition_active:
        return (
            f"Fair because the GPS fast-transition rule is active with "
            f"{confidence}% confidence while ordinary source consensus is "
            f"{consensus_score}%."
        )

    if health == "Fair":
        return (
            f"Fair because consensus is {consensus_score}% and confidence is "
            f"{confidence}%."
        )

    if health == "Poor":
        return (
            f"Poor because confidence is {confidence}%, stale sources are "
            f"{len(stale_results)}, and missing or unknown sources are "
            f"{len(missing_results)}."
        )

    return "Critical because source health could not be calculated reliably."



def format_dashboard_datetime(value: str | None) -> str | None:
    """Return a short dashboard-friendly datetime string.

    HALP! stores timestamps internally in ISO format because that is stable and
    easy to restore after a restart.

    Dashboards should show a shorter human-readable form, for example:
    Fri 6/12; 10:56am

    If the value cannot be parsed, return it unchanged so the sensor never
    breaks because of an unexpected restored state.
    """
    if not value:
        return None

    try:
        dt = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return value

    weekday = dt.strftime("%a")
    hour = dt.hour
    suffix = "am" if hour < 12 else "pm"
    hour_12 = hour % 12

    if hour_12 == 0:
        hour_12 = 12

    return f"{weekday} {dt.month}/{dt.day}; {hour_12}:{dt.minute:02d}{suffix}"


class HalpBaseSensor(SensorEntity):
    """Base class shared by all HALP! sensors.

    The base class centralizes common behavior:
    - entity naming
    - unique ID creation
    - device grouping
    - missing Person handling
    """

    _attr_should_poll = False

    _refresh_registry_key = RUNTIME_SENSOR_REFRESH_CALLBACKS

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        config: dict[str, Any],
        suffix: str,
        icon: str,
    ) -> None:
        """Initialize the base HALP! sensor."""
        self.hass = hass
        self.entry = entry
        self.config = config

        self._attr_icon = icon
        self._attr_name = f"{NAME} {entry.title} {suffix}"

        # Snapshot of the last HA-visible HALP! payload. Source events may arrive
        # frequently even when HALP!'s published result is unchanged. Keeping this
        # fingerprint lets HALP! evaluate every event immediately without creating
        # a Recorder row unless this entity's state or meaningful attributes change.
        self._last_published_fingerprint: Any = None

        safe_suffix = suffix.lower().replace(" ", "_")
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{safe_suffix}"

    @property
    def device_info(self) -> dict[str, Any]:
        """Group all HALP! entities for one Person under one HA device."""
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
        """Return whether the configured Person still exists."""
        return not self.config.get("person_missing", False)

    def _missing_person_attributes(self) -> dict[str, Any]:
        """Return attributes used when the configured Person is missing."""
        return {
            "halp_status": "Configured Person entity could not be found.",
            "person_entity": self.config.get(CONF_PERSON_ENTITY),
        }

    async def async_added_to_hass(self) -> None:
        """Register this entity for event-driven HALP! refreshes."""
        await super().async_added_to_hass()

        # async_add_entities(..., update_before_add=True) has already established
        # the entity's initial HA state. Seed the comparison snapshot from that
        # same public payload so the first unchanged source event is not written
        # again merely because HALP! has just started.
        self._last_published_fingerprint = self._halp_publication_fingerprint()

        callbacks = self.config.setdefault(self._refresh_registry_key, set())
        callbacks.add(self._async_refresh_from_halp)

    async def async_will_remove_from_hass(self) -> None:
        """Unregister this entity from event-driven HALP! refreshes."""
        callbacks = self.config.get(self._refresh_registry_key)
        if isinstance(callbacks, set):
            callbacks.discard(self._async_refresh_from_halp)
        await super().async_will_remove_from_hass()

    @staticmethod
    def _freeze_publication_value(value: Any) -> Any:
        """Return a deterministic, hashable representation of HA-visible data."""
        if isinstance(value, dict):
            return tuple(
                sorted(
                    (str(key), HalpBaseSensor._freeze_publication_value(item))
                    for key, item in value.items()
                )
            )
        if isinstance(value, (list, tuple)):
            return tuple(
                HalpBaseSensor._freeze_publication_value(item) for item in value
            )
        if isinstance(value, set):
            return tuple(
                sorted(
                    (HalpBaseSensor._freeze_publication_value(item) for item in value),
                    key=repr,
                )
            )
        return value

    @staticmethod
    def _semantic_publication_value(value: Any) -> Any:
        """Return HA-visible data with timestamp-only churn removed.

        Source integrations can refresh their timestamps even when the location
        evidence itself has not changed. Those bookkeeping timestamps are useful
        diagnostics, but they must not by themselves cause HALP! to publish a new
        state and create another Recorder row.

        Meaningful values such as source state, usability, freshness factor,
        confidence, consensus, conflicts, and vetted location remain part of the
        fingerprint.
        """
        volatile_keys = {
            "last_updated",
            "last_changed",
            "updated",
            "unchanged",
        }

        if isinstance(value, dict):
            return {
                key: HalpBaseSensor._semantic_publication_value(item)
                for key, item in value.items()
                if str(key) not in volatile_keys
            }
        if isinstance(value, list):
            return [
                HalpBaseSensor._semantic_publication_value(item) for item in value
            ]
        if isinstance(value, tuple):
            return tuple(
                HalpBaseSensor._semantic_publication_value(item) for item in value
            )
        if isinstance(value, set):
            return {
                HalpBaseSensor._semantic_publication_value(item) for item in value
            }
        if isinstance(value, str):
            # Location Explanation intentionally includes source timestamps for
            # diagnostics. A source may refresh one of those timestamps without
            # changing any location evidence. Normalize only timestamps that are
            # explicitly introduced by ``last updated`` or ``last changed`` so
            # timestamp-only prose churn cannot defeat publication deduplication.
            return re.sub(
                r"(last (?:updated|changed) )"
                r"\d{4}-\d{2}-\d{2}T[0-9:.+-]+Z?",
                r"\1<timestamp>",
                value,
                flags=re.IGNORECASE,
            )
        return value

    @staticmethod
    def _drop_publication_keys(value: Any, ignored_keys: set[str]) -> Any:
        """Return nested data with entity-specific diagnostic keys removed."""
        if isinstance(value, dict):
            return {
                key: HalpBaseSensor._drop_publication_keys(item, ignored_keys)
                for key, item in value.items()
                if str(key) not in ignored_keys
            }
        if isinstance(value, list):
            return [
                HalpBaseSensor._drop_publication_keys(item, ignored_keys)
                for item in value
            ]
        if isinstance(value, tuple):
            return tuple(
                HalpBaseSensor._drop_publication_keys(item, ignored_keys)
                for item in value
            )
        if isinstance(value, set):
            return {
                HalpBaseSensor._drop_publication_keys(item, ignored_keys)
                for item in value
            }
        return value

    def _publication_attributes_for_fingerprint(self) -> Any:
        """Return attributes that are meaningful for this entity's publication.

        Vetted Location, Source Summary, and Source Details all expose source
        diagnostics, but a freshness-factor step alone does not change what
        those entities represent. Tracker Reliability Table intentionally keeps
        freshness factor/rating in its fingerprint because freshness is one of
        that entity's primary diagnostics.
        """
        attributes = self._semantic_publication_value(self.extra_state_attributes)

        if self.__class__.__name__ in {
            "HalpVettedLocationSensor",
            "HalpSourceSummarySensor",
            "HalpSourceDetailsSensor",
        }:
            attributes = self._drop_publication_keys(
                attributes,
                {"freshness_factor", "freshness_rating"},
            )

        return attributes

    def _halp_publication_fingerprint(self) -> Any:
        """Snapshot state and semantically meaningful attributes exposed to HA."""
        return (
            self.available,
            self._freeze_publication_value(self.native_value),
            self._freeze_publication_value(
                self._publication_attributes_for_fingerprint()
            ),
        )

    async def _async_refresh_from_halp(self) -> None:
        """Evaluate immediately, but publish only an HA-visible change."""
        async_update = getattr(self, "async_update", None)
        if callable(async_update):
            await async_update()

        fingerprint = self._halp_publication_fingerprint()
        previous_fingerprint = self._last_published_fingerprint
        if fingerprint == previous_fingerprint:
            return

        # The publication fingerprint is (availability, native value, attributes).
        # Once an entity has published, any later publication with the same
        # displayed state is necessarily an attributes-only publication because
        # an identical full fingerprint was already suppressed above. Keep this
        # annotation strictly in the Core log; the HA state/Recorder payload is
        # unchanged.
        attributes_only_change = (
            previous_fingerprint is not None
            and fingerprint[1] == previous_fingerprint[1]
        )

        log_suffix = " (attributes changed)" if attributes_only_change else ""
        _LOGGER.info(
            "%s: %s%s",
            self.entity_id or self.name,
            self.native_value,
            log_suffix,
        )

        self._last_published_fingerprint = fingerprint
        self.async_write_ha_state()


class HalpVettedLocationSensor(HalpBaseSensor):
    """Sensor containing HALP!'s best current location conclusion.

    This sensor is HALP!'s answer to:
    'Based on the configured evidence, where does the person appear to be?'
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        config: dict[str, Any],
    ) -> None:
        """Initialize the vetted location sensor."""
        super().__init__(
            hass,
            entry,
            config,
            "Vetted Location",
            "mdi:account-check",
        )

    @property
    def native_value(self) -> str | None:
        """Return HALP!'s current vetted location."""
        if not self.available:
            return None

        results = analyze_sources(self.hass, self.config)
        return calculate_vetted_location(results)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return source details and optional supporting evidence."""
        if not self.available:
            return self._missing_person_attributes()

        results = analyze_sources(self.hass, self.config)

        return {
            "person_entity": self.config.get(CONF_PERSON_ENTITY),
            "ha_person_state": get_state(
                self.hass,
                self.config.get(CONF_PERSON_ENTITY),
            ),
            "sources": [source_result_to_attribute(result) for result in results],
            "battery_level": get_state(
                self.hass,
                self.config.get(CONF_BATTERY_LEVEL_ENTITY),
            ),
            "battery_state": get_state(
                self.hass,
                self.config.get(CONF_BATTERY_STATE_ENTITY),
            ),
            "location_permission": get_state(
                self.hass,
                self.config.get(CONF_LOCATION_PERMISSION_ENTITY),
            ),
            "ssid": get_state(
                self.hass,
                self.config.get(CONF_SSID_ENTITY),
            ),
            "bssid": get_state(
                self.hass,
                self.config.get(CONF_BSSID_ENTITY),
            ),
            "connection_type": get_state(
                self.hass,
                self.config.get(CONF_CONNECTION_TYPE_ENTITY),
            ),
        }


class HalpLocationConfidenceSensor(HalpBaseSensor):
    """Sensor containing HALP!'s current location confidence percentage.

    Confidence answers:
    'How strongly does HALP! trust the vetted location right now?'
    """

    _attr_native_unit_of_measurement = "%"

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        config: dict[str, Any],
    ) -> None:
        """Initialize the confidence sensor."""
        super().__init__(
            hass,
            entry,
            config,
            "Location Confidence",
            "mdi:map-marker-check",
        )

    @property
    def native_value(self) -> int | None:
        """Return the current confidence score."""
        if not self.available:
            return None

        results = analyze_sources(self.hass, self.config)
        vetted_location = calculate_vetted_location(results)

        return calculate_confidence(results, vetted_location)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return confidence context."""
        if not self.available:
            return self._missing_person_attributes()

        results = analyze_sources(self.hass, self.config)
        vetted_location = calculate_vetted_location(results)

        confidence = calculate_confidence(results, vetted_location)
        base_confidence = calculate_base_confidence(results, vetted_location)
        gps_fast_transition_active = bool(
            self.config.get(RUNTIME_GPS_NOT_HOME_PRIORITY_ACTIVE, False)
        )

        attributes = {
            "vetted_location": vetted_location,
            "ha_person_state": get_state(
                self.hass,
                self.config.get(CONF_PERSON_ENTITY),
            ),
            "calculation_mode": (
                "gps_fast_transition"
                if gps_fast_transition_active
                else "ordinary_weighted_evidence"
            ),
            "ordinary_weighted_confidence": base_confidence,
            "reported_confidence": confidence,
        }

        if gps_fast_transition_active:
            attributes.update(
                {
                    "gps_fast_transition_active": True,
                    "gps_fast_departure_active": True,
                    "gps_trigger_entity": self.config.get(
                        RUNTIME_GPS_NOT_HOME_TRIGGER_ENTITY
                    ),
                    "gps_priority_location": self.config.get(
                        RUNTIME_GPS_PRIORITY_LOCATION
                    ),
                    "confidence_floor": 80,
                    "confidence_reason": (
                        "Two matching GPS location updates activated the "
                        "fast-transition rule. Confidence is held at no less "
                        "than 80% and may increase as other sources agree."
                    ),
                }
            )
        else:
            attributes["gps_fast_transition_active"] = False
            attributes["gps_fast_departure_active"] = False
            attributes["confidence_reason"] = (
                "Calculated from ordinary weighted agreeing and conflicting "
                "source evidence."
            )

        return attributes


class HalpConsensusScoreSensor(HalpBaseSensor):
    """Sensor showing how much usable evidence agrees.

    Consensus is different from confidence.

    Consensus asks:
    'Do the usable sources agree with each other?'
    """

    _attr_native_unit_of_measurement = "%"

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        config: dict[str, Any],
    ) -> None:
        """Initialize the consensus score sensor."""
        super().__init__(
            hass,
            entry,
            config,
            "Consensus Score",
            "mdi:account-group-outline",
        )

    @property
    def native_value(self) -> int | None:
        """Return consensus score from 0 to 100."""
        if not self.available:
            return None

        results = analyze_sources(self.hass, self.config)
        vetted_location = calculate_vetted_location(results)

        return calculate_consensus_score(results, vetted_location)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return consensus details."""
        if not self.available:
            return self._missing_person_attributes()

        results = analyze_sources(self.hass, self.config)
        vetted_location = calculate_vetted_location(results)

        usable_results = [result for result in results if result.usable]
        conflicting_results = [
            result
            for result in usable_results
            if result.normalized_state != vetted_location
        ]

        return {
            "vetted_location": vetted_location,
            "usable_sources": len(usable_results),
            "conflicting_sources": len(conflicting_results),
            "configured_sources": len(results),
        }


class HalpSourceHealthSensor(HalpBaseSensor):
    """Sensor giving a simple dashboard-friendly source health label.

    Source Health summarizes whether the current tracking setup looks healthy.
    It intentionally returns labels such as Excellent, Good, Fair, Poor, and
    Critical instead of another percentage.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        config: dict[str, Any],
    ) -> None:
        """Initialize the source health sensor."""
        super().__init__(
            hass,
            entry,
            config,
            "Source Health",
            "mdi:heart-pulse",
        )

    @property
    def native_value(self) -> str | None:
        """Return Excellent, Good, Fair, Poor, or Critical."""
        if not self.available:
            return None

        results = analyze_sources(self.hass, self.config)
        vetted_location = calculate_vetted_location(results)
        confidence = calculate_confidence(results, vetted_location)
        consensus_score = calculate_consensus_score(results, vetted_location)

        return calculate_source_health(
            results,
            vetted_location,
            confidence,
            consensus_score,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the numbers used to calculate source health."""
        if not self.available:
            return self._missing_person_attributes()

        results = analyze_sources(self.hass, self.config)
        vetted_location = calculate_vetted_location(results)
        confidence = calculate_confidence(results, vetted_location)
        consensus_score = calculate_consensus_score(results, vetted_location)

        health = calculate_source_health(
            results,
            vetted_location,
            confidence,
            consensus_score,
        )

        usable_results = [result for result in results if result.usable]

        stale_results = [
            result
            for result in results
            if is_valid_location_state(result.normalized_state) and result.freshness_factor <= 0
        ]

        conflicting_results = [
            result
            for result in usable_results
            if result.normalized_state != vetted_location
        ]

        return {
            "health_reason": source_health_reason(
                results,
                confidence,
                consensus_score,
                health,
            ),
            "confidence": confidence,
            "consensus_score": consensus_score,
            "vetted_location": vetted_location,
            "configured_sources": len(results),
            "usable_sources": len(usable_results),
            "stale_sources": len(stale_results),
            "conflicting_sources": len(conflicting_results),
        }


class HalpSourceDetailsSensor(HalpBaseSensor):
    """Sensor exposing detailed per-source status in attributes.

    This is a general source snapshot. The more detailed tracker-focused view
    lives in Tracker Reliability Table.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        config: dict[str, Any],
    ) -> None:
        """Initialize the source details sensor."""
        super().__init__(
            hass,
            entry,
            config,
            "Source Details",
            "mdi:format-list-bulleted-type",
        )

    @property
    def native_value(self) -> str | None:
        """Return a compact source count."""
        if not self.available:
            return None

        results = analyze_sources(self.hass, self.config)

        return f"{len(results)} sources"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return detailed per-source attributes."""
        if not self.available:
            return self._missing_person_attributes()

        results = analyze_sources(self.hass, self.config)

        return {
            "sources": [source_result_to_attribute(result) for result in results],
            "configured_sources": len(results),
            "usable_sources": len([result for result in results if result.usable]),
            "stale_sources": len(
                [
                    result
                    for result in results
                    if is_valid_location_state(result.normalized_state)
                    and result.freshness_factor <= 0
                ]
            ),
            "missing_or_unknown_sources": len(
                [
                    result
                    for result in results
                    if result.normalized_state in ("missing", "unavailable", "unknown")
                ]
            ),
        }


class HalpTrackerReliabilityTableSensor(HalpBaseSensor):
    """Sensor exposing a current per-tracker reliability table.

    This is the main detailed diagnostic sensor for HALP!.

    The sensor state is a health label, so it is useful on dashboards.
    The detailed per-tracker table is stored in attributes.

    This is not historical learning yet. It is current-state reliability.

    Future historical learning can add fields such as:
    - historical agreement percent
    - historical conflict count
    - learned reliability score
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        config: dict[str, Any],
    ) -> None:
        """Initialize the tracker reliability table sensor."""
        super().__init__(
            hass,
            entry,
            config,
            "Tracker Reliability Table",
            "mdi:table-account",
        )

    @property
    def native_value(self) -> str | None:
        """Return the current tracker table health label."""
        if not self.available:
            return None

        results = analyze_sources(self.hass, self.config)
        vetted_location = calculate_vetted_location(results)
        confidence = calculate_confidence(results, vetted_location)
        consensus_score = calculate_consensus_score(results, vetted_location)

        return calculate_source_health(
            results,
            vetted_location,
            confidence,
            consensus_score,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return per-tracker reliability details."""
        if not self.available:
            return self._missing_person_attributes()

        results = analyze_sources(self.hass, self.config)
        vetted_location = calculate_vetted_location(results)
        confidence = calculate_confidence(results, vetted_location)
        consensus_score = calculate_consensus_score(results, vetted_location)

        health = calculate_source_health(
            results,
            vetted_location,
            confidence,
            consensus_score,
        )

        trackers: list[dict[str, Any]] = []

        for result in results:
            agrees_with_vetted_location = (
                result.usable and result.normalized_state == vetted_location
            )

            conflicts_with_vetted_location = (
                result.usable and result.normalized_state != vetted_location
            )

            if result.freshness_factor >= 1.0:
                freshness_rating = "excellent"
            elif result.freshness_factor >= 0.9:
                freshness_rating = "good"
            elif result.freshness_factor >= 0.75:
                freshness_rating = "fair"
            elif result.freshness_factor >= 0.5:
                freshness_rating = "poor"
            else:
                freshness_rating = "stale"

            trackers.append(
                {
                    "entity_id": result.entity_id,
                    "source_type": result.source_type,
                    "source_type_name": result.source_type_name,
                    "state": result.raw_state,
                    "normalized_state": result.normalized_state,
                    "weight": result.weight,
                    "freshness_rating": freshness_rating,
                    "freshness_factor": result.freshness_factor,
                    "last_updated": result.last_updated,
                    "last_changed": result.last_changed,
                    "usable": result.usable,
                    "agrees_with_vetted_location": agrees_with_vetted_location,
                    "conflicts_with_vetted_location": conflicts_with_vetted_location,
                }
            )

        return {
            "health": health,
            "health_reason": source_health_reason(
                results,
                confidence,
                consensus_score,
                health,
            ),
            "vetted_location": vetted_location,
            "confidence": confidence,
            "consensus_score": consensus_score,
            "tracker_count": len(results),
            "usable_tracker_count": len([result for result in results if result.usable]),
            "trackers": trackers,
        }


class HalpHistorySummarySensor(HalpBaseSensor):
    _refresh_registry_key = RUNTIME_HISTORY_REFRESH_CALLBACKS

    """Sensor summarizing stored HALP! history samples.

    This sensor is mainly for verifying that history recording is working.

    It answers:
    - how many samples have been recorded
    - what time range the samples cover
    - recent average confidence
    - recent average consensus
    - how often HALP! reported home, away, unknown, or critical

    This uses the short-term rolling history cache only.
    Long-term history should eventually use compact daily rollups.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        config: dict[str, Any],
    ) -> None:
        """Initialize the history summary sensor."""
        super().__init__(
            hass,
            entry,
            config,
            "History Summary",
            "mdi:chart-timeline-variant",
        )

        self._samples: list[dict[str, Any]] = []
        self._daily_summaries: dict[str, Any] = {}

    async def async_update(self) -> None:
        """Load latest history samples and daily summaries from storage."""
        self._samples = await async_get_entry_history(
            self.hass,
            self.entry.entry_id,
        )

        self._daily_summaries = await async_get_entry_daily_summaries(
            self.hass,
            self.entry.entry_id,
        )


    @property
    def native_value(self) -> str | None:
        """Return the number of stored history samples."""
        if not self.available:
            return None

        return f"{len(self._samples)} samples"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return summarized history details.

        This combines:
        - recent raw sample statistics
        - long-term daily summary statistics
        """
        if not self.available:
            return self._missing_person_attributes()

        #
        # Raw sample statistics
        #
        if not self._samples:
            return {
                "sample_count": 0,
                "daily_summary_count": len(self._daily_summaries),
                "oldest_sample": None,
                "newest_sample": None,
                "average_confidence": None,
                "average_consensus": None,
                "home_samples": 0,
                "away_samples": 0,
                "unknown_samples": 0,
                "critical_samples": 0,
            }

        confidence_values = [
            sample.get("confidence")
            for sample in self._samples
            if isinstance(sample.get("confidence"), (int, float))
        ]

        consensus_values = [
            sample.get("consensus_score")
            for sample in self._samples
            if isinstance(sample.get("consensus_score"), (int, float))
        ]

        home_samples = len(
            [
                sample
                for sample in self._samples
                if sample.get("vetted_location") == "home"
            ]
        )

        away_samples = len(
            [
                sample
                for sample in self._samples
                if sample.get("vetted_location") in (LOCATION_NOT_HOME, "away")
            ]
        )

        unknown_samples = len(
            [
                sample
                for sample in self._samples
                if sample.get("vetted_location") == "unknown"
            ]
        )

        critical_samples = len(
            [
                sample
                for sample in self._samples
                if sample.get("source_health") == "Critical"
            ]
        )

        #
        # Daily summary statistics
        #
        daily_summary_count = len(self._daily_summaries)

        oldest_daily_summary = None
        newest_daily_summary = None

        latest_daily_average_confidence = None
        latest_daily_average_consensus = None
        latest_daily_home_samples = None
        latest_daily_away_samples = None

        if self._daily_summaries:
            sorted_dates = sorted(self._daily_summaries.keys())

            oldest_daily_summary = sorted_dates[0]
            newest_daily_summary = sorted_dates[-1]

            latest_summary = self._daily_summaries[newest_daily_summary]

            latest_daily_average_confidence = (
                latest_summary.get("average_confidence")
            )

            latest_daily_average_consensus = (
                latest_summary.get("average_consensus")
            )

            latest_daily_home_samples = (
                latest_summary.get("home_samples")
            )

            latest_daily_away_samples = (
                latest_summary.get("away_samples")
            )

        return {
            #
            # Raw sample statistics
            #
            "sample_count": len(self._samples),
            "oldest_sample": self._samples[0].get("timestamp"),
            "newest_sample": self._samples[-1].get("timestamp"),
            "average_confidence": round(
                sum(confidence_values) / len(confidence_values),
                1,
            )
            if confidence_values
            else None,
            "average_consensus": round(
                sum(consensus_values) / len(consensus_values),
                1,
            )
            if consensus_values
            else None,
            "home_samples": home_samples,
            "away_samples": away_samples,
            "unknown_samples": unknown_samples,
            "critical_samples": critical_samples,

            #
            # Daily summary statistics
            #
            "daily_summary_count": daily_summary_count,
            "oldest_daily_summary": oldest_daily_summary,
            "newest_daily_summary": newest_daily_summary,
            "latest_daily_average_confidence": (
                latest_daily_average_confidence
            ),
            "latest_daily_average_consensus": (
                latest_daily_average_consensus
            ),
            "latest_daily_home_samples": (
                latest_daily_home_samples
            ),
            "latest_daily_away_samples": (
                latest_daily_away_samples
            ),
        }

class HalpDailyTrendSensor(HalpBaseSensor):
    _refresh_registry_key = RUNTIME_HISTORY_REFRESH_CALLBACKS

    """Base class for daily summary trend sensors."""

    trend_key: str
    trend_label: str

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        config: dict[str, Any],
        suffix: str,
        icon: str,
        trend_key: str,
        trend_label: str,
    ) -> None:
        """Initialize the daily trend sensor."""
        super().__init__(hass, entry, config, suffix, icon)

        self.trend_key = trend_key
        self.trend_label = trend_label
        self._daily_summaries: dict[str, Any] = {}

    async def async_update(self) -> None:
        """Load latest daily summaries from storage."""
        self._daily_summaries = await async_get_entry_daily_summaries(
            self.hass,
            self.entry.entry_id,
        )

    @property
    def native_value(self) -> float | int | None:
        """Return the latest daily value for this trend."""
        if not self.available:
            return None

        if not self._daily_summaries:
            return None

        newest_date = sorted(self._daily_summaries.keys())[-1]
        value = self._daily_summaries[newest_date].get(self.trend_key)

        if isinstance(value, (int, float)):
            return value

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return recent daily trend statistics."""
        if not self.available:
            return self._missing_person_attributes()

        if not self._daily_summaries:
            return {
                "daily_summary_count": 0,
                "trend_label": self.trend_label,
                "latest_day": None,
                "latest_value": None,
                "seven_day_average": None,
                "thirty_day_average": None,
                "best_day": None,
                "best_value": None,
                "worst_day": None,
                "worst_value": None,
            }

        sorted_dates = sorted(self._daily_summaries.keys())

        values: list[tuple[str, float]] = []

        for date_key in sorted_dates:
            value = self._daily_summaries[date_key].get(self.trend_key)

            if isinstance(value, (int, float)):
                values.append((date_key, float(value)))

        if not values:
            return {
                "daily_summary_count": len(self._daily_summaries),
                "trend_label": self.trend_label,
                "latest_day": sorted_dates[-1],
                "latest_value": None,
                "seven_day_average": None,
                "thirty_day_average": None,
                "best_day": None,
                "best_value": None,
                "worst_day": None,
                "worst_value": None,
            }

        latest_day, latest_value = values[-1]

        last_7_values = [value for _, value in values[-7:]]
        last_30_values = [value for _, value in values[-30:]]

        best_day, best_value = max(values, key=lambda item: item[1])
        worst_day, worst_value = min(values, key=lambda item: item[1])

        return {
            "daily_summary_count": len(self._daily_summaries),
            "trend_label": self.trend_label,
            "latest_day": latest_day,
            "latest_value": latest_value,
            "seven_day_average": round(
                sum(last_7_values) / len(last_7_values),
                1,
            ),
            "thirty_day_average": round(
                sum(last_30_values) / len(last_30_values),
                1,
            ),
            "best_day": best_day,
            "best_value": best_value,
            "worst_day": worst_day,
            "worst_value": worst_value,
        }


class HalpConfidenceTrendSensor(HalpDailyTrendSensor):
    """Sensor showing confidence trend from daily summaries."""

    _attr_native_unit_of_measurement = "%"

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        config: dict[str, Any],
    ) -> None:
        """Initialize the confidence trend sensor."""
        super().__init__(
            hass,
            entry,
            config,
            "Confidence Trend",
            "mdi:chart-line",
            "average_confidence",
            "Average Confidence",
        )

class HalpConsensusTrendSensor(HalpDailyTrendSensor):
    """Sensor showing consensus trend from daily summaries."""

    _attr_native_unit_of_measurement = "%"

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        config: dict[str, Any],
    ) -> None:
        """Initialize the consensus trend sensor."""
        super().__init__(
            hass,
            entry,
            config,
            "Consensus Trend",
            "mdi:chart-line-variant",
            "average_consensus",
            "Average Consensus",
        )


class HalpLocationExplanationSensor(HalpBaseSensor):
    """Sensor containing a short human-readable explanation.

    This is the human-facing summary of the current HALP! decision.

    The state always includes:
    - vetted location
    - confidence
    - usable source count
    - complete source status list

    Including every source is intentional. If there are conflicts or stale
    sources, users should not need to open attributes to understand what HALP!
    is seeing.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        config: dict[str, Any],
    ) -> None:
        """Initialize the explanation sensor."""
        super().__init__(
            hass,
            entry,
            config,
            "Location Explanation",
            "mdi:text-box-search",
        )

    def _source_label(self, entity_id: str, source_type_name: str) -> str:
        """Return a short readable label for one source."""
        lower_entity_id = entity_id.lower()

        if "gps" in lower_entity_id:
            return "GPS"
        if "ble" in lower_entity_id:
            return "BLE"
        if "hacs" in lower_entity_id and "router" in lower_entity_id:
            return "HACS router"
        if "official" in lower_entity_id and "router" in lower_entity_id:
            return "Official router"
        if "router" in lower_entity_id:
            return "Router"

        return source_type_name

    def _source_status_text(self, result: Any) -> str:
        """Return one compact source status for explanation text."""
        label = self._source_label(result.entity_id, result.source_type_name)

        if result.usable:
            status = display_location_state(result.normalized_state)
        elif getattr(result, "geographic_snapback_suppressed", False):
            status = (
                f"geographically excluded "
                f"{display_location_state(result.normalized_state)}"
            )
        elif is_valid_location_state(result.normalized_state):
            status = f"stale {display_location_state(result.normalized_state)}"
        else:
            status = result.normalized_state

        return f"{label}={status}"

    @property
    def native_value(self) -> str | None:
        """Return a compact but complete explanation for dashboard display."""
        if not self.available:
            return None

        results = analyze_sources(self.hass, self.config)
        vetted_location = calculate_vetted_location(results)
        confidence = calculate_confidence(results, vetted_location)

        source_count = len(results)

        usable_results = [
            result
            for result in results
            if result.usable
        ]

        conflicting_results = [
            result
            for result in usable_results
            if result.normalized_state != vetted_location
        ]

        stale_results = [
            result
            for result in results
            if is_valid_location_state(result.normalized_state) and result.freshness_factor <= 0
        ]

        source_text = "; ".join(
            [
                self._source_status_text(result)
                for result in results
            ]
        )

        if vetted_location == "unknown":
            parts = [
                "Unknown because no fresh location source is usable.",
                f"{len(usable_results)} of {source_count} sources usable.",
                f"Sources: {source_text}.",
            ]
        else:
            parts = [
                f"{display_location_state(vetted_location)} with {confidence}% confidence.",
                f"{len(usable_results)} of {source_count} sources usable.",
                f"Sources: {source_text}.",
            ]

        if conflicting_results:
            parts.append(
                f"{len(conflicting_results)} source"
                f"{'s' if len(conflicting_results) != 1 else ''} disagree "
                f"with {display_location_state(vetted_location)}."
            )

        if stale_results:
            parts.append(
                f"{len(stale_results)} source"
                f"{'s are' if len(stale_results) != 1 else ' is'} stale."
            )

        return " ".join(parts)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return a longer explanation with source-by-source detail."""
        if not self.available:
            return self._missing_person_attributes()

        results = analyze_sources(self.hass, self.config)
        vetted_location = calculate_vetted_location(results)
        confidence = calculate_confidence(results, vetted_location)
        consensus_score = calculate_consensus_score(results, vetted_location)

        person_state = get_state(
            self.hass,
            self.config.get(CONF_PERSON_ENTITY),
        )

        usable_results = [result for result in results if result.usable]

        stale_results = [
            result
            for result in results
            if result.freshness_factor <= 0 and is_valid_location_state(result.normalized_state)
        ]

        missing_results = [
            result
            for result in results
            if result.normalized_state in ("missing", "unavailable", "unknown")
        ]

        conflicting_results = [
            result
            for result in usable_results
            if result.normalized_state != vetted_location
        ]

        source_statuses = [
            self._source_status_text(result)
            for result in results
        ]

        lines = [
            f"HALP! currently evaluates the location as {display_location_state(vetted_location)} with {confidence}% confidence.",
            f"The usable source consensus score is {consensus_score}%.",
            f"Home Assistant Person state is {person_state}.",
            f"Current source states are: {'; '.join(source_statuses)}.",
        ]

        if usable_results:
            lines.append("Usable current evidence:")

            for result in usable_results:
                lines.append(
                    f"{result.source_type_name} source {result.entity_id} reports "
                    f"{display_location_state(result.normalized_state)}, last updated "
                    f"{result.last_updated}, last changed {result.last_changed}."
                )

        if conflicting_results:
            lines.append("Conflicting usable evidence:")

            for result in conflicting_results:
                lines.append(
                    f"{result.source_type_name} source {result.entity_id} reports "
                    f"{display_location_state(result.normalized_state)}, which disagrees with "
                    f"{display_location_state(vetted_location)}."
                )

        if stale_results:
            lines.append("Discounted stale evidence:")

            for result in stale_results:
                lines.append(
                    f"{result.source_type_name} source {result.entity_id} reports "
                    f"{display_location_state(result.normalized_state)}, but last updated "
                    f"{result.last_updated}."
                )

        if missing_results:
            lines.append("Unavailable or unknown evidence:")

            for result in missing_results:
                lines.append(
                    f"{result.source_type_name} source {result.entity_id} is "
                    f"{result.normalized_state}."
                )

        return {
            "explanation": " ".join(lines),
            "source_statuses": source_statuses,
            "vetted_location": vetted_location,
            "confidence": confidence,
            "consensus_score": consensus_score,
            "usable_sources": len(usable_results),
            "configured_sources": len(results),
            "conflicting_sources": len(conflicting_results),
            "stale_sources": len(stale_results),
        }


class HalpSourceSummarySensor(HalpBaseSensor):
    """Sensor summarizing the configured source table.

    This is the simple count-focused companion to Source Details.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        config: dict[str, Any],
    ) -> None:
        """Initialize the source summary sensor."""
        super().__init__(
            hass,
            entry,
            config,
            "Source Summary",
            "mdi:table-search",
        )

    @property
    def native_value(self) -> str | None:
        """Return the number of usable sources out of total sources."""
        if not self.available:
            return None

        results = analyze_sources(self.hass, self.config)
        usable_count = len([result for result in results if result.usable])

        return f"{usable_count}/{len(results)} usable"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return a simple source summary."""
        if not self.available:
            return self._missing_person_attributes()

        results = analyze_sources(self.hass, self.config)

        return {
            "source_count": len(results),
            "usable_source_count": len([result for result in results if result.usable]),
            "sources": [source_result_to_attribute(result) for result in results],
        }


class HalpConflictingSourcesSensor(HalpBaseSensor):
    """Sensor showing sources that disagree with the vetted location."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        config: dict[str, Any],
    ) -> None:
        """Initialize the conflicting sources sensor."""
        super().__init__(
            hass,
            entry,
            config,
            "Conflicting Sources",
            "mdi:source-branch-alert",
        )

    @property
    def native_value(self) -> int | None:
        """Return the number of usable sources that conflict."""
        if not self.available:
            return None

        results = analyze_sources(self.hass, self.config)
        vetted_location = calculate_vetted_location(results)

        return len(
            [
                result
                for result in results
                if result.usable and result.normalized_state != vetted_location
            ]
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return conflicting source details."""
        if not self.available:
            return self._missing_person_attributes()

        results = analyze_sources(self.hass, self.config)
        vetted_location = calculate_vetted_location(results)

        conflicting_results = [
            result
            for result in results
            if result.usable and result.normalized_state != vetted_location
        ]

        return {
            "vetted_location": vetted_location,
            "conflicting_source_count": len(conflicting_results),
            "sources": [
                source_result_to_attribute(result)
                for result in conflicting_results
            ],
        }



class HalpConflictDetailsSensor(HalpBaseSensor):
    """Sensor showing source states whenever conflicts exist.

    The normal Conflicting Sources sensor only reports a number.

    This sensor is designed for dashboards. When there are no conflicts, it
    clearly says so. When there are conflicts, it shows the current state of
    every configured source so the user can immediately see the whole picture.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        config: dict[str, Any],
    ) -> None:
        """Initialize the conflict details sensor."""
        super().__init__(
            hass,
            entry,
            config,
            "Conflict Details",
            "mdi:alert-circle-outline",
        )

    def _source_label(self, entity_id: str, source_type_name: str) -> str:
        """Return a short readable label for one source."""
        lower_entity_id = entity_id.lower()

        if "gps" in lower_entity_id:
            return "GPS"
        if "ble" in lower_entity_id:
            return "BLE"
        if "hacs" in lower_entity_id and "router" in lower_entity_id:
            return "HACS router"
        if "official" in lower_entity_id and "router" in lower_entity_id:
            return "Official router"
        if "router" in lower_entity_id:
            return "Router"

        return source_type_name

    def _source_status_text(self, result: Any) -> str:
        """Return one short source status for dashboard display."""
        label = self._source_label(result.entity_id, result.source_type_name)

        if result.usable:
            status = display_location_state(result.normalized_state)
        elif getattr(result, "geographic_snapback_suppressed", False):
            status = (
                f"geographically excluded "
                f"{display_location_state(result.normalized_state)}"
            )
        elif is_valid_location_state(result.normalized_state):
            status = f"stale {display_location_state(result.normalized_state)}"
        else:
            status = result.normalized_state

        return f"{label}={status}"

    @property
    def native_value(self) -> str | None:
        """Return all source states when any source conflicts."""
        if not self.available:
            return None

        results = analyze_sources(self.hass, self.config)
        vetted_location = calculate_vetted_location(results)

        conflicts = [
            result
            for result in results
            if result.usable and result.normalized_state != vetted_location
        ]

        if not conflicts:
            return "0: No conflicts"

        source_text = "; ".join(
            [
                self._source_status_text(result)
                for result in results
            ]
        )

        return f"{len(conflicts)}: {source_text}"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return all source details plus conflict details."""
        if not self.available:
            return self._missing_person_attributes()

        results = analyze_sources(self.hass, self.config)
        vetted_location = calculate_vetted_location(results)

        all_sources = []
        conflicts = []

        for result in results:
            is_conflict = (
                result.usable
                and result.normalized_state != vetted_location
            )

            source_details = {
                "entity_id": result.entity_id,
                "source_label": self._source_label(
                    result.entity_id,
                    result.source_type_name,
                ),
                "source_type": result.source_type,
                "source_type_name": result.source_type_name,
                "state": result.raw_state,
                "normalized_state": result.normalized_state,
                "usable": result.usable,
                "conflicts": is_conflict,
                "last_updated": result.last_updated,
                "last_changed": result.last_changed,
            }

            all_sources.append(source_details)

            if is_conflict:
                conflicts.append(source_details)

        return {
            "vetted_location": vetted_location,
            "conflict_count": len(conflicts),
            "source_count": len(results),
            "conflict_summary": self.native_value,
            "sources": all_sources,
            "conflicts": conflicts,
        }


class HalpStaleSourcesSensor(HalpBaseSensor):
    """Sensor showing configured sources that are stale.

    A source is stale when it reports home or away but is too old to be usable.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        config: dict[str, Any],
    ) -> None:
        """Initialize the stale sources sensor."""
        super().__init__(
            hass,
            entry,
            config,
            "Stale Sources",
            "mdi:clock-alert-outline",
        )

    @property
    def native_value(self) -> int | None:
        """Return the number of stale configured sources."""
        if not self.available:
            return None

        results = analyze_sources(self.hass, self.config)

        return len(
            [
                result
                for result in results
                if is_valid_location_state(result.normalized_state) and result.freshness_factor <= 0
            ]
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return stale source details."""
        if not self.available:
            return self._missing_person_attributes()

        results = analyze_sources(self.hass, self.config)

        stale_results = [
            result
            for result in results
            if is_valid_location_state(result.normalized_state) and result.freshness_factor <= 0
        ]

        return {
            "stale_source_count": len(stale_results),
            "sources": [
                source_result_to_attribute(result)
                for result in stale_results
            ],
        }


class HalpLastReliableChangeSensor(HalpBaseSensor, RestoreEntity):
    """Sensor showing when HALP! last established a reliable location change.

    RestoreEntity is used so this sensor survives Home Assistant restarts.

    The timestamp changes only when HALP! has confidence at or above the
    configured reliability threshold and the reliable vetted location changes
    from the previously established reliable location.

    Confidence changes by themselves do not move this timestamp. An unreliable
    interval also does not move it. If the location changes while reliability is
    low, the timestamp is updated only when that new location later becomes
    reliable.

    Older HALP! releases used this entity for a different concept: the last time
    the reliable/not-reliable Boolean changed. Because that historical timestamp
    cannot be converted reliably, the first run of this implementation starts a
    new baseline when the current location is reliable.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        config: dict[str, Any],
    ) -> None:
        """Initialize the last reliable location change sensor."""
        super().__init__(
            hass,
            entry,
            config,
            "Last Reliable Change",
            "mdi:timeline-clock-outline",
        )

        self._last_reliable_location: str | None = None
        self._last_change: str | None = None

    async def async_added_to_hass(self) -> None:
        """Restore the new reliable-location state after Home Assistant restart."""
        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()
        if last_state is None:
            return

        restored_location = last_state.attributes.get("last_reliable_location")

        # Only restore timestamps written by this implementation. Previous HALP!
        # versions stored the time when reliability itself changed, which has a
        # different meaning and must not be carried forward as though it were a
        # reliable location-change timestamp.
        if isinstance(restored_location, str) and is_valid_location_state(restored_location):
            self._last_reliable_location = restored_location

            if last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                self._last_change = last_state.state

    @property
    def native_value(self) -> str | None:
        """Return when HALP! last established a reliable location change."""
        if not self.available:
            return None

        results = analyze_sources(self.hass, self.config)
        vetted_location = calculate_vetted_location(results)
        confidence = calculate_confidence(results, vetted_location)

        threshold = reliable_threshold(self.config)
        reliable = confidence >= threshold

        if reliable and is_valid_location_state(vetted_location):
            if self._last_reliable_location is None:
                # Establish a baseline for a new installation or for migration
                # from the older reliability-transition meaning of this sensor.
                self._last_reliable_location = vetted_location
                self._last_change = datetime.now().isoformat(timespec="seconds")
            elif vetted_location != self._last_reliable_location:
                self._last_reliable_location = vetted_location
                self._last_change = datetime.now().isoformat(timespec="seconds")

        return format_dashboard_datetime(self._last_change)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return current reliability and last reliable-location details."""
        if not self.available:
            return self._missing_person_attributes()

        results = analyze_sources(self.hass, self.config)
        vetted_location = calculate_vetted_location(results)
        confidence = calculate_confidence(results, vetted_location)
        threshold = reliable_threshold(self.config)

        return {
            "currently_reliable": confidence >= threshold,
            "confidence": confidence,
            "threshold": threshold,
            "vetted_location": vetted_location,
            "last_reliable_location": self._last_reliable_location,
        }
