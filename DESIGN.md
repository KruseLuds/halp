# HALP! DESIGN DOCUMENT

Version: **2.1.0 (Living Document)**

## Purpose

HALP! is a read-only analysis and diagnostics engine for Home Assistant
location and presence.

It explains **why** Home Assistant reached a location decision and how
much confidence should be placed in that decision.

## Mission

HALP! does not determine location.

HALP! determines how much confidence should be placed in existing
location information.

## Source of Truth

Home Assistant remains the source of truth.

HALP! never modifies Person entities, device trackers, zones, or
automations.

## Vetted Location State Vocabulary

HALP!'s Vetted Location sensor uses Home Assistant-compatible location
states:

-   `home`
-   `not_home`
-   any named active Home Assistant zone
-   `unknown`

GPS is dynamic and receives no fixed HALP! zone assignment. Each BLE
tracker is fixed to exactly one active zone. Each fixed WiFi/router
tracker is fixed to exactly one active zone; a genuinely mobile
WiFi/router source may use **None / Mobile** and does not cast an
absolute geographic vote.

Fixed-source positive detection is location evidence. Loss of fixed
detection does not prove `not_home` globally.

The same source weights, freshness rules, reliability threshold,
Confidence formula, and Consensus formula apply to every location. HALP!
does not maintain separate tuning parameters per zone.

When several locations tie, Home retains the existing safety bias if
Home is among the leaders. A tie between non-Home locations resolves to
`unknown`.

The optional second matching GPS update rule can accelerate any location
transition. A candidate must repeat unchanged before HALP! prioritizes
it.

## Ignore Trackers

Version 1.0 introduced Ignore tracker classification.

Ignored trackers: - remain visible for diagnostics - are excluded from
confidence scoring - are excluded from mismatch detection

## Supporting Evidence

Supporting evidence may include:

-   Battery level
-   Charging status
-   WiFi SSID
-   WiFi BSSID
-   WiFi enabled state
-   Bluetooth enabled state
-   GPS enabled state
-   Connection type
-   Location permission status
-   Last update trigger

These values primarily explain confidence rather than determine
confidence.

## Long-Term Goal

HALP! should become the definitive diagnostics tool for Home Assistant
location reliability, and possibly later, presence reliability.

## Optional Faster GPS Location Transition

HALP! can optionally prioritize a second matching GPS update for any
location transition. The setting is enabled by default and is configured
separately for each Person.

The rule applies when:

1.  HALP! has a current Vetted Location.
2.  A configured GPS tracker reports a different Home Assistant location
    state.
3.  The same GPS tracker publishes a later state update while still
    reporting that same new location.

At the third step, HALP! can publish the confirmed location immediately.
The location may be `home`, `not_home`, or a named active Home Assistant
zone. A changing candidate is not accepted. For example,
`School -> not_home -> Park` does not confirm either new state; a later
second Park update can confirm Park.

The temporary priority state ends when ordinary weighted voting
independently supports the same location or when a different location
transition supersedes it. The feature never modifies the Home Assistant
Person, GPS tracker, or zones.

## Geographic snap-back protection after confirmed GPS departure

Version 2.1.0 extends the optional second matching GPS transition rule with a runtime geographic protection model.

When the second matching GPS update confirms that GPS has departed Zone A, HALP! remembers the departed Zone, the confirming GPS entity, and the confirmation time. This context is runtime-only and is not persisted across Home Assistant restarts or HALP! reloads.

A fixed BLE/router source assigned to Zone A is considered old sticky evidence only when all of the following are true:

1.  The source is still positively reporting Zone A.
2.  Its current positive state began before the GPS-confirmed departure.
3.  The same confirming GPS source still has a valid and sufficiently fresh location.
4.  GPS is either `not_home`, or GPS is in another concrete Zone B that does not overlap Zone A.

Home Assistant Zones are treated as circles using their current latitude, longitude, and radius attributes. Two named Zones that overlap are not considered mutually exclusive. If Zone geometry cannot be evaluated safely, HALP! keeps the fixed evidence rather than excluding it.

`unknown` and `unavailable` GPS do not establish geographic exclusion.

A real fixed-source transition from `not_home` to positive presence after the confirmed departure is new arrival evidence, not sticky evidence. If GPS has not updated yet, HALP! temporarily prioritizes that fresh fixed arrival. The temporary arrival priority ends on the next GPS update, after which the source remains ordinary positive evidence.

This design preserves fast fixed-source arrival behavior while preventing a slow BLE/router source from resurrecting a previously departed, geographically incompatible Zone.

## GPS transition option availability and upgrade acknowledgement

The GPS transition option requires at least one configured GPS tracker.
HALP! still exposes the switch when no GPS tracker is configured, but
marks it unavailable and explains why.

For backward compatibility, the stored v1.0.4 setting key and switch
unique ID are retained. Existing entries that have not acknowledged the
option continue to require review before it becomes active; new entries
receive the enabled default.

## Zone assignment and reconciliation

GPS receives no fixed zone assignment because Home Assistant already
reports its dynamic zone state. Each BLE tracker may be assigned to
exactly one active Home Assistant zone. Each fixed WiFi/router tracker
may be assigned to exactly one active zone; a genuinely mobile
WiFi/router source may use **None / Mobile** and therefore does not cast
an absolute geographic vote.

HALP! tracks the configured active-zone inventory. Adding or removing
Home Assistant zones can create a persistent notification instructing
the user to open **Settings -\> Devices & services -\> HALP!** and click
the **gear icon for that Person** to review/update settings. Deleted
trackers and deleted zone references are discarded during
reconfiguration.

## Calculation documentation

The user-facing formulas and decision rules for Vetted Location,
Confidence, Consensus, and Source Health are documented in
[`docs/How_HALP_Calculates_Location_Confidence_Consensus_and_Health.md`](docs/How_HALP_Calculates_Location_Confidence_Consensus_and_Health.md).

During the optional GPS transition priority, confidence has an 80%
minimum and a runtime high-water mark. It may rise as other sources
agree but cannot fall while the override remains active. Consensus is
not altered and continues to report actual weighted source agreement.
