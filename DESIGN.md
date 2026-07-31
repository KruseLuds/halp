# HALP! DESIGN DOCUMENT

Version: **1.0.4 (Living Document)**

## Purpose

HALP! is a read-only analysis and diagnostics engine for Home Assistant location and presence.

It explains **why** Home Assistant reached a location decision and how much confidence should be placed in that decision.

## Mission

HALP! does not determine location.

HALP! determines how much confidence should be placed in existing location information.

## Source of Truth

Home Assistant remains the source of truth.

HALP! never modifies Person entities, device trackers, zones, or automations.

## Vetted Location State Vocabulary

HALP!'s Vetted Location sensor uses Home Assistant-compatible location states:

- `home`
- `not_home`
- `unknown`

Home Assistant normally displays `not_home` as **Away** in the user interface. Code, automations, templates, stored current-state samples, and integration logic should use `not_home`; human-readable explanations may continue to use **Away**.

HALP! accepts a legacy incoming `away` value and normalizes it to `not_home` for compatibility.

## Ignore Trackers

Version 1.0 introduced Ignore tracker classification.

Ignored trackers:
- remain visible for diagnostics
- are excluded from confidence scoring
- are excluded from mismatch detection

## Supporting Evidence

Supporting evidence may include:

- Battery level
- Charging status
- WiFi SSID
- WiFi BSSID
- WiFi enabled state
- Bluetooth enabled state
- GPS enabled state
- Connection type
- Location permission status
- Last update trigger

These values primarily explain confidence rather than determine confidence.

## Long-Term Goal

HALP! should become the definitive diagnostics tool for Home Assistant presence reliability.


## Optional Faster `not_home` Transition

HALP! can optionally prioritize a second GPS update that remains `not_home`. The setting is enabled by default and is configured separately for each Person.

The rule applies only when:

1. Vetted Location was `home`.
2. A configured GPS tracker changes from `home` to `not_home`.
3. The same GPS tracker publishes a later Home Assistant state update while its state remains `not_home`.

At the third step, HALP! publishes `not_home` immediately. The feature does not modify the Home Assistant Person or GPS tracker. Existing HALP! weighted voting continues to operate before the second update and after ordinary evidence independently supports `not_home`. A later positive Home transition clears the temporary priority state so normal arrival behavior remains available.

## Fast-departure option availability and upgrade acknowledgement

The fast `not_home` transition requires at least one configured GPS tracker. HALP! still exposes the switch when no GPS tracker is configured, but marks it unavailable and reports: `Unavailable (there is no GPS tracker sensor configured for this person)`.

For backward compatibility, entries created before this option existed do not silently inherit the new enabled behavior. The effective value remains disabled until the user opens the HALP! Configure flow, chooses the desired value, and saves. A stable persistent notification is recreated until that acknowledgement is stored. New entries receive the enabled default and are marked reviewed during initial setup.


## Calculation documentation

The user-facing formulas and decision rules for Vetted Location, Confidence, Consensus, and Source Health are documented in [`docs/How_HALP_Calculates_Location_Confidence_Consensus_and_Health.md`](docs/How_HALP_Calculates_Location_Confidence_Consensus_and_Health.md).

During the optional fast-departure override, confidence has an 80% minimum and a runtime high-water mark. It may rise as other sources agree but cannot fall while the override remains active. Consensus is not altered and continues to report actual weighted source agreement.
