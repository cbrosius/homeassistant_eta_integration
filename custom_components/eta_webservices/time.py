from __future__ import annotations

import logging
from datetime import timedelta, time

_LOGGER = logging.getLogger(__name__)
from .api import EtaAPI, ETAEndpoint
from .coordinator import ETAWritableUpdateCoordinator
from .entity import EtaWritableSensorEntity

from homeassistant.components.time import (
    TimeEntity,
    ENTITY_ID_FORMAT,
)

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant import config_entries
from .const import (
    DOMAIN,
    CHOSEN_WRITABLE_SENSORS,
    WRITABLE_DICT,
    CUSTOM_UNIT_MINUTES_SINCE_MIDNIGHT,
    WRITABLE_UPDATE_COORDINATOR,
)

SCAN_INTERVAL = timedelta(minutes=1)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities,
):
    """Setup time sensors from a config entry created in the integrations UI."""
    config = hass.data[DOMAIN][config_entry.entry_id]

    coordinator = config[WRITABLE_UPDATE_COORDINATOR]

    chosen_entities = config[CHOSEN_WRITABLE_SENSORS]
    time_sensors = [
        EtaTime(config, hass, entity, config[WRITABLE_DICT][entity], coordinator)
        for entity in chosen_entities
        if config[WRITABLE_DICT][entity]["unit"] == CUSTOM_UNIT_MINUTES_SINCE_MIDNIGHT
    ]
    async_add_entities(time_sensors, update_before_add=True)


class EtaTime(TimeEntity, EtaWritableSensorEntity):
    """Representation of a Time Sensor."""

    def __init__(
        self,
        config: dict,
        hass: HomeAssistant,
        unique_id: str,
        endpoint_info: ETAEndpoint,
        coordinator: ETAWritableUpdateCoordinator,
    ) -> None:
        """
        Initialize sensor.

        To show all values: http://192.168.178.75:8080/user/menu
        """
        _LOGGER.info("ETA Integration - init time sensor")

        super().__init__(
            coordinator, config, hass, unique_id, endpoint_info, ENTITY_ID_FORMAT
        )

        # set an initial value to avoid errors. This will be overwritten by the coordinator immediately after initialization.
        self._attr_native_value = time(hour=19)
        self._attr_should_poll = True

    def handle_data_updates(self, data: float) -> None:
        total_minutes = int(data)
        hours = total_minutes // 60
        minutes = total_minutes % 60

        self._attr_native_value = time(hour=hours, minute=minutes)

    async def async_set_value(self, value: time):
        total_minutes = value.hour * 60 + value.minute
        if total_minutes >= 60 * 24:
            raise HomeAssistantError("Invalid time: Must be between 00:00 and 23:59")
        eta_client = EtaAPI(self.session, self.host, self.port)
        success = await eta_client.write_endpoint(self.uri, total_minutes)
        if not success:
            raise HomeAssistantError("Could not write value, see log for details")
        await self.coordinator.async_refresh()
