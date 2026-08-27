<p align="center">
  <img src="https://raw.githubusercontent.com/KruseLuds/halp/main/brand/logo.png" width="350" alt="HALP! Logo">
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

# What's New in Version 2.1.0

Version 2.1.0 builds on HALP!'s multi-zone location consensus system by preventing slow fixed-location sources from temporarily pulling Vetted Location back to a Zone that GPS has already confirmed was left.

## Geographic Snap-Back Protection

When the optional **Speed up location transitions** feature confirms a GPS departure with a second matching GPS update, HALP! remembers that departed Zone at runtime.

If a fixed BLE or router/WiFi source was already positively reporting that old Zone before the confirmed departure and simply continues reporting it afterward, HALP! can identify that as old "sticky" evidence.

* If current GPS reports `not_home`, the sticky fixed source cannot pull Vetted Location back to the departed Zone.
* If current GPS reports another named Zone, HALP! compares the actual Home Assistant Zone circles. The old fixed evidence is excluded only when the departed Zone and current GPS Zone do **not** overlap.
* If the Zones overlap, normal voting continues because both Zone memberships may be geographically possible.
* `unknown` or `unavailable` GPS does not exclude fixed-location evidence.
* No learned timer or fixed delay is used.

Fresh arrival evidence remains intentionally fast. If a fixed BLE/router source genuinely changes from `not_home` to positive presence for its configured Zone while GPS has not yet updated, HALP! treats that as new arrival evidence and can immediately prioritize that Zone. The temporary arrival priority ends when GPS next updates.

Bug fix: HALP! also preserves Home Assistant Zone friendly names exactly in human-facing explanations. A Zone such as `Wendy's` therefore remains `Wendy's` instead of being changed to `Wendy'S`.

## Multi-Zone Location Support

HALP! can now evaluate presence across **every Zone configured in Home Assistant**, rather than treating location as simply Home or Away.

* Vetted Location can report `home`, `not_home`, or a named Home Assistant Zone.
* GPS sources provide dynamic location evidence across Home Assistant Zones.
* Fixed-location sources such as BLE and router/WiFi presence can be associated with a specific Zone.
* HALP! combines the available evidence to determine the most reliable current location while accounting for source freshness, agreement, and conflicts.
* Positive evidence that a person is at a location is treated differently from the loss of evidence that the person is there.

This gives HALP! multi-zone location functionality with location-consensus logic that is independent of the standard Home Assistant Person state.

## Faster Departure Detection Across All Zones

HALP! can recognize a departure from a previously confirmed location faster than the standard Home Assistant Person state when slower location sources lag behind GPS. This now works automatically with not just the Home or selected Zones, but **EVERY Zone that is set up in Home Assistant**.

### Optional faster zone-departure detection

An exposed on/off switch, which can be added to a Home Assistant dashboard, allows HALP! to update the Vetted Location more quickly when leaving any Zone, such as Home.

For example, after leaving Home, HALP! can report the Vetted Location as `not_home` (displayed as **Away** by Home Assistant) as soon as a second consecutive GPS update confirms that the person is no longer in the Home Zone. This allows HALP! to recognize departures from a previously confirmed location faster than the standard Home Assistant Person state when slower location sources lag behind GPS.

Requiring a second GPS update also helps protect against GPS "jitter," such as brief location readings outside a Zone boundary while moving slowly near its edge.

The feature can be enabled or disabled at any time through either:

* **Settings → Devices & Services → HALP! → Configure**
* The HALP! switch entity created for each configured Person

The setting is enabled by default.

## Sensor Classification and Fixed-Location Configuration

HALP! v2.0.0 introduced expanded sensor classification so HALP! knows both **what kind of location evidence a source provides** and, when appropriate, **where that source is physically fixed**.

Each Person-assigned sensor can be classified as:

* **BLE** — fixed-location source
* **GPS** — dynamic location source
* **Router** — fixed-location source
* **Other** — can be configured as fixed or dynamic
* **None** — explicitly excluded from HALP!'s location calculation

A fixed-location source must be assigned to a real Home Assistant Zone. This allows, for example, a BLE or router/WiFi source at Home to provide strong positive evidence for Home while GPS continues to provide dynamic evidence across all Zones.

`None` is a valid classification. It intentionally excludes that sensor from HALP!'s calculation and does not generate a missing-classification warning.

## Configuration Reconciliation and Validation

HALP! now reconciles saved configuration against the current Home Assistant People, sensors, and Zones when configuration is opened.

