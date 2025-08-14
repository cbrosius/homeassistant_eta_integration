from __future__ import annotations
import logging
from homeassistant.core import HomeAssistant, callback
from homeassistant import config_entries
from homeassistant.components.switch import SwitchEntity, ENTITY_ID_FORMAT
from .const import DOMAIN, CHOSEN_SWITCHES, SWITCHES_DICT, DATA_UPDATE_COORDINATOR
from .api import EtaAPI, ETAEndpoint
from .entity import EtaCoordinatorEntity
from .coordinator import EtaDataUpdateCoordinator
from .utils import create_device_info

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities,
):
    """Setup switches from a config entry created in the integrations UI."""
    entry_id = config_entry.entry_id
    config = config_entry.data
    options = config_entry.options
    switches = []

    for device_name in config.get("chosen_devices", []):
        if device_name in hass.data[DOMAIN][entry_id]:
            device_data = hass.data[DOMAIN][entry_id][device_name]
            coordinator = device_data["coordinator"]
            device_info = create_device_info(
                config["host"], config["port"], device_name
            )

            switches_dict = device_data.get(SWITCHES_DICT, {})
            chosen_switches = options.get(
                CHOSEN_SWITCHES, list(switches_dict.keys())
            )

            for unique_id, endpoint_info in switches_dict.items():
                if unique_id in chosen_switches:
                    switches.append(
                        EtaSwitch(
                            coordinator,
                            config,
                            hass,
                            unique_id,
                            endpoint_info,
                            device_info,
                        )
                    )

    async_add_entities(switches, update_before_add=True)


class EtaSwitch(EtaCoordinatorEntity, SwitchEntity):
    """Representation of a Switch."""

    def __init__(
        self,
        coordinator: EtaDataUpdateCoordinator,
        config: dict,
        hass: HomeAssistant,
        unique_id: str,
        endpoint_info: ETAEndpoint,
        device_info,
    ) -> None:
        """Initialize switch."""
        super().__init__(
            coordinator,
            config,
            hass,
            unique_id,
            endpoint_info,
            ENTITY_ID_FORMAT,
            device_info,
        )
        self._attr_icon = "mdi:power"
        self.on_value = endpoint_info["valid_values"].get("on_value", 1803)
        self.off_value = endpoint_info["valid_values"].get("off_value", 1802)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update attributes when the coordinator updates."""
        if self.unique_id in self.coordinator.data:
            self._attr_is_on = self.coordinator.data[self.unique_id] == self.on_value
            self.async_write_ha_state()

    async def async_turn_on(self, **kwargs):
        eta_client = EtaAPI(self.session, self.host, self.port)
        if await eta_client.set_switch_state(self.uri, self.on_value):
            self._attr_is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        eta_client = EtaAPI(self.session, self.host, self.port)
        if await eta_client.set_switch_state(self.uri, self.off_value):
            self._attr_is_on = False
            self.async_write_ha_state()
