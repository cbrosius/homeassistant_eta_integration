"""
Platform for ETA sensor integration in Home Assistant

Help Links:
 Entity Source: https://github.com/home-assistant/core/blob/dev/homeassistant/helpers/entity.py
 SensorEntity derives from Entity https://github.com/home-assistant/core/blob/dev/homeassistant/components/sensor/__init__.py


author nigl, Tidone, cbrosius

"""

from __future__ import annotations

import logging
from datetime import timedelta

_LOGGER = logging.getLogger(__name__)
from .api import ETAEndpoint, ETAError
from .coordinator import ETAErrorUpdateCoordinator, ETAWritableUpdateCoordinator
from .entity import EtaSensorEntity, EtaErrorEntity, EtaWritableSensorEntity

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
    ENTITY_ID_FORMAT,
)

from homeassistant.core import HomeAssistant
from homeassistant import config_entries
from homeassistant.const import EntityCategory
from .const import (
    DOMAIN,
    CHOSEN_FLOAT_SENSORS,
    CHOSEN_TEXT_SENSORS,
    CHOSEN_WRITABLE_SENSORS,
    FLOAT_DICT,
    TEXT_DICT,
    ERROR_UPDATE_COORDINATOR,
    WRITABLE_UPDATE_COORDINATOR,
)
from .utils import create_device_info

SCAN_INTERVAL = timedelta(minutes=1)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities,
):
    """Setup sensors from a config entry created in the integrations UI."""
    config = hass.data[DOMAIN][config_entry.entry_id]

    writable_coordinator = config[WRITABLE_UPDATE_COORDINATOR]

    chosen_float_sensors = config[CHOSEN_FLOAT_SENSORS]
    chosen_writable_sensors = config[CHOSEN_WRITABLE_SENSORS]
    # sensors don't use a coordinator if they are not also selected as writable endpoints,
    sensors = [
        EtaFloatSensor(
            config,
            hass,
            entity,
            config[FLOAT_DICT][entity],
        )
        for entity in chosen_float_sensors
        if entity + "_writable" not in chosen_writable_sensors
    ]
    # sensors use a coordinator if they are also selected as writable endpoints,
    # to be able to update the value immediately if the user writes a new value
    sensors.extend(
        [
            EtaFloatWritableSensor(
                config,
                hass,
                entity,
                config[FLOAT_DICT][entity],
                writable_coordinator,
            )
            for entity in chosen_float_sensors
            if entity + "_writable" in chosen_writable_sensors
        ]
    )
    chosen_text_sensors = config[CHOSEN_TEXT_SENSORS]
    sensors.extend(
        [
            EtaTextSensor(
                config,
                hass,
                entity,
                config[TEXT_DICT][entity],
            )
            for entity in chosen_text_sensors
        ]
    )
    error_coordinator = config[ERROR_UPDATE_COORDINATOR]
    sensors.extend(
        [
            EtaNbrErrorsSensor(config, hass, error_coordinator),
            EtaLatestErrorSensor(config, hass, error_coordinator),
        ]
    )
    async_add_entities(sensors, update_before_add=True)


def _determine_device_class(unit):
    unit_dict_eta = {
        "°C": SensorDeviceClass.TEMPERATURE,
        "W": SensorDeviceClass.POWER,
        "A": SensorDeviceClass.CURRENT,
        "Hz": SensorDeviceClass.FREQUENCY,
        "Pa": SensorDeviceClass.PRESSURE,
        "V": SensorDeviceClass.VOLTAGE,
        "W/m²": SensorDeviceClass.IRRADIANCE,
        "bar": SensorDeviceClass.PRESSURE,
        "kW": SensorDeviceClass.POWER,
        "kWh": SensorDeviceClass.ENERGY,
        "kg": SensorDeviceClass.WEIGHT,
        "mV": SensorDeviceClass.VOLTAGE,
        "s": SensorDeviceClass.DURATION,
        "%rH": SensorDeviceClass.HUMIDITY,
    }

    if unit in unit_dict_eta:
        return unit_dict_eta[unit]

    return None


def _get_native_unit(unit):
    if unit == "%rH":
        return "%"
    if unit == "":
        return None
    return unit