* References to removed People, sensors, or Zones are discarded rather than retained as stale configuration.
* Required classifications and fixed-location assignments are validated before configuration can be saved.
* Fixed-location sources require a valid Zone assignment.
* Existing installations are guided through any configuration updates required by the new multi-zone model.

## Existing Installations

Version 2.0.0 substantially expands HALP!'s location model. After upgrading, review each HALP! Person configuration and verify the classification and fixed-location assignment of each presence sensor.

HALP! may create a persistent notification when an existing Person configuration needs attention. Open **Settings → Devices & services → HALP!** and use the **gear icon for that Person** to review and update the configuration.

## Understanding the calculations

For a detailed plain-English explanation of Vetted Location, source weights, freshness, Confidence, Consensus, Source Health, and HALP!'s location decision rules, see:

**[How HALP! Calculates Location, Confidence, Consensus, and Source Health](docs/How_HALP_Calculates_Location_Confidence_Consensus_and_Health.md)**

## Roadmap

HALP! will continue exploring additional ways to make confirmed location transition updates even faster while preserving the reliability protections that help prevent false transitions.

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

* A vetted location assessment (Home, Away, or Unknown), using Home Assistant-compatible entity states: `home`, `not_home`, and `unknown`
* A confidence score
* A human-readable explanation
* Source-by-source analysis
* Historical reliability statistics
* Recommendations

See **[How HALP! Calculates Location, Confidence, Consensus, and Source Health](docs/How_HALP_Calculates_Location_Confidence_Consensus_and_Health.md)** for the exact formulas and decision rules.

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


# Installation

> [!IMPORTANT]
>
> ## **PLEASE READ THIS FIRST**
>
> **HALP! analyzes the presence system you have already built in Home Assistant. It does not create Person entities or location trackers for you.**
>
> # **[READ: Building a Reliable Home Assistant Presence System](docs/Building_a_Reliable_Presence_System.md)**
>
> **That guide explains how to create a Person, configure GPS, BLE, and router/WiFi trackers, prepare Android and iPhone devices, prevent MAC-address changes from breaking router tracking, obtain a phone IRK for Private BLE Device, and assign the resulting trackers to the Person.**
>
> **Reading the guide first is strongly recommended. HALP! can analyze weak or incomplete tracking, but it cannot turn an incorrectly configured tracker into a reliable one.**

## Prerequisites

At minimum, you need:

* A working Home Assistant installation
* HACS installed
* One Home Assistant Person entity
* At least one `device_tracker` assigned to that Person

For a more complete HALP! analysis, the Person should normally have several independent tracker types:

* GPS from the Home Assistant Companion App or another GPS-capable integration
* BLE presence from Private BLE Device, Bermuda, ESPresense, or another BLE solution
* Router/WiFi presence from a supported router or network-controller integration

GPS, BLE, and router/WiFi are not all mandatory. HALP! supports zero or more trackers in each category, but at least one tracker must be classified as GPS, BLE, or WiFi during setup.

## Install HALP! Through HACS

1. Open **HACS** in Home Assistant.
2. Open **Integrations**.
3. Search for **HALP!**
4. Select **HALP! (HA Location & Presence analyzer)**.
5. Select **Download**.
6. Choose the current release and complete the download.
7. Restart Home Assistant when HACS requests it.

If HALP! is not yet listed in the default HACS catalog, add the repository as a custom repository:

1. Open **HACS**.
2. Open the three-dot menu.
3. Select **Custom repositories**
4. In the **Repository** field, enter:
   ```text
   https://github.com/KruseLuds/halp
   ```
5. Select **Integration** as the category.
6. Add the repository, then download HALP!.
7. Restart Home Assistant when HACS requests it.

## Add the HALP! Integration

After Home Assistant restarts:

1. Go to **Settings → Devices & services**.
2. Select **Add integration**.
3. Search for **HALP!**
4. Select **HALP!**
5. Select the Home Assistant Person HALP! should analyze.

HALP! reads the device trackers currently assigned to that Person and presents each tracker for classification.

## Classify Every Assigned Tracker

For each tracker shown, choose one classification:

* **GPS** for long-range geographic tracking, commonly from the Home Assistant Companion App or iCloud3
* **BLE** for Bluetooth-based home or room presence
* **WiFi** for router or network-controller presence tracking
* **Other** for a tracker that is not a HALP! location source but should still be reported as an unhandled Person tracker
* **Ignore** for a tracker that should remain assigned to the Home Assistant Person but should be intentionally excluded from HALP! analysis and mismatch warnings

