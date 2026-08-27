# How HALP! Calculates Location, Confidence, Consensus, and Source Health

HALP! analyzes the location sources already configured in Home
Assistant. It does not modify Person entities, device trackers, zones,
or automations.

This document explains the calculations behind HALP!'s principal
dashboard values in clear English. The source code remains the final
technical authority, primarily in `custom_components/halp/helpers.py`.

## 1. Location vocabulary and source types

HALP! uses Home Assistant-compatible location states. A Vetted Location
may be:

-   `home` (as per HA standard, firendly name is all lowervase)
-   `not_home` (as per HA standard, friendly name shown as all lowercare `away` and actally specifically means, not in any zone)
-   the name of an active Home Assistant zone, such as `Work`, `School`,
    or `Park`
-   `unknown` when HALP! cannot choose a reliable current location from
    usable evidence

GPS trackers are dynamic. HALP! does not assign a zone to a GPS tracker
because Home Assistant already evaluates the GPS position against
configured zones.

BLE and fixed WiFi/router trackers are different. They identify presence
at a fixed receiving location rather than geographic position by
themselves:

-   each BLE tracker is assigned to exactly one active Home Assistant
    zone;
-   each fixed WiFi/router tracker is assigned to exactly one active
    Home Assistant zone;
-   a WiFi/router tracker that is genuinely mobile may be configured as
    **None / Mobile**. It remains visible in HALP! diagnostics but does
    not vote for an absolute geographic location;
-   one BLE tracker cannot represent several HALP! zones. If the same
    physical BLE device is detected at several sites, Home Assistant
    must expose separate location-specific tracker entities for HALP! to
    assign those entities to different zones.

A fixed tracker's positive detection votes for its configured zone. Loss
of that fixed detection does not prove that the person is outside every
Home Assistant zone, so a fixed source reporting `not_home` does not
cast a global `not_home` vote.

## 2. Source voting strength

Each configured GPS, BLE, or router/WiFi tracker has a voting weight.

Default weights are:

  Source type     Default weight
  ------------- ----------------
  GPS                        100
  BLE                         70
  Router/WiFi                 55

Weights are relative voting strengths, not percentages. Users may change
them in the HALP! Configure flow.

The same weight for a source type applies in every zone. HALP! does not
require separate Home, Work, School, or other-zone weights.

HALP! also applies a freshness factor based on how recently the tracker
updated:

  Time since last update                Freshness factor
  ----------------------------------- ------------------
  15 minutes or less                                1.00
  More than 15 through 60 minutes                   0.90
  More than 60 through 240 minutes                  0.75
  More than 240 through 480 minutes                 0.50
  More than 480 minutes                             0.00

A source's effective score is:

``` text
effective score = configured weight × freshness factor
```

A source with a freshness factor of zero is not usable in the current
vote.

## 3. Vetted Location

Under ordinary operation, HALP! totals the effective scores for every
location reported by usable sources.

For example:

``` text
home score   = sum of usable source scores voting Home
work score   = sum of usable source scores voting Work
school score = sum of usable source scores voting School
not_home score = sum of usable source scores voting not_home
```

The location with the largest total wins.

If no usable source can vote for a location, Vetted Location is
`unknown`.

If Home is tied for the largest score, HALP! preserves the existing
safety bias toward `home`. A tie between two non-Home locations resolves
to `unknown` rather than choosing an arbitrary zone.

### Optional fast GPS location-transition rule

When **Speed up location transitions: prioritize second matching GPS
location update** is enabled, HALP! may temporarily prioritize a new GPS
location before slower fixed sources catch up.

The generalized rule is:

1.  HALP! has a current Vetted Location A.
2.  A configured GPS tracker changes to a different valid location B.
3.  HALP! remembers B as that GPS tracker's transition candidate.
4.  The same GPS tracker later updates again and still reports B.
5.  HALP! may immediately publish B as Vetted Location.

This applies equally to Home, named zones, and `not_home`.

Examples:

``` text
home -> Work -> Work
Work -> not_home -> not_home
School -> Park -> Park
```

In each example, the second matching GPS update confirms the new
location.

A changing candidate is not prematurely accepted. For example:

``` text
School -> not_home -> Park
```

does not confirm `not_home` or Park. If the next GPS update is still
Park:

``` text
School -> not_home -> Park -> Park
```

HALP! may then prioritize Park. This prevents a brief gap between nearby
zones from being treated as a confirmed intermediate location.

The temporary priority ends when ordinary weighted voting independently
reaches the same target location, or when GPS moves to a different
location before the target is independently supported.

### Geographic snap-back protection

Version 2.1.0 adds a second protection around a GPS-confirmed departure.
Once the second matching GPS update confirms departure from a concrete
Zone A, HALP! remembers that departed Zone at runtime.

A fixed BLE/router source assigned to Zone A may be excluded from the
current vote when its positive state began before that confirmed
departure and it is still merely reporting the old Zone.

The exclusion applies only while the same confirming GPS source still
provides contradictory valid location evidence:

-   if GPS reports `not_home`, the old Zone A fixed evidence is
    geographically incompatible with the confirmed GPS result;
-   if GPS reports another named Zone B, HALP! compares the current Home
    Assistant Zone circles using latitude, longitude, and radius;
-   if Zone A and Zone B do not overlap, the old fixed evidence for Zone
    A is excluded;
-   if the Zones overlap, normal voting continues because both Zone
    memberships can be geographically possible;
-   `unknown` or `unavailable` GPS does not exclude the fixed evidence.

If a fixed source actually changes state after the confirmed departure,
its new positive state is not treated as the old sticky evidence.

