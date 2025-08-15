"""
Platform for ETA number integration in Home Assistant

author cbrosius

"""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)
from .api import EtaAPI, ETAEndpoint, ETAValidWritableValues
from .entity import EtaCoordinatorEntity
from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberMode,
    ENTITY_ID_FORMAT,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant import config_entries
from homeassistant.const import EntityCategory
from .coordinator import EtaDataUpdateCoordinator
from .const import (
    DOMAIN,
    CHOSEN_WRITABLE_SENSORS,
    WRITABLE_DICT,
    DATA_UPDATE_COORDINATOR,
    INVISIBLE_UNITS,
    CHOSEN_DEVICES,
)
from .utils import create_device_info


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities,
):
    """Setup sensors from a config entry created in the integrations UI."""
    entry_id = config_entry.entry_id
    config = config_entry.data
    options = config_entry.options
    numbers = []

    for device_name in config.get(CHOSEN_DEVICES, []):
        if device_name in hass.data[DOMAIN][entry_id]:
            coordinator = hass.data[DOMAIN][entry_id][device_name]
            device_info = create_device_info(
                config["host"], config["port"], device_name
            )

            writable_dict = coordinator.data.get(WRITABLE_DICT, {})
            chosen_writable_sensors = options.get(
                CHOSEN_WRITABLE_SENSORS, list(writable_dict.keys())
            )

            for unique_id, endpoint_info in writable_dict.items():
                if (
                    unique_id in chosen_writable_sensors
                    and endpoint_info.get("unit") not in INVISIBLE_UNITS
                ):
                    _LOGGER.debug(
                        "Creating number entity for %s with endpoint_info: %s",
                        unique_id,
                        endpoint_info,
                    )
                    numbers.append(
                        EtaWritableNumberSensor(
                            coordinator,
                            config,
                            hass,
                            unique_id,
                            endpoint_info,
                            device_info,
                        )
                    )

    async_add_entities(numbers, update_before_add=True)


class EtaWritableNumberSensor(EtaCoordinatorEntity, NumberEntity):
    """Representation of a Number Entity."""

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

        self._attr_device_class = self.determine_device_class(endpoint_info["unit"])
        self.valid_values: ETAValidWritableValues = endpoint_info["valid_values"]
        self._attr_native_unit_of_measurement = endpoint_info["unit"]
        if self._attr_native_unit_of_measurement == "":
            self._attr_native_unit_of_measurement = None
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_mode = NumberMode.BOX
        self._attr_native_min_value = endpoint_info["valid_values"]["scaled_min_value"]
        self._attr_native_max_value = endpoint_info["valid_values"]["scaled_max_value"]
        self._attr_native_step = pow(
            10, endpoint_info["valid_values"]["dec_places"] * -1
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update attributes when the coordinator updates."""
        if self.unique_id in self.coordinator.data["values"]:
            self._attr_native_value = self.coordinator.data["values"][self.unique_id]
            self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        raw_value = round(value, self.valid_values["dec_places"])
        raw_value *= self.valid_values["scale_factor"]
        eta_client = EtaAPI(self.session, self.host, self.port)
        success = await eta_client.write_endpoint(self.uri, raw_value)
        if not success:
            raise HomeAssistantError("Could not write value, see log for details")
        await self.coordinator.async_request_refresh()

    @staticmethod
    def determine_device_class(unit):
        unit_dict_eta = {
            "°C": NumberDeviceClass.TEMPERATURE,
            "W": NumberDeviceClass.POWER,
            "A": NumberDeviceClass.CURRENT,
            "Hz": NumberDeviceClass.FREQUENCY,
            "Pa": NumberDeviceClass.PRESSURE,
            "V": NumberDeviceClass.VOLTAGE,
            "W/m²": NumberDeviceClass.IRRADIANCE,
            "bar": NumberDeviceClass.PRESSURE,
            "kW": NumberDeviceClass.POWER,
            "kWh": NumberDeviceClass.ENERGY,
            "kg": NumberDeviceClass.WEIGHT,
            "mV": NumberDeviceClass.VOLTAGE,
            "s": NumberDeviceClass.DURATION,
        }

        if unit in unit_dict_eta:
            return unit_dict_eta[unit]

        return None