At least one tracker must be classified as GPS, BLE, or WiFi.

Select **Submit** when all trackers have been classified.

## Name and Assign the HALP! Device

After you submit the HALP! setup form, Home Assistant may display its standard **Name and assign** dialog for the logical HALP! device.

The dialog contains:

* **Device name** — The display name Home Assistant will use for this HALP! device.
* **Area** — An optional Home Assistant Area assignment - if not blank, ideally this would be "ROAMING". (If you wish the area to be ROAMING but do not have that area, just scroll to the bottom of the list and select "+ Add area")

These choices also affect the initial entity IDs Home Assistant creates.

Home Assistant normally builds each entity ID from:

```text
[area_]device_name_entity_name
```

The Area portion is included only when an Area is selected. Home Assistant converts spaces and punctuation to lowercase underscores.

For example, leaving the Area blank and entering this Device name:

```text
HALP! Kruse
```

typically creates entity IDs such as:

```text
sensor.halp_kruse_vetted_location
sensor.halp_kruse_location_confidence
binary_sensor.halp_kruse_location_reliable
switch.halp_kruse_speed_up_not_home_transition
```

Entering this Device name:

```text
Whatever The Name Is
```

and assigning the device to the **ROAMING** Area typically creates:

```text
sensor.roaming_whatever_the_name_is_vetted_location
sensor.roaming_whatever_the_name_is_location_confidence
binary_sensor.roaming_whatever_the_name_is_location_reliable
switch.roaming_whatever_the_name_is_speed_up_not_home_transition
```

The Device name and Area do not change which Home Assistant Person HALP! analyzes. They affect how the HALP! device is organized and how Home Assistant initially names its entities.

You may select **Skip and finish** to keep the proposed Device name and leave the Area unassigned. A Home Assistant administrator may later change the device name, Area, or individual entity IDs through Home Assistant.

## Configure Reliability Settings

After setup, open:

**Settings → Devices & services → HALP! → Configure**

The Configure flow lets you:

* Confirm or change the Person
* Reclassify the Person's currently assigned trackers
* Adjust the reliable-confidence threshold
* Adjust the voting weights for GPS, BLE, and router/WiFi sources

The default values are intended to provide a reasonable starting point. It is usually best to collect real data before changing the weights.

HALP! also provides this per-Person option, enabled by default:

**Speed up 'not_home' transition: prioritize second 'not_home' GPS update.**

When Vetted Location was `home`, a configured GPS tracker changes from `home` to `not_home`, and that same GPS tracker then updates again while remaining `not_home`, HALP! immediately changes Vetted Location to `not_home`. The option can also be controlled through the HALP! switch entity created for that Person.

## Confirm the Installation

After setup:

1. Open **Settings → Devices & services → Entities**.
2. If you had selected "Skip and Finish" in the last dialog above, Search for `halp_`. (Otherwise, search for the device name part of the entity you had just created above.)
3. Confirm HALP! entities were created for the selected Person.
4. Open the Vetted Location, Location Confidence, Consensus Score, Source Health, and Location Explanation entities.
5. Confirm their source attributes contain the trackers you classified as GPS, BLE, or WiFi.

Ignored trackers should appear in HALP! configuration and diagnostics where appropriate, but they are not be included in scoring.

## Add Another Person

HALP! creates one config entry for each Person.

To add another Person to analyze:

1. Go to **Settings → Devices & services**.
2. Double-click on ther **Halp!** integration.
3. Click **Add Entry**.
4. Select the next Person.
5. Classify that Person's trackers.

Repeat for every Person you want HALP! to analyze.

## After Changing Person Tracker Assignments

If you later add or remove a tracker from the Home Assistant Person, HALP! periodically checks the assigned tracker list.

HALP! will create a persistent notification when:

* A tracker is assigned to the Person but is not classified as GPS, BLE, WiFi, or Ignore in HALP!
* A GPS, BLE, or WiFi tracker remains configured in HALP! but is no longer assigned to the Person

Open the HALP! integration entry and select **Configure** to update classifications.

Choose **Ignore** only when the tracker should remain assigned to the Person but should not participate in HALP! analysis.

---

# Building a Reliable Presence System

Before using HALP!, each person should first be configured in Home Assistant using a standard Person entity.

