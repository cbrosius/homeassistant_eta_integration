from abc import abstractmethod
from typing import Any, Generic, TypeVar, cast
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity, generate_entity_id
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import ETAEndpoint, EtaAPI
from .utils import create_device_info
from .coordinator import ETAErrorUpdateCoordinator, ETAWritableUpdateCoordinator

_EntityT = TypeVar("_EntityT")


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
        self.uri = endpoint_info["url"]

        self._attr_device_info = create_device_info(self.host, self.port)
        self.entity_id = generate_entity_id(entity_id_format, unique_id, hass=hass)
        self._attr_unique_id = unique_id


class EtaSensorEntity(SensorEntity, EtaEntity, Generic[_EntityT]):
    async def async_update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        readme: activate first: https://www.meineta.at/javax.faces.resource/downloads/ETA-RESTful-v1.2.pdf.xhtml?ln=default&v=0
        """
        eta_client = EtaAPI(self.session, self.host, self.port)
        value, _ = await eta_client.get_data(self.uri)
        self._attr_native_value = cast(_EntityT, value)


class EtaWritableSensorEntity(
    EtaEntity, CoordinatorEntity[ETAWritableUpdateCoordinator]
):
    def __init__(
        self,
        coordinator: ETAWritableUpdateCoordinator,
        config: dict,
        hass: HomeAssistant,
        unique_id: str,
        endpoint_info: ETAEndpoint,
        entity_id_format: str,
    ) -> None:
        EtaEntity.__init__(
            self, config, hass, unique_id, endpoint_info, entity_id_format
        )
        CoordinatorEntity.__init__(self, coordinator)

        self.handle_data_updates(float(coordinator.data[self.unique_id]))

    @abstractmethod
    def handle_data_updates(self, data: float) -> None:
        raise NotImplementedError

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update attributes when the coordinator updates."""
        data = self.coordinator.data[self.unique_id]
        self.handle_data_updates(float(data))
        super()._handle_coordinator_update()


class EtaErrorEntity(CoordinatorEntity[ETAErrorUpdateCoordinator]):
    def __init__(
        self,
        coordinator: ETAErrorUpdateCoordinator,
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

    @abstractmethod
    def handle_data_updates(self, data) -> None:
        raise NotImplementedError

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update attributes when the coordinator updates."""
        self.handle_data_updates(self.coordinator.data)
        super()._handle_coordinator_update()
