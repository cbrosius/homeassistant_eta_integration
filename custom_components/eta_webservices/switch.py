from __future__ import annotations

import logging
from datetime import timedelta

_LOGGER = logging.getLogger(__name__)
from .api import EtaAPI, ETAEndpoint

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    ENTITY_ID_FORMAT,
)

from homeassistant.core import HomeAssistant
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.const import CONF_HOST, CONF_PORT
from .const import DOMAIN, CHOSEN_SWITCHES, SWITCHES_DICT

SCAN_INTERVAL = timedelta(minutes=1)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities,
):
    """Setup switches from a config entry created in the integrations UI."""
    config = hass.data[DOMAIN][config_entry.entry_id]
    # Update our config to include new repos and remove those that have been removed.
    if config_entry.options:
        config.update(config_entry.options)

    chosen_entities = config[CHOSEN_SWITCHES]
    switches = [
        EtaSwitch(config, hass, entity, config[SWITCHES_DICT][entity])
        for entity in chosen_entities
    ]
    async_add_entities(switches, update_before_add=True)


class EtaSwitch(SwitchEntity):
    """Representation of a Switch."""

    def __init__(
        self,
        config: dict,
        hass: HomeAssistant,
        unique_id: str,
        endpoint_info: ETAEndpoint,
    ) -> None:
        """
        Initialize switch.

        To show all values: http://192.168.178.75:8080/user/menu
        """
        _LOGGER.info("ETA Integration - init switch")

        self._attr_name = endpoint_info["friendly_name"]
        self.entity_id = generate_entity_id(ENTITY_ID_FORMAT, unique_id, hass=hass)
        self._attr_icon = "mdi:power"
        self.session = async_get_clientsession(hass)

        self.uri = endpoint_info["url"]
        self.host = config.get(CONF_HOST)
        self.port = config.get(CONF_PORT)
        self.on_value = endpoint_info["valid_values"]["on_value"]
        self.off_value = endpoint_info["valid_values"]["off_value"]
        self._is_on = False

        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, "eta_" + self.host.replace(".", "_") + "_" + str(self.port))
            },
            name="ETA",
            manufacturer="ETA",
        )

        # This must be a unique value within this domain. This is done using host
        self._attr_unique_id = unique_id

    async def async_update(self):
        """Fetch new state data for the switch.
        This is the only method that should fetch new data for Home Assistant.
        readme: activate first: https://www.meineta.at/javax.faces.resource/downloads/ETA-RESTful-v1.2.pdf.xhtml?ln=default&v=0
        """
        eta_client = EtaAPI(self.session, self.host, self.port)
        value = await eta_client.get_switch_state(self.uri)
        if value == self.on_value:
            self._is_on = True
        else:
            self._is_on = False

    @property
    def unique_id(self):
        return self._attr_unique_id

    async def async_turn_on(self, **kwargs):
        eta_client = EtaAPI(self.session, self.host, self.port)
        res = await eta_client.set_switch_state(self.uri, self.on_value)
        if res:
            self._is_on = True

    async def async_turn_off(self, **kwargs):
        eta_client = EtaAPI(self.session, self.host, self.port)
        res = await eta_client.set_switch_state(self.uri, self.off_value)
        if res:
            self._is_on = False

    @property
    def is_on(self):
        """If the switch is currently on or off."""
        return self._is_on

    @property
    def should_poll(self):
        return True
