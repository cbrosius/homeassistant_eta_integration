from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN


def create_device_info(host: str, port: str, device_name: str = "ETA"):
    return DeviceInfo(
        identifiers={
            (DOMAIN, f"eta_{host.replace('.', '_')}_{port}_{device_name}")
        },  # Use device_name in identifier
        name=(
            f"ETA {device_name}" if device_name != "ETA" else "ETA"
        ),  # Use device_name as name, default to "ETA" if no device name provided
        manufacturer="ETA",
        configuration_url="https://www.meineta.at",
    )
