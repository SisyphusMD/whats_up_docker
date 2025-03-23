"""Coordinator for the What's Up Docker integration."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


class WUDDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to manage fetching data from WUD API."""

    def __init__(
        self,
        hass: HomeAssistant,
        session: aiohttp.ClientSession,
        url: str,
        auth: aiohttp.BasicAuth,
        instance_name: str | None = None,
        github_token: str | None = None,
    ) -> None:
        """Initialize the coordinator."""
        self._session = session
        self._url = url
        self._auth = auth
        self._instance_name = instance_name
        self._github_token = github_token

        super().__init__(
            hass,
            _LOGGER,
            name=f"WUDDataUpdateCoordinator-{instance_name}",
            update_interval=timedelta(seconds=5),  # Adjust as needed
        )

    @property
    def session(self) -> aiohttp.ClientSession:
        """Return the aiohttp ClientSession."""
        return self._session

    @property
    def url(self) -> str:
        """Return the WUD server URL."""
        return self._url

    @property
    def auth(self) -> aiohttp.BasicAuth:
        """Return the BasicAuth credentials."""
        return self._auth

    @property
    def instance_name(self) -> str:
        """A user-friendly name/identifier for the instance."""
        return self._instance_name

    @property
    def github_token(self) -> str | None:
        """Return the optional GitHub token, if provided."""
        return self._github_token

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch the latest data from WUD."""
        try:
            data = await asyncio.wait_for(self._async_fetch_data(), timeout=5)
            # Convert container list into a dict keyed by container name
            return {container["name"]: container for container in data}
        except TimeoutError as err:
            _LOGGER.error("Timeout fetching data from WUD: %s", err)
            raise UpdateFailed(f"Timeout fetching data from WUD: {err}") from err
        except aiohttp.ClientError as err:
            _LOGGER.error("Client error fetching data from WUD: %s", err)
            raise UpdateFailed(f"Client error fetching data from WUD: {err}") from err
        except Exception as err:
            _LOGGER.error("Unexpected error fetching data from WUD: %s", err)
            raise UpdateFailed(
                f"Unexpected error fetching data from WUD: {err}"
            ) from err

    async def _async_fetch_data(self) -> list[dict[str, Any]]:
        """Perform the actual fetch from the WUD API."""
        async with self._session.get(self._url, auth=self._auth) as response:
            response.raise_for_status()
            return await response.json()