Each Person should have one or more location sources assigned to it, such as GPS trackers, BLE trackers, and router/WiFi trackers. Home Assistant combines those sources to determine the Person's current location, while HALP! analyzes the quality and reliability of those decisions.

HALP! works best when Home Assistant is configured with multiple independent location sources - especially including GPS, which can speed up the recognition that a person has become "not_home" faster than the original person status due to the extra logic provided.

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

A Home Visit begins when the selected reference source transitions from Away to Home:

```text
not_home -> home
```

A Home Visit ends when the selected reference source transitions from Home to Away:

```text
home -> not_home
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
| Router | not_home | 12 min ago | 18% |

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

## Finding Your HALP! Entity Names

After creating a HALP! Person entry, open:

```text
Settings -> Devices & services -> Entities
```

Search for the Device name you entered in the **Name and assign** dialog.

For example, when the Device name is:

```text
HALP! Kruse
```

search for:

```text
halp_kruse
```

You can also search for a specific HALP! entity name, such as:

```text
Vetted Location
Location Confidence
Location Explanation
Speed up not_home transition
```

The exact entity IDs depend on the Device name and optional Area selected during setup.

With no Area and Device name `HALP! Kruse`, you will typically see:

```text
sensor.halp_kruse_vetted_location
sensor.halp_kruse_location_confidence
sensor.halp_kruse_consensus_score
sensor.halp_kruse_source_health
binary_sensor.halp_kruse_location_reliable
switch.halp_kruse_speed_up_not_home_transition
```

With Area `ROAMING` and Device name `HALP! Kruse`, the same entities will typically begin with:

```text
sensor.roaming_halp_kruse_
binary_sensor.roaming_halp_kruse_
switch.roaming_halp_kruse_
```

For the dashboard examples below, replace:

```text
<halp_entity_prefix>
```

with the complete portion of the entity ID between the domain and the HALP! entity-specific suffix.

Examples:

```text
sensor.halp_kruse_vetted_location
       ^^^^^^^^^^
       halp_entity_prefix = halp_kruse
```

```text
sensor.roaming_halp_kruse_vetted_location
       ^^^^^^^^^^^^^^^^^^^
       halp_entity_prefix = roaming_halp_kruse
```

Do not assume that every HALP! entity ID contains only `halp_` plus the Person name. Home Assistant bases the initial entity IDs on the Device name and optional Area chosen in the **Name and assign** dialog.

Note: The Vetted Location sensor is HALP!'s own location determination.

The Vetted Location sensor uses Home Assistant-compatible location states:

```text
home
not_home
unknown
```

Home Assistant normally presents `not_home` as **Away** in the user interface. Automations and templates must compare against the actual entity state `not_home`, not the display label `Away`.

When one or more Person-assigned trackers are intentionally classified as Ignore, the HALP! Vetted Location sensor is generally the recommended location sensor to use for automations instead of:

```text
person.<person_name>
```

This is because the Vetted Location sensor reflects HALP!'s analyzed location result rather than Home Assistant's default Person location calculation.

---

## Single Person Example Dashboard

This example uses one HALP! person entry.

Replace:

```text
<halp_entity_prefix>
```

with the actual prefix identified in the preceding section.

For example:

```text
halp_kruse
```

or:

```text
roaming_halp_kruse
```

(Note, the "device_tracker" GPS sensor name typically comes from the HA Companion App on the phone. For more details, please reread [Building a Reliable Home Assistant Presence System](docs/Building_a_Reliable_Presence_System.md) about device trackers.)

And then replace:

```text
<person_name's initials!>
```

with their actual initials.


```yaml
title: HALP!

views:
  - title: HALP! Location Analysis
    path: overview
    icon: mdi:map-search

    cards:
      - type: entities
        title: <person_name>
        entities:
          - entity: sensor.<halp_entity_prefix>_vetted_location
            name: Location
          - entity: sensor.<halp_entity_prefix>_location_confidence
            name: Confidence
          - entity: sensor.<halp_entity_prefix>_consensus_score
            name: Consensus
          - entity: sensor.<halp_entity_prefix>_source_health
            name: Health

      - type: map
        entities:
          - entity: device_tracker.<person_name>_iphone_17_pro_gps
            name: <person_name's initials!>
            theme_mode: light
            hours_to_show: 48

      - type: history-graph
        title: Confidence
        hours_to_show: 336
        entities:
          - entity: sensor.<halp_entity_prefix>_confidence_trend
            name: Person #1

      - type: history-graph
        title: Consensus
        hours_to_show: 336
        entities:
          - entity: sensor.<halp_entity_prefix>_consensus_trend
            name: Person #1

      - type: entities
        title: Diagnostics
        entities:
          - entity: sensor.<halp_entity_prefix>_conflict_details
            name: Person #1 conflicts
            icon: mdi:alert-circle-outline
          - entity: sensor.<halp_entity_prefix>_stale_sources
            name: Person #1 stale
          - entity: sensor.<halp_entity_prefix>_last_reliable_change
            name: Person #1 last reliable
          - entity: sensor.<halp_entity_prefix>_location_explanation
            name: Explanation
            icon: mdi:text-box-search
