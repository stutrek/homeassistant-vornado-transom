"""Shared base entity for the Vornado Transom device."""

from typing import override

from homeassistant.components.infrared import InfraredEmitterConsumerEntity
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN
from .controller import TransomController


class TransomEntity(InfraredEmitterConsumerEntity):
    """Base entity: shares one device, mirrors controller state, tracks emitter availability."""

    _attr_has_entity_name = True
    _attr_assumed_state = True

    def __init__(self, controller: TransomController, entry_id: str, title: str) -> None:
        """Initialize the entity."""
        self.controller = controller
        self._infrared_emitter_entity_id = controller.emitter_entity_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=title,
            manufacturer="Vornado",
            model="Transom",
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to controller state changes."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.controller.async_add_listener(self.async_write_ha_state)
        )
