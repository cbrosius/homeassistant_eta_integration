from __future__ import annotations

from typing import Any
from homeassistant.components.button import ButtonEntity, ENTITY_ID_FORMAT
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers import config_entry_flow

from .const import DOMAIN, ERROR_UPDATE_COORDINATOR
from .coordinator import ETAErrorUpdateCoordinator
from .utils import create_device_info


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    config = hass.data[DOMAIN][config_entry.entry_id]
    error_coordinator = config[ERROR_UPDATE_COORDINATOR]

    buttons = [
        EtaResendErrorEventsButton(config, hass, error_coordinator)
    ]

    # Add a button to configure entities for each selected device.
    for device_name in config.get("chosen_devices", []):
        buttons.append(EtaDeviceConfigButton(config, hass, device_name))

    async_add_entities(buttons)


class EtaResendErrorEventsButton(ButtonEntity):
    """Button to resend error events."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        config: dict,
        hass: HomeAssistant,
        device_name: str,
    ) -> None:
        self, config: dict, hass: HomeAssistant, coordinator: ETAErrorUpdateCoordinator
    ) -> None:
        host = config.get(CONF_HOST)
        port = config.get(CONF_PORT)
        self.coordinator = coordinator

        self._attr_translation_key = "send_error_events_btn"
        self._attr_unique_id = (
            "eta_" + host.replace(".", "_") + "_" + str(port) + "_send_events_btn"
        )
        self.entity_id = generate_entity_id(
            ENTITY_ID_FORMAT, self._attr_unique_id, hass=hass
        )
        self._attr_device_info = create_device_info(host, port)
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    async def async_press(self) -> None:
        """Force the error update coordinator to resend all error events"""
        # Delete the old error list to force the coordinator to resend all events
        self.coordinator.data = []
        await self.coordinator.async_refresh()


class EtaDeviceConfigButton(ButtonEntity):
    """Button to trigger the device-specific entity config flow."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, config: dict, hass: HomeAssistant, device_name: str) -> None:
        self.device_name = device_name
        self.hass = hass
        host = config.get(CONF_HOST)
        port = config.get(CONF_PORT)

        self._attr_translation_key = "configure_device_entities"  # Add this to your translations!
        self._attr_unique_id = (
            f"eta_{host.replace('.', '_')}_{port}_{device_name}_config_btn"
        )
        self.entity_id = generate_entity_id(
            ENTITY_ID_FORMAT, self._attr_unique_id, hass=hass
        )
        self._attr_device_info = create_device_info(host, port)
        self._attr_name = f"Configure {device_name}"

    async def async_press(self) -> None:
        """Trigger the config flow for this device."""
        config_entry_flow.async_init(
            self.hass,
            DOMAIN,
            context={"source": "user", "device": self.device_name},
        )