```

---

## Two Person Example Dashboard

This example uses two HALP! person entries.

Replace:

```text
<halp_entity_prefix_1>
<halp_entity_prefix_2>
```

with the actual HALP! entity prefixes for the two configured HALP! devices.

And then replace:

```text
<person_name_1's initials!>
<person_name_2's initials!>
```

with their actual initials.

(Note, the "device_tracker" GPS sensor names typically comes from the HA Companion App on the phone. For more details, please reread [Building a Reliable Home Assistant Presence System](docs/Building_a_Reliable_Presence_System.md) about device trackers.)


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
                title: 👩🏻 <person_name_1>
                entities:
                  - entity: sensor.<halp_entity_prefix_1>_vetted_location
                    name: Location
                  - entity: sensor.<halp_entity_prefix_1>_location_confidence
                    name: Confidence
                  - entity: sensor.<halp_entity_prefix_1>_consensus_score
                    name: Consensus
                  - entity: sensor.<halp_entity_prefix_1>_source_health
                    name: Health

          - type: vertical-stack
            cards:
              - type: entities
                title: 👱‍♂️ <person_name_2>
                entities:
                  - entity: sensor.<halp_entity_prefix_2>_vetted_location
                    name: Location
                  - entity: sensor.<halp_entity_prefix_2>_location_confidence
                    name: Confidence
                  - entity: sensor.<halp_entity_prefix_2>_consensus_score
                    name: Consensus
                  - entity: sensor.<halp_entity_prefix_2>_source_health
                    name: Health

      - type: horizontal-stack
        cards:
          - type: map
            entities:
              - entity: device_tracker.<person_name_1>_iphone_17_pro_gps
                name: <person_name_1's initials!>
                theme_mode: light
                hours_to_show: 48
          - type: map
            entities:
              - entity: device_tracker.<person_name_2>_galaxy_s26_ultra_gps
                name: <person_name_2's initials!>
                theme_mode: light
                hours_to_show: 48

      - type: grid
        columns: 2
        square: false
        cards:
          - type: history-graph
            title: Confidence
            hours_to_show: 336
            entities:
              - entity: sensor.<halp_entity_prefix_1>_confidence_trend
                name: Cathy
              - entity: sensor.<halp_entity_prefix_2>_confidence_trend
                name: Kruse

          - type: history-graph
            title: Consensus
            hours_to_show: 336
            entities:
              - entity: sensor.<halp_entity_prefix_1>_consensus_trend
                name: Cathy
              - entity: sensor.<halp_entity_prefix_2>_consensus_trend
                name: Kruse

      - type: vertical-stack
        cards:
          - type: custom:expander-card
            title: Diagnostics
            padding: true
            clear: false
            cards:
               - type: entities 
                 entities:
                  - entity: sensor.<halp_entity_prefix_1>_conflict_details
                    name: <person_name_1> conflicts
                    icon: mdi:alert-circle-outline
                  - entity: sensor.<halp_entity_prefix_1>_stale_sources
                    name: <person_name_1> stale
                  - entity: sensor.<halp_entity_prefix_1>_last_reliable_change
                    name: <person_name_1> last reliable
                  - entity: sensor.<halp_entity_prefix_1>_location_explanation
                    name: Explanation
                    icon: mdi:text-box-search                    
                  - entity: sensor.<halp_entity_prefix_2>_conflict_details
                    name: <person_name_2> conflicts
                    icon: mdi:alert-circle-outline
                  - entity: sensor.<halp_entity_prefix_2>_stale_sources
                    name: <person_name_2> stale
                  - entity: sensor.<halp_entity_prefix_2>_last_reliable_change
                    name: <person_name_1> last reliable
                  - entity: sensor.<halp_entity_prefix_2>_location_explanation
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
