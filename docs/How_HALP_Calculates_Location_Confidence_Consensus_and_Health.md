# How HALP! Calculates Location, Confidence, Consensus, and Source Health

HALP! analyzes the location sources already configured in Home Assistant. It does not modify Person entities, device trackers, zones, or automations.

This document explains the calculations behind HALP!'s principal dashboard values in clear English. The source code remains the final technical authority, primarily in `custom_components/halp/helpers.py`.

## 1. Source voting strength

Each configured GPS, BLE, or router/WiFi tracker has a voting weight.

Default weights are:

| Source type | Default weight |
| --- | ---: |
| GPS | 100 |
| BLE | 70 |
| Router/WiFi | 55 |

Weights are relative voting strengths, not percentages. Users may change them in the HALP! Configure flow.

HALP! also applies a freshness factor based on how recently the tracker updated:

| Time since last update | Freshness factor |
| --- | ---: |
| 15 minutes or less | 1.00 |
| More than 15 through 60 minutes | 0.90 |
| More than 60 through 240 minutes | 0.75 |
| More than 240 through 480 minutes | 0.50 |
| More than 480 minutes | 0.00 |

A source's effective score is:

```text
effective score = configured weight × freshness factor
```

A source with a freshness factor of zero is not usable in the current vote.

## 2. Vetted Location

Under ordinary operation, HALP! adds the effective scores of usable sources reporting `home` and separately adds the effective scores of usable sources reporting `not_home`.

```text
home score = sum of usable Home source scores
not_home score = sum of usable Away source scores
```

If both totals are zero, Vetted Location is `unknown`.

Otherwise, the larger total wins. A tie resolves to `home`, which deliberately avoids declaring a departure without stronger Away evidence.

### Optional fast-departure rule

When **Speed up `not_home` transition** is enabled, HALP! may temporarily bypass ordinary weighted voting:

1. Vetted Location was `home`.
2. A configured GPS tracker changes from `home` to `not_home`.
3. The same GPS tracker later updates again while remaining `not_home`.

HALP! then publishes `not_home` immediately. The rule does not alter the underlying tracker or Home Assistant Person.

The temporary override ends when ordinary weighted voting also reaches `not_home`, or when a new positive Home transition occurs.

## 3. Confidence

Confidence answers:

> How strongly should HALP!'s current Vetted Location be trusted?

For ordinary weighted evidence, HALP! separates usable sources into agreeing and conflicting groups.

```text
agreeing score = sum of scores matching Vetted Location
conflicting score = sum of scores opposing Vetted Location
strongest score = largest single agreeing source score
```

HALP! then calculates:

```text
raw confidence =
    strongest agreeing score
    + 25% of all additional agreeing score
    - 40% of conflicting score
```

The result is rounded and limited to 0 through 99. HALP! never reports 100% confidence because location certainty is never perfect.

This formula intentionally gives the strongest credible source most of the value, gives smaller credit to corroborating sources, and penalizes fresh disagreement.

### Confidence during fast GPS departure

Two consecutive GPS-away updates are deliberate evidence even when slower BLE and router sources still report Home. Therefore, while the fast-departure override is active:

- reported confidence is never below **80%**;
- ordinary weighted confidence is still calculated and exposed for transparency;
- confidence may increase as additional sources agree;
- a runtime high-water mark prevents confidence from falling during that temporary override.

When ordinary weighted voting independently supports `not_home`, the special floor is removed and normal confidence calculation resumes.

## 4. Consensus

Consensus answers a different question:

> What percentage of the usable weighted evidence agrees with Vetted Location?

```text
consensus =
    agreeing usable score
    ÷ total usable score
    × 100
```

Consensus ranges from 0 through 100.

HALP! intentionally does **not** raise consensus during the fast-departure override. A value such as 36% truthfully shows that GPS has confirmed departure while slower local sources have not yet caught up.

High confidence and low consensus can therefore coexist for a short period. That is not contradictory:

- Confidence expresses trust in the final decision.
- Consensus expresses agreement among all current sources.

## 5. Source Health

Source Health provides a compact dashboard label: **Excellent**, **Good**, **Fair**, **Poor**, or **Critical**.

The evaluation order is:

1. **Critical**
   - no sources are configured;
   - no configured source is usable; or
   - every source is missing, unavailable, or unknown.

2. **Poor**
   - more than half of configured sources are stale; or
   - confidence is below 40%.

3. **Fair**
   - two or more usable sources conflict with Vetted Location; or
   - consensus is below 70%.

4. **Good**
   - at least one source is stale, missing, unknown, or conflicting; or
   - the source set is usable but does not meet the stricter Excellent criteria.

5. **Excellent**
   - confidence is at least 80%;
   - consensus is at least 90%;
   - no source is stale, missing, unknown, or conflicting.

During fast GPS departure, Source Health may correctly be **Fair** even with 80% or greater confidence. This communicates that HALP! trusts the confirmed GPS departure while several slower sources still disagree.

## 6. Why values change over time

HALP! recalculates as trackers update and age:

- a new agreeing update can raise confidence and consensus;
- a conflicting update can reduce ordinary confidence and consensus;
- a stale source loses voting strength;
- a very stale source stops voting;
- the fast GPS departure confidence floor remains non-decreasing until ordinary Away voting takes over.

This is why the dashboard can show a confident early departure followed by gradually improving consensus as BLE and router trackers recognize that the person has left.

## 7. Related source files

The principal implementation is located in:

- `custom_components/halp/helpers.py` — source analysis and calculations;
- `custom_components/halp/__init__.py` — runtime fast-departure event handling;
- `custom_components/halp/sensor.py` — Home Assistant sensors and explanatory attributes;
- `custom_components/halp/const.py` — defaults, thresholds, and runtime keys.
