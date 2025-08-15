from datetime import datetime
import logging
from typing import TypedDict

from aiohttp import ClientSession
from packaging import version
import xmltodict

from .const import CUSTOM_UNIT_MINUTES_SINCE_MIDNIGHT

_LOGGER = logging.getLogger(__name__)


class ETAValidSwitchValues(TypedDict):
    on_value: int
    off_value: int


class ETAValidWritableValues(TypedDict):
    scaled_min_value: float
    scaled_max_value: float
    scale_factor: int
    dec_places: int


class ETAEndpoint(TypedDict):
    url: str
    value: float | str
    valid_values: dict | ETAValidSwitchValues | ETAValidWritableValues | None
    friendly_name: str
    unit: str
    endpoint_type: str


class ETAError(TypedDict):
    msg: str
    priority: str
    time: datetime
    text: str
    fub: str
    host: str
    port: int


class EtaAPI:
    def __init__(self, session, host, port) -> None:
        self._session: ClientSession = session
        self._host = host
        self._port = int(port)

        self._float_sensor_units = [
            "%",
            "A",
            "Hz",
            "Ohm",
            "Pa",
            "U/min",
            "V",
            "W",
            "W/m²",
            "bar",
            "kW",
            "kWh",
            "kg",
            "l",
            "l/min",
            "mV",
            "m²",
            "s",
            "°C",
            "%rH",
            CUSTOM_UNIT_MINUTES_SINCE_MIDNIGHT,
        ]

        self._writable_sensor_units = [
            "%",
            "°C",
            "kg",
            CUSTOM_UNIT_MINUTES_SINCE_MIDNIGHT,
        ]
        self._default_valid_writable_values = {
            "%": ETAValidWritableValues(
                scaled_min_value=-100,
                scaled_max_value=100,
                scale_factor=1,
                dec_places=0,
            ),
            "°C": ETAValidWritableValues(
                scaled_min_value=-100,
                scaled_max_value=200,
                scale_factor=1,
                dec_places=0,
            ),
            "kg": ETAValidWritableValues(
                scaled_min_value=-100000,
                scaled_max_value=100000,
                scale_factor=1,
                dec_places=0,
            ),
        }

    def build_uri(self, suffix):
        return "http://" + self._host + ":" + str(self._port) + suffix

    def _parse_menu_node(self, node):
        """Recursively parse a node from the /user/menu XML."""
        if not isinstance(node, dict):
            return None

        entity = {
            "name": node.get("@name"),
            "uri": node.get("@uri"),
            "children": [],
        }

        if "object" in node and node["object"] is not None:
            children = node["object"]
            if not isinstance(children, list):
                children = [children]
            for child_node in children:
                child_entity = self._parse_menu_node(child_node)
                if child_entity:
                    entity["children"].append(child_entity)

        return entity

    async def get_entity_structure(self, device_name: str):
        """Get the hierarchical structure of entities for a specific device."""
        menu = await self.get_menu()
        fubs = menu.get("eta", {}).get("menu", {}).get("fub", [])
        if not isinstance(fubs, list):
            fubs = [fubs]

        for fub in fubs:
            if fub.get("@name") == device_name:
                return self._parse_menu_node(fub)

        return None

    async def _get_request(self, suffix):
        data = await self._session.get(self.build_uri(suffix))
        return data

    async def post_request(self, suffix, data):
        data = await self._session.post(self.build_uri(suffix), data=data)
        return data

    async def does_endpoint_exists(self):
        resp = await self._get_request("/user/menu")
        return resp.status == 200

    async def get_api_version(self):
        data = await self._get_request("/user/api")
        text = await data.text()
        return version.parse(xmltodict.parse(text)["eta"]["api"]["@version"])

    async def is_correct_api_version(self):
        eta_version = await self.get_api_version()
        required_version = version.parse("1.2")

        return eta_version >= required_version

    def _parse_data(self, data, force_number_handling=False):
        _LOGGER.debug("Parsing data %s", data)
        unit = data["@unit"]
        if unit in self._float_sensor_units or force_number_handling:
            scale_factor = int(data["@scaleFactor"])
            decimal_places = int(data["@decPlaces"])
            raw_value = float(data["#text"])
            value = raw_value / scale_factor
            value = round(value, decimal_places)
        else:
            # use default text string representation for values that cannot be parsed properly
            value = data["@strValue"]
        return value, unit

    async def get_data(self, uri, force_number_handling=False):
        data = await self._get_request("/user/var/" + str(uri))
        text = await data.text()
        data = xmltodict.parse(text)["eta"]["value"]
        return self._parse_data(data, force_number_handling)

    async def _get_data_plus_raw(self, uri):
        data = await self._get_request("/user/var/" + str(uri))
        text = await data.text()
        data = xmltodict.parse(text)["eta"]["value"]
        value, unit = self._parse_data(data)
        return value, unit, data

    async def get_menu(self):
        data = await self._get_request("/user/menu")
        text = await data.text()
        return xmltodict.parse(text)

    async def async_get_entity_metadata(self, uri: str) -> dict:
        """Get detailed metadata for a single entity URI."""
        if await self.is_correct_api_version():
            return await self._get_entity_metadata_v12(uri)
        else:
            return await self._get_entity_metadata_v11(uri)

    async def _get_entity_metadata_v11(self, uri: str) -> dict:
        """Get metadata for a single entity on API v1.1."""
        value, unit, raw_dict = await self._get_data_plus_raw(uri)
        endpoint_info = ETAEndpoint(
            url=uri,
            valid_values=None,
            friendly_name="",  # This will be populated from the menu structure
            unit=unit,
            endpoint_type="TEXT",  # Fallback
            value=value,
        )

        if self._is_writable_v11(endpoint_info):
            self._parse_valid_writable_values_v11(endpoint_info, raw_dict)

        if self._is_switch_v11(endpoint_info, raw_dict["#text"]):
            self._parse_switch_values_v11(endpoint_info)

        return endpoint_info

    async def _get_entity_metadata_v12(self, uri: str) -> dict:
        """Get metadata for a single entity on API v1.2."""
        endpoint_info = await self._get_varinfo(None, uri)  # fub is not needed here
        if endpoint_info is None:
            return None
        value, _ = await self.get_data(uri)
        endpoint_info["value"] = value

        if self._is_switch(endpoint_info):
            self._parse_switch_values(endpoint_info)

        return endpoint_info

    def classify_entity(self, endpoint_info: ETAEndpoint) -> str | None:
        """Classify an entity based on its metadata."""
        _LOGGER.debug("Classifying entity: %s", endpoint_info)
        entity_type = None
        if self._is_writable(endpoint_info) or self._is_writable_v11(endpoint_info):
            if endpoint_info.get("unit") == CUSTOM_UNIT_MINUTES_SINCE_MIDNIGHT:
                entity_type = "time"
            else:
                entity_type = "number"
        elif self._is_switch(endpoint_info) or self._is_switch_v11(
            endpoint_info, str(endpoint_info.get("value"))
        ):
            entity_type = "switch"
        elif self._is_float_sensor(endpoint_info):
            entity_type = "sensor"
        elif self._is_text_sensor(endpoint_info):
            entity_type = "sensor"

        _LOGGER.debug("Classified as: %s", entity_type)
        return entity_type

    def _is_switch_v11(self, endpoint_info: ETAEndpoint, raw_value: str):
        if endpoint_info["unit"] == "" and raw_value in ("1802", "1803"):
            return True
        return False

    def _parse_switch_values_v11(self, endpoint_info: ETAEndpoint):
        endpoint_info["valid_values"] = ETAValidSwitchValues(
            on_value=1803, off_value=1802
        )

    def _is_writable_v11(self, endpoint_info: ETAEndpoint):
        if endpoint_info["unit"] in self._writable_sensor_units:
            return True
        return False

    def _parse_valid_writable_values_v11(
        self, endpoint_info: ETAEndpoint, raw_dict: dict
    ):
        endpoint_info["valid_values"] = self._default_valid_writable_values[
            endpoint_info["unit"]
        ]
        endpoint_info["valid_values"]["dec_places"] = int(raw_dict["@decPlaces"])
        endpoint_info["valid_values"]["scale_factor"] = int(raw_dict["@scaleFactor"])

    def _parse_switch_values(self, endpoint_info: ETAEndpoint):
        valid_values = ETAValidSwitchValues(on_value=0, off_value=0)
        for key in endpoint_info["valid_values"]:
            if key in ("Ein", "On", "Ja", "Yes"):
                valid_values["on_value"] = endpoint_info["valid_values"][key]
            elif key in ("Aus", "Off", "Nein", "No"):
                valid_values["off_value"] = endpoint_info["valid_values"][key]
        endpoint_info["valid_values"] = valid_values

    def _is_writable(self, endpoint_info: ETAEndpoint):
        return (
            endpoint_info["valid_values"] is not None
            and "scaled_min_value" in endpoint_info["valid_values"]
        )

    def _is_text_sensor(self, endpoint_info: ETAEndpoint):
        return endpoint_info["unit"] == "" and endpoint_info["endpoint_type"] == "TEXT"

    def _is_float_sensor(self, endpoint_info: ETAEndpoint):
        return endpoint_info["unit"] in self._float_sensor_units

    def _is_switch(self, endpoint_info: ETAEndpoint):
        valid_values = endpoint_info["valid_values"]
        if valid_values is None:
            return False
        if len(valid_values) != 2:
            return False
        if not all(
            k in ("Ein", "Aus", "On", "Off", "Ja", "Nein", "Yes", "No")
            for k in valid_values
        ):
            return False
        return True

    def _parse_unit(self, data):
        unit = data["@unit"]
        if unit == "":
            if (
                "validValues" in data
                and data["validValues"] is not None
                and "min" in data["validValues"]
                and "max" in data["validValues"]
                and "#text" in data["validValues"]["min"]
                and int(data["@scaleFactor"]) == 1
                and int(data["@decPlaces"]) == 0
            ):
                _LOGGER.debug("Found time endpoint")
                min_value = int(data["validValues"]["min"]["#text"])
                max_value = int(data["validValues"]["max"]["#text"])
                if min_value == 0 and max_value == 24 * 60 - 1:
                    unit = CUSTOM_UNIT_MINUTES_SINCE_MIDNIGHT
        return unit

    def _parse_varinfo(self, data):
        _LOGGER.debug("Parsing varinfo %s", data)
        valid_values = None
        unit = self._parse_unit(data)
        if (
            "validValues" in data
            and data["validValues"] is not None
            and "value" in data["validValues"]
        ):
            values = data["validValues"]["value"]
            if not isinstance(values, list):
                values = [values]
            valid_values = dict(
                zip(
                    [k["@strValue"] for k in values],
                    [int(v["#text"]) for v in values],
                    strict=False,
                )
            )
        elif (
            "validValues" in data
            and data["validValues"] is not None
            and "min" in data["validValues"]
            and "#text" in data["validValues"]["min"]
            and unit in self._writable_sensor_units
        ):
            min_value = data["validValues"]["min"]["#text"]
            max_value = data["validValues"]["max"]["#text"]
            scale_factor = int(data["@scaleFactor"])
            dec_places = int(data["@decPlaces"])

            min_value = round(float(min_value) / scale_factor, dec_places)
            max_value = round(float(max_value) / scale_factor, dec_places)
            valid_values = ETAValidWritableValues(
                scaled_min_value=min_value,
                scaled_max_value=max_value,
                scale_factor=scale_factor,
                dec_places=dec_places,
            )

        return ETAEndpoint(
            valid_values=valid_values,
            friendly_name=data["@fullName"],
            unit=unit,
            endpoint_type=data["type"],
        )

    async def _get_varinfo(self, fub, uri):
        data = await self._get_request("/user/varinfo/" + str(uri))
        text = await data.text()
        parsed_xml = xmltodict.parse(text)
        if "eta" not in parsed_xml or "varInfo" not in parsed_xml["eta"]:
            _LOGGER.debug(f"URI {uri} does not seem to be a valid variable, skipping.")
            return None
        data = parsed_xml["eta"]["varInfo"]["variable"]
        endpoint_info = self._parse_varinfo(data)
        endpoint_info["url"] = uri
        if fub:
            endpoint_info["friendly_name"] = f"{fub} > {endpoint_info['friendly_name']}"
        return endpoint_info

    async def set_switch_state(self, uri, state):
        payload = {"value": state}
        uri = "/user/var/" + str(uri)
        data = await self.post_request(uri, payload)
        text = await data.text()
        data = xmltodict.parse(text)["eta"]
        if "success" in data:
            return True

        _LOGGER.error(
            "ETA Integration - could not set state of switch. Got invalid result: %s",
            text,
        )
        return False

    async def write_endpoint(self, uri, value, begin=None, end=None):
        payload = {"value": value}
        if begin is not None:
            payload["begin"] = begin
            payload["end"] = end
        uri = "/user/var/" + str(uri)
        data = await self.post_request(uri, payload)
        text = await data.text()
        data = xmltodict.parse(text)["eta"]
        if "success" in data:
            return True
        if "error" in data:
            _LOGGER.error(
                "ETA Integration - could not set write value to endpoint. Terminal returned: %s",
                data["error"],
            )
            return False

        _LOGGER.error(
            "ETA Integration - could not set write value to endpoint. Got invalid result: %s",
            text,
        )
        return False

    def _parse_errors(self, data):
        errors = []
        if isinstance(data, dict):
            data = [
                data,
            ]

        for fub in data:
            fub_name = fub.get("@name", "")
            fub_errors = fub.get("error", [])
            if isinstance(fub_errors, dict):
                fub_errors = [
                    fub_errors,
                ]
            errors = [
                ETAError(
                    msg=error["@msg"],
                    priority=error["@priority"],
                    time=(
                        datetime.strptime(error["@time"], "%Y-%m-%d %H:%M:%S")
                        if error.get("@time", "") != ""
                        else datetime.now
                    ),
                    text=error["#text"],
                    fub=fub_name,
                    host=self._host,
                    port=self._port,
                )
                for error in fub_errors
            ]

        return errors

    async def get_errors(self):
        data = await self._get_request("/user/errors")
        text = await data.text()
        data = xmltodict.parse(text)["eta"]["errors"]["fub"]
        return self._parse_errors(data)
