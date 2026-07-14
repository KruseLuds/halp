# HALP! DESIGN DOCUMENT

Version: **1.0 (Living Document)**

## Purpose

HALP! is a read-only analysis and diagnostics engine for Home Assistant location and presence.

It explains **why** Home Assistant reached a location decision and how much confidence should be placed in that decision.

## Mission

HALP! does not determine location.

HALP! determines how much confidence should be placed in existing location information.

## Source of Truth

Home Assistant remains the source of truth.

HALP! never modifies Person entities, device trackers, zones, or automations.

## Ignore Trackers

Version 1.0 introduced Ignore tracker classification.

Ignored trackers:
- remain visible for diagnostics
- are excluded from confidence scoring
- are excluded from mismatch detection

## Supporting Evidence

Supporting evidence may include:

- Battery level
- Charging status
- WiFi SSID
- WiFi BSSID
- WiFi enabled state
- Bluetooth enabled state
- GPS enabled state
- Connection type
- Location permission status
- Last update trigger

These values primarily explain confidence rather than determine confidence.

## Long-Term Goal

HALP! should become the definitive diagnostics tool for Home Assistant presence reliability.
