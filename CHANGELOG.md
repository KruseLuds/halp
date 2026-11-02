# HALP! Changelog

All notable changes to HALP! will be documented in this file.

This project follows Semantic Versioning (SemVer).


# Version 2.1.3

**Release Date:**
Pending publication

## Fixed

- Added the root-level `hacs.json` repository metadata so the Home Assistant Marketplace can install and update HALP! (issue #5).

## Compatibility

- Packaging-only change. Existing HACS installations remain supported.
- No changes to presence calculations, notifications, entities, configuration, or the runtime integration code.

------------------------------------------------------------------------

# Version 2.1.2

**Release Date:**
November 2, 2026

## Fixed

- Removed redundant configuration warnings triggered by unrelated Home Assistant zone additions, renames, and removals. HALP! still warns when an assigned fixed BLE or router/WiFi zone is missing or inactive.
- Prevented repeated `persistent_notification.create` and `persistent_notification.dismiss` service calls from unchanged one-minute HALP! checks.
- Retired the legacy whole-zone-inventory warning and cleared existing instances during config-entry startup.

## Changed

- Centralized persistent notification updates behind stable IDs and exact message/title comparison.
- Preserved manual dismissal of an unchanged warning for the remainder of the current config-entry runtime. An unresolved warning may reappear once after Home Assistant restart or HALP! reload.
- Stopped saving redundant active-zone-inventory snapshots during configuration.
- Added automated regression tests for notification deduplication, manual dismissal, fixed-zone validation, and unchanged-zone behavior.

## Compatibility

- Retained one-minute configuration validation and warnings for actual invalid BLE and router/WiFi fixed-zone assignments.
- No changes to Home Assistant Person entities, trackers, zones, automations, HALP! location scoring, Confidence, Consensus, Source Health, or history calculations.
- Validated locally with unit tests and confirmed that unrelated zone additions/deletions generated no HALP! notification calls in a running Home Assistant installation. Additional edge-case runtime validation remains part of release review.

------------------------------------------------------------------------

# Version 2.1.1

**Release Date:**
September 23, 2026

## Changed

- Reworked HALP! sensor publication to be event-driven instead of continuously republishing ordinary sensor state.
- Added semantic publication deduplication so source events are still evaluated immediately, but HALP! writes a new Home Assistant state only when the entity's displayed state or meaningful attributes actually change.
- Timestamp-only source refreshes no longer create new HALP! Recorder rows by themselves.
- Freshness-only changes are ignored for Vetted Location, Source Summary, and Source Details publication decisions while remaining available to HALP!'s calculations and diagnostics.
- Tracker Reliability Table continues to publish meaningful freshness-factor or freshness-rating changes because freshness is a primary purpose of that diagnostic entity.
- Repeated HALP! INFO log publications with an unchanged displayed state are now explicitly marked `(attributes changed)` so diagnostic activity is easier to distinguish from a real state transition.
- Removed the user-facing History Summary sensor. Its fixed rolling-buffer count eventually reaches and stays at the predetermined `288 samples` (= 12 samples per hour x 24 hours) while the underlying history continued to roll, so the displayed state did not provide useful operational information. HALP!'s underlying history collection and history-derived calculations remain in place.

## Fixed

- Greatly reduced unnecessary Home Assistant Recorder activity caused by repeated HALP! publications when the effective state and meaningful attributes had not changed.
- Prevented source `last_updated` / `last_changed` timestamp churn from defeating publication deduplication.
- Preserved real location transitions, named-zone transitions, source-availability changes, confidence/consensus changes, and meaningful diagnostic changes while suppressing duplicate publications.

## Compatibility

- HALP!'s location calculations, source weighting, freshness evaluation, Confidence, Consensus, Source Health, and multi-zone behavior are unchanged by the publication optimization.
- Existing Vetted Location states remain Home Assistant-compatible: `home`, `not_home`, named active Zones, and `unknown`.
- The History Summary entity is removed, but HALP!'s internal rolling history and history-derived functionality continue to operate.
- No Home Assistant Person, device tracker, Zone, or automation is modified by HALP!.

------------------------------------------------------------------------

# Version 2.1.0

**Release Date:**
August 27, 2026

## Added

- Added geographic snap-back protection for confirmed GPS departures from fixed-source Zones.
- After the existing second matching GPS update confirms departure from a Zone, HALP! remembers that confirmed departure at runtime.
- A fixed BLE or fixed WiFi/router source that was already positively reporting the departed Zone before the confirmed GPS departure is treated as old sticky evidence if it continues reporting that same Zone.
- If current GPS reports `not_home`, that old fixed evidence cannot pull Vetted Location back to the departed Zone.
- If current GPS reports another named Zone, HALP! compares the actual Home Assistant Zone circles. Old fixed evidence from the departed Zone is excluded only when the two Zones do not overlap.
- Added fresh fixed-arrival priority: when a fixed BLE/router source genuinely changes from `not_home` to positive presence for its configured Zone before GPS updates, that new arrival evidence can immediately take precedence until GPS publishes its next update.
- Added diagnostics showing geographic snap-back suppression and the runtime confirmed-departure context.

## Changed

- Preserved exact Home Assistant Zone friendly names in Location Explanation text instead of applying Python title-casing. This fixes zone names such as `Wendy's` being displayed incorrectly as `Wendy'S`.
- Geographic snap-back protection is tied to the existing per-Person **Speed up location transitions** option.
- `unknown` or `unavailable` GPS does not geographically exclude fixed-location evidence.
- A real fixed-source state change after a confirmed departure is treated as new arrival evidence and is not suppressed as sticky evidence.

## Compatibility

- Vetted Location continues to use Home Assistant-compatible states: `home`, `not_home`, named active Zones, and `unknown`.
- The new confirmed-departure context is runtime-only and is cleared by a Home Assistant restart or HALP! reload.
- Existing source weights, freshness calculations, Confidence, Consensus, and Source Health behavior remain in place except that geographically impossible old fixed evidence is excluded from the active vote while the protection rule applies.

------------------------------------------------------------------------

  ---------------------
  \# Version 2.0.0

  **Release Date:**
  August 15, 2026

  \## Added - Multiple
  Zone Support!

  \- Added first-class
  support for named
  Home Assistant zones
  in Vetted Location,
  Confidence,
  Consensus, Source
  Health, explanations,
  diagnostics, and
  history. - Added
  exactly one
  fixed-zone assignment
  per BLE tracker and
  per fixed WiFi/router
  tracker. - Added
  **None / Mobile** for
  genuinely mobile
  WiFi/router sources;
  these remain visible
  diagnostically but do
  not vote for an
  absolute zone. -
  Added active-zone
  inventory tracking
  and a persistent
  notification when
  Home Assistant's
  active zone set
  changes after HALP!
  configuration. -
  Added per-zone
  history counts for
  named Vetted Location
  states.

  \## Changed

  \- Generalized the
  second-GPS-update
  feature from Home →
  `not_home` to any
  confirmed GPS
  location
  transition. - Renamed
  the user-facing
  option to **Speed up
  location transitions:
  prioritize second
  matching GPS location
  update.** - Preserved
  the existing 80%
  fast-GPS Confidence
  floor and high-water
  behavior for all
  confirmed location
  transitions. -
  Generalized ordinary
  weighted voting from
  a binary Home/Away
  vote to an N-location
  vote using the same
  source weights,
  freshness factors,
  and reliability
  threshold in every
  zone. - Fixed-source
  positive detection
  votes for its
  configured zone; loss
  of a fixed BLE/router
  detection no longer
  acts as proof that
  the person is outside
  every Home Assistant
  zone. - Configure now
  reconciles current
  Person trackers and
  active zones,
  discarding removed
  trackers and stale
  zone references when
  configuration is
  saved. - Corrected
  **Last Reliable
  Change** so it
  records the last
  reliably established
  location transition
  rather than the last
  reliable/unreliable
  threshold change.

  \## Compatibility

  \- GPS requires no
  new zone mapping. -
  Existing BLE and
  fixed router/WiFi
  trackers without a
  saved zone mapping
  retain
  Home-compatible
  runtime behavior
  until the new
  fixed-zone
  assignments are
  reviewed. HALP!
  raises a persistent
  configuration
  notification until
  that review is
  completed. - The
  stored v1.0.4 GPS
  speedup setting key
  and switch unique ID
  are retained for
  backward
  compatibility even
  though the
  user-facing behavior
  is now multi-zone.
  ---------------------

# Version 1.0.4

**Release Date:** July 30, 2026

## Added

-   Added the per-Person setting **Accelerate `not_home` transition:
    prioritize second `not_home` GPS update**.
-   Added a dashboard-controllable switch for the same setting.
-   Added a detailed calculation guide explaining source weights,
    freshness, Vetted Location, Confidence, Consensus, Source Health,
    and the fast-departure confidence rule.
-   Added explanatory confidence attributes identifying ordinary
    calculation mode versus GPS fast-departure mode.

## Changed

-   Corrected the tracker event callback so repeated state updates from
    a GPS tracker are processed by the asynchronous fast-departure
    handler.
-   When the second consecutive GPS `not_home` update activates fast
    departure, Confidence now has an 80% minimum.
-   While the temporary GPS override remains active, Confidence uses a
    high-water mark: it may rise as other sources agree, but it cannot
    fall.
-   Consensus remains based on actual weighted source agreement and is
    not artificially increased by the GPS override.
-   Source Health explanations now identify when a Fair result reflects
    a trusted GPS departure while slower sources still disagree.
-   The fast `not_home` switch is unavailable when no GPS tracker is
    configured, with the status comment:
    `Unavailable (there is no GPS tracker sensor configured for this person)`.

## Upgrade behavior

-   Existing HALP! entries must explicitly review and save the new
    fast-departure option.
-   Until reviewed, the option remains disabled and HALP! creates a
    persistent notification that is recreated until configuration is
    saved.
-   New entries default the option to enabled.

## Behavior

When enabled, and HALP!'s Vetted Location was `home`, a configured GPS
tracker must first change from `home` to `not_home`. If that same GPS
tracker then publishes another update while its state remains
`not_home`, HALP! immediately changes Vetted Location to `not_home`.

The fast-departure decision starts with at least 80% Confidence.
Confidence can increase, but not decrease, while the temporary override
remains active. Ordinary weighted voting and arrival behavior continue
unchanged, and Consensus continues to show the true percentage of usable
weighted evidence that agrees.

------------------------------------------------------------------------

# Version 1.0.3

**Release Date:** July 2026

## Overview

This maintenance release improves compatibility with Home Assistant by
aligning HALP!'s Vetted Location sensor with Home Assistant's native
location state model.

## Added

-   Improved documentation describing HALP!'s location state model.
-   Added guidance for using the Vetted Location sensor in Home
    Assistant automations.
-   Clarified the distinction between Home Assistant's displayed
    location labels and the underlying entity states.

## Changed

-   HALP! Vetted Location now publishes Home Assistant's native
    `not_home` entity state instead of the custom `away` state.
-   HALP! now behaves as a drop-in replacement for Home Assistant Person
    entities in automations using `home` and `not_home`.
-   Internal location normalization has been updated to preserve Home
    Assistant's native state vocabulary.

## Compatibility

HALP! continues to recognize legacy incoming `away` values from existing
data and normalizes them internally to `not_home` for compatibility.

## Breaking Change

Users with automations similar to:

``` yaml
condition:
  - condition: state
    entity_id: sensor.halp_<person>_vetted_location
    state: away
```

should update them to:

``` yaml
condition:
  - condition: state
    entity_id: sensor.halp_<person>_vetted_location
    state: not_home
```

Home Assistant will normally continue displaying this state as **Away**
in the user interface even though the actual entity state is `not_home`.

------------------------------------------------------------------------

# Version 1.0.2

**Release Date:** July 2026

## Overview

Initial public release.

### Features

-   Multi-person support
-   GPS, BLE, and Router/WiFi source analysis
-   Vetted Location sensor
-   Confidence and Consensus scoring
-   Source Health evaluation
-   Human-readable explanations
-   Conflict detection
-   Historical analysis
-   Ignore tracker classification
-   Tracker mismatch detection
-   Dashboard examples
-   Comprehensive installation documentation
