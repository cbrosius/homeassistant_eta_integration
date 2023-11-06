from __future__ import annotations

import logging
from datetime import timedelta

_LOGGER = logging.getLogger(__name__)
from .api import EtaAPI
from .coordinator import ETAErrorUpdateCoordinator

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    ENTITY_ID_FORMAT,
)

from homeassistant.core import HomeAssistant, callback
from homeassistant import config_entries
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.const import CONF_HOST, CONF_PORT
from .const import (
    DOMAIN,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities,
):
    """Setup error sensor"""
    config = hass.data[DOMAIN][config_entry.entry_id]
    # Update our config to include new repos and remove those that have been removed.
    if config_entry.options:
        config.update(config_entry.options)

    coordinator = config["error_update_coordinator"]

    sensors = [EtaErrorSensor(config, hass, coordinator)]
    async_add_entities(sensors, update_before_add=True)


class EtaErrorSensor(BinarySensorEntity, CoordinatorEntity[ETAErrorUpdateCoordinator]):
    """Representation of a Sensor."""

    def __init__(
        self, config: dict, hass: HomeAssistant, coordinator: ETAErrorUpdateCoordinator
    ) -> None:
        """
        Initialize sensor.

        To show all values: http://192.168.178.75:8080/user/errors

        """
        _LOGGER.info("ETA Integration - init error sensor")

        super().__init__(coordinator)

        self._attr_has_entity_name = True

        self._attr_device_class = BinarySensorDeviceClass.PROBLEM

        host = config.get(CONF_HOST)
        port = config.get(CONF_PORT)

        self._attr_translation_key = "state_sensor"
        self._attr_unique_id = "eta_" + host.replace(".", "_") + "_errors"
        self.entity_id = generate_entity_id(
            ENTITY_ID_FORMAT, self._attr_unique_id, hass=hass
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "eta_" + host.replace(".", "_") + "_" + str(port))}
        )

        self._handle_error_updates(self.coordinator.data)

    def _handle_error_updates(self, errors: list):
        self._is_on = len(errors) > 0

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update attributes when the coordinator updates."""
        self._handle_error_updates(self.coordinator.data)
        super()._handle_coordinator_update()

    @property
    def is_on(self):
        """If the switch is currently on or off."""
        return self._is_on
