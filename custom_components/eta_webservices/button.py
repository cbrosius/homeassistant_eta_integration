from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN
from .coordinator import ETAErrorUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    config = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = config["error_update_coordinator"]

    buttons = [
        EtaResendErrorEventsButton(config, coordinator),
    ]

    async_add_entities(buttons)


class EtaResendErrorEventsButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, config: dict, coordinator: ETAErrorUpdateCoordinator) -> None:
        host = config.get(CONF_HOST)
        port = config.get(CONF_PORT)
        self.coordinator = coordinator

        self._attr_translation_key = "send_error_events_btn"
        self._attr_unique_id = (
            "eta_" + host.replace(".", "_") + "_" + str(port) + "_send_events_btn"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "eta_" + host.replace(".", "_") + "_" + str(port))}
        )
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    async def async_press(self) -> None:
        """Force the error update coordinator to resend all error events"""
        # Delete the old error list to force the coordinator to resend all events
        self.coordinator.data = []
        await self.coordinator.async_refresh()
