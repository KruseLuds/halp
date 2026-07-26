# HALP! Changelog

All notable changes to HALP! will be documented in this file.

This project follows Semantic Versioning (SemVer).

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