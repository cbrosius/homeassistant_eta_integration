from typing import Any, TypeVar
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity, generate_entity_id
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import ETAEndpoint
from .utils import create_device_info

_CoordinatorT = TypeVar("_CoordinatorT")


class EtaEntity(Entity):
    def __init__(
        self,
        config: dict,
        hass: HomeAssistant,
        unique_id: str,
        endpoint_info: ETAEndpoint,
        entity_id_format: str,
    ) -> None:
        self._attr_name = endpoint_info["friendly_name"]
        self.session = async_get_clientsession(hass)
        self.host = config.get(CONF_HOST)
        self.port = config.get(CONF_PORT)

        self._attr_device_info = create_device_info(self.host, self.port)
        self.entity_id = generate_entity_id(entity_id_format, unique_id, hass=hass)
        self._attr_unique_id = unique_id


class EtaEntityWithCoordinator(CoordinatorEntity[_CoordinatorT]):
    def __init__(
        self,
        coordinator: _CoordinatorT,
        config: dict,
        hass: HomeAssistant,
        entity_id_format: str,
        unique_id_suffix: str,
    ) -> None:
        super().__init__(coordinator)

        host = config.get(CONF_HOST)
        port = config.get(CONF_PORT)

        self._attr_unique_id = (
            "eta_" + host.replace(".", "_") + "_" + str(port) + unique_id_suffix
        )

        self.entity_id = generate_entity_id(
            entity_id_format, self._attr_unique_id, hass=hass
        )

        self._attr_device_info = create_device_info(host, port)

    def handle_data_updates(self, data):
        raise NotImplementedError

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update attributes when the coordinator updates."""
        self.handle_data_updates(self.coordinator.data)
        super()._handle_coordinator_update()
