"""Rolling history storage for HALP!.

This module stores HALP! history in Home Assistant's local .storage area.

Important design note:

Home Assistant .storage is not a real time-series database. HALP! should not
store unlimited detailed raw samples here.

HALP! therefore keeps two levels of history:

1. Short-term raw samples
   - Used for recent dashboard graphs and troubleshooting.
   - Limited to 24 hours per configured Person.

2. Daily summaries
   - Used for long-term reliability trends.
   - Kept for 5 years.
   - Compact enough to support many people without creating a huge file.

Long term, HALP! can add more compact per-tracker statistics here without
needing an external database.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .helpers import SourceResult

STORAGE_KEY = "halp_history"
STORAGE_VERSION = 1

# 24 hours at 5-minute intervals:
# 12 samples/hour * 24 hours = 288 samples.
#
# Detailed samples are only kept for recent dashboard graphs.
MAX_SAMPLES_PER_ENTRY = 288

# 5 years of daily summaries:
# 365 days/year * 5 years = 1825 daily records.
#
# This is small enough to keep in .storage even for larger households.
MAX_DAILY_SUMMARIES_PER_ENTRY = 1825

# One shared lock prevents two HALP! config entries from reading and writing
# the history file at the same time and overwriting each other.
_HISTORY_LOCK = asyncio.Lock()


def utc_now() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    """Return the current UTC timestamp as an ISO string."""
    return utc_now().isoformat(timespec="seconds")


def utc_today_key() -> str:
    """Return today's UTC date key.

    Daily summaries currently use UTC dates so the stored data is stable and
    independent of timezone changes.

    Later, HALP! can optionally summarize by the user's local timezone.
    """
    return utc_now().date().isoformat()


def source_result_to_history_sample(
    result: SourceResult,
    vetted_location: str,
) -> dict[str, Any]:
    """Convert one analyzed source into a compact stored history record."""
    agrees = result.usable and result.normalized_state == vetted_location
    conflicts = result.usable and result.normalized_state != vetted_location

    return {
        "entity_id": result.entity_id,
        "source_type": result.source_type,
        "state": result.raw_state,
        "normalized_state": result.normalized_state,
        "weight": result.weight,
        "freshness_factor": result.freshness_factor,
        "updated_minutes": round(result.last_updated_minutes, 2),
        "changed_minutes": round(result.last_changed_minutes, 2),
        "usable": result.usable,
        "agrees": agrees,
        "conflicts": conflicts,
    }


def build_history_sample(
    vetted_location: str,
    confidence: int,
    consensus_score: int,
    source_health: str,
    results: list[SourceResult],
) -> dict[str, Any]:
    """Build one raw history sample.

    This raw sample is intentionally detailed because it supports recent
    troubleshooting and short-term graphs.
    """
    return {
        "timestamp": utc_now_iso(),
        "vetted_location": vetted_location,
        "confidence": confidence,
        "consensus_score": consensus_score,
        "source_health": source_health,
        "source_count": len(results),
        "usable_source_count": len([result for result in results if result.usable]),
        "conflicting_source_count": len(
            [
                result
                for result in results
                if result.usable and result.normalized_state != vetted_location
            ]
        ),
        "stale_source_count": len(
            [
                result
                for result in results
                if result.normalized_state in ("home", "away") and not result.usable
            ]
        ),
        "sources": [
            source_result_to_history_sample(result, vetted_location)
            for result in results
        ],
    }


def blank_daily_summary(date_key: str) -> dict[str, Any]:
    """Return a new empty daily summary structure."""
    return {
        "date": date_key,
        "sample_count": 0,
        "confidence_total": 0,
        "consensus_total": 0,
        "average_confidence": None,
        "average_consensus": None,
        "home_samples": 0,
        "away_samples": 0,
        "unknown_samples": 0,
        "critical_samples": 0,
        "poor_samples": 0,
        "fair_samples": 0,
        "good_samples": 0,
        "excellent_samples": 0,
        "source_count_total": 0,
        "usable_source_count_total": 0,
        "conflicting_source_count_total": 0,
        "stale_source_count_total": 0,
        "average_source_count": None,
        "average_usable_source_count": None,
        "average_conflicting_source_count": None,
        "average_stale_source_count": None,
    }


def update_daily_summary(
    daily_summary: dict[str, Any],
    sample: dict[str, Any],
) -> None:
    """Update one daily summary using one raw sample.

    The summary stores totals and averages. Totals are retained because they
    let HALP! update averages cheaply without re-reading every raw sample.
    """
    daily_summary["sample_count"] = int(daily_summary.get("sample_count", 0)) + 1
    sample_count = daily_summary["sample_count"]

    confidence = sample.get("confidence")
    if isinstance(confidence, (int, float)):
        daily_summary["confidence_total"] = (
            daily_summary.get("confidence_total", 0) + confidence
        )
        daily_summary["average_confidence"] = round(
            daily_summary["confidence_total"] / sample_count,
            1,
        )

    consensus_score = sample.get("consensus_score")
    if isinstance(consensus_score, (int, float)):
        daily_summary["consensus_total"] = (
            daily_summary.get("consensus_total", 0) + consensus_score
        )
        daily_summary["average_consensus"] = round(
            daily_summary["consensus_total"] / sample_count,
            1,
        )

    vetted_location = sample.get("vetted_location")
    if vetted_location == "home":
        daily_summary["home_samples"] = daily_summary.get("home_samples", 0) + 1
    elif vetted_location == "away":
        daily_summary["away_samples"] = daily_summary.get("away_samples", 0) + 1
    elif vetted_location == "unknown":
        daily_summary["unknown_samples"] = daily_summary.get("unknown_samples", 0) + 1

    source_health = sample.get("source_health")
    if source_health == "Critical":
        daily_summary["critical_samples"] = daily_summary.get("critical_samples", 0) + 1
    elif source_health == "Poor":
        daily_summary["poor_samples"] = daily_summary.get("poor_samples", 0) + 1
    elif source_health == "Fair":
        daily_summary["fair_samples"] = daily_summary.get("fair_samples", 0) + 1
    elif source_health == "Good":
        daily_summary["good_samples"] = daily_summary.get("good_samples", 0) + 1
    elif source_health == "Excellent":
        daily_summary["excellent_samples"] = (
            daily_summary.get("excellent_samples", 0) + 1
        )

    source_count = sample.get("source_count", 0)
    usable_source_count = sample.get("usable_source_count", 0)
    conflicting_source_count = sample.get("conflicting_source_count", 0)
    stale_source_count = sample.get("stale_source_count", 0)

    daily_summary["source_count_total"] = (
        daily_summary.get("source_count_total", 0) + source_count
    )
    daily_summary["usable_source_count_total"] = (
        daily_summary.get("usable_source_count_total", 0) + usable_source_count
    )
    daily_summary["conflicting_source_count_total"] = (
        daily_summary.get("conflicting_source_count_total", 0)
        + conflicting_source_count
    )
    daily_summary["stale_source_count_total"] = (
        daily_summary.get("stale_source_count_total", 0) + stale_source_count
    )

    daily_summary["average_source_count"] = round(
        daily_summary["source_count_total"] / sample_count,
        2,
    )
    daily_summary["average_usable_source_count"] = round(
        daily_summary["usable_source_count_total"] / sample_count,
        2,
    )
    daily_summary["average_conflicting_source_count"] = round(
        daily_summary["conflicting_source_count_total"] / sample_count,
        2,
    )
    daily_summary["average_stale_source_count"] = round(
        daily_summary["stale_source_count_total"] / sample_count,
        2,
    )


def trim_daily_summaries(
    daily_summaries: dict[str, Any],
) -> dict[str, Any]:
    """Keep only the newest daily summaries.

    Daily summary keys are ISO date strings, so sorting the keys sorts them by
    date as long as they remain in YYYY-MM-DD format.
    """
    if len(daily_summaries) <= MAX_DAILY_SUMMARIES_PER_ENTRY:
        return daily_summaries

    newest_keys = sorted(daily_summaries.keys())[-MAX_DAILY_SUMMARIES_PER_ENTRY:]

    return {
        date_key: daily_summaries[date_key]
        for date_key in newest_keys
    }


async def async_load_history(hass: HomeAssistant) -> dict[str, Any]:
    """Load HALP! history from Home Assistant storage."""
    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    stored = await store.async_load()

    if not isinstance(stored, dict):
        return {"entries": {}}

    entries = stored.get("entries")
    if not isinstance(entries, dict):
        return {"entries": {}}

    return stored


async def async_save_history(
    hass: HomeAssistant,
    history: dict[str, Any],
) -> None:
    """Save HALP! history to Home Assistant storage."""
    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    await store.async_save(history)


async def async_record_history_sample(
    hass: HomeAssistant,
    entry_id: str,
    entry_title: str,
    person_entity: str | None,
    vetted_location: str,
    confidence: int,
    consensus_score: int,
    source_health: str,
    results: list[SourceResult],
) -> None:
    """Record one rolling history sample for one HALP! config entry.

    The lock is important because each configured person records on the same
    timer interval. Without the lock, two entries can load the same file, each
    add its own sample, and then the last save wins.
    """
    async with _HISTORY_LOCK:
        history = await async_load_history(hass)

        entries = history.setdefault("entries", {})
        entry_history = entries.setdefault(
            entry_id,
            {
                "title": entry_title,
                "person_entity": person_entity,
                "samples": [],
                "daily_summaries": {},
            },
        )

        entry_history["title"] = entry_title
        entry_history["person_entity"] = person_entity

        samples = entry_history.setdefault("samples", [])
        if not isinstance(samples, list):
            samples = []
            entry_history["samples"] = samples

        daily_summaries = entry_history.setdefault("daily_summaries", {})
        if not isinstance(daily_summaries, dict):
            daily_summaries = {}
            entry_history["daily_summaries"] = daily_summaries

        sample = build_history_sample(
            vetted_location=vetted_location,
            confidence=confidence,
            consensus_score=consensus_score,
            source_health=source_health,
            results=results,
        )

        samples.append(sample)

        date_key = utc_today_key()
        daily_summary = daily_summaries.setdefault(
            date_key,
            blank_daily_summary(date_key),
        )

        update_daily_summary(daily_summary, sample)

        entry_history["samples"] = samples[-MAX_SAMPLES_PER_ENTRY:]
        entry_history["daily_summaries"] = trim_daily_summaries(daily_summaries)

        await async_save_history(hass, history)


async def async_get_entry_history(
    hass: HomeAssistant,
    entry_id: str,
) -> list[dict[str, Any]]:
    """Return stored raw history samples for one HALP! config entry."""
    history = await async_load_history(hass)
    entry_history = history.get("entries", {}).get(entry_id, {})

    samples = entry_history.get("samples", [])
    if not isinstance(samples, list):
        return []

    return samples


async def async_get_entry_daily_summaries(
    hass: HomeAssistant,
    entry_id: str,
) -> dict[str, Any]:
    """Return stored daily summaries for one HALP! config entry."""
    history = await async_load_history(hass)
    entry_history = history.get("entries", {}).get(entry_id, {})

    daily_summaries = entry_history.get("daily_summaries", {})
    if not isinstance(daily_summaries, dict):
        return {}

    return daily_summaries