from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CozytouchAPI
from .coordinator import CozytouchCoordinator

type CozytouchConfigEntry = ConfigEntry[CozytouchCoordinator]

PLATFORMS = ["climate"]


async def async_setup_entry(hass: HomeAssistant, entry: CozytouchConfigEntry) -> bool:
    session = async_get_clientsession(hass)
    api = CozytouchAPI(session)
    await api.login(entry.data["email"], entry.data["password"])

    coordinator = CozytouchCoordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: CozytouchConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
