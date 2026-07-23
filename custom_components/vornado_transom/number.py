"""Target temperature number entity for the Vornado Transom."""

from typing import override

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TransomConfigEntry
from .const import TEMP_MAX, TEMP_MIN
from .controller import TransomController
from .entity import TransomEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TransomConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the number entity."""
    async_add_entities(
        [TransomTargetTemp(entry.runtime_data, entry.entry_id, entry.title)]
    )


class TransomTargetTemp(TransomEntity, NumberEntity):
    """Auto-mode target temperature. Setting it enables auto mode."""

    _attr_translation_key = "target_temperature"
    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT
    _attr_native_min_value = TEMP_MIN
    _attr_native_max_value = TEMP_MAX
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self, controller: TransomController, entry_id: str, title: str
    ) -> None:
        """Initialize the number entity."""
        super().__init__(controller, entry_id, title)
        self._attr_unique_id = f"{entry_id}_target_temp"

    @property
    @override
    def native_value(self) -> float:
        """Return the assumed target temperature."""
        return self.controller.state.target_temp

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the target temperature (enables auto mode if it's off)."""
        await self.controller.async_set_target_temp(round(value))
