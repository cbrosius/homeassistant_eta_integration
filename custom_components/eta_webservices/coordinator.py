"""The Airzone integration."""

from __future__ import annotations

from asyncio import timeout
from datetime import timedelta
import logging

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN,
    FLOAT_DICT,
    SWITCHES_DICT,
    TEXT_DICT,
    WRITABLE_DICT,
    CHOSEN_FLOAT_SENSORS,
    CHOSEN_SWITCHES,
    CHOSEN_TEXT_SENSORS,
    CHOSEN_WRITABLE_SENSORS,
    CUSTOM_UNIT_MINUTES_SINCE_MIDNIGHT,
    FORCE_LEGACY_MODE,
    DATA_UPDATE_COORDINATOR,
)
from .api import EtaAPI, ETAError, ETAEndpoint

DATA_SCAN_INTERVAL = timedelta(minutes=1)
# the error endpoint doesn't have to be updated as often because we don't expect any updates most of the time
ERROR_SCAN_INTERVAL = timedelta(minutes=2)

_LOGGER = logging.getLogger(__name__)


class EtaDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the ETA terminal."""

    def __init__(
        self, hass: HomeAssistant, config: dict, device_name: str, entry_id: str
    ) -> None:
        """Initialize."""
        self.host = config.get(CONF_HOST)
        self.port = config.get(CONF_PORT)
        self.session = async_get_clientsession(hass)
        self.device_name = device_name
        self.entry_id = entry_id
        self.config = config

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{device_name}",
            update_interval=DATA_SCAN_INTERVAL,
        )

    def _should_force_number_handling(self, unit):
        return unit == CUSTOM_UNIT_MINUTES_SINCE_MIDNIGHT

    async def _async_update_data(self) -> dict:
        """Update data via library."""

        # Discover entities on the first run
        if not self.data:
            _LOGGER.info(
                "First update for device %s, getting all endpoints", self.device_name
            )
            eta_client = EtaAPI(self.session, self.host, self.port)
            entity_structure = await eta_client.get_entity_structure(self.device_name)

            float_dict = {}
            switches_dict = {}
            text_dict = {}
            writable_dict = {}

            async def discover_entities(node, path=""):
                name = node.get("name")
                uri = node.get("uri")

                current_path = f"{path}_{name}" if path else f"_{name}"

                if uri and not node.get("children"):
                    metadata = await eta_client.async_get_entity_metadata(uri)
                    if metadata:
                        entity_type = eta_client.classify_entity(metadata)
                        unique_key = f"eta_{self.host.replace('.', '_')}_{current_path.lower().replace(' ', '_')}"
                        metadata["friendly_name"] = " > ".join(
                            current_path.split("_")[2:]
                        )

                        if entity_type == "sensor":
                            if metadata.get("unit") == "":
                                text_dict[unique_key] = metadata
                            else:
                                float_dict[unique_key] = metadata
                        elif entity_type == "switch":
                            switches_dict[unique_key] = metadata
                        elif entity_type == "number":
                            writable_dict[unique_key] = metadata
                        elif entity_type == "time":
                            writable_dict[unique_key] = metadata

                for child in node.get("children", []):
                    await discover_entities(child, current_path)

            if entity_structure:
                await discover_entities(entity_structure)

            # The coordinator's data will now hold everything
            self.data = {
                FLOAT_DICT: float_dict,
                SWITCHES_DICT: switches_dict,
                TEXT_DICT: text_dict,
                WRITABLE_DICT: writable_dict,
                "values": {},  # To store the entity values
            }

        # Update the values for all chosen sensors
        eta_client = EtaAPI(self.session, self.host, self.port)
        config_entry = self.hass.config_entries.async_get_entry(self.entry_id)
        options = config_entry.options

        all_sensors = {
            **self.data.get(FLOAT_DICT, {}),
            **self.data.get(SWITCHES_DICT, {}),
            **self.data.get(TEXT_DICT, {}),
            **self.data.get(WRITABLE_DICT, {}),
        }

        # If options are not set, update all discovered sensors
        chosen_sensors_keys = [
            *options.get(
                CHOSEN_FLOAT_SENSORS, list(self.data.get(FLOAT_DICT, {}).keys())
            ),
            *options.get(
                CHOSEN_SWITCHES, list(self.data.get(SWITCHES_DICT, {}).keys())
            ),
            *options.get(
                CHOSEN_TEXT_SENSORS, list(self.data.get(TEXT_DICT, {}).keys())
            ),
            *options.get(
                CHOSEN_WRITABLE_SENSORS, list(self.data.get(WRITABLE_DICT, {}).keys())
            ),
        ]

        updated_values = {}
        for sensor_key in chosen_sensors_keys:
            if sensor_key in all_sensors:
                sensor_endpoint = all_sensors[sensor_key]
                try:
                    async with timeout(10):
                        value, _ = await eta_client.get_data(
                            sensor_endpoint["url"],
                            self._should_force_number_handling(sensor_endpoint["unit"]),
                        )
                        updated_values[sensor_key] = value
                except Exception as e:
                    _LOGGER.error(
                        "Error updating sensor %s for device %s: %s",
                        sensor_key,
                        self.device_name,
                        e,
                    )

        # Return a new data object with updated values
        return {**self.data, "values": updated_values}


class ETAErrorUpdateCoordinator(DataUpdateCoordinator[list[ETAError]]):
    """Class to manage fetching error data from the ETA terminal."""

    def __init__(self, hass: HomeAssistant, config: dict) -> None:
        """Initialize."""

        self.host = config.get(CONF_HOST)
        self.port = config.get(CONF_PORT)
        self.session = async_get_clientsession(hass)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=ERROR_SCAN_INTERVAL,
        )

    def _handle_error_events(self, new_errors):
        old_errors = self.data
        if old_errors is None:
            old_errors = []

        for error in old_errors:
            if error not in new_errors:
                self.hass.bus.async_fire(
                    "eta_webservices_error_cleared", event_data=error
                )

        for error in new_errors:
            if error not in old_errors:
                self.hass.bus.async_fire(
                    "eta_webservices_error_detected", event_data=error
                )

    async def _async_update_data(self) -> list[ETAError]:
        """Update data via library."""
        errors = []
        eta_client = EtaAPI(self.session, self.host, self.port)

        async with timeout(10):
            errors = await eta_client.get_errors()
            self._handle_error_events(errors)
            return errors
