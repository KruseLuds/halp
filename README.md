<p align="center">
  <img src="brand/logo.png" width="350" alt="HALP! Logo">
</p>

<h1 align="center">HALP!</h1>

<p align="center">
Home Assistant Location & Presence analyzer
</p>

HALP! helps Home Assistant users understand, verify, and improve location-based automations.

HALP! does not replace Home Assistant Person entities, GPS trackers, BLE trackers, router trackers, or zone logic.

Instead, HALP! analyzes the location information Home Assistant already has and helps answer a simple question:

> How much should I trust Home Assistant's current location decision?

---

# Why HALP!?

Many Home Assistant users eventually encounter situations like:

* Why didn't my arrival lights turn on?
* Why didn't my garage door automation run?
* Why did Home Assistant think I was still Home?
* Why did Home Assistant think I had left?
* Why does GPS disagree with BLE?
* Why does router tracking never seem to work?
* Which location source should I trust?

Home Assistant provides many ways to determine location.

HALP! helps determine how reliable those methods actually are.

---

# Typical Use Cases

HALP! is especially useful when:

* Arrival automations do not trigger consistently
* Departure automations trigger unexpectedly
* GPS and BLE disagree
* Router tracking appears unreliable
* Multiple location sources produce conflicting results
* Users want objective measurements of tracker reliability

HALP! helps identify which sources deserve trust and which sources should be improved, replaced, classified as Other, or intentionally ignored.

---

# What HALP! Does

HALP! analyzes:

* Person entities
* GPS location sources
* BLE location sources
* Router/WiFi location sources
* Intentionally ignored Person-assigned trackers
* Source freshness
* Source agreement
* Source conflicts
* Historical reliability

HALP! then produces:

* A vetted location assessment (Home, Away, or Unknown)
* A confidence score
* A human-readable explanation
* Source-by-source analysis
* Historical reliability statistics
* Recommendations

---

# What HALP! Does Not Do

HALP! never:

* Modifies Person entities
* Modifies Device Trackers
* Replaces Home Assistant location logic
* Controls automations
* Tracks people independently
* Acts as a GPS tracker
* Acts as a BLE tracker
* Acts as a router tracker

HALP! is intentionally read-only.

---

# Design Philosophy

Most location integrations answer:

> Where is the person?

HALP! answers:

> How much confidence should I place in that answer?

This distinction is the foundation of the project.

---

# Building a Reliable Presence System

Before using HALP!, each person should first be configured in Home Assistant using a standard Person entity.

Each Person should have one or more location sources assigned to it, such as GPS trackers, BLE trackers, and router/WiFi trackers. Home Assistant combines those sources to determine the Person's current location, while HALP! analyzes the quality and reliability of those decisions.

HALP! works best when Home Assistant is configured with multiple independent location sources.

## Tracker Classification During Setup

During setup and Configure, HALP! shows the device trackers currently assigned to the selected Home Assistant Person. Each tracker can be classified as one of the following:

| Classification | Used for HALP! scoring | Suppresses tracker mismatch warnings | Purpose |
| -------------- | ---------------------- | ------------------------------------ | ------- |
| GPS | Yes | Yes | Long-range location evidence, usually from the Home Assistant Companion App, iCloud3, or another GPS tracker. |
| BLE | Yes | Yes | Local presence evidence from Bluetooth-based tracking such as Bermuda, ESPresense, Bluetooth proxies, or companion-app BLE. |
| WiFi | Yes | Yes | Router or WiFi presence evidence from integrations such as UniFi, Omada, OpenWRT, or other router trackers. |
| Other | No | No | A normal non-location classification. HALP! does not score it, and it does not hide mismatch warnings. |
| Ignore | No | Yes | A tracker intentionally excluded from HALP!. Use this when a tracker should remain assigned to the Person but should not be analyzed by HALP!. |

Other and Ignore are intentionally different.

Other means the tracker is not one of HALP!'s scored location source types. If that tracker remains assigned to the Home Assistant Person, HALP! may still warn that the Person has an assigned tracker that HALP! is not using.

Ignore means the tracker is intentionally excluded. Ignored trackers are not used for scoring, confidence, consensus, source health, history samples, or source details, but they are treated as accounted for when HALP! checks for tracker mismatch warnings.

### Important: Ignore Only Affects HALP!

Ignore only affects HALP!'s analysis.

HALP! does not modify Home Assistant Person entities and cannot change how Home Assistant calculates a Person's state.

If a tracker remains assigned to a Home Assistant Person but is classified as Ignore within HALP!, Home Assistant will continue using that tracker when determining the Person's Home, Away, and zone states.

