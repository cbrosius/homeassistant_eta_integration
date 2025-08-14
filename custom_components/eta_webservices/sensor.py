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
from .coordinator import ETAErrorUpdateCoordinator
from .entity import EtaCoordinatorEntity, EtaErrorEntity
from .coordinator import EtaDataUpdateCoordinator

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
    DATA_UPDATE_COORDINATOR,
)
from .utils import create_device_info

SCAN_INTERVAL = timedelta(minutes=1)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities,
):
    """Setup sensors from a config entry created in the integrations UI."""
    entry_id = config_entry.entry_id
    config = config_entry.data
    options = config_entry.options
    sensors = []

    for device_name in config.get("chosen_devices", []):
        if device_name in hass.data[DOMAIN][entry_id]:
            device_data = hass.data[DOMAIN][entry_id][device_name]
            coordinator = device_data["coordinator"]
            device_info = create_device_info(
                config["host"], config["port"], device_name
            )

            float_sensors = device_data.get(FLOAT_DICT, {})
            chosen_float_sensors = options.get(
                CHOSEN_FLOAT_SENSORS, list(float_sensors.keys())
            )
            text_sensors = device_data.get(TEXT_DICT, {})
            chosen_text_sensors = options.get(
                CHOSEN_TEXT_SENSORS, list(text_sensors.keys())
            )

            # Float sensors
            for unique_id, endpoint_info in float_sensors.items():
                if unique_id in chosen_float_sensors:
                    sensors.append(
                        EtaFloatSensor(
                            coordinator,
                            config,
                            hass,
                            unique_id,
                            endpoint_info,
                            device_info,
                        )
                    )

            # Text sensors
            for unique_id, endpoint_info in text_sensors.items():
                if unique_id in chosen_text_sensors:
                    sensors.append(
                        EtaTextSensor(
                            coordinator,
                            config,
                            hass,
                            unique_id,
                            endpoint_info,
                            device_info,
                        )
                    )

    # Error sensors
    error_coordinator = hass.data[DOMAIN][entry_id][ERROR_UPDATE_COORDINATOR]
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


class EtaFloatSensor(EtaCoordinatorEntity, SensorEntity):
    """Representation of a Float Sensor."""

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
        self._attr_device_class = _determine_device_class(endpoint_info["unit"])
        self._attr_native_unit_of_measurement = _get_native_unit(endpoint_info["unit"])
        if self._attr_device_class == SensorDeviceClass.ENERGY:
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        else:
            self._attr_state_class = SensorStateClass.MEASUREMENT


class EtaTextSensor(EtaCoordinatorEntity, SensorEntity):
    """Representation of a Text Sensor."""

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
