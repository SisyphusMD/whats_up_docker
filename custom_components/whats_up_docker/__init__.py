"""Initialize the What's Up Docker integration."""

from __future__ import annotations

import logging

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util.hass_dict import HassEntryKey

from .const import DOMAIN, PLATFORMS
from .coordinator import WUDDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# A typed key to store a dict mapped from entry_id -> WUDDataUpdateCoordinator
COORDINATOR_KEY: HassEntryKey[dict[str, WUDDataUpdateCoordinator]] = HassEntryKey(
    DOMAIN
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the What's Up Docker integration from a config entry."""
    # Prepare a dictionary under the typed key to store coordinators
    domain_data = hass.data.setdefault(COORDINATOR_KEY, {})

    instance_name = entry.data["name"]
    protocol = entry.data["protocol"]
    host = entry.data["host"]
    port = entry.data["port"]
    username = entry.data["username"]
    password = entry.data["password"]
    github_token = entry.data["token"]

    # Assemble the URL from protocol, host, and port
    url = f"{protocol}://{host}:{port}/api/containers"

    # Home Assistant's managed HTTP session
    session = async_get_clientsession(hass)

    # Basic auth for your WUD API endpoints
    auth = aiohttp.BasicAuth(username, password)

    # Create the coordinator for this entry
    coordinator = WUDDataUpdateCoordinator(
        hass, session, url, auth, instance_name, github_token
    )
    await coordinator.async_config_entry_first_refresh()

    # Store the coordinator in the dictionary
    domain_data[entry.entry_id] = coordinator

    # Forward the setup request to the desired platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a WUD config entry."""
    # Unload all platforms that were forwarded
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Remove the coordinator for this unloaded entry
        domain_data = hass.data.get(COORDINATOR_KEY, {})
        domain_data.pop(entry.entry_id)

    return unload_ok