HALP! will exclude the tracker from its own analysis, scoring, confidence calculations, consensus calculations, source health calculations, historical statistics, and diagnostics.

If a tracker is ignored because it produces unreliable location information, users should consider using HALP!'s Vetted Location sensor for location-based automations instead of relying solely on the Home Assistant Person state.

HALP! also continuously monitors Person tracker assignments. If a tracker is added to or removed from a Home Assistant Person, HALP! will automatically create or clear tracker mismatch notifications without requiring a Home Assistant restart or HALP! reload.

No single tracking method is perfect. GPS can be delayed, BLE can have range limitations, and router tracking can miss devices due to power-saving features or WiFi roaming behavior.

For the most reliable results, combine GPS, BLE, and WiFi/router tracking whenever possible.

HALP! is designed to help determine which sources are actually reliable in your environment.

## GPS Tracking

GPS is typically the primary source used to determine when a person arrives at or leaves Home.

Recommended sources include:

* Home Assistant Companion App
* iCloud3
* Other GPS-capable device trackers

Best practices:

* Disable battery optimization for the Home Assistant Companion App.
* Allow background location access.
* Allow precise location access when available.
* Verify that Home Assistant receives regular location updates.
* Confirm that Home and other zones are correctly configured.

GPS generally provides the best long-range presence information but may not immediately reflect indoor movement.

## BLE Tracking

BLE is often the fastest method for confirming that someone is physically present at Home.

Recommended sources include:

* ESPresense
* Bermuda
* Bluetooth Proxies
* Companion App BLE tracking

Best practices:

* Deploy multiple BLE receivers throughout the home.
* Avoid relying on a single Bluetooth receiver.
* Place receivers away from major sources of RF interference.
* Verify that the phone advertises BLE consistently.
* Test detection reliability in common living areas.

BLE is often extremely effective for confirming presence but usually cannot determine precise away locations.

## WiFi / Router Tracking

Router-based tracking can provide useful supporting evidence when a device is connected to the home network.

Examples include:

* UniFi
* Omada
* OpenWRT
* Router integrations supported by Home Assistant

Best practices:

* Ensure devices reconnect automatically to home WiFi.
* Verify that the router integration reports device presence reliably.
* If using DHCP reservations or static IP assignments, ensure the phone or device is configured to use a consistent MAC address for the home WiFi network. Devices configured to randomize their MAC address may receive different identities from the router, preventing reliable DHCP reservation assignment and causing router-based presence tracking to become unreliable.
* Be aware that modern phones may enter aggressive power-saving modes.
* Treat router tracking as supporting evidence rather than the sole source of truth.

Router tracking can be very reliable in some environments and nearly unusable in others. HALP! helps determine which is true for your installation.

## Recommended Approach

For most installations:

GPS
+
BLE
+
WiFi / Router Tracking

provides significantly better results than relying on any single source.

HALP! evaluates how well those sources agree, how recently they reported, and how reliable they have historically been so that you can make informed decisions about your Home Assistant automations.

---

# Location Analysis Engine

HALP! evaluates all configured location sources.

Supported source categories:

Ignored trackers are not supported source categories for scoring. They are saved only so HALP! knows a Person-assigned tracker was excluded on purpose.

## GPS Sources

Examples:

* Home Assistant Companion App GPS
* iCloud3
* Other GPS-based trackers

A person may have zero, one, or many GPS sources.

---

## BLE Sources

Examples:

* Companion App BLE
* Bermuda
* ESPresense
* Bluetooth Proxy
* Other BLE-based trackers

A person may have zero, one, or many BLE sources.

---

## Router/WiFi Sources

Examples:

* UniFi
* Omada
* OpenWRT
* Other router-based trackers

A person may have zero, one, or many router sources.

---

# Source Freshness

HALP! evaluates freshness using:

```text
last_updated
```

Freshness answers:

> When did this source last report?

A fresh source generally deserves more trust than a stale source.

---

# State Duration

HALP! separately evaluates:

```text
last_changed
```

State duration answers:

> How long has this source been in the same state?

Example:

```text
GPS reports Home
Updated: 2 minutes ago
Unchanged: 9 hours
```

This means the source has continued reporting Home and recently refreshed.

---

# Historical Reliability

Historical analysis is expected to become one of HALP!'s most valuable features.

Example:

```text
BLE detected this phone during 46 of 50 GPS-confirmed Home visits.

BLE Reliability: 92%
```

Example:

```text
Router tracking detected this phone during 8 of 50 GPS-confirmed Home visits where WiFi appeared available.

Router Reliability: 16%
```

These measurements are installation-specific.

