import logging
from homeassistant import config_entries, core
from homeassistant.const import Platform

from .const import DOMAIN
from .coordinator import ETAErrorUpdateCoordinator
from .services import async_setup_services

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
]

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Set up platform from a ConfigEntry."""
    hass.data.setdefault(DOMAIN, {})
    config = dict(entry.data)
    # Registers update listener to update config entry when options are updated.
    unsub_options_update_listener = entry.add_update_listener(options_update_listener)
    # Store a reference to the unsubscribe function to cleanup if an entry is unloaded.
    config["unsub_options_update_listener"] = unsub_options_update_listener
    error_coordinator = ETAErrorUpdateCoordinator(hass, config)
    config["error_update_coordinator"] = error_coordinator

    if entry.options:
        config.update(entry.options)

    await error_coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = config

    # Forward the setup to the sensor platform.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    await async_setup_services(hass, entry)

    return True


async def async_setup(hass: core.HomeAssistant, config: dict) -> bool:
    """Set up the eta Custom component from yaml configuration."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def options_update_listener(
    hass: core.HomeAssistant, config_entry: config_entries.ConfigEntry
):
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Remove options_update_listener.
        hass.data[DOMAIN][entry.entry_id]["unsub_options_update_listener"]()

        # Remove config entry from domain.
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
