# HALP! Roadmap

## Version 1.0

**Status:** Released

### Highlights

-   Multiple person support
-   GPS, BLE, Router/WiFi and Person analysis
-   Confidence scoring
-   Consensus scoring
-   Human-readable explanations
-   Source freshness analysis
-   Conflict detection
-   Ignore tracker classification
-   Automatic mismatch detection
-   Dashboard examples
-   Installation guide
-   Local branding

### Version 1.0.4 Fast Departure Update

-   Optional second GPS `not_home` update priority rule
-   Enabled by default per Person
-   Dashboard switch for immediate testing and control

### Version 1.0.3 Maintenance Update

-   Vetted Location now uses Home Assistant-compatible `home`,
    `not_home`, and `unknown` entity states
-   Home Assistant continues to display `not_home` as Away in the user
    interface
-   Legacy incoming `away` source values are normalized to `not_home`
-   Documentation and automation guidance updated for the native state
    vocabulary

------------------------------------------------------------------------

## Version 2.0

**Status:** Released

### Highlights

-   Full multi-zone Vetted Location support using Home
    Assistant-compatible location states
-   GPS sources can dynamically report `home`, `not_home`, or named
    zones
-   Optional second matching GPS location update can accelerate any
    confirmed zone transition
-   Fixed BLE trackers are assigned to exactly one zone per tracker
-   Fixed WiFi/router trackers are assigned to exactly one zone per
    tracker
-   Mobile WiFi/router sources may use no fixed zone
-   Zone additions and removals are detected and surfaced through
    persistent notifications
-   Deleted or stale Person, tracker, and zone references are reconciled
    during configuration
-   Last Reliable Change now applies to reliable transitions between any
    supported locations
-   Existing source weights, freshness rules, confidence, consensus, and
    reliability thresholds remain global per Person and apply across all
    zones

------------------------------------------------------------------------

## Version 2.1

**Status:** Released

-   Geographic snap-back protection after second-matching-GPS
    confirmation of departure from a fixed-source Zone
-   Actual Home Assistant Zone-circle overlap detection so geographically
    compatible overlapping Zones continue normal voting
-   Old fixed BLE/router evidence from a non-overlapping departed Zone
    cannot resurrect that Zone while the confirming GPS still provides
    contradictory valid location evidence
-   Fresh fixed-source `not_home` to positive transitions remain fast
    arrival evidence and can temporarily take precedence until GPS next
    updates
-   Exact preservation of Home Assistant Zone friendly names in
    human-facing HALP! explanations (bug fix)

------------------------------------------------------------------------

## Version 2.2

**Status:** Planned

-   Home Visit reliability analysis
-   Reliability percentages
-   Reliability trend graphs
-   Enhanced dashboards
-   Additional multi-zone diagnostics and usability refinements
-   Adaptive source weighting
-   Smarter confidence calculations
-   Additional zone-transition reliability analysis

------------------------------------------------------------------------

## Version 2.3

**Status:** Planned

-   WiFi enabled detection
-   Bluetooth enabled detection
-   GPS enabled detection
-   Battery optimization detection
-   Expanded explanation engine

------------------------------------------------------------------------

## Future

**Status:** Future

-   Arrival/departure reliability recommendations by zone
-   Automation troubleshooting
-   Zone-specific reliability recommendations
-   Reliability recommendation engine
-   Additional support for advanced BLE and mobile-location topologies

### Preserved design principles

-   GPS remains dynamic and is not assigned to a fixed zone.
-   Each fixed BLE tracker is associated with exactly one zone.
-   Each fixed WiFi/router tracker is associated with exactly one zone.
-   A mobile WiFi/router source may be configured without a fixed zone.
-   Positive fixed-location detection is stronger evidence than loss of
    detection.
-   Direct transitions between named zones are supported without
    requiring an intermediate `not_home` state.
-   Configuration should validate current people, trackers, and zones
    and discard stale stored references when the Configure flow opens.
-   Capability-aware settings remain visible but unavailable when their
    prerequisite source type is not configured, with a clear reason
    shown to the user.
-   Behavior-changing defaults for existing entries should require
    explicit acknowledgement rather than being silently applied during
    upgrade.
