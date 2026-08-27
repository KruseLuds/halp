"""Constants for HALP!."""

from __future__ import annotations

DOMAIN = "halp"
NAME = "HALP!"
VERSION = "2.1.0"

PLATFORMS = ["sensor", "binary_sensor", "switch"]

CONF_PERSON_ENTITY = "person_entity"
CONF_PERSON_UNIQUE_ID = "person_unique_id"

CONF_GPS_ENTITIES = "gps_entities"
CONF_BLE_ENTITIES = "ble_entities"
CONF_ROUTER_ENTITIES = "router_entities"
CONF_IGNORED_ENTITIES = "ignored_entities"

# Fixed-location mappings. GPS is intentionally excluded because GPS already
# reports Home Assistant zone states dynamically.
CONF_BLE_ZONES = "ble_zones"
CONF_ROUTER_ZONES = "router_zones"
CONF_KNOWN_ZONES = "known_zones"
ROUTER_ZONE_NONE_MOBILE = "__none_mobile__"

CONF_BATTERY_LEVEL_ENTITY = "battery_level_entity"
CONF_BATTERY_STATE_ENTITY = "battery_state_entity"
CONF_LOCATION_PERMISSION_ENTITY = "location_permission_entity"
CONF_SSID_ENTITY = "ssid_entity"
CONF_BSSID_ENTITY = "bssid_entity"
CONF_CONNECTION_TYPE_ENTITY = "connection_type_entity"

CONF_RELIABLE_THRESHOLD = "reliable_threshold"
CONF_GPS_WEIGHT = "gps_weight"
CONF_BLE_WEIGHT = "ble_weight"
CONF_ROUTER_WEIGHT = "router_weight"

# Keep the stored key names from v1.0.4 for backward compatibility. Since v2.0.0
# the behavior is generalized from home -> not_home to any confirmed GPS
# location transition.
CONF_PRIORITIZE_SECOND_GPS_NOT_HOME = "prioritize_second_gps_not_home"
CONF_PRIORITIZE_SECOND_GPS_NOT_HOME_REVIEWED = (
    "prioritize_second_gps_not_home_reviewed"
)

SOURCE_TYPE_GPS = "gps"
SOURCE_TYPE_BLE = "ble"
SOURCE_TYPE_ROUTER = "router"

SOURCE_TYPE_NAMES = {
    SOURCE_TYPE_GPS: "GPS",
    SOURCE_TYPE_BLE: "BLE",
    SOURCE_TYPE_ROUTER: "Router",
}

LOCATION_HOME = "home"
LOCATION_NOT_HOME = "not_home"
LOCATION_UNKNOWN = "unknown"
LOCATION_UNAVAILABLE = "unavailable"
LOCATION_MISSING = "missing"

DEFAULT_RELIABLE_THRESHOLD = 70

DEFAULT_GPS_WEIGHT = 100
DEFAULT_BLE_WEIGHT = 70
DEFAULT_ROUTER_WEIGHT = 55

DEFAULT_PRIORITIZE_SECOND_GPS_NOT_HOME = True
GPS_NOT_HOME_PRIORITY_CONFIDENCE_FLOOR = 80

# Runtime-only keys. These are kept in hass.data and are never persisted.
# The older names are retained where useful so existing code/entity identity is
# not needlessly disturbed, but the runtime state is now generic multi-zone.
RUNTIME_GPS_TRANSITION_CANDIDATES = "_gps_transition_candidates"
RUNTIME_GPS_TRANSITION_ORIGINS = "_gps_transition_origins"
RUNTIME_GPS_DEPARTED_ZONE_CONTEXTS = "_gps_departed_zone_contexts"
RUNTIME_FIXED_ARRIVAL_PRIORITY_ACTIVE = "_fixed_arrival_priority_active"
RUNTIME_FIXED_ARRIVAL_PRIORITY_LOCATION = "_fixed_arrival_priority_location"
RUNTIME_FIXED_ARRIVAL_PRIORITY_ENTITY = "_fixed_arrival_priority_entity"
RUNTIME_GPS_NOT_HOME_PRIORITY_ACTIVE = "_gps_not_home_priority_active"
RUNTIME_GPS_NOT_HOME_TRIGGER_ENTITY = "_gps_not_home_trigger_entity"
RUNTIME_GPS_PRIORITY_LOCATION = "_gps_priority_location"
RUNTIME_GPS_NOT_HOME_CONFIDENCE_HIGH_WATER = (
    "_gps_not_home_confidence_high_water"
)

# Legacy runtime key retained only for compatibility with any in-memory code
# during a reload. v2.1.0 does not use it as the primary candidate store.
RUNTIME_GPS_NOT_HOME_ARMED = "_gps_not_home_armed"

FRESHNESS_EXCELLENT_MINUTES = 15
FRESHNESS_GOOD_MINUTES = 60
FRESHNESS_FAIR_MINUTES = 240
FRESHNESS_POOR_MINUTES = 480

DEFAULT_SOURCE_WEIGHTS = {
    SOURCE_TYPE_GPS: DEFAULT_GPS_WEIGHT,
    SOURCE_TYPE_BLE: DEFAULT_BLE_WEIGHT,
    SOURCE_TYPE_ROUTER: DEFAULT_ROUTER_WEIGHT,
}
