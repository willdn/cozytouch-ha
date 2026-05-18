from __future__ import annotations

import voluptuous as vol
import aiohttp
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CozytouchAPI
from .const import DOMAIN

STEP_SCHEMA = vol.Schema({
    vol.Required("email"): str,
    vol.Required("password"): str,
})


class CozytouchConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            api = CozytouchAPI(session)
            try:
                await api.login(user_input["email"], user_input["password"])
            except aiohttp.ClientResponseError:
                errors["base"] = "invalid_auth"
            except Exception:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(user_input["email"].lower())
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Cozytouch", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_SCHEMA,
            errors=errors,
        )
