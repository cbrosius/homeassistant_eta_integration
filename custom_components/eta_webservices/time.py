from __future__ import annotations

import logging
from datetime import timedelta, time

_LOGGER = logging.getLogger(__name__)
from .api import EtaAPI, ETAEndpoint
from .coordinator import EtaDataUpdateCoordinator
from .entity import EtaCoordinatorEntity
from homeassistant.components.time import TimeEntity, ENTITY_ID_FORMAT
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant import config_entries
from .const import (
    DOMAIN,
    CHOSEN_WRITABLE_SENSORS,
    WRITABLE_DICT,
    CUSTOM_UNIT_MINUTES_SINCE_MIDNIGHT,
    DATA_UPDATE_COORDINATOR,
)
from .utils import create_device_info


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities,
):
    """Setup time sensors from a config entry created in the integrations UI."""
    entry_id = config_entry.entry_id
    config = config_entry.data
    options = config_entry.options
    time_sensors = []

    for device_name in config.get("chosen_devices", []):
        if device_name in hass.data[DOMAIN][entry_id]:
            device_data = hass.data[DOMAIN][entry_id][device_name]
            coordinator = device_data[DATA_UPDATE_COORDINATOR]
            device_info = create_device_info(
                config["host"], config["port"], device_name
            )

            writable_dict = device_data.get(WRITABLE_DICT, {})
            chosen_writable_sensors = options.get(
                CHOSEN_WRITABLE_SENSORS, list(writable_dict.keys())
            )

            for unique_id, endpoint_info in writable_dict.items():
                if (
                    unique_id in chosen_writable_sensors
                    and endpoint_info.get("unit") == CUSTOM_UNIT_MINUTES_SINCE_MIDNIGHT
                ):
                    time_sensors.append(
                        EtaTime(
                            coordinator,
                            config,
                            hass,
                            unique_id,
                            endpoint_info,
                            device_info,
                        )
                    )

    async_add_entities(time_sensors, update_before_add=True)


class EtaTime(EtaCoordinatorEntity, TimeEntity):
    """Representation of a Time Sensor."""

    def __init__(
        self,
        coordinator: EtaDataUpdateCoordinator,
        config: dict,
        hass: HomeAssistant,
        unique_id: str,
        endpoint_info: ETAEndpoint,
        device_info,
    ) -> None:
        """Initialize sensor."""
        super().__init__(
            coordinator,
            config,
            hass,
            unique_id,
            endpoint_info,
            ENTITY_ID_FORMAT,
            device_info,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update attributes when the coordinator updates."""
        if self.unique_id in self.coordinator.data:
            total_minutes = int(self.coordinator.data[self.unique_id])
            hours = total_minutes // 60
            minutes = total_minutes % 60
            self._attr_native_value = time(hour=hours, minute=minutes)
            self.async_write_ha_state()

    async def async_set_value(self, value: time):
        total_minutes = value.hour * 60 + value.minute
        if total_minutes >= 60 * 24:
            raise HomeAssistantError("Invalid time: Must be between 00:00 and 23:59")
        eta_client = EtaAPI(self.session, self.host, self.port)
        success = await eta_client.write_endpoint(self.uri, total_minutes)
        if not success:
            raise HomeAssistantError("Could not write value, see log for details")
        await self.coordinator.async_refresh()
