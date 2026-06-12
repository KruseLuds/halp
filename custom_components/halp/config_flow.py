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
    CONF_BLE_WEIGHT,
    CONF_GPS_ENTITIES,
    CONF_GPS_WEIGHT,
    CONF_PERSON_ENTITY,
    CONF_PERSON_UNIQUE_ID,
    CONF_RELIABLE_THRESHOLD,
    CONF_ROUTER_ENTITIES,
    CONF_ROUTER_WEIGHT,
    DEFAULT_BLE_WEIGHT,
    DEFAULT_GPS_WEIGHT,
    DEFAULT_RELIABLE_THRESHOLD,
    DEFAULT_ROUTER_WEIGHT,
    DOMAIN,
)

PERSON_STORAGE_KEY = "person"
PERSON_STORAGE_VERSION = 2

CLASS_GPS = "GPS"
CLASS_WIFI = "WiFi"
CLASS_BLE = "BLE"
CLASS_OTHER = "Other"


def classification_options() -> list[str]:
    """Return the choices shown when classifying tracker sources."""
    return [CLASS_GPS, CLASS_WIFI, CLASS_BLE, CLASS_OTHER]


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
            # classify each one as GPS, WiFi, BLE, or Other.
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
            gps_entities, ble_entities, router_entities = self._classified_groups(
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

                # Save default tuning values. The user can change these later
                # from the Configure button on the integration entry.
                self._data[CONF_RELIABLE_THRESHOLD] = DEFAULT_RELIABLE_THRESHOLD
                self._data[CONF_GPS_WEIGHT] = DEFAULT_GPS_WEIGHT
                self._data[CONF_BLE_WEIGHT] = DEFAULT_BLE_WEIGHT
                self._data[CONF_ROUTER_WEIGHT] = DEFAULT_ROUTER_WEIGHT

                return self.async_create_entry(
                    title=self._person_name(),
                    data=self._data,
                )

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

    def _classified_groups(
        self,
        user_input: dict[str, Any],
        trackers: list[str],
    ) -> tuple[list[str], list[str], list[str]]:
        """Split tracker entity IDs into GPS, BLE, and WiFi groups."""
        gps_entities: list[str] = []
        ble_entities: list[str] = []
        router_entities: list[str] = []

        for entity_id in trackers:
            classification = user_input.get(entity_id, CLASS_OTHER)

            if classification == CLASS_GPS:
                gps_entities.append(entity_id)
            elif classification == CLASS_BLE:
                ble_entities.append(entity_id)
            elif classification == CLASS_WIFI:
                router_entities.append(entity_id)

        return gps_entities, ble_entities, router_entities

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
        """Guess GPS, WiFi, BLE, or Other from entity metadata."""
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
    """Handle the Configure flow for an existing HALP! entry."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Store the config entry being edited."""
        self._config_entry = config_entry

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Open the tuning screen."""
        return await self.async_step_tuning(user_input)

    async def async_step_tuning(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Edit reliability threshold and source weights."""
        current = {**dict(self._config_entry.data), **dict(self._config_entry.options)}

        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    **dict(self._config_entry.options),
                    CONF_RELIABLE_THRESHOLD: user_input[CONF_RELIABLE_THRESHOLD],
                    CONF_GPS_WEIGHT: user_input[CONF_GPS_WEIGHT],
                    CONF_BLE_WEIGHT: user_input[CONF_BLE_WEIGHT],
                    CONF_ROUTER_WEIGHT: user_input[CONF_ROUTER_WEIGHT],
                },
            )

        return self.async_show_form(
            step_id="tuning",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_RELIABLE_THRESHOLD,
                        default=current.get(
                            CONF_RELIABLE_THRESHOLD,
                            DEFAULT_RELIABLE_THRESHOLD,
                        ),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=100,
                            step=1,
                            mode=selector.NumberSelectorMode.SLIDER,
                        )
                    ),
                    vol.Required(
                        CONF_GPS_WEIGHT,
                        default=current.get(CONF_GPS_WEIGHT, DEFAULT_GPS_WEIGHT),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=200,
                            step=5,
                            mode=selector.NumberSelectorMode.SLIDER,
                        )
                    ),
                    vol.Required(
                        CONF_BLE_WEIGHT,
                        default=current.get(CONF_BLE_WEIGHT, DEFAULT_BLE_WEIGHT),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=200,
                            step=5,
                            mode=selector.NumberSelectorMode.SLIDER,
                        )
                    ),
                    vol.Required(
                        CONF_ROUTER_WEIGHT,
                        default=current.get(CONF_ROUTER_WEIGHT, DEFAULT_ROUTER_WEIGHT),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=200,
                            step=5,
                            mode=selector.NumberSelectorMode.SLIDER,
                        )
                    ),
                }
            ),
            errors={},
        )