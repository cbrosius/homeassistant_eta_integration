from __future__ import annotations

import logging
from datetime import timedelta

_LOGGER = logging.getLogger(__name__)
from .api import EtaAPI

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    ENTITY_ID_FORMAT,
)

from homeassistant.core import HomeAssistant
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.const import CONF_HOST, CONF_PORT
from .const import (
    DOMAIN,
)

SCAN_INTERVAL = timedelta(minutes=10)


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

    sensors = [
        EtaErrorSensor(
            config,
            hass,
        )
    ]
    async_add_entities(sensors, update_before_add=True)


class EtaErrorSensor(BinarySensorEntity):
    """Representation of a Sensor."""

    def __init__(self, config, hass):
        """
        Initialize sensor.

        To show all values: http://192.168.178.75:8080/user/errors

        """
        _LOGGER.info("ETA Integration - init error sensor")

        self._attr_device_class = BinarySensorDeviceClass.PROBLEM

        self.host = config.get(CONF_HOST)
        self.port = config.get(CONF_PORT)

        self._attr_name = "State"
        self._attr_unique_id = "eta_" + self.host.replace(".", "_") + "_errors"
        self.entity_id = generate_entity_id(
            ENTITY_ID_FORMAT, self._attr_unique_id, hass=hass
        )
        self.session = async_get_clientsession(hass)

        self._is_on = False

    async def async_update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        readme: activate first: https://www.meineta.at/javax.faces.resource/downloads/ETA-RESTful-v1.2.pdf.xhtml?ln=default&v=0
        """
        eta_client = EtaAPI(self.session, self.host, self.port)
        errors = await eta_client.get_errors()
        self._is_on = len(errors) > 0

    @property
    def is_on(self):
        """If the switch is currently on or off."""
        return self._is_on
