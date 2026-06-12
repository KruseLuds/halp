# HALP! DESIGN DOCUMENT

Version: Draft 0.1

Project Name:

HALP!

Home Assistant Location & Presence Analyzer

Technical Name:

halp

GitHub Repository:

halp

Home Assistant Domain:

halp

---

# Purpose

HALP! exists because Home Assistant users frequently encounter location problems but have no way to determine why they occurred.

Examples:

* Why did my garage door not open?
* Why did my arrival lights not turn on?
* Why did my alarm think I was home?
* Why did Home Assistant still think I was home after I left?
* Why does GPS say one thing while BLE says another?
* Why does router tracking never seem to work?

Existing Home Assistant integrations generally focus on determining location.

HALP! focuses on evaluating, explaining, and measuring the reliability of location data.

---

# Mission Statement

HALP! helps Home Assistant users understand, verify, and improve location-based automations by analyzing the quality, freshness, agreement, and historical reliability of existing location sources.

HALP! does not determine location.

HALP! determines how much confidence should be placed in existing location information.

---

# Core Philosophy

Most location systems answer:

"Where is the person?"

HALP! answers:

"How much should I trust the answer?"

This distinction is the foundation of the project.

HALP! is intentionally an observer and analyzer rather than a location provider.

---

# Source Of Truth

Home Assistant remains the source of truth.

HALP! never modifies:

* Person entities
* Device trackers
* GPS integrations
* BLE integrations
* Router integrations
* Zone definitions
* Existing automations

HALP! is read-only.

HALP! observes, measures, analyzes, and explains.

---

# What HALP! Is

HALP! is:

* A location analyzer
* A confidence engine
* A diagnostics engine
* A historical reliability evaluator
* An explanation layer for Home Assistant location decisions
* A decision support tool

---

# What HALP! Is Not

HALP! is not:

* A GPS tracker
* A BLE tracker
* A router tracker
* A mobile device management system
* A phone health monitor
* A replacement Person integration
* A replacement for Home Assistant location logic
* A surveillance tool

---

# The Big Idea

Two homes may use identical hardware and identical integrations and produce very different results.

Example:

House A

Router Tracking Reliability:
98%

House B

Router Tracking Reliability:
14%

Traditional Home Assistant cannot easily explain this.

HALP! can.

HALP! is designed to answer:

"How useful has this source actually been in this installation?"

---

# Primary Value

HALP! delivers value in three areas:

1. Current-State Analysis
2. Historical Reliability Analysis
3. Human-Readable Diagnostics

The combination of all three creates a much more useful picture than any individual location source alone.

---

# Current-State Analysis

HALP! evaluates the current state of all configured location sources.

For each source HALP! analyzes:

* Current state
* Freshness
* State duration
* Availability
* Agreement
* Conflict
* Historical reliability

HALP! then determines:

* Vetted location
* Confidence score
* Reliability score
* Human-readable explanation

---

# Historical Analysis

Historical analysis is expected to become the primary differentiator of HALP!.

Historical analysis measures how useful a source has actually been over time.

Examples:

BLE Reliability:
94%

Router Reliability:
18%

GPS Reliability:
99%

These values are installation-specific.

They are not assumptions.

They are measurements.

---

# Home Visit Definition

A Home Visit represents one continuous period where the selected reference source indicates the person is Home.

Home Visit Start:

Away → Home

Home Visit End:

Home → Away

Everything between those transitions is one Home Visit.

Example:

08:00 GPS becomes Home

09:00 GPS refreshes Home

10:00 WiFi connects

12:00 BLE detects Home

18:00 GPS becomes Away

Result:

One Home Visit

Duration:
10 hours

---

# Home Visit Success Criteria

A source receives credit for a Home Visit if it successfully detects the person at least once during that visit.

Example:

Visit Duration:
10 hours

Router connects once.

Result:

Router Success

HALP! intentionally evaluates successful detection rather than counting every connect/disconnect event.

The goal is to measure usefulness rather than connection stability.

---

# Reliability Scoring

Reliability is measured independently for each source.

Examples:

BLE detected during 46 of 50 GPS-confirmed Home Visits.

BLE Reliability:
92%

Router connected during 8 of 50 GPS-confirmed Home Visits while WiFi appeared available.

Router Reliability:
16%

These statistics help users decide which sources deserve trust.

---

# Freshness

Freshness is determined using:

last_updated

Freshness answers:

"When did this source last report?"

Freshness is expected to be one of the most important inputs into confidence calculations.

---

# State Duration

State duration is determined using:

last_changed

State duration answers:

"How long has this source been in the same state?"

State duration is primarily informational.

State duration and freshness are intentionally treated separately.

---

# Supporting Evidence

HALP! may use supporting evidence to explain confidence.

Examples:

* Battery level
* Charging status
* WiFi SSID
* WiFi BSSID
* WiFi enabled state
* Connection type
* Location permission status
* Last update trigger

Supporting evidence should normally explain confidence rather than determine confidence.

---

# Human Explanations

Every confidence score should have an explanation.

Bad:

Confidence:
83%

Good:

Cathy is likely Home with high confidence.

GPS reports Home and refreshed recently.

BLE also reports Home.

Router tracking disagrees but has historically detected this phone during only 18% of GPS-confirmed Home Visits where WiFi appeared available.

Router evidence is currently discounted.

---

# Design Rule

Before adding a feature, ask:

"Does this help explain, measure, validate, or improve confidence in a Home Assistant location decision?"

If the answer is no, the feature probably does not belong in HALP!.

This rule exists to prevent feature creep and maintain focus on the mission.

---

# Long-Term Goal

HALP! should eventually become the definitive tool for understanding Home Assistant location reliability.

The objective is not to provide more location data.

The objective is to help users trust the location data they already have.