A source that works perfectly in one home may be nearly useless in another.

HALP! measures actual performance rather than relying on assumptions.

---

# Home Visit Definition

A Home Visit begins when the selected reference source transitions:

```text
Away -> Home
```

A Home Visit ends when the selected reference source transitions:

```text
Home -> Away
```

Everything in between is considered one Home Visit.

---

# Source Success During A Home Visit

A source receives credit for a Home Visit if it successfully detects the person at least once during that visit.

Temporary disconnects during the visit do not automatically make the visit a failure.

HALP! measures usefulness rather than connection stability.

---

# Example Analysis

Current Sources

| Source | State | Updated | Reliability |
| ------ | ----- | ------- | ----------- |
| GPS | Home | 2 min ago | 99% |
| BLE | Home | 1 min ago | 94% |
| Router | Away | 12 min ago | 18% |

Result

```text
Location: Home

Confidence: 96%
```

Explanation

```text
GPS and BLE currently support Home and were updated recently.

Router tracking disagrees, but historical analysis shows router tracking has only detected this device during 18% of GPS-confirmed Home visits where WiFi appeared available.

Router evidence is currently discounted.
```

---

# Supporting Evidence

HALP! may optionally use supporting sensors to help explain results.

Examples:

* Battery level
* Charging state
* WiFi SSID
* WiFi BSSID
* Connection type
* Location permission status

These values help explain confidence but are not primary location sources.

---

# Dashboard Examples

> **Note:** The confidence and consensus charts shown below are currently only partially populated. The most recent HALP! build included cleanup and removal of development and test history data. These screenshots will be updated after approximately two weeks of production data collection.

## Dashboard Overview

<p align="center">
  <img src="images/dashboard_example.jpg" width="450" alt="HALP Dashboard">
</p>

The dashboard provides:

* Current vetted location
* Confidence score
* Consensus score
* Source health
* Historical confidence trends
* Historical consensus trends

---

## Diagnostics and Explainability

<p align="center">
  <img src="images/dashboard_diagnostics.jpg" width="450" alt="HALP Diagnostics">
</p>

The diagnostics section provides:

* Conflict detection
* Stale source detection
* Last reliable location timestamp
* Human-readable location explanations
* Source-by-source status reporting

Example explanation:

```text
Home with 99% confidence. 2 of 4 sources usable. Sources: GPS=home; BLE=home; HACS router=missing; Official router=missing.
```

---

# Example Dashboard Configuration

HALP! does not automatically create a dashboard because Home Assistant YAML dashboards cannot automatically loop through all configured people without additional custom frontend cards.

The examples below are intended as starting points.

## Finding Your HALP! Sensor Names

After creating a HALP! person entry:

```text
Settings -> Devices & Services -> Entities
```

Search for:

```text
halp_
```

You will see sensors similar to:

```text
sensor.halp_john_vetted_location
sensor.halp_john_location_confidence
sensor.halp_john_consensus_score
sensor.halp_john_source_health
```

Replace placeholders such as:

```text
<person_name_1>
```

with the actual HALP! entity slug.

Example:

```text
<person_name_1> -> john
```

would produce:

```text
sensor.halp_john_vetted_location
```

Note: The Vetted Location sensor is HALP!'s own location determination.

Meaning, if one or more Person-assigned trackers are intentionally classified as Ignore, this sensor is generally the recommended location sensor to use for automations because it reflects HALP!'s analyzed location result rather than Home Assistant's default Person calculation.

---

## Single Person Example Dashboard

```yaml
title: HALP!

views:
  - title: HALP! Location Analysis
    path: overview
    icon: mdi:map-search

    cards:
      - type: entities
        title: <person_name_1>
        entities:
          - entity: sensor.halp_<person_name_1>_vetted_location
            name: Location
          - entity: sensor.halp_<person_name_1>_location_confidence
            name: Confidence
          - entity: sensor.halp_<person_name_1>_consensus_score
            name: Consensus
          - entity: sensor.halp_<person_name_1>_source_health
            name: Health

      - type: history-graph
        title: Confidence
        hours_to_show: 336
        entities:
          - entity: sensor.halp_<person_name_1>_confidence_trend
            name: Person #1

      - type: history-graph
        title: Consensus
        hours_to_show: 336
        entities:
          - entity: sensor.halp_<person_name_1>_consensus_trend
            name: Person #1

      - type: entities
        title: History (14 days)
        entities:
          - entity: sensor.halp_<person_name_1>_history_summary
            name: Person #1

      - type: entities
        title: Diagnostics
        entities:
          - entity: sensor.halp_<person_name_1>_conflict_details
            name: Person #1 conflicts
            icon: mdi:alert-circle-outline
          - entity: sensor.halp_<person_name_1>_stale_sources
            name: Person #1 stale
          - entity: sensor.halp_<person_name_1>_last_reliable_change
            name: Person #1 last reliable
          - entity: sensor.halp_<person_name_1>_location_explanation
            name: Explanation
            icon: mdi:text-box-search
```

