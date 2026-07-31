# HALP! Changelog

All notable changes to HALP! will be documented in this file.

This project follows Semantic Versioning (SemVer).

---

# Version 1.0.4

**Release Date:** July 30, 2026

## Added

- Added the per-Person setting **Accelerate `not_home` transition: prioritize second `not_home` GPS update**.
- Added a dashboard-controllable switch for the same setting.
- Added a detailed calculation guide explaining source weights, freshness, Vetted Location, Confidence, Consensus, Source Health, and the fast-departure confidence rule.
- Added explanatory confidence attributes identifying ordinary calculation mode versus GPS fast-departure mode.

## Changed

- Corrected the tracker event callback so repeated state updates from a GPS tracker are processed by the asynchronous fast-departure handler.
- When the second consecutive GPS `not_home` update activates fast departure, Confidence now has an 80% minimum.
- While the temporary GPS override remains active, Confidence uses a high-water mark: it may rise as other sources agree, but it cannot fall.
- Consensus remains based on actual weighted source agreement and is not artificially increased by the GPS override.
- Source Health explanations now identify when a Fair result reflects a trusted GPS departure while slower sources still disagree.
- The fast `not_home` switch is unavailable when no GPS tracker is configured, with the status comment: `Unavailable (there is no GPS tracker sensor configured for this person)`.

## Upgrade behavior

- Existing HALP! entries must explicitly review and save the new fast-departure option.
- Until reviewed, the option remains disabled and HALP! creates a persistent notification that is recreated until configuration is saved.
- New entries default the option to enabled.

## Behavior

When enabled, and HALP!'s Vetted Location was `home`, a configured GPS tracker must first change from `home` to `not_home`. If that same GPS tracker then publishes another update while its state remains `not_home`, HALP! immediately changes Vetted Location to `not_home`.

The fast-departure decision starts with at least 80% Confidence. Confidence can increase, but not decrease, while the temporary override remains active. Ordinary weighted voting and arrival behavior continue unchanged, and Consensus continues to show the true percentage of usable weighted evidence that agrees.

---

# Version 1.0.3

**Release Date:** July 2026

## Overview

This maintenance release improves compatibility with Home Assistant by aligning HALP!'s Vetted Location sensor with Home Assistant's native location state model.

## Added

- Improved documentation describing HALP!'s location state model.
- Added guidance for using the Vetted Location sensor in Home Assistant automations.
- Clarified the distinction between Home Assistant's displayed location labels and the underlying entity states.

## Changed

- HALP! Vetted Location now publishes Home Assistant's native `not_home` entity state instead of the custom `away` state.
- HALP! now behaves as a drop-in replacement for Home Assistant Person entities in automations using `home` and `not_home`.
- Internal location normalization has been updated to preserve Home Assistant's native state vocabulary.

## Compatibility

HALP! continues to recognize legacy incoming `away` values from existing data and normalizes them internally to `not_home` for compatibility.

## Breaking Change

Users with automations similar to:

```yaml
condition:
  - condition: state
    entity_id: sensor.halp_<person>_vetted_location
    state: away
```

should update them to:

```yaml
condition:
  - condition: state
    entity_id: sensor.halp_<person>_vetted_location
    state: not_home
```

Home Assistant will normally continue displaying this state as **Away** in the user interface even though the actual entity state is `not_home`.

---

# Version 1.0.2

**Release Date:** July 2026

## Overview

Initial public release.

### Features

- Multi-person support
- GPS, BLE, and Router/WiFi source analysis
- Vetted Location sensor
- Confidence and Consensus scoring
- Source Health evaluation
- Human-readable explanations
- Conflict detection
- Historical analysis
- Ignore tracker classification
- Tracker mismatch detection
- Dashboard examples
- Comprehensive installation documentation

