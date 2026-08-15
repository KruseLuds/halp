"""Config flow and options flow for HALP!."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import selector
from homeassistant.helpers.storage import Store

from .const import (
    CONF_BLE_ENTITIES,
    CONF_BLE_ZONES,
    CONF_BLE_WEIGHT,
    CONF_GPS_ENTITIES,
    CONF_GPS_WEIGHT,
    CONF_IGNORED_ENTITIES,
    CONF_KNOWN_ZONES,
    CONF_PERSON_ENTITY,
    CONF_PERSON_UNIQUE_ID,
    CONF_PRIORITIZE_SECOND_GPS_NOT_HOME,
    CONF_PRIORITIZE_SECOND_GPS_NOT_HOME_REVIEWED,
    CONF_RELIABLE_THRESHOLD,
    CONF_ROUTER_ENTITIES,
    CONF_ROUTER_ZONES,
    CONF_ROUTER_WEIGHT,
    DEFAULT_BLE_WEIGHT,
    DEFAULT_GPS_WEIGHT,
    DEFAULT_RELIABLE_THRESHOLD,
    DEFAULT_ROUTER_WEIGHT,
    DEFAULT_PRIORITIZE_SECOND_GPS_NOT_HOME,
    DOMAIN,
    ROUTER_ZONE_NONE_MOBILE,
)

PERSON_STORAGE_KEY = "person"
PERSON_STORAGE_VERSION = 2

CLASS_GPS = "GPS"
CLASS_WIFI = "WiFi"
CLASS_BLE = "BLE"
CLASS_OTHER = "Other"
CLASS_IGNORE = "Ignore"


def classification_options() -> list[str]:
    """Return the choices shown when classifying tracker sources."""
    # Order matters because this is the dropdown order shown to users.
    # GPS, BLE, and WiFi are HALP! scoring sources.
    # Other remains a normal non-location classification.
    # Ignore means the tracker is intentionally excluded from HALP!.
    return [CLASS_GPS, CLASS_BLE, CLASS_WIFI, CLASS_OTHER, CLASS_IGNORE]


def _active_zone_options(hass, include_mobile: bool = False) -> list[dict[str, str]]:
    """Return current non-passive Home Assistant zones for selectors."""
    options: list[dict[str, str]] = []
    for state in sorted(
        hass.states.async_all("zone"),
        key=lambda item: str(item.attributes.get("friendly_name", item.entity_id)).casefold(),
    ):
        if bool(state.attributes.get("passive", False)):
            continue
        label = state.attributes.get("friendly_name")
        if not isinstance(label, str) or not label:
            label = state.entity_id
        options.append({"value": state.entity_id, "label": label})
    if include_mobile:
        options.append({"value": ROUTER_ZONE_NONE_MOBILE, "label": "None / Mobile"})
    return options


def _active_zone_ids(hass) -> set[str]:
    """Return entity IDs of current non-passive zones."""
    return {
        state.entity_id
        for state in hass.states.async_all("zone")
        if not bool(state.attributes.get("passive", False))
    }


class HalpConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the first-time HALP! setup flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize temporary setup state.

        These values live only while the config flow is running.
        The final selected values are saved into the config entry.
        """
        self._data: dict[str, Any] = {}
        self._assigned_trackers: list[str] = []
        self._guessed_classes: dict[str, str] = {}

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the Configure flow for an existing HALP! entry."""
        return HalpOptionsFlowHandler(config_entry)

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Ask the user which Home Assistant Person to analyze."""
        if user_input is not None:
            person_entity = user_input[CONF_PERSON_ENTITY]

            # Store both the current Person entity ID and the registry unique ID.
            # The entity ID is useful and readable. The unique ID gives HALP!
            # a more stable reference if the Person entity is renamed later.
            registry = er.async_get(self.hass)
            person_registry_entry = registry.async_get(person_entity)

            person_unique_id = None
            if person_registry_entry is not None:
                person_unique_id = person_registry_entry.unique_id

            # Prevent adding the same Person twice.
            await self.async_set_unique_id(person_unique_id or person_entity)
            self._abort_if_unique_id_configured()

            self._data[CONF_PERSON_ENTITY] = person_entity
            self._data[CONF_PERSON_UNIQUE_ID] = person_unique_id

            # Pull device_trackers assigned to this Person so the user can
            # classify each one as GPS, BLE, WiFi, Other, or Ignore.
            await self._discover_sources(person_entity)

            return await self.async_step_classify_person_sources_v2()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PERSON_ENTITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="person")
                    ),
                }
            ),
            errors={},
        )

    async def async_step_classify_person_sources_v2(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Let the user classify the Person's assigned trackers."""
        errors: dict[str, str] = {}

        if user_input is not None:
            (
                gps_entities,
                ble_entities,
                router_entities,
                ignored_entities,
            ) = self._classified_groups(
                user_input,
                self._assigned_trackers,
            )

            if not gps_entities and not ble_entities and not router_entities:
                errors["base"] = "at_least_one_classified_source_required"
            else:
                # Save the classified source groups.
                self._data[CONF_GPS_ENTITIES] = gps_entities
                self._data[CONF_BLE_ENTITIES] = ble_entities
                self._data[CONF_ROUTER_ENTITIES] = router_entities
                self._data[CONF_IGNORED_ENTITIES] = ignored_entities

                return await self.async_step_assign_fixed_zones_v2()

        return self.async_show_form(
            step_id="classify_person_sources_v2",
            data_schema=self._classification_schema(
                self._assigned_trackers,
                self._guessed_classes,
            ),
            errors=errors,
            description_placeholders={
                "person_name": self._person_name(),
            },
        )

    async def async_step_assign_fixed_zones_v2(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Assign each fixed BLE/router tracker to its one physical zone."""
        ble_entities = self._data.get(CONF_BLE_ENTITIES, [])
        router_entities = self._data.get(CONF_ROUTER_ENTITIES, [])
        active_zones = _active_zone_ids(self.hass)

        if not ble_entities and not router_entities:
            self._data[CONF_BLE_ZONES] = {}
            self._data[CONF_ROUTER_ZONES] = {}
            return self._finish_initial_setup()

        errors: dict[str, str] = {}
        if user_input is not None:
            ble_zones: dict[str, str] = {}
            router_zones: dict[str, str] = {}
            for entity_id in ble_entities:
                zone_id = user_input.get(entity_id)
                if not isinstance(zone_id, str) or zone_id not in active_zones:
                    errors["base"] = "fixed_zone_required"
                    break
                ble_zones[entity_id] = zone_id
            if not errors:
                for entity_id in router_entities:
                    zone_id = user_input.get(entity_id)
                    if not isinstance(zone_id, str) or (
                        zone_id != ROUTER_ZONE_NONE_MOBILE and zone_id not in active_zones
                    ):
                        errors["base"] = "fixed_zone_required"
                        break
                    router_zones[entity_id] = zone_id
            if not errors:
                self._data[CONF_BLE_ZONES] = ble_zones
                self._data[CONF_ROUTER_ZONES] = router_zones
                return self._finish_initial_setup()

        schema_fields: dict[Any, Any] = {}
        home_default = "zone.home" if "zone.home" in active_zones else next(iter(active_zones), None)
        for entity_id in ble_entities:
            schema_fields[vol.Required(entity_id, default=home_default)] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=_active_zone_options(self.hass),
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )
        for entity_id in router_entities:
            schema_fields[vol.Required(entity_id, default=home_default or ROUTER_ZONE_NONE_MOBILE)] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=_active_zone_options(self.hass, include_mobile=True),
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )
        return self.async_show_form(
            step_id="assign_fixed_zones_v2",
            data_schema=vol.Schema(schema_fields),
            errors=errors,
            description_placeholders={"person_name": self._person_name()},
        )

    def _finish_initial_setup(self) -> config_entries.ConfigFlowResult:
        """Apply default tuning and finish first-time setup."""
        self._data[CONF_RELIABLE_THRESHOLD] = DEFAULT_RELIABLE_THRESHOLD
        self._data[CONF_GPS_WEIGHT] = DEFAULT_GPS_WEIGHT
        self._data[CONF_BLE_WEIGHT] = DEFAULT_BLE_WEIGHT
        self._data[CONF_ROUTER_WEIGHT] = DEFAULT_ROUTER_WEIGHT
        self._data[CONF_PRIORITIZE_SECOND_GPS_NOT_HOME] = DEFAULT_PRIORITIZE_SECOND_GPS_NOT_HOME
        self._data[CONF_PRIORITIZE_SECOND_GPS_NOT_HOME_REVIEWED] = bool(
            self._data.get(CONF_GPS_ENTITIES, [])
        )
        self._data[CONF_KNOWN_ZONES] = sorted(_active_zone_ids(self.hass))
        return self.async_create_entry(title=self._person_name(), data=self._data)

    def _classified_groups(
        self,
        user_input: dict[str, Any],
        trackers: list[str],
    ) -> tuple[list[str], list[str], list[str], list[str]]:
        """Split tracker IDs into GPS, BLE, WiFi, and Ignore groups."""
        gps_entities: list[str] = []
        ble_entities: list[str] = []
        router_entities: list[str] = []
        ignored_entities: list[str] = []

        for entity_id in trackers:
            classification = user_input.get(entity_id, CLASS_OTHER)

            if classification == CLASS_GPS:
                gps_entities.append(entity_id)
            elif classification == CLASS_BLE:
                ble_entities.append(entity_id)
            elif classification == CLASS_WIFI:
                router_entities.append(entity_id)
            elif classification == CLASS_IGNORE:
                # Ignore is deliberately stored so the mismatch checker knows
                # this Person-assigned tracker was excluded on purpose. It is
                # not a scoring source and is not analyzed by HALP!.
                ignored_entities.append(entity_id)

        return gps_entities, ble_entities, router_entities, ignored_entities

    def _classification_schema(
        self,
        trackers: list[str],
        defaults: dict[str, str],
    ) -> vol.Schema:
        """Build the tracker classification form."""
        schema_fields: dict[Any, Any] = {}

        for entity_id in trackers:
            schema_fields[
                vol.Required(
                    entity_id,
                    default=defaults.get(entity_id, CLASS_OTHER),
                )
            ] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=classification_options(),
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )

        return vol.Schema(schema_fields)

    async def _discover_sources(self, person_entity: str) -> None:
        """Discover device_trackers assigned to the selected Person."""
        assigned_trackers = await self._assigned_trackers_for_person(person_entity)

        # Also include the Person's current active source if Home Assistant
        # exposes one and it is a device_tracker entity.
        person_state = self.hass.states.get(person_entity)
        if person_state:
            current_source = person_state.attributes.get("source")
            if isinstance(current_source, str) and current_source.startswith("device_tracker."):
                assigned_trackers.append(current_source)

        self._assigned_trackers = sorted(set(assigned_trackers))

        # Guess the source type so setup is easier, but the user remains in
        # control and can correct every dropdown.
        registry = er.async_get(self.hass)
        self._guessed_classes = {}

        for entity_id in self._assigned_trackers:
            entity = registry.async_get(entity_id)
            text = self._registry_search_text(entity) if entity else entity_id.lower()
            self._guessed_classes[entity_id] = self._guess_classification(text)

    async def _assigned_trackers_for_person(self, person_entity: str) -> list[str]:
        """Read the Person storage file and return assigned device_trackers."""
        registry = er.async_get(self.hass)
        person_registry_entry = registry.async_get(person_entity)

        if person_registry_entry is None:
            return []

        person_unique_id = person_registry_entry.unique_id

        store = Store(self.hass, PERSON_STORAGE_VERSION, PERSON_STORAGE_KEY)
        stored = await store.async_load()

        if not isinstance(stored, dict):
            return []

        items = stored.get("items", [])
        if not isinstance(items, list):
            items = stored.get("data", {}).get("items", [])

        if not isinstance(items, list):
            return []

        for item in items:
            if not isinstance(item, dict):
                continue

            if item.get("id") != person_unique_id:
                continue

            trackers = item.get("device_trackers", [])
            if not isinstance(trackers, list):
                return []

            return [
                tracker
                for tracker in trackers
                if isinstance(tracker, str) and tracker.startswith("device_tracker.")
            ]

        return []

    def _person_name(self) -> str:
        """Return the selected Person friendly name for the entry title."""
        person_entity = self._data.get(CONF_PERSON_ENTITY)

        if not isinstance(person_entity, str):
            return "this Person"

        person_state = self.hass.states.get(person_entity)

        if person_state:
            friendly_name = person_state.attributes.get("friendly_name")
            if isinstance(friendly_name, str) and friendly_name:
                return friendly_name

        return person_entity

    def _registry_search_text(self, entity: er.RegistryEntry | None) -> str:
        """Build searchable text from an entity registry entry."""
        if entity is None:
            return ""

        fields = [
            entity.entity_id,
            entity.name or "",
            entity.original_name or "",
            entity.platform or "",
            str(entity.unique_id or ""),
        ]

        return " ".join(fields).lower()

    def _guess_classification(self, text: str) -> str:
        """Guess GPS, BLE, WiFi, or Other from entity metadata."""
        if any(term in text for term in ["ble", "bluetooth", "bermuda", "espresense"]):
            return CLASS_BLE

        if any(
            term in text
            for term in [
                "router",
                "wifi",
                "wi-fi",
                "unifi",
                "omada",
                "openwrt",
                "asuswrt",
                "luci",
                "fritz",
                "ddwrt",
            ]
        ):
            return CLASS_WIFI

        if any(term in text for term in ["gps", "mobile_app", "icloud", "icloud3"]):
            return CLASS_GPS

        return CLASS_OTHER


class HalpOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle the Configure flow for an existing HALP! entry.

    The Configure flow is intentionally based on the trackers currently assigned
    to the Home Assistant Person entity.

    If a user replaces a phone or changes Person tracker assignments, old HALP!
    tracker selections should not continue to appear in the Configure dialog.
    Submitting this flow saves only the trackers currently assigned to the
    Person and removes any stale tracker IDs that were previously stored.
    """

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Store the config entry being edited."""
        self._config_entry = config_entry
        self._data: dict[str, Any] = {}
        self._assigned_trackers: list[str] = []
        self._guessed_classes: dict[str, str] = {}

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Start the Configure flow."""
        return await self.async_step_person()

    async def async_step_person(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Allow the user to confirm or change the Person entity."""
        current = {
            **dict(self._config_entry.data),
            **dict(self._config_entry.options),
        }

        if user_input is not None:
            person_entity = user_input[CONF_PERSON_ENTITY]

            registry = er.async_get(self.hass)
            person_registry_entry = registry.async_get(person_entity)

            person_unique_id = None
            if person_registry_entry is not None:
                person_unique_id = person_registry_entry.unique_id

            self._data = dict(current)
            self._data[CONF_PERSON_ENTITY] = person_entity
            self._data[CONF_PERSON_UNIQUE_ID] = person_unique_id

            await self._discover_sources(person_entity, current)

            return await self.async_step_classify_person_sources()

        return self.async_show_form(
            step_id="person",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_PERSON_ENTITY,
                        default=current.get(CONF_PERSON_ENTITY),
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="person")
                    ),
                }
            ),
            errors={},
        )

    async def async_step_classify_person_sources(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Allow the user to classify the current Person trackers."""
        errors: dict[str, str] = {}

        if user_input is not None:
            (
                gps_entities,
                ble_entities,
                router_entities,
                ignored_entities,
            ) = self._classified_groups(
                user_input,
                self._assigned_trackers,
            )

            if not gps_entities and not ble_entities and not router_entities:
                errors["base"] = "at_least_one_classified_source_required"
            else:
                self._data[CONF_GPS_ENTITIES] = gps_entities
                self._data[CONF_BLE_ENTITIES] = ble_entities
                self._data[CONF_ROUTER_ENTITIES] = router_entities
                self._data[CONF_IGNORED_ENTITIES] = ignored_entities

                return await self.async_step_assign_fixed_zones()

        return self.async_show_form(
            step_id="classify_person_sources",
            data_schema=self._classification_schema(
                self._assigned_trackers,
                self._guessed_classes,
            ),
            errors=errors,
            description_placeholders={
                "person_name": self._person_name(),
            },
        )

    async def async_step_assign_fixed_zones(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Reconcile and edit fixed BLE/router zone assignments."""
        current = {**dict(self._config_entry.data), **dict(self._config_entry.options), **dict(self._data)}
        ble_entities = self._data.get(CONF_BLE_ENTITIES, [])
        router_entities = self._data.get(CONF_ROUTER_ENTITIES, [])
        active_zones = _active_zone_ids(self.hass)

        if not ble_entities and not router_entities:
            self._data[CONF_BLE_ZONES] = {}
            self._data[CONF_ROUTER_ZONES] = {}
            return await self.async_step_tuning()

        stored_ble = current.get(CONF_BLE_ZONES, {})
        if not isinstance(stored_ble, dict):
            stored_ble = {}
        stored_router = current.get(CONF_ROUTER_ZONES, {})
        if not isinstance(stored_router, dict):
            stored_router = {}

        # Reconcile deleted zones and trackers by building assignments only for
        # the trackers and active zones that still exist now. Legacy entries
        # without mappings default to Home to preserve v1.0.4 behavior.
        errors: dict[str, str] = {}
        if user_input is not None:
            ble_zones: dict[str, str] = {}
            router_zones: dict[str, str] = {}
            for entity_id in ble_entities:
                zone_id = user_input.get(entity_id)
                if not isinstance(zone_id, str) or zone_id not in active_zones:
                    errors["base"] = "fixed_zone_required"
                    break
                ble_zones[entity_id] = zone_id
            if not errors:
                for entity_id in router_entities:
                    zone_id = user_input.get(entity_id)
                    if not isinstance(zone_id, str) or (
                        zone_id != ROUTER_ZONE_NONE_MOBILE and zone_id not in active_zones
                    ):
                        errors["base"] = "fixed_zone_required"
                        break
                    router_zones[entity_id] = zone_id
            if not errors:
                self._data[CONF_BLE_ZONES] = ble_zones
                self._data[CONF_ROUTER_ZONES] = router_zones
                return await self.async_step_tuning()

        home_default = "zone.home" if "zone.home" in active_zones else next(iter(active_zones), None)
        schema_fields: dict[Any, Any] = {}
        for entity_id in ble_entities:
            default = stored_ble.get(entity_id, "zone.home")
            if default not in active_zones:
                default = home_default
            schema_fields[vol.Required(entity_id, default=default)] = selector.SelectSelector(
                selector.SelectSelectorConfig(options=_active_zone_options(self.hass), mode=selector.SelectSelectorMode.DROPDOWN)
            )
        for entity_id in router_entities:
            default = stored_router.get(entity_id, "zone.home")
            if default != ROUTER_ZONE_NONE_MOBILE and default not in active_zones:
                default = home_default or ROUTER_ZONE_NONE_MOBILE
            schema_fields[vol.Required(entity_id, default=default)] = selector.SelectSelector(
                selector.SelectSelectorConfig(options=_active_zone_options(self.hass, include_mobile=True), mode=selector.SelectSelectorMode.DROPDOWN)
            )
        return self.async_show_form(
            step_id="assign_fixed_zones",
            data_schema=vol.Schema(schema_fields),
            errors=errors,
            description_placeholders={"person_name": self._person_name()},
        )

    async def async_step_tuning(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Edit reliability threshold, source weights, and GPS location-transition behavior."""
        current = {
            **dict(self._config_entry.data),
            **dict(self._config_entry.options),
            **dict(self._data),
        }

        has_gps = bool(self._data.get(CONF_GPS_ENTITIES, []))
        previously_reviewed = bool(
            current.get(
                CONF_PRIORITIZE_SECOND_GPS_NOT_HOME_REVIEWED,
                False,
            )
        )

        if user_input is not None:
            new_data = dict(self._config_entry.data)

            if has_gps:
                prioritize_second_gps_not_home = user_input[
                    CONF_PRIORITIZE_SECOND_GPS_NOT_HOME
                ]
                prioritize_second_gps_not_home_reviewed = True
            else:
                # The setting is not applicable without a GPS source, so it is
                # omitted from the form. Preserve its stored value and review
                # state. An entry that has never had GPS therefore remains
                # unreviewed and will be prompted if GPS is added later.
                prioritize_second_gps_not_home = current.get(
                    CONF_PRIORITIZE_SECOND_GPS_NOT_HOME,
                    DEFAULT_PRIORITIZE_SECOND_GPS_NOT_HOME,
                )
                prioritize_second_gps_not_home_reviewed = previously_reviewed

            new_data.update(
                {
                    CONF_PERSON_ENTITY: self._data[CONF_PERSON_ENTITY],
                    CONF_PERSON_UNIQUE_ID: self._data.get(CONF_PERSON_UNIQUE_ID),
                    CONF_GPS_ENTITIES: self._data.get(CONF_GPS_ENTITIES, []),
                    CONF_BLE_ENTITIES: self._data.get(CONF_BLE_ENTITIES, []),
                    CONF_BLE_ZONES: self._data.get(CONF_BLE_ZONES, {}),
                    CONF_ROUTER_ENTITIES: self._data.get(CONF_ROUTER_ENTITIES, []),
                    CONF_ROUTER_ZONES: self._data.get(CONF_ROUTER_ZONES, {}),
                    CONF_IGNORED_ENTITIES: self._data.get(CONF_IGNORED_ENTITIES, []),
                    CONF_KNOWN_ZONES: sorted(_active_zone_ids(self.hass)),
                    CONF_RELIABLE_THRESHOLD: user_input[CONF_RELIABLE_THRESHOLD],
                    CONF_GPS_WEIGHT: user_input[CONF_GPS_WEIGHT],
                    CONF_BLE_WEIGHT: user_input[CONF_BLE_WEIGHT],
                    CONF_ROUTER_WEIGHT: user_input[CONF_ROUTER_WEIGHT],
                    CONF_PRIORITIZE_SECOND_GPS_NOT_HOME: (
                        prioritize_second_gps_not_home
                    ),
                    CONF_PRIORITIZE_SECOND_GPS_NOT_HOME_REVIEWED: (
                        prioritize_second_gps_not_home_reviewed
                    ),
                }
            )

            self.hass.config_entries.async_update_entry(
                self._config_entry,
                data=new_data,
                options={},
                title=self._person_name(),
            )

            self.hass.async_create_task(
                self.hass.config_entries.async_reload(self._config_entry.entry_id)
            )

            return self.async_create_entry(title="", data={})

        schema_fields: dict[Any, Any] = {}

        # Only show the GPS-specific option when at least one GPS source is
        # configured for this Person.
        if has_gps:
            schema_fields[
                vol.Required(
                    CONF_PRIORITIZE_SECOND_GPS_NOT_HOME,
                    default=(
                        current.get(
                            CONF_PRIORITIZE_SECOND_GPS_NOT_HOME,
                            DEFAULT_PRIORITIZE_SECOND_GPS_NOT_HOME,
                        )
                        if previously_reviewed
                        else False
                    ),
                )
            ] = selector.BooleanSelector()

        schema_fields[
            vol.Required(
                CONF_RELIABLE_THRESHOLD,
                default=current.get(
                    CONF_RELIABLE_THRESHOLD,
                    DEFAULT_RELIABLE_THRESHOLD,
                ),
            )
        ] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0,
                max=100,
                step=1,
                mode=selector.NumberSelectorMode.SLIDER,
            )
        )

        schema_fields[
            vol.Required(
                CONF_GPS_WEIGHT,
                default=current.get(CONF_GPS_WEIGHT, DEFAULT_GPS_WEIGHT),
            )
        ] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0,
                max=200,
                step=5,
                mode=selector.NumberSelectorMode.SLIDER,
            )
        )

        schema_fields[
            vol.Required(
                CONF_BLE_WEIGHT,
                default=current.get(CONF_BLE_WEIGHT, DEFAULT_BLE_WEIGHT),
            )
        ] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0,
                max=200,
                step=5,
                mode=selector.NumberSelectorMode.SLIDER,
            )
        )

        schema_fields[
            vol.Required(
                CONF_ROUTER_WEIGHT,
                default=current.get(CONF_ROUTER_WEIGHT, DEFAULT_ROUTER_WEIGHT),
            )
        ] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0,
                max=200,
                step=5,
                mode=selector.NumberSelectorMode.SLIDER,
            )
        )

        return self.async_show_form(
            step_id="tuning",
            data_schema=vol.Schema(schema_fields),
            errors={},
        )

    def _classified_groups(
        self,
        user_input: dict[str, Any],
        trackers: list[str],
    ) -> tuple[list[str], list[str], list[str], list[str]]:
        """Split tracker IDs into GPS, BLE, WiFi, and Ignore groups."""
        gps_entities: list[str] = []
        ble_entities: list[str] = []
        router_entities: list[str] = []
        ignored_entities: list[str] = []

        for entity_id in trackers:
            classification = user_input.get(entity_id, CLASS_OTHER)

            if classification == CLASS_GPS:
                gps_entities.append(entity_id)
            elif classification == CLASS_BLE:
                ble_entities.append(entity_id)
            elif classification == CLASS_WIFI:
                router_entities.append(entity_id)
            elif classification == CLASS_IGNORE:
                # Ignore is deliberately stored so the mismatch checker knows
                # this Person-assigned tracker was excluded on purpose. It is
                # not a scoring source and is not analyzed by HALP!.
                ignored_entities.append(entity_id)

        return gps_entities, ble_entities, router_entities, ignored_entities

    def _classification_schema(
        self,
        trackers: list[str],
        defaults: dict[str, str],
    ) -> vol.Schema:
        """Build the tracker classification form."""
        schema_fields: dict[Any, Any] = {}

        for entity_id in trackers:
            schema_fields[
                vol.Required(
                    entity_id,
                    default=defaults.get(entity_id, CLASS_OTHER),
                )
            ] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=classification_options(),
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )

        return vol.Schema(schema_fields)

    async def _discover_sources(
        self,
        person_entity: str,
        current: dict[str, Any],
    ) -> None:
        """Discover only the trackers currently assigned to the selected Person."""
        assigned_trackers = await self._assigned_trackers_for_person(person_entity)

        # Also include the Person's current active source if Home Assistant
        # exposes one and it is a device_tracker entity. This should normally
        # already be included in the Person tracker list, but this makes the
        # Configure flow resilient if HA exposes it separately.
        person_state = self.hass.states.get(person_entity)
        if person_state:
            current_source = person_state.attributes.get("source")
            if isinstance(current_source, str) and current_source.startswith("device_tracker."):
                assigned_trackers.append(current_source)

        # Important:
        # Do NOT include previously configured HALP trackers here.
        #
        # If the Person changed from an old phone to a new phone, including old
        # configured trackers would keep stale entity IDs in the Configure form.
        # The Configure flow should show the current Person trackers only, and
        # submitting it should replace the old HALP tracker lists.
        self._assigned_trackers = sorted(set(assigned_trackers))

        registry = er.async_get(self.hass)
        self._guessed_classes = {}

        for entity_id in self._assigned_trackers:
            if entity_id in current.get(CONF_GPS_ENTITIES, []):
                self._guessed_classes[entity_id] = CLASS_GPS
                continue

            if entity_id in current.get(CONF_BLE_ENTITIES, []):
                self._guessed_classes[entity_id] = CLASS_BLE
                continue

            if entity_id in current.get(CONF_ROUTER_ENTITIES, []):
                self._guessed_classes[entity_id] = CLASS_WIFI
                continue

            if entity_id in current.get(CONF_IGNORED_ENTITIES, []):
                self._guessed_classes[entity_id] = CLASS_IGNORE
                continue

            entity = registry.async_get(entity_id)
            text = self._registry_search_text(entity) if entity else entity_id.lower()
            self._guessed_classes[entity_id] = self._guess_classification(text)

    async def _assigned_trackers_for_person(self, person_entity: str) -> list[str]:
        """Read the Person storage file and return assigned device_trackers."""
        registry = er.async_get(self.hass)
        person_registry_entry = registry.async_get(person_entity)

        if person_registry_entry is None:
            return []

        person_unique_id = person_registry_entry.unique_id

        store = Store(self.hass, PERSON_STORAGE_VERSION, PERSON_STORAGE_KEY)
        stored = await store.async_load()

        if not isinstance(stored, dict):
            return []

        items = stored.get("items", [])
        if not isinstance(items, list):
            items = stored.get("data", {}).get("items", [])

        if not isinstance(items, list):
            return []

        for item in items:
            if not isinstance(item, dict):
                continue

            if item.get("id") != person_unique_id:
                continue

            trackers = item.get("device_trackers", [])
            if not isinstance(trackers, list):
                return []

            return [
                tracker
                for tracker in trackers
                if isinstance(tracker, str) and tracker.startswith("device_tracker.")
            ]

        return []

    def _person_name(self) -> str:
        """Return the selected Person friendly name for the entry title."""
        person_entity = self._data.get(
            CONF_PERSON_ENTITY,
            self._config_entry.data.get(CONF_PERSON_ENTITY),
        )

        if not isinstance(person_entity, str):
            return self._config_entry.title

        person_state = self.hass.states.get(person_entity)

        if person_state:
            friendly_name = person_state.attributes.get("friendly_name")
            if isinstance(friendly_name, str) and friendly_name:
                return friendly_name

        return person_entity

    def _registry_search_text(self, entity: er.RegistryEntry | None) -> str:
        """Build searchable text from an entity registry entry."""
        if entity is None:
            return ""

        fields = [
            entity.entity_id,
            entity.name or "",
            entity.original_name or "",
            entity.platform or "",
            str(entity.unique_id or ""),
        ]

        return " ".join(fields).lower()

    def _guess_classification(self, text: str) -> str:
        """Guess GPS, BLE, WiFi, or Other from entity metadata."""
        if any(term in text for term in ["ble", "bluetooth", "bermuda", "espresense"]):
            return CLASS_BLE

        if any(
            term in text
            for term in [
                "router",
                "wifi",
                "wi-fi",
                "unifi",
                "omada",
                "openwrt",
                "asuswrt",
                "luci",
                "fritz",
                "ddwrt",
            ]
        ):
            return CLASS_WIFI

        if any(term in text for term in ["gps", "mobile_app", "icloud", "icloud3"]):
            return CLASS_GPS

        return CLASS_OTHER
