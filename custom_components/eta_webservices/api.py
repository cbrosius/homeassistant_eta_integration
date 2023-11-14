from datetime import datetime
from typing import TypedDict
from packaging import version
from aiohttp import ClientSession
import xmltodict
import logging

_LOGGER = logging.getLogger(__name__)


class ETAValidSwitchValues(TypedDict):
    on_value: int
    off_value: int


class ETAEndpoint(TypedDict):
    url: str
    value: float | str
    valid_values: dict | ETAValidSwitchValues | None
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
    def __init__(self, session, host, port):
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
        ]

    def build_uri(self, suffix):
        return "http://" + self._host + ":" + str(self._port) + suffix

    def evaluate_xml_dict(self, xml_dict, uri_dict, prefix=""):
        if type(xml_dict) == list:
            for child in xml_dict:
                self.evaluate_xml_dict(child, uri_dict, prefix)
        else:
            if "object" in xml_dict:
                child = xml_dict["object"]
                new_prefix = f"{prefix}_{xml_dict['@name']}"
                # add parent to uri_dict and evaluate childs then
                uri_dict[f"{prefix}_{xml_dict['@name']}"] = xml_dict["@uri"]
                self.evaluate_xml_dict(child, uri_dict, new_prefix)
            else:
                uri_dict[f"{prefix}_{xml_dict['@name']}"] = xml_dict["@uri"]

    async def get_request(self, suffix):
        data = await self._session.get(self.build_uri(suffix))
        return data

    async def post_request(self, suffix, data):
        data = await self._session.post(self.build_uri(suffix), data=data)
        # data = await self._session.post("http://httpbin.org/post", data=data)  # TODO
        return data

    async def does_endpoint_exists(self):
        resp = await self.get_request("/user/menu")
        return resp.status == 200

    async def is_correct_api_version(self):
        data = await self.get_request("/user/api")
        text = await data.text()
        eta_version = version.parse(xmltodict.parse(text)["eta"]["api"]["@version"])
        required_version = version.parse("1.2")

        return eta_version >= required_version

    def _parse_data(self, data):
        unit = data["@unit"]
        if unit in self._float_sensor_units:
            scale_factor = int(data["@scaleFactor"])
            decimal_places = int(data["@decPlaces"])
            raw_value = float(data["#text"])
            value = raw_value / scale_factor
            value = round(value, decimal_places)
        else:
            # use default text string representation for values that cannot be parsed properly
            value = data["@strValue"]
        return value, unit

    async def get_data(self, uri):
        data = await self.get_request("/user/var/" + str(uri))
        text = await data.text()
        data = xmltodict.parse(text)["eta"]["value"]
        return self._parse_data(data)

    async def _get_data_plus_raw(self, uri):
        data = await self.get_request("/user/var/" + str(uri))
        text = await data.text()
        data = xmltodict.parse(text)["eta"]["value"]
        value, unit = self._parse_data(data)
        return value, unit, data["#text"]

    async def get_raw_sensor_dict(self):
        data = await self.get_request("/user/menu")
        text = await data.text()
        data = xmltodict.parse(text)
        raw_dict = data["eta"]["menu"]["fub"]
        return raw_dict

    async def get_sensors_dict(self):
        raw_dict = await self.get_raw_sensor_dict()
        uri_dict = {}
        self.evaluate_xml_dict(raw_dict, uri_dict)
        return uri_dict

    async def get_all_sensors(self, float_dict, switches_dict, text_dict):
        if await self.is_correct_api_version():
            # New version with varinfo endpoint detected
            return await self._get_all_sensors_v12(float_dict, switches_dict, text_dict)
        else:
            # varinfo not available -> fall back to compatibility mode
            return await self._get_all_sensors_v11(float_dict, switches_dict, text_dict)

    def _get_friendly_name(self, key: str):
        components = key.split("_")[1:]  # The first part ist always empty
        return " > ".join(components)

    def _is_switch_v11(self, endpoint_info: ETAEndpoint, raw_value):
        if endpoint_info["unit"] == "" and raw_value in ("1802", "1803"):
            return True
        return False

    def _parse_switch_values_v11(self, endpoint_info: ETAEndpoint):
        endpoint_info["valid_values"] = ETAValidSwitchValues(
            on_value=1803, off_value=1802
        )

    async def _get_all_sensors_v11(self, float_dict, switches_dict, text_dict):
        all_endpoints = await self.get_sensors_dict()
        queried_endpoints = []
        for key in all_endpoints:
            try:
                if all_endpoints[key] in queried_endpoints:
                    # ignore duplicate endpoints
                    continue

                queried_endpoints.append(all_endpoints[key])

                value, unit, raw_value = await self._get_data_plus_raw(
                    all_endpoints[key]
                )

                endpoint_info = ETAEndpoint(
                    url=all_endpoints[key],
                    valid_values=None,
                    friendly_name=self._get_friendly_name(key),
                    unit=unit,
                    # Fallback: declare all endpoints as text sensors.
                    # If the unit is in the list of known units, the sensor will be detected as a float sensor anyway.
                    endpoint_type="TEXT",
                    value=value,
                )

                unique_key = (
                    "eta_"
                    + self._host.replace(".", "_")
                    + "_"
                    + key.lower().replace(" ", "_")
                )

                if self._is_float_sensor(endpoint_info):
                    float_dict[unique_key] = endpoint_info
                elif self._is_switch_v11(endpoint_info, raw_value):
                    self._parse_switch_values_v11(endpoint_info)
                    switches_dict[unique_key] = endpoint_info
                elif self._is_text_sensor(endpoint_info) and value != "":
                    # Ignore enpoints with an empty value
                    # This has to be the last branch for the fallback to work
                    text_dict[unique_key] = endpoint_info

            except:
                pass

    def _parse_switch_values(self, endpoint_info: ETAEndpoint):
        valid_values = ETAValidSwitchValues(on_value=0, off_value=0)
        for key in endpoint_info["valid_values"]:
            if key in ("Ein", "On"):
                valid_values["on_value"] = endpoint_info["valid_values"][key]
            elif key in ("Aus", "Off"):
                valid_values["off_value"] = endpoint_info["valid_values"][key]
        endpoint_info["valid_values"] = valid_values

    async def _get_all_sensors_v12(self, float_dict, switches_dict, text_dict):
        all_endpoints = await self.get_sensors_dict()
        queried_endpoints = []
        for key in all_endpoints:
            try:
                if all_endpoints[key] in queried_endpoints:
                    # ignore duplicate endpoints
                    continue

                queried_endpoints.append(all_endpoints[key])

                fub = key.split("_")[1]
                endpoint_info = await self._get_varinfo(fub, all_endpoints[key])

                unique_key = (
                    "eta_"
                    + self._host.replace(".", "_")
                    + "_"
                    + key.lower().replace(" ", "_")
                )

                if (
                    self._is_float_sensor(endpoint_info)
                    or self._is_switch(endpoint_info)
                    or self._is_text_sensor(endpoint_info)
                ):
                    value, _ = await self.get_data(all_endpoints[key])
                    endpoint_info["value"] = value

                if self._is_float_sensor(endpoint_info):
                    float_dict[unique_key] = endpoint_info
                elif self._is_switch(endpoint_info):
                    self._parse_switch_values(endpoint_info)
                    switches_dict[unique_key] = endpoint_info
                elif self._is_text_sensor(endpoint_info):
                    text_dict[unique_key] = endpoint_info

            except:
                pass

    def _is_text_sensor(self, endpoint_info: ETAEndpoint):
        return (
            endpoint_info["unit"] == ""
            and endpoint_info["valid_values"] is None
            and endpoint_info["endpoint_type"] == "TEXT"
        )

    def _is_float_sensor(self, endpoint_info: ETAEndpoint):
        return endpoint_info["unit"] in self._float_sensor_units

    def _is_switch(self, endpoint_info: ETAEndpoint):
        valid_values = endpoint_info["valid_values"]
        if valid_values is None:
            return False
        if len(valid_values) != 2:
            return False
        if not all(k in ("Ein", "Aus", "On", "Off") for k in valid_values):
            return False
        return True

    def _parse_varinfo(self, data):
        is_writable = data["@isWritable"]
        valid_values = None
        if (
            is_writable == "1"
            and "validValues" in data
            and "value" in data["validValues"]
        ):
            values = data["validValues"]["value"]
            valid_values = dict(
                zip([k["@strValue"] for k in values], [int(v["#text"]) for v in values])
            )

        return ETAEndpoint(
            valid_values=valid_values,
            friendly_name=data["@fullName"],
            unit=data["@unit"],
            endpoint_type=data["type"],
        )

    async def _get_varinfo(self, fub, uri):
        data = await self.get_request("/user/varinfo/" + str(uri))
        text = await data.text()
        data = xmltodict.parse(text)["eta"]["varInfo"]["variable"]
        endpoint_info = self._parse_varinfo(data)
        endpoint_info["url"] = uri
        endpoint_info["friendly_name"] = f"{fub} > {endpoint_info['friendly_name']}"
        return endpoint_info

    def _parse_switch_state(self, data):
        return int(data["#text"])

    async def get_switch_state(self, uri):
        data = await self.get_request("/user/var/" + str(uri))
        text = await data.text()
        data = xmltodict.parse(text)["eta"]["value"]
        return self._parse_switch_state(data)

    async def set_switch_state(self, uri, state):
        payload = {"value": state}
        uri = "/user/var/" + str(uri)
        data = await self.post_request(uri, payload)
        text = await data.text()
        data = xmltodict.parse(text)["eta"]
        if "success" in data:
            return True

        _LOGGER.error(
            f"ETA Integration - could not set state of switch. Got invalid result: {text}"
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
        elif "error" in data:
            _LOGGER.error(
                f"ETA Integration - could not set write value to endpoint. Terminal returned: {data['error']}"
            )
            return False

        _LOGGER.error(
            f"ETA Integration - could not set write value to endpoint. Got invalid result: {text}"
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
            for error in fub_errors:
                errors.append(
                    ETAError(
                        msg=error["@msg"],
                        priority=error["@priority"],
                        time=datetime.strptime(error["@time"], "%Y-%m-%d %H:%M:%S"),
                        text=error["#text"],
                        fub=fub_name,
                        host=self._host,
                        port=self._port,
                    )
                )

        return errors

    async def get_errors(self):
        data = await self.get_request("/user/errors")
        text = await data.text()
        data = xmltodict.parse(text)["eta"]["errors"]["fub"]
        return self._parse_errors(data)
