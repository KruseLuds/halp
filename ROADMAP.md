# HALP! Roadmap

## Version 1.0

**Status:** Released

### Highlights

- Multiple person support
- GPS, BLE, Router/WiFi and Person analysis
- Confidence scoring
- Consensus scoring
- Human-readable explanations
- Source freshness analysis
- Conflict detection
- Ignore tracker classification
- Automatic mismatch detection
- Dashboard examples
- Installation guide
- Local branding

### Version 1.0.4 Fast Departure Update

- Optional second GPS `not_home` update priority rule
- Enabled by default per Person
- Dashboard switch for immediate testing and control

### Version 1.0.3 Maintenance Update

- Vetted Location now uses Home Assistant-compatible `home`, `not_home`, and `unknown` entity states
- Home Assistant continues to display `not_home` as Away in the user interface
- Legacy incoming `away` source values are normalized to `not_home`
- Documentation and automation guidance updated for the native state vocabulary

---

## Version 1.1

**Status:** Planned

- Home Visit reliability analysis
- Reliability percentages
- Reliability trend graphs
- Enhanced dashboards

## Version 1.2

**Status:** Planned

- Adaptive source weighting
- Smarter confidence calculations

## Version 1.3

**Status:** Planned

- WiFi enabled detection
- Bluetooth enabled detection
- GPS enabled detection
- Battery optimization detection
- Expanded explanation engine

## Version 2.0

**Status:** Future

- Arrival/departure reliability analysis
- Zone-specific recommendations
- Automation troubleshooting
- Reliability recommendation engine


## Future Multi-Zone Design

**Status:** Deferred to a future release

The current release remains focused on `home` and `not_home`. The following design decisions are retained for future multi-zone work:

- Internally distinguish a specific named zone from being outside all configured zones, while publishing Home Assistant-compatible `not_home`.
- GPS remains position-based and may identify any zone.
- Router/WiFi remains fixed-location evidence assigned to one zone.
- BLE remains fixed-location evidence, but a future configuration may allow one BLE source to be associated with multiple zones when Home Assistant aggregates gateways across locations.
- Positive fixed-location detection is stronger than loss of detection.
- Direct transitions between named zones should be possible without requiring an intermediate `not_home` state.
- Multi-zone configuration must validate current people, trackers, and zones and discard stale stored references when the configuration flow opens.

The detailed design discussion is intentionally summarized here rather than storing a binary DOCX file in the source repository.

- Preserve capability-aware settings: GPS-only controls remain visible but unavailable when a person has no configured GPS tracker, with a clear reason shown to the user.
- Require explicit acknowledgement when a future release introduces a behavior-changing default for existing entries, rather than silently applying it during upgrade.