class EtaFloatSensor(EtaSensorEntity[float]):
    """Representation of a Float Sensor."""

    def __init__(
        self,
        config: dict,
        hass: HomeAssistant,
        unique_id: str,
        endpoint_info: ETAEndpoint,
    ) -> None:
        """
        Initialize sensor.

        To show all values: http://192.168.178.75:8080/user/menu

        """
        _LOGGER.info("ETA Integration - init float sensor")

        super().__init__(config, hass, unique_id, endpoint_info, ENTITY_ID_FORMAT)

        # Extract the device name from the unique_id
        parts = unique_id.split("_")
        if len(parts) >= 3:
            device_name = parts[2]
        else:
            device_name = (
                "Unknown"  # Handle cases where the unique_id format is unexpected
            )
            _LOGGER.warning(
                "Could not extract device name from unique_id '%s'. Using 'Unknown' as device name.",
                unique_id,
            )
        self._attr_device_info = create_device_info(self.host, self.port, device_name)

        self._attr_device_class = _determine_device_class(endpoint_info["unit"])

        self._attr_native_unit_of_measurement = _get_native_unit(endpoint_info["unit"])

        if self._attr_device_class == SensorDeviceClass.ENERGY:
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        else:
            self._attr_state_class = SensorStateClass.MEASUREMENT

        self._attr_native_value = float


class EtaFloatWritableSensor(SensorEntity, EtaWritableSensorEntity):
    """Representation of a Float Sensor."""

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
        _LOGGER.info("ETA Integration - init float sensor with coordinator")

        super().__init__(
            coordinator, config, hass, unique_id, endpoint_info, ENTITY_ID_FORMAT
        )

        self._attr_device_class = _determine_device_class(endpoint_info["unit"])

        self._attr_native_unit_of_measurement = _get_native_unit(endpoint_info["unit"])

        if self._attr_device_class == SensorDeviceClass.ENERGY:
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        else:
            self._attr_state_class = SensorStateClass.MEASUREMENT

    def handle_data_updates(self, data: float) -> None:
        self._attr_native_value = data


class EtaTextSensor(EtaSensorEntity[str]):
    """Representation of a Text Sensor."""

    def __init__(
        self,
        config: dict,
        hass: HomeAssistant,
        unique_id: str,
        endpoint_info: ETAEndpoint,
    ) -> None:
        """
        Initialize sensor.

        To show all values: http://192.168.178.75:8080/user/menu

        """
        _LOGGER.info("ETA Integration - init text sensor")

        super().__init__(config, hass, unique_id, endpoint_info, ENTITY_ID_FORMAT)

        self._attr_native_value = ""


class EtaNbrErrorsSensor(SensorEntity, EtaErrorEntity):
    """Representation of a sensor showing the number of active errors."""

    def __init__(
        self, config: dict, hass: HomeAssistant, coordinator: ETAErrorUpdateCoordinator
    ) -> None:
        super().__init__(
            coordinator, config, hass, ENTITY_ID_FORMAT, "_nbr_active_errors"
        )

        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_state_class = SensorStateClass.MEASUREMENT

        self._attr_native_value = float
        self._attr_native_unit_of_measurement = None

        self._attr_has_entity_name = True
        self._attr_translation_key = "nbr_active_errors_sensor"

        self.handle_data_updates(self.coordinator.data)

    def handle_data_updates(self, data: list):
        self._attr_native_value = len(data)


class EtaLatestErrorSensor(SensorEntity, EtaErrorEntity):
    """Representation of a sensor showing the latest active error."""

    def __init__(
        self, config: dict, hass: HomeAssistant, coordinator: ETAErrorUpdateCoordinator
    ) -> None:
        super().__init__(coordinator, config, hass, ENTITY_ID_FORMAT, "_latest_error")

        self._attr_entity_category = EntityCategory.DIAGNOSTIC

        self._attr_native_value = ""
        self._attr_native_unit_of_measurement = None

        self._attr_has_entity_name = True
        self._attr_translation_key = "latest_error_sensor"

        self.handle_data_updates(self.coordinator.data)

    def handle_data_updates(self, data: list[ETAError]):
        if len(data) == 0:
            self._attr_native_value = "-"
            return

        sorted_errors = sorted(data, key=lambda d: d["time"])
        self._attr_native_value = sorted_errors[-1]["msg"]
