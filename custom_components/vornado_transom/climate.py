"""Climate entity exposing the Transom's auto (thermostat) mode."""

import logging
from typing import Any, override

from homeassistant.components.climate import (
    ATTR_TEMPERATURE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, UnitOfTemperature
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util.unit_conversion import TemperatureConverter

from . import TransomConfigEntry
from .const import (
    CONF_TEMPERATURE_SENSOR_ENTITY_ID,
    SPEED_MAX,
    SPEED_MIN,
    TEMP_MAX,
    TEMP_MIN,
)
from .controller import TransomController
from .entity import TransomEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

FAN_MODES = ["low", "medium", "high", "turbo"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TransomConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the climate entity."""
    sensor_entity_id = entry.options.get(
        CONF_TEMPERATURE_SENSOR_ENTITY_ID,
        entry.data.get(CONF_TEMPERATURE_SENSOR_ENTITY_ID),
    )
    async_add_entities(
        [
            TransomClimate(
                entry.runtime_data, entry.entry_id, entry.title, sensor_entity_id
            )
        ]
    )


class TransomClimate(TransomEntity, ClimateEntity):
    """The Transom's thermostat mode as a climate entity."""

    _attr_translation_key = "thermostat"
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.FAN_ONLY, HVACMode.AUTO]
    _attr_fan_modes = FAN_MODES
    _attr_temperature_unit = UnitOfTemperature.FAHRENHEIT
    _attr_min_temp = TEMP_MIN
    _attr_max_temp = TEMP_MAX
    _attr_target_temperature_step = 1
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(
        self,
        controller: TransomController,
        entry_id: str,
        title: str,
        sensor_entity_id: str | None,
    ) -> None:
        """Initialize the climate entity."""
        super().__init__(controller, entry_id, title)
        self._attr_unique_id = f"{entry_id}_climate"
        self._sensor_entity_id = sensor_entity_id
        self._attr_current_temperature = None

    @override
    async def async_added_to_hass(self) -> None:
        """Mirror the optional external temperature sensor."""
        await super().async_added_to_hass()
        if self._sensor_entity_id is None:
            return
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._sensor_entity_id], self._async_sensor_changed
            )
        )
        self._update_current_temperature()

    @callback
    def _async_sensor_changed(self, event: Event[EventStateChangedData]) -> None:
        self._update_current_temperature()
        self.async_write_ha_state()

    @callback
    def _update_current_temperature(self) -> None:
        """Read the sensor, converting to Fahrenheit if needed."""
        state = self.hass.states.get(self._sensor_entity_id)
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            self._attr_current_temperature = None
            return
        try:
            value = float(state.state)
        except ValueError:
            self._attr_current_temperature = None
            return
        unit = state.attributes.get("unit_of_measurement")
        if unit and unit != UnitOfTemperature.FAHRENHEIT:
            try:
                value = TemperatureConverter.convert(
                    value, unit, UnitOfTemperature.FAHRENHEIT
                )
            except (ValueError, TypeError):
                _LOGGER.warning(
                    "Cannot convert %s %s from %s", state.entity_id, value, unit
                )
                self._attr_current_temperature = None
                return
        self._attr_current_temperature = value

    @property
    @override
    def hvac_mode(self) -> HVACMode:
        """Return the assumed mode."""
        if not self.controller.state.power:
            return HVACMode.OFF
        if self.controller.state.auto:
            return HVACMode.AUTO
        return HVACMode.FAN_ONLY

    @property
    @override
    def target_temperature(self) -> float:
        """Return the assumed target temperature."""
        return self.controller.state.target_temp

    @property
    @override
    def fan_mode(self) -> str:
        """Return the assumed fan speed as a mode name."""
        return FAN_MODES[self.controller.state.speed - SPEED_MIN]

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the mode: off, manual fan, or thermostat."""
        if hvac_mode == HVACMode.OFF:
            await self.controller.async_set_power(False)
        elif hvac_mode == HVACMode.AUTO:
            await self.controller.async_set_auto(True)
        else:
            await self.controller.async_set_auto(False)

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature (enables auto mode if it's off)."""
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is not None:
            await self.controller.async_set_target_temp(round(temp))

    @override
    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set a manual speed; drops out of auto mode."""
        await self.controller.async_set_speed(FAN_MODES.index(fan_mode) + SPEED_MIN)

    @override
    async def async_turn_on(self) -> None:
        """Turn on the fan."""
        await self.controller.async_set_power(True)

    @override
    async def async_turn_off(self) -> None:
        """Turn off the fan."""
        await self.controller.async_set_power(False)
