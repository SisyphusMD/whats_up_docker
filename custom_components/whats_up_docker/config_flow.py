"""Config flow for WUD integration."""

import logging

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_TOKEN,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client

from .const import (
    DEFAULT_CONF_NAME,
    DEFAULT_GITHUB_TOKEN,
    DEFAULT_HOST,
    DEFAULT_PASSWORD,
    DEFAULT_PORT,
    DEFAULT_PROTOCOL,
    DEFAULT_USERNAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class WUDConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WUD."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial setup step."""
        errors = {}
        if user_input is not None:
            instance_name = user_input[CONF_NAME]
            protocol = user_input[CONF_PROTOCOL]
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            github_token = user_input[CONF_TOKEN]
            url = f"{protocol}://{host}:{port}/api/containers"
            session = aiohttp_client.async_get_clientsession(self.hass)
            auth = aiohttp.BasicAuth(username, password)
            try:
                async with session.get(url, auth=auth, timeout=10) as response:
                    if response.status != 200:
                        errors["base"] = "cannot_connect"
                    else:
                        # Check if already configured
                        await self.async_set_unique_id(f"{instance_name}_{host}")
                        self._abort_if_unique_id_configured()
                        # Save the data
                        data = {
                            CONF_NAME: instance_name,
                            CONF_PROTOCOL: protocol,
                            CONF_HOST: host,
                            CONF_PORT: port,
                            CONF_USERNAME: username,
                            CONF_PASSWORD: password,
                            CONF_TOKEN: github_token,
                        }
                        return self.async_create_entry(
                            title=f"WUD ({instance_name})", data=data
                        )
            except aiohttp.ClientError:
                _LOGGER.exception("Client error connecting to WUD")
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error")
                errors["base"] = "unknown"

        data_schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=DEFAULT_CONF_NAME): str,
                vol.Required(CONF_PROTOCOL, default=DEFAULT_PROTOCOL): str,
                vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): str,
                vol.Required(CONF_PASSWORD, default=DEFAULT_PASSWORD): str,
                vol.Optional(CONF_TOKEN, default=DEFAULT_GITHUB_TOKEN): str,
            }
        )
        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow."""
        return WUDOptionsFlowHandler(config_entry)


class WUDOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle WUD options."""

    def __init__(self, config_entry) -> None:
        """Initialize WUD options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the WUD options."""
        if user_input is not None:
            # Update options
            return self.async_create_entry(title="", data=user_input)

        data_schema = vol.Schema(
            {vol.Optional(CONF_TOKEN, default=DEFAULT_GITHUB_TOKEN): str}
        )
        return self.async_show_form(step_id="init", data_schema=data_schema)
