"""Adds config flow for Blueprint."""

import copy
import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.entity_registry import (
    async_entries_for_config_entry,
    async_get,
)
import homeassistant.helpers.config_validation as cv
from .api import ETAEndpoint, EtaAPI
from .const import (
    DOMAIN,
    FLOAT_DICT,
    SWITCHES_DICT,
    TEXT_DICT,
    WRITABLE_DICT,
    CHOSEN_FLOAT_SENSORS,
    CHOSEN_SWITCHES,
    CHOSEN_TEXT_SENSORS,
    CHOSEN_WRITABLE_SENSORS,
    CHOSEN_DEVICES,
    DATA_UPDATE_COORDINATOR,
    FORCE_LEGACY_MODE,
    FORCE_SENSOR_DETECTION,
    ENABLE_DEBUG_LOGGING,
    INVISIBLE_UNITS,
)

_LOGGER = logging.getLogger(__name__)


class EtaFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Eta."""

    VERSION = 5
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self) -> None:
        """Initialize."""
        self._errors = {}
        self.data = {}
        self._old_logging_level = logging.NOTSET

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        self._errors = {}

        # Uncomment the next 2 lines if only a single instance of the integration is allowed:
        # if self._async_current_entries():
        #     return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            platform_entries = self._async_current_entries()
            for entry in platform_entries:
                if entry.data.get(CONF_HOST, "") == user_input[CONF_HOST]:
                    return self.async_abort(reason="single_instance_allowed")
            valid = await self._test_url(user_input[CONF_HOST], user_input[CONF_PORT])
            if valid == 1:
                is_correct_api_version = await self._is_correct_api_version(
                    user_input[CONF_HOST], user_input[CONF_PORT]
                )
                if not is_correct_api_version:
                    self._errors["base"] = "wrong_api_version"
                elif user_input[FORCE_LEGACY_MODE]:
                    self._errors["base"] = "legacy_mode_selected"

                if user_input[ENABLE_DEBUG_LOGGING]:
                    self._old_logging_level = _LOGGER.parent.getEffectiveLevel()
                    _LOGGER.parent.setLevel(logging.DEBUG)

                self.data = user_input
                self.data["possible_devices"] = await self._get_possible_devices(
                    user_input[CONF_HOST], user_input[CONF_PORT]
                )

                if not self.data["possible_devices"]:
                    self._errors["base"] = "no_devices_found"
                    return await self._show_config_form_user(user_input)
                return await self.async_step_select_devices()
            else:
                self._errors["base"] = (
                    "no_eta_endpoint" if valid == 0 else "unknown_host"
                )

            return await self._show_config_form_user(user_input)

        user_input = {}
        # Provide defaults for form
        user_input[CONF_HOST] = "192.168.60.199"
        user_input[CONF_PORT] = "49999"

        return await self._show_config_form_user(user_input)

    async def async_step_select_devices(self, user_input: dict = None):
        """Second step in config flow to select devices."""
        if user_input is not None:
            self.data[CHOSEN_DEVICES] = user_input.get(CHOSEN_DEVICES, [])
            # Create a config entry without scanning for entities
            return self.async_create_entry(
                title=f"ETA at {self.data[CONF_HOST]}",
                data=self.data,
            )

        return self.async_show_form(
            step_id="select_devices",
            data_schema=vol.Schema(
                {
                    vol.Required(CHOSEN_DEVICES): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(value=device, label=device)
                                for device in self.data["possible_devices"]
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                            multiple=True,
                        )
                    ),
                }
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return EtaOptionsFlowHandler(config_entry)

    async def _show_config_form_user(
        self, user_input
    ):  # pylint: disable=unused-argument
        """Show the configuration form to edit host and port data."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=user_input[CONF_HOST]): str,  #
                    vol.Required(CONF_PORT, default=user_input[CONF_PORT]): str,
                    vol.Required(FORCE_LEGACY_MODE, default=False): cv.boolean,
                    vol.Required(ENABLE_DEBUG_LOGGING, default=False): cv.boolean,
                }
            ),
            errors=self._errors,
        )

    async def _show_config_form_endpoint(
        self,
        current_chosen_sensors=[],
        current_chosen_switches=[],
        current_chosen_text_sensors=[],
        current_chosen_writable_sensors=[],
    ):
        """Show the configuration form to select which endpoints should become entities."""
        sensors_dict: dict[str, ETAEndpoint] = self.data[FLOAT_DICT]
        switches_dict: dict[str, ETAEndpoint] = self.data[SWITCHES_DICT]
        text_dict: dict[str, ETAEndpoint] = self.data[TEXT_DICT]
        writable_dict: dict[str, ETAEndpoint] = self.data[WRITABLE_DICT]

        return self.async_show_form(
            step_id="select_entities",
            data_schema=vol.Schema(
                {
                    vol.Optional(CHOSEN_FLOAT_SENSORS): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(
                                    value=key,
                                    label=f"{sensors_dict[key]['friendly_name']} ({sensors_dict[key]['value']} {sensors_dict[key]['unit'] if sensors_dict[key]['unit'] not in INVISIBLE_UNITS else ""})",
                                )
                                for key in sensors_dict
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                            multiple=True,
                        )
                    ),
                    vol.Optional(CHOSEN_SWITCHES): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(
                                    value=key,
                                    label=f"{switches_dict[key]['friendly_name']} ({switches_dict[key]['value']})",
                                )
                                for key in switches_dict
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                            multiple=True,
                        )
                    ),
                    vol.Optional(CHOSEN_TEXT_SENSORS): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(
                                    value=key,
                                    label=f"{text_dict[key]['friendly_name']} ({text_dict[key]['value']})",
                                )
                                for key in text_dict
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                            multiple=True,
                        )
                    ),
                    vol.Optional(CHOSEN_WRITABLE_SENSORS): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(
                                    value=key,
                                    label=f"{writable_dict[key]['friendly_name']} ({writable_dict[key]['value']} {writable_dict[key]['unit'] if writable_dict[key]['unit'] not in INVISIBLE_UNITS else ""})",
                                )
                                for key in writable_dict
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                            multiple=True,
                        )
                    ),
                }
            ),
            errors=self._errors,
        )

    async def _get_possible_devices(self, host, port) -> list[str]:
        """Get a list of possible devices (fubs) from the ETA API."""
        session = async_get_clientsession(self.hass)
        eta_client = EtaAPI(session, host, port)
        try:
            menu = await eta_client.get_menu()
            raw_devices = menu["eta"]["menu"]["fub"]
            if not isinstance(raw_devices, list):
                raw_devices = [raw_devices]
            return [device["@name"] for device in raw_devices if "@name" in device]
        except Exception as e:
            _LOGGER.error(f"Error getting devices from ETA API: {e}")
            return []


    async def _test_url(self, host, port):
        """Return true if host port is valid."""
        session = async_get_clientsession(self.hass)
        eta_client = EtaAPI(session, host, port)

        try:
            does_endpoint_exist = await eta_client.does_endpoint_exists()
        except:
            return -1
        return 1 if does_endpoint_exist else 0

    async def _get_all_sensors_from_device(
        self, host, port, force_legacy_mode, device_name: str
    ):
        """Get all possible endpoints for a specific device."""
        session = async_get_clientsession(self.hass)
        eta_client = EtaAPI(session, host, port)

        float_dict = {}
        switches_dict = {}
        text_dict = {}
        writable_dict = {}
        await eta_client.get_all_sensors(
            force_legacy_mode,
            float_dict,
            switches_dict,
            text_dict,
            writable_dict,
            [device_name],  # Filter by device
        )

        _LOGGER.debug(
            f"Queried sensors for device {device_name}: Number of float sensors: {len(float_dict)}, Number of switches: {len(switches_dict)}, Number of text sensors: {len(text_dict)}, Number of writable sensors: {len(writable_dict)}"
        )

        return float_dict, switches_dict, text_dict, writable_dict

    async def _is_correct_api_version(self, host, port):
        session = async_get_clientsession(self.hass)
        eta_client = EtaAPI(session, host, port)

        return await eta_client.is_correct_api_version()


