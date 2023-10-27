"""Adds config flow for Blueprint."""
import voluptuous as vol
from copy import deepcopy
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.entity_registry import (
    async_entries_for_config_entry,
    async_get,
)
from .api import ETAEndpoint, EtaAPI
from .const import (
    DOMAIN,
    FLOAT_DICT,
    SWITCHES_DICT,
    TEXT_DICT,
    CHOSEN_FLOAT_SENSORS,
    CHOSEN_SWITCHES,
    CHOSEN_TEXT_SENSORS,
)


class EtaFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Eta."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize."""
        self._errors = {}

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

                self.data = user_input
                (
                    self.data[FLOAT_DICT],
                    self.data[SWITCHES_DICT],
                    self.data[TEXT_DICT],
                ) = await self._get_possible_endpoints(
                    user_input[CONF_HOST], user_input[CONF_PORT]
                )

                return await self.async_step_select_entities()
            else:
                self._errors["base"] = (
                    "no_eta_endpoint" if valid == 0 else "unknown_host"
                )

            return await self._show_config_form_user(user_input)

        user_input = {}
        # Provide defaults for form
        user_input[CONF_HOST] = "0.0.0.0"
        user_input[CONF_PORT] = "8080"

        return await self._show_config_form_user(user_input)

    async def async_step_select_entities(self, user_input: dict = None):
        """Second step in config flow to add a repo to watch."""
        if user_input is not None:
            # add chosen entities to data
            self.data[CHOSEN_FLOAT_SENSORS] = user_input.get(CHOSEN_FLOAT_SENSORS, [])
            self.data[CHOSEN_SWITCHES] = user_input.get(CHOSEN_SWITCHES, [])
            self.data[CHOSEN_TEXT_SENSORS] = user_input.get(CHOSEN_TEXT_SENSORS, [])

            # User is done, create the config entry.
            return self.async_create_entry(
                title=f"ETA at {self.data[CONF_HOST]}", data=self.data
            )

        return await self._show_config_form_endpoint()

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
                    vol.Required(CONF_HOST, default=user_input[CONF_HOST]): str,
                    vol.Required(CONF_PORT, default=user_input[CONF_PORT]): str,
                }
            ),
            errors=self._errors,
        )

    async def _show_config_form_endpoint(self):
        """Show the configuration form to select which endpoints should become entities."""
        sensors_dict: dict[str, ETAEndpoint] = self.data[FLOAT_DICT]
        switches_dict: dict[str, ETAEndpoint] = self.data[SWITCHES_DICT]
        text_dict: dict[str, ETAEndpoint] = self.data[TEXT_DICT]

        return self.async_show_form(
            step_id="select_entities",
            data_schema=vol.Schema(
                {
                    vol.Optional(CHOSEN_FLOAT_SENSORS): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(
                                    value=key,
                                    label=f"{sensors_dict[key]['friendly_name']} ({sensors_dict[key]['value']} {sensors_dict[key]['unit']})",
                                )
                                for key in sensors_dict.keys()
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
                                for key in switches_dict.keys()
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
                                for key in text_dict.keys()
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                            multiple=True,
                        )
                    ),
                }
            ),
            errors=self._errors,
        )

    async def _get_possible_endpoints(self, host, port):
        session = async_get_clientsession(self.hass)
        eta_client = EtaAPI(session, host, port)
        float_dict = {}
        switches_dict = {}
        text_dict = {}
        await eta_client.get_all_sensors(float_dict, switches_dict, text_dict)

        return float_dict, switches_dict, text_dict

    async def _test_url(self, host, port):
        """Return true if host port is valid."""
        session = async_get_clientsession(self.hass)
        eta_client = EtaAPI(session, host, port)

        try:
            does_endpoint_exist = await eta_client.does_endpoint_exists()
        except:
            return -1
        return 1 if does_endpoint_exist else 0

    async def _is_correct_api_version(self, host, port):
        session = async_get_clientsession(self.hass)
        eta_client = EtaAPI(session, host, port)

        return await eta_client.is_correct_api_version()


class EtaOptionsFlowHandler(config_entries.OptionsFlow):
    """Blueprint config flow options handler."""

    def __init__(self, config_entry):
        """Initialize HACS options flow."""
        self.config_entry = config_entry
        self.data = dict(config_entry.data)

    async def async_step_init(self, user_input=None):  # pylint: disable=unused-argument
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Manage the options."""
        self._errors = {}

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

        if user_input is not None:
            removed_entities = [
                entity_map_sensors[entity_id]
                for entity_id in entity_map_sensors.keys()
                if entity_id not in user_input[CHOSEN_FLOAT_SENSORS]
            ]
            removed_entities.extend(
                [
                    entity_map_switches[entity_id]
                    for entity_id in entity_map_switches.keys()
                    if entity_id not in user_input[CHOSEN_SWITCHES]
                ]
            )
            removed_entities.extend(
                [
                    entity_map_text_sensors[entity_id]
                    for entity_id in entity_map_text_sensors.keys()
                    if entity_id not in user_input[CHOSEN_TEXT_SENSORS]
                ]
            )
            for e in removed_entities:
                # Unregister from HA
                entity_registry.async_remove(e.entity_id)

            data = {
                CHOSEN_FLOAT_SENSORS: user_input[CHOSEN_FLOAT_SENSORS],
                CHOSEN_SWITCHES: user_input[CHOSEN_SWITCHES],
                CHOSEN_TEXT_SENSORS: user_input[CHOSEN_TEXT_SENSORS],
                FLOAT_DICT: self.data[FLOAT_DICT],
                SWITCHES_DICT: self.data[SWITCHES_DICT],
                TEXT_DICT: self.data[TEXT_DICT],
                CONF_HOST: self.data[CONF_HOST],
                CONF_PORT: self.data[CONF_PORT],
            }

            return self.async_create_entry(title="", data=data)
        return await self._show_config_form_endpoint(
            [key for key in entity_map_sensors.keys()],
            [key for key in entity_map_switches.keys()],
            [key for key in entity_map_text_sensors.keys()],
        )

    async def _show_config_form_endpoint(
        self,
        current_chosen_sensors,
        current_chosen_switches,
        current_chosen_text_sensors,
    ):
        """Show the configuration form to select which endpoints should become entities."""
        sensors_dict: dict[str, ETAEndpoint] = self.data[FLOAT_DICT]
        switches_dict: dict[str, ETAEndpoint] = self.data[SWITCHES_DICT]
        text_dict: dict[str, ETAEndpoint] = self.data[TEXT_DICT]

        session = async_get_clientsession(self.hass)
        eta_client = EtaAPI(session, self.data[CONF_HOST], self.data[CONF_PORT])

        # Update current values
        for entity in sensors_dict:
            sensors_dict[entity]["value"], _ = await eta_client.get_data(
                sensors_dict[entity]["url"]
            )
        for entity in switches_dict:
            switches_dict[entity]["value"], _ = await eta_client.get_data(
                switches_dict[entity]["url"]
            )
        for entity in text_dict:
            text_dict[entity]["value"], _ = await eta_client.get_data(
                text_dict[entity]["url"]
            )

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
                                    label=f"{sensors_dict[key]['friendly_name']} ({sensors_dict[key]['value']} {sensors_dict[key]['unit']})",
                                )
                                for key in sensors_dict.keys()
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
                                for key in switches_dict.keys()
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
                                for key in text_dict.keys()
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                            multiple=True,
                        )
                    ),
                }
            ),
        )

    async def _update_options(self):
        """Update config entry options."""
        return self.async_create_entry(
            title=self.config_entry.data.get(CONF_HOST), data=self.options
        )
