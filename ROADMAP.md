# HALP! Roadmap

## Version 1.0

Status: Complete

### Core Features

* Analyze one or more Home Assistant Person entities
* Analyze GPS, BLE, router/WiFi, and Person location sources
* Generate a vetted location assessment
* Generate confidence and consensus scores
* Track source freshness and state duration
* Generate human-readable explanations
* Detect source conflicts
* Detect stale sources
* Store rolling historical data
* Store daily summary statistics
* Provide dashboard examples
* Provide local integration branding

---

## Version 1.1

Status: Planned

### Historical Reliability Scoring

Goals:

* Measure GPS reliability
* Measure BLE reliability
* Measure router/WiFi reliability
* Measure Person entity reliability
* Calculate installation-specific reliability percentages

Example:

```text
BLE Reliability: 94%
Router Reliability: 18%
GPS Reliability: 99%
```

---

## Version 1.2

Status: Planned

### Adaptive Source Weighting

Goals:

* Automatically adjust source weighting based on measured reliability
* Reduce influence of historically poor sources
* Increase influence of historically reliable sources

---

## Version 1.3

Status: Planned

### Advanced Dashboarding

Goals:

* Reliability trend charts
* Reliability leaderboards
* Source comparison views
* Dynamic multi-person dashboards

---

## Version 2.0

Status: Future

### Advanced Location Intelligence

Goals:

* Zone-specific reliability analysis
* Arrival reliability analysis
* Departure reliability analysis
* Automation troubleshooting recommendations
* Reliability recommendation engine

---

## Guiding Principle

HALP! exists to help users understand, validate, and improve confidence in Home Assistant location decisions.

HALP! is intentionally focused on analysis, diagnostics, explainability, and reliability rather than becoming another location provider.