class EtaOptionsFlowHandler(config_entries.OptionsFlow):
    """Blueprint config flow options handler."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        self.data = {}
        self._errors = {}

    async def async_step_init(self, user_input=None):  # pylint: disable=unused-argument
        """Manage the options."""
        # self.config_entry is the config entry from the config flow, but we need to get the data from the coordinator
        self.data = self.hass.data[DOMAIN][self.config_entry.entry_id][
            "config_entry_data"
        ]

        if self.data.get(FORCE_SENSOR_DETECTION, False):
            _LOGGER.info("Forcing new endpoint discovery")
            # Clear the coordinator data to force a re-scan on the next update
            for device_name in self.data.get("chosen_devices", []):
                if device_name in self.hass.data[DOMAIN][self.config_entry.entry_id]:
                    coordinator = self.hass.data[DOMAIN][self.config_entry.entry_id][
                        device_name
                    ][DATA_UPDATE_COORDINATOR]
                    coordinator.data = {}
            # Reload the config entry to apply the changes
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_abort(reason="reauth_successful")

        device_name_context = self.handler.context.get("device") if self.handler.context else None

        if device_name_context:
            # If a device is specified in the context, only show entities for that device
            self.data = self.hass.data[DOMAIN][self.config_entry.entry_id][
                device_name_context
            ]
        else:
            # aggregate data from all device coordinators
            self.data[FLOAT_DICT] = {}
            self.data[SWITCHES_DICT] = {}
            self.data[TEXT_DICT] = {}
            self.data[WRITABLE_DICT] = {}
            self.data[CHOSEN_FLOAT_SENSORS] = []
            self.data[CHOSEN_SWITCHES] = []
            self.data[CHOSEN_TEXT_SENSORS] = []
            self.data[CHOSEN_WRITABLE_SENSORS] = []

            for device_name in self.data.get(CHOSEN_DEVICES, []):
                if device_name in self.hass.data[DOMAIN][self.config_entry.entry_id]:
                    device_data = self.hass.data[DOMAIN][self.config_entry.entry_id][
                        device_name
                    ]
                    self.data[FLOAT_DICT].update(device_data.get(FLOAT_DICT, {}))
                    self.data[SWITCHES_DICT].update(
                        device_data.get(SWITCHES_DICT, {})
                    )
                    self.data[TEXT_DICT].update(device_data.get(TEXT_DICT, {}))
                    self.data[WRITABLE_DICT].update(
                        device_data.get(WRITABLE_DICT, {})
                    )
                    self.data[CHOSEN_FLOAT_SENSORS].extend(
                        device_data.get(CHOSEN_FLOAT_SENSORS, [])
                    )
                    self.data[CHOSEN_SWITCHES].extend(
                        device_data.get(CHOSEN_SWITCHES, [])
                    )
                    self.data[CHOSEN_TEXT_SENSORS].extend(
                        device_data.get(CHOSEN_TEXT_SENSORS, [])
                    )
                    self.data[CHOSEN_WRITABLE_SENSORS].extend(
                        device_data.get(CHOSEN_WRITABLE_SENSORS, [])
                    )

        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Manage the options."""
        entity_registry = async_get(self.hass)
        entries = async_entries_for_config_entry(
            entity_registry, self.config_entry.entry_id
        )

        entity_map_sensors = {
            e.unique_id: e for e in entries if e.unique_id in self.data[FLOAT_DICT]
        }
        entity_map_switches = {
            e.unique_id: e for e in entries if e.unique_id in self.data[SWITCHES_DICT]
        }
        entity_map_text_sensors = {
            e.unique_id: e for e in entries if e.unique_id in self.data[TEXT_DICT]
        }
        entity_map_writable_sensors = {
            e.unique_id: e for e in entries if e.unique_id in self.data[WRITABLE_DICT]
        }

        if user_input is not None:
            removed_entities = [
                entity_map_sensors[entity_id]
                for entity_id in entity_map_sensors
                if entity_id not in user_input[CHOSEN_FLOAT_SENSORS]
            ]
            removed_entities.extend(
                [
                    entity_map_switches[entity_id]
                    for entity_id in entity_map_switches
                    if entity_id not in user_input[CHOSEN_SWITCHES]
                ]
            )
            removed_entities.extend(
                [
                    entity_map_text_sensors[entity_id]
                    for entity_id in entity_map_text_sensors
                    if entity_id not in user_input[CHOSEN_TEXT_SENSORS]
                ]
            )
            removed_entities.extend(
                [
                    entity_map_writable_sensors[entity_id]
                    for entity_id in entity_map_writable_sensors
                    if entity_id not in user_input[CHOSEN_WRITABLE_SENSORS]
                ]
            )
            for e in removed_entities:
                # Unregister from HA
                entity_registry.async_remove(e.entity_id)

            data = {
                CHOSEN_FLOAT_SENSORS: user_input[CHOSEN_FLOAT_SENSORS],
                CHOSEN_SWITCHES: user_input[CHOSEN_SWITCHES],
                CHOSEN_TEXT_SENSORS: user_input[CHOSEN_TEXT_SENSORS],
                CHOSEN_WRITABLE_SENSORS: user_input[CHOSEN_WRITABLE_SENSORS],
                FLOAT_DICT: self.data[FLOAT_DICT],
                SWITCHES_DICT: self.data[SWITCHES_DICT],
                TEXT_DICT: self.data[TEXT_DICT],
                WRITABLE_DICT: self.data[WRITABLE_DICT],
                CONF_HOST: self.data[CONF_HOST],
                CONF_PORT: self.data[CONF_PORT],
            }

            return self.async_create_entry(title="", data=data)
        return await self._show_config_form_endpoint(
            list(entity_map_sensors.keys()),
            list(entity_map_switches.keys()),
            list(entity_map_text_sensors.keys()),
            list(entity_map_writable_sensors.keys()),
        )

    async def _show_config_form_endpoint(
        self,
        current_chosen_sensors: list[str],
        current_chosen_switches: list[str],
        current_chosen_text_sensors: list[str],
        current_chosen_writable_sensors: list[str],
    ):
        """Show the configuration form to select which endpoints should become entities.
        The default arguments for this function must be lists, otherwise the Selectors will crash
        """

        _LOGGER.debug("Displaying option flow endpoint selection form")

        # Create shallow copies of the dicts to make sure the del operators below won't delete the original data
        sensors_dict: dict[str, ETAEndpoint] = copy.copy(self.data[FLOAT_DICT])
        switches_dict: dict[str, ETAEndpoint] = copy.copy(self.data[SWITCHES_DICT])
        text_dict: dict[str, ETAEndpoint] = copy.copy(self.data[TEXT_DICT])
        writable_dict: dict[str, ETAEndpoint] = copy.copy(self.data[WRITABLE_DICT])

        session = async_get_clientsession(self.hass)
        eta_client = EtaAPI(session, self.data[CONF_HOST], self.data[CONF_PORT])

        is_correct_api_version = await eta_client.is_correct_api_version()
        if not is_correct_api_version:
            self._errors["base"] = "wrong_api_version"

        # Update current values
        for entity in list(sensors_dict.keys()):
            try:
                sensors_dict[entity]["value"], _ = await eta_client.get_data(
                    sensors_dict[entity]["url"]
                )
            except Exception:
                _LOGGER.error(
                    "Exception while updating the value for endpoint '%s' (%s), removing sensor from the lists",
                    sensors_dict[entity]["friendly_name"],
                    sensors_dict[entity]["url"],
                )
                del sensors_dict[entity]
                self._errors["base"] = "value_update_error"

        for entity in list(switches_dict.keys()):
            try:
                switches_dict[entity]["value"], _ = await eta_client.get_data(
                    switches_dict[entity]["url"]
                )
            except Exception:
                _LOGGER.error(
                    "Exception while updating the value for endpoint '%s' (%s), removing sensor from the lists",
                    switches_dict[entity]["friendly_name"],
                    switches_dict[entity]["url"],
                )
                del switches_dict[entity]
                self._errors["base"] = "value_update_error"
        for entity in list(text_dict.keys()):
            try:
                text_dict[entity]["value"], _ = await eta_client.get_data(
                    text_dict[entity]["url"]
                )
            except Exception:
                _LOGGER.error(
                    "Exception while updating the value for endpoint '%s' (%s), removing sensor from the lists",
                    text_dict[entity]["friendly_name"],
                    text_dict[entity]["url"],
                )
                del text_dict[entity]
                self._errors["base"] = "value_update_error"
        for entity in list(writable_dict.keys()):
            try:
                writable_dict[entity]["value"], _ = await eta_client.get_data(
                    writable_dict[entity]["url"]
                )
            except Exception:
                _LOGGER.error(
                    "Exception while updating the value for endpoint '%s' (%s), removing sensor from the lists",
                    writable_dict[entity]["friendly_name"],
                    writable_dict[entity]["url"],
                )
                del writable_dict[entity]
                self._errors["base"] = "value_update_error"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CHOSEN_FLOAT_SENSORS, default=current_chosen_sensors
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(
                                    value=key,
                                    label=f"{sensors_dict[key]['friendly_name']} ({sensors_dict[key]['value']} {sensors_dict[key]['unit'] if sensors_dict[key]['unit'] not in INVISIBLE_UNITS else ""})",
                                )
                                for key in sensors_dict
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                            multiple=True,
                        )
                    ),
                    vol.Optional(
                        CHOSEN_SWITCHES, default=current_chosen_switches
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(
                                    value=key,
                                    label=f"{switches_dict[key]['friendly_name']} ({switches_dict[key]['value']})",
                                )
                                for key in switches_dict
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                            multiple=True,
                        )
                    ),
                    vol.Optional(
                        CHOSEN_TEXT_SENSORS, default=current_chosen_text_sensors
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(
                                    value=key,
                                    label=f"{text_dict[key]['friendly_name']} ({text_dict[key]['value']})",
                                )
                                for key in text_dict
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                            multiple=True,
                        )
                    ),
                    vol.Optional(
                        CHOSEN_WRITABLE_SENSORS, default=current_chosen_writable_sensors
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(
                                    value=key,
                                    label=f"{writable_dict[key]['friendly_name']} ({writable_dict[key]['value']} {writable_dict[key]['unit'] if writable_dict[key]['unit'] not in INVISIBLE_UNITS else ""})",
                                )
                                for key in writable_dict
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                            multiple=True,
                        )
                    ),
                }
            ),
            errors=self._errors,
        )