---

## Two Person Example Dashboard

This example uses two HALP! person entries.

Replace:

```text
<person_name_1>
<person_name_2>
```

with the actual HALP! entity slugs from your Home Assistant system.

```yaml
title: HALP!

views:
  - title: HALP! Location Analysis
    path: overview
    icon: mdi:map-search

    cards:
      - type: grid
        columns: 2
        square: false
        cards:
          - type: vertical-stack
            cards:
              - type: entities
                title: <person_name_1>
                entities:
                  - entity: sensor.halp_<person_name_1>_vetted_location
                    name: Location
                  - entity: sensor.halp_<person_name_1>_location_confidence
                    name: Confidence
                  - entity: sensor.halp_<person_name_1>_consensus_score
                    name: Consensus
                  - entity: sensor.halp_<person_name_1>_source_health
                    name: Health

          - type: vertical-stack
            cards:
              - type: entities
                title: <person_name_2>
                entities:
                  - entity: sensor.halp_<person_name_2>_vetted_location
                    name: Location
                  - entity: sensor.halp_<person_name_2>_location_confidence
                    name: Confidence
                  - entity: sensor.halp_<person_name_2>_consensus_score
                    name: Consensus
                  - entity: sensor.halp_<person_name_2>_source_health
                    name: Health

      - type: grid
        columns: 2
        square: false
        cards:
          - type: history-graph
            title: Confidence
            hours_to_show: 336
            entities:
              - entity: sensor.halp_<person_name_1>_confidence_trend
                name: Person #1
              - entity: sensor.halp_<person_name_2>_confidence_trend
                name: Person #2

          - type: history-graph
            title: Consensus
            hours_to_show: 336
            entities:
              - entity: sensor.halp_<person_name_1>_consensus_trend
                name: Person #1
              - entity: sensor.halp_<person_name_2>_consensus_trend
                name: Person #2

      - type: vertical-stack
        cards:
          - type: entities
            title: History (14 days)
            entities:
              - entity: sensor.halp_<person_name_1>_history_summary
                name: Person #1
              - entity: sensor.halp_<person_name_2>_history_summary
                name: Person #2

          - type: custom:expander-card
            title: Diagnostics
            padding: true
            clear: false
            cards:
              - type: entities
                entities:
                  - entity: sensor.halp_<person_name_1>_conflict_details
                    name: Person #1 conflicts
                    icon: mdi:alert-circle-outline
                  - entity: sensor.halp_<person_name_1>_stale_sources
                    name: Person #1 stale
                  - entity: sensor.halp_<person_name_1>_last_reliable_change
                    name: Person #1 last reliable
                  - entity: sensor.halp_<person_name_1>_location_explanation
                    name: Explanation
                    icon: mdi:text-box-search

                  - entity: sensor.halp_<person_name_2>_conflict_details
                    name: Person #2 conflicts
                    icon: mdi:alert-circle-outline
                  - entity: sensor.halp_<person_name_2>_stale_sources
                    name: Person #2 stale
                  - entity: sensor.halp_<person_name_2>_last_reliable_change
                    name: Person #2 last reliable
                  - entity: sensor.halp_<person_name_2>_location_explanation
                    name: Explanation
                    icon: mdi:text-box-search
```

---

## Example configuration.yaml Entry

If using a YAML dashboard, add a dashboard entry similar to this:

```yaml
lovelace:
  dashboards:
    halp:
      mode: yaml
      title: HALP!
      icon: mdi:map-search
      show_in_sidebar: true
      filename: /config/halp_dashboard.yaml
```

Then place your dashboard YAML at:

```text
/config/halp_dashboard.yaml
```

Restart Home Assistant or reload Lovelace dashboards after adding the dashboard entry.

---

# Future Direction

Planned future enhancements include:

* Historical source reliability scoring
* Automatic source weighting
* Zone-specific reliability analysis
* Reliability recommendation engine
* Long-term reliability trend analysis
* Dynamic dashboard generation

The focus will remain on location reliability, confidence, diagnostics, and explainability.

---

# License

See the repository license for licensing terms and conditions.

---

Created with the assistance of AI during development and documentation. HALP! DOES NOT USE ANY AI AT ANY TIME DURING INSTALLATION OR OPERATION.
