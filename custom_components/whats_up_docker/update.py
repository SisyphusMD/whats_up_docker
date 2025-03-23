"""Update platform for What's Up Docker integration."""

from __future__ import annotations

import asyncio
import logging
import re

import aiohttp

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import COORDINATOR_KEY
from .coordinator import WUDDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up WUD update entities from a config entry."""
    # 1) Retrieve the coordinator that was created in __init__.py
    domain_data = hass.data.get(COORDINATOR_KEY, {})
    coordinator: WUDDataUpdateCoordinator | None = domain_data.get(entry.entry_id)
    if not coordinator:
        _LOGGER.error("No WUD coordinator found for entry_id %s", entry.entry_id)
        return

    # 2) Check coordinator state
    if not coordinator.last_update_success:
        _LOGGER.error("Failed to retrieve data from WUD at startup")
        return

    # 3) Build entities
    entities = [
        WUDUpdateEntity(
            coordinator,
            container_name,
            coordinator.instance_name,
            entry.entry_id,
        )
        for container_name in coordinator.data
    ]
    async_add_entities(entities)

    # 4) To enable reloading config or options dynamically
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload entry when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)


class WUDUpdateEntity(CoordinatorEntity[WUDDataUpdateCoordinator], UpdateEntity):
    """Representation of a WUD Docker container update entity."""

    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.RELEASE_NOTES
    )

    def __init__(
        self,
        coordinator: WUDDataUpdateCoordinator,
        container_name: str,
        instance_name: str,
        entry_id: str,
    ) -> None:
        """Initialize the update entity."""
        super().__init__(coordinator)
        self._container_name = container_name
        self._entry_id = entry_id

        # Set a user-friendly name
        self._attr_name = f"{container_name} ({instance_name})"
        self._attr_unique_id = f"{entry_id}_{container_name}"
        self._attr_entity_registry_enabled_default = True

        # Set the icon and picture
        self._attr_icon = "mdi:docker"

    @property
    def entity_picture(self) -> str | None:
        """Return the picture URL."""
        return (
            "https://raw.githubusercontent.com/getwud/wud/main/docs/assets/wud-logo.svg"
        )

    @property
    def installed_version(self) -> str | None:
        """Return the currently installed version."""
        container_data = self.coordinator.data.get(self._container_name)
        if container_data:
            return container_data.get("image", {}).get("tag", {}).get("value")
        return None

    @property
    def latest_version(self) -> str | None:
        """Return the latest available version."""
        container_data = self.coordinator.data.get(self._container_name)
        if container_data:
            # If updateAvailable is True, WUD has a 'result' tag
            if container_data.get("updateAvailable"):
                return container_data.get("result", {}).get("tag")
            return container_data.get("image", {}).get("tag", {}).get("value")
        return None

    @property
    def release_url(self) -> str | None:
        """Return URL to release notes."""
        container_data = self.coordinator.data.get(self._container_name)
        if container_data:
            # Use the link from the 'result' field if an update is available
            if container_data.get("updateAvailable"):
                link = container_data.get("result", {}).get("link")
                tag = container_data.get("result", {}).get("tag")
            else:
                link = container_data.get("link")
                tag = container_data.get("image", {}).get("tag", {}).get("value")

            # Fix for "undefined" image prerelease links
            # Check if the link ends with "undefined"
            if link and link.endswith("undefined"):
                # Extract the last sequence of digits from the tag
                match = re.search(r"\d+$", tag)
                if match:
                    digits = match.group()
                    # Replace "undefined" in the link with the extracted digits
                    link = link.replace("undefined", digits)
            # Fix for prerelease tags missing without "undefined"
            # Check if the link ends with "."
            elif link and link.endswith("."):
                # Extract the last sequence of digits from the tag
                match = re.search(r"\d+$", tag)
                if match:
                    digits = match.group()
                    # Append the extracted digits onto the end
                    link += digits

            return link
        return None

    async def async_release_notes(self) -> str | None:
        """Return the release notes."""
        container_data = self.coordinator.data.get(self._container_name)
        if not container_data:
            return None

        release_url = self.release_url
        if release_url and "github.com" in release_url:
            # Check if the URL is for a specific tag or latest release
            if "/releases/tag/" in release_url or "/tags/" in release_url:
                api_url = release_url.replace(
                    "https://github.com/", "https://api.github.com/repos/"
                )
                if "/releases/tag/" in api_url:
                    api_url = api_url.replace("/releases/tag/", "/releases/tags/")
            elif "/releases/latest" in release_url:
                api_url = release_url.replace(
                    "https://github.com/", "https://api.github.com/repos/"
                )
            else:
                _LOGGER.error("Unsupported GitHub URL format: %s", release_url)
                return None

            headers = {"Accept": "application/vnd.github.v3+json"}
            # Include the token if available
            # github_token = self.coordinator.github_token
            # if github_token:
            #     headers["Authorization"] = f"token {github_token}"

            try:
                async with asyncio.timeout(10):
                    async with self.coordinator.session.get(
                        api_url, headers=headers
                    ) as response:
                        if response.status == 403:
                            _LOGGER.error("GitHub API rate limit exceeded")
                            return None
                        response.raise_for_status()
                        data = await response.json()
                        return data.get("body")
            except TimeoutError:
                _LOGGER.error("Timeout fetching release notes from GitHub")
                return None
            except aiohttp.ClientError as err:
                _LOGGER.error("Error fetching release notes from GitHub API: %s", err)
                return None
            except Exception:
                _LOGGER.exception("Unexpected error")
                return None
        else:
            _LOGGER.debug("No GitHub URL found or not applicable: %s", release_url)

        return None

    @property
    def in_progress(self) -> bool:
        """Return update installation status."""
        # Implement if there's a way to know if an update is in progress
        return False

    async def async_install(self, version: str, backup: bool, **kwargs) -> None:
        """Install an update."""
        _LOGGER.info("Starting update for container %s", self._attr_name)
        container_data = self.coordinator.data.get(self._container_name)
        if not container_data:
            _LOGGER.error("Container data not found for %s", self._attr_name)
            return

        # The WUD label that indicates the custom trigger name
        trigger_name = container_data.get("labels", {}).get("wud.trigger.hass", {})
        if not trigger_name:
            _LOGGER.error("HASS Trigger Label not found for %s", self._attr_name)
            return

        trigger_url_path = trigger_name.replace(".", "/")
        container_id = container_data.get("id")
        if not container_id:
            _LOGGER.error("No container id for %s", self._attr_name)
            return

        # Build endpoint
        trigger_endpoint = (
            f"{self.coordinator.url}/{container_id}/triggers/{trigger_url_path}"
        )
        try:
            _LOGGER.debug(
                "Sending update request to WUD trigger endpoint: %s", trigger_endpoint
            )
            async with self.coordinator.session.post(
                trigger_endpoint, auth=self.coordinator.auth
            ) as response:
                response_text = await response.text()
                if response.status == 200:
                    _LOGGER.info(
                        "Update for container %s has been triggered successfully",
                        self._attr_name,
                    )
                    # If you could track progress, you might do:
                    # self._attr_in_progress = True
                    # self.async_write_ha_state()
                else:
                    _LOGGER.error(
                        "Failed to trigger update for container %s: %s",
                        self._attr_name,
                        response_text,
                    )
        except aiohttp.ClientError as err:
            _LOGGER.error("Error communicating with WUD API: %s", err)
        except Exception:
            _LOGGER.exception("Unexpected error during update")

    @property
    def available(self) -> bool:
        """Return True if coordinator last update was successful."""
        return self.coordinator.last_update_success

    @property
    def should_poll(self) -> bool:
        """Return False because CoordinatorEntity handles updates."""
        return False

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass, listen for coordinator updates."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )
