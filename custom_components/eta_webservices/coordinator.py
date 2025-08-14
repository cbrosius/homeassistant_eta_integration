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
        self.data = {}
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
        data = {}
        eta_client = EtaAPI(self.session, self.host, self.port)

        config_entry = self.hass.config_entries.async_get_entry(self.entry_id)
        options = config_entry.options

        all_sensors = {
            **options.get(FLOAT_DICT, {}),
            **options.get(SWITCHES_DICT, {}),
            **options.get(TEXT_DICT, {}),
            **options.get(WRITABLE_DICT, {}),
        }

        chosen_sensors = [
            *options.get(CHOSEN_FLOAT_SENSORS, []),
            *options.get(CHOSEN_SWITCHES, []),
            *options.get(CHOSEN_TEXT_SENSORS, []),
            *options.get(CHOSEN_WRITABLE_SENSORS, []),
        ]

        for sensor_key in chosen_sensors:
            if sensor_key in all_sensors:
                sensor_endpoint = all_sensors[sensor_key]
                try:
                    async with timeout(10):
                        value, _ = await eta_client.get_data(
                            sensor_endpoint["url"],
                            self._should_force_number_handling(sensor_endpoint["unit"]),
                        )
                        data[sensor_key] = value
                except Exception as e:
                    _LOGGER.error(
                        "Error updating sensor %s for device %s: %s",
                        sensor_key,
                        self.device_name,
                        e,
                    )

        return data


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
