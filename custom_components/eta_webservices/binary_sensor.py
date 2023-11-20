from __future__ import annotations

import logging

_LOGGER = logging.getLogger(__name__)
from .coordinator import ETAErrorUpdateCoordinator
from .entity import EtaErrorEntity

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    ENTITY_ID_FORMAT,
)

from homeassistant.core import HomeAssistant
from homeassistant import config_entries
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.const import CONF_HOST
from .const import DOMAIN, ERROR_UPDATE_COORDINATOR


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities,
):
    """Setup error sensor"""
    config = hass.data[DOMAIN][config_entry.entry_id]

    error_coordinator = config[ERROR_UPDATE_COORDINATOR]

    sensors = [EtaErrorSensor(config, hass, error_coordinator)]
    async_add_entities(sensors, update_before_add=True)


class EtaErrorSensor(BinarySensorEntity, EtaErrorEntity):
    """Representation of a Sensor."""

    def __init__(
        self, config: dict, hass: HomeAssistant, coordinator: ETAErrorUpdateCoordinator
    ) -> None:
        """
        Initialize sensor.

        To show all values: http://192.168.178.75:8080/user/errors

        """
        _LOGGER.info("ETA Integration - init error sensor")

        super().__init__(coordinator, config, hass, ENTITY_ID_FORMAT, "_errors")

        self._attr_has_entity_name = True
        self._attr_translation_key = "state_sensor"

        self._attr_device_class = BinarySensorDeviceClass.PROBLEM

        host = config.get(CONF_HOST)

        # replace the unique id and entity id to keep the entity backwards compatible
        self._attr_unique_id = "eta_" + host.replace(".", "_") + "_errors"
        self.entity_id = generate_entity_id(
            ENTITY_ID_FORMAT, self._attr_unique_id, hass=hass
        )

        self.handle_data_updates(self.coordinator.data)

    def handle_data_updates(self, data: list):
        self._attr_is_on = len(data) > 0