### Fresh fixed-source arrival priority

A real fixed BLE/router transition from `not_home` to positive presence
for its configured Zone is fresh arrival evidence. When GPS has not
updated yet, HALP! temporarily prioritizes that newly detected fixed
Zone so arrival behavior remains fast.

That temporary fixed-arrival priority ends on the next GPS update. The
fixed source then remains ordinary positive evidence in the normal
weighted calculation.

This is intentionally different from a source that never changed from
its old positive state after departure.

## 4. Confidence

Confidence answers:

> How strongly should HALP!'s current Vetted Location be trusted?

For ordinary weighted evidence, HALP! separates usable sources into
agreeing and conflicting groups.

``` text
agreeing score = sum of scores matching Vetted Location
conflicting score = sum of scores voting for other locations
strongest score = largest single agreeing source score
```

HALP! then calculates:

``` text
raw confidence =
    strongest agreeing score
    + 25% of all additional agreeing score
    - 40% of conflicting score
```

The result is rounded and limited to 0 through 99. HALP! never reports
100% confidence because location certainty is never perfect.

The same formula applies regardless of whether the Vetted Location is
Home, Away, Work, School, Park, or another named zone.

### Confidence during a fast GPS transition

Two consecutive matching GPS location updates are deliberate evidence
even when slower BLE and router sources still report an earlier
location. Therefore, while the fast GPS transition is active:

-   reported confidence is never below **80%**;
-   ordinary weighted confidence is still calculated and exposed for
    transparency;
-   confidence may increase as additional sources agree;
-   a runtime high-water mark prevents confidence from falling during
    that temporary priority period.

When ordinary weighted voting independently supports the GPS-prioritized
target location, the special floor is removed and normal confidence
calculation resumes.

## 5. Consensus

Consensus answers a different question:

> What percentage of the usable weighted evidence agrees with Vetted
> Location?

``` text
consensus =
    agreeing usable score
    ÷ total usable score
    × 100
```

Consensus ranges from 0 through 100.

HALP! intentionally does not raise consensus during a fast GPS
transition. A low consensus value truthfully shows that the GPS
transition has been confirmed while slower fixed sources have not yet
caught up.

High confidence and low consensus can therefore coexist briefly:

-   Confidence expresses trust in the final decision.
-   Consensus expresses agreement among all current usable sources.

## 6. Source Health

Source Health provides a compact dashboard label: **Excellent**,
**Good**, **Fair**, **Poor**, or **Critical**.

The evaluation order is:

1.  **Critical**
    -   no sources are configured;
    -   no configured source is usable; or
    -   every source is missing, unavailable, or unknown.
2.  **Poor**
    -   more than half of configured location sources are stale; or
    -   confidence is below 40%.
3.  **Fair**
    -   two or more usable sources conflict with Vetted Location; or
    -   consensus is below 70%.
4.  **Good**
    -   at least one source is stale, missing, unknown, or conflicting;
        or
    -   the source set is usable but does not meet the stricter
        Excellent criteria.
5.  **Excellent**
    -   confidence is at least 80%;
    -   consensus is at least 90%;
    -   no usable source is stale, missing, unknown, or conflicting.

During a fast GPS transition, Source Health may correctly be **Fair**
even with 80% or greater confidence. This communicates that HALP! trusts
the confirmed GPS transition while several slower sources still
disagree.

## 7. Zone configuration and reconciliation

HALP! stores fixed-zone assignments by Home Assistant zone entity ID,
not only by friendly name.

When the Configure flow is opened and saved:

-   trackers no longer assigned to the Person are discarded from HALP!
    configuration;
-   deleted zone references are discarded;
-   newly created active zones appear as choices;
-   BLE requires exactly one active zone per BLE tracker;
-   fixed WiFi/router requires exactly one active zone per tracker;
-   mobile WiFi/router may use **None / Mobile**;
-   GPS never receives a fixed-zone assignment.

HALP! also records the set of active zones when configuration is saved
and can notify the user if the active Home Assistant zone set later
changes, prompting a configuration review.

## 8. Last Reliable Change

**Last Reliable Change** records the last time HALP! reliably
established a different Vetted Location.

It is not merely the last time confidence crossed the reliability
threshold.

Examples that can update the timestamp include:

``` text
home -> Work
Work -> Park
Park -> not_home
not_home -> home
```

Confidence changes while the reliable location itself remains unchanged
do not move this timestamp. The value is restored across Home Assistant
restarts.

## 9. Why values change over time

HALP! recalculates as trackers update and age:

-   a new agreeing update can raise confidence and consensus;
-   a source voting for a different location can reduce ordinary
    confidence and consensus;
-   a stale source loses voting strength;
-   a very stale source stops voting;
-   a fast GPS transition can establish a new zone before slower fixed
    sources catch up;
-   the fast GPS confidence floor remains non-decreasing until ordinary
    weighted voting independently supports the same target.

## 10. Related source files

The principal implementation is located in:

-   `custom_components/halp/helpers.py` --- source analysis, fixed-zone
    mapping, and calculations;
-   `custom_components/halp/__init__.py` --- runtime GPS transition
    handling and configuration-change monitoring;
-   `custom_components/halp/config_flow.py` --- tracker classification
    and fixed-zone assignment;
-   `custom_components/halp/sensor.py` --- Home Assistant sensors and
    explanatory attributes;
-   `custom_components/halp/history.py` --- rolling and daily multi-zone
    history;
-   `custom_components/halp/const.py` --- defaults, thresholds, zone
    mapping keys, and runtime keys.
