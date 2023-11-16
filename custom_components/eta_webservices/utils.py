from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN
from .api import EtaAPI


def create_device_info(host: str, port: str):
    eta_client = EtaAPI(None, host, port)
    url = eta_client.build_uri("/user/menu")

    return DeviceInfo(
        identifiers={(DOMAIN, "eta_" + host.replace(".", "_") + "_" + str(port))},
        name="ETA",
        manufacturer="ETA",
        configuration_url=url,
    )
