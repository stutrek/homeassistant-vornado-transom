"""The Vornado Transom integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_INFRARED_ENTITY_ID
from .controller import TransomController

PLATFORMS = [Platform.CLIMATE, Platform.FAN, Platform.NUMBER]

type TransomConfigEntry = ConfigEntry[TransomController]


async def async_setup_entry(hass: HomeAssistant, entry: TransomConfigEntry) -> bool:
    """Set up Vornado Transom from a config entry."""
    emitter_entity_id = entry.options.get(
        CONF_INFRARED_ENTITY_ID, entry.data[CONF_INFRARED_ENTITY_ID]
    )
    controller = TransomController(hass, entry.entry_id, emitter_entity_id)
    await controller.async_load()
    entry.runtime_data = controller

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: TransomConfigEntry) -> bool:
    """Unload a config entry."""
    entry.runtime_data.async_shutdown()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
