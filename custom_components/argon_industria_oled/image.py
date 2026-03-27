"""Image entity for the Argon Industria OLED integration."""

from __future__ import annotations

import logging
from datetime import datetime

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import ArgonIndustriaOledCoordinator
from .helpers import build_device_info

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the OLED display image entity from a config entry."""
    coordinator: ArgonIndustriaOledCoordinator = entry.runtime_data
    async_add_entities([ArgonOledImageEntity(hass, coordinator, entry)])


class ArgonOledImageEntity(ImageEntity):
    """Expose the current OLED framebuffer as a preview image.

    The entity refreshes automatically whenever the display content changes
    (draw, clear, or startup splash).  The image is returned as a 4x scaled
    PNG so it remains legible in the Home Assistant UI.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "display_image"
    _attr_content_type = "image/png"

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: ArgonIndustriaOledCoordinator,
        entry: ConfigEntry,
    ) -> None:
        ImageEntity.__init__(self, hass)
        self._coordinator = coordinator
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_display_image"
        self._cached_image: bytes | None = None
        self._attr_image_last_updated: datetime | None = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info so this entity is grouped with the OLED device."""
        return build_device_info(self._entry)

    async def async_added_to_hass(self) -> None:
        """Register for display update notifications when entity joins HA."""
        self.async_on_remove(
            self._coordinator.subscribe_display_update(self._handle_display_update)
        )
        _LOGGER.debug("Display image entity registered (unique_id=%s)", self.unique_id)

    @callback
    def _handle_display_update(self) -> None:
        """Invalidate the image cache and update the entity state."""
        _LOGGER.debug("Display updated — refreshing image entity (unique_id=%s)", self.unique_id)
        self._cached_image = None
        self._attr_image_last_updated = dt_util.utcnow()
        self.async_write_ha_state()

    async def async_image(self) -> bytes | None:
        """Return the current OLED framebuffer as a PNG.

        Fetches fresh bytes from the device on first call after each display
        update; subsequent calls within the same update cycle use a cache.
        """
        if self._cached_image is None:
            self._cached_image = await self.hass.async_add_executor_job(
                self._coordinator.get_display_image_bytes
            )
        return self._cached_image
