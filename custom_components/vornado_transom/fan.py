"""Fan entity for the Vornado Transom."""

import math
from typing import Any, override

import voluptuous as vol

from homeassistant.components.fan import (
    DIRECTION_FORWARD,
    DIRECTION_REVERSE,
    FanEntity,
    FanEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from . import TransomConfigEntry
from .const import (
    BUTTON_CODES,
    DIRECTION_DIRECT,
    DIRECTION_EXHAUST,
    SERVICE_CALIBRATE,
    SERVICE_SEND_BUTTON,
    SERVICE_SET_ASSUMED_STATE,
    SPEED_MAX,
    SPEED_MIN,
    TEMP_MAX,
    TEMP_MIN,
)
from .controller import TransomController
from .entity import TransomEntity

PARALLEL_UPDATES = 0

PRESET_MODE_AUTO = "Auto"

SPEED_RANGE = (SPEED_MIN, SPEED_MAX)

# HA fan direction <-> Transom airflow direction. Forward blows air into the
# room (direct mode), reverse pushes it out the window (exhaust mode).
HA_TO_TRANSOM_DIRECTION = {
    DIRECTION_FORWARD: DIRECTION_DIRECT,
    DIRECTION_REVERSE: DIRECTION_EXHAUST,
}
TRANSOM_TO_HA_DIRECTION = {v: k for k, v in HA_TO_TRANSOM_DIRECTION.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TransomConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the fan entity and the integration's entity services."""
    async_add_entities([TransomFan(entry.runtime_data, entry.entry_id, entry.title)])

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SET_ASSUMED_STATE,
        {
            vol.Optional("power"): cv.boolean,
            vol.Optional("speed"): vol.All(
                vol.Coerce(int), vol.Range(min=SPEED_MIN, max=SPEED_MAX)
            ),
            vol.Optional("direction"): vol.In([DIRECTION_DIRECT, DIRECTION_EXHAUST]),
            vol.Optional("auto"): cv.boolean,
            vol.Optional("target_temp"): vol.All(
                vol.Coerce(int), vol.Range(min=TEMP_MIN, max=TEMP_MAX)
            ),
        },
        "async_service_set_assumed_state",
    )
    platform.async_register_entity_service(
        SERVICE_SEND_BUTTON,
        {
            vol.Required("button"): vol.In(sorted(BUTTON_CODES)),
            vol.Optional("presses", default=1): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=40)
            ),
        },
        "async_service_send_button",
    )
    platform.async_register_entity_service(
        SERVICE_CALIBRATE, None, "async_service_calibrate"
    )


class TransomFan(TransomEntity, FanEntity):
    """The Transom as a fan: power, 4 speeds, direction, auto preset."""

    _attr_name = None
    _attr_preset_modes = [PRESET_MODE_AUTO]
    _attr_speed_count = SPEED_MAX
    _attr_supported_features = (
        FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.SET_SPEED
        | FanEntityFeature.DIRECTION
        | FanEntityFeature.PRESET_MODE
    )

    def __init__(
        self, controller: TransomController, entry_id: str, title: str
    ) -> None:
        """Initialize the fan entity."""
        super().__init__(controller, entry_id, title)
        self._attr_unique_id = f"{entry_id}_fan"

    @property
    @override
    def is_on(self) -> bool:
        """Return whether the fan is desired on."""
        return self.controller.desired.power

    @property
    @override
    def percentage(self) -> int | None:
        """Return the desired speed as a percentage."""
        if not self.controller.desired.power:
            return 0
        return ranged_value_to_percentage(SPEED_RANGE, self.controller.desired.speed)

    @property
    @override
    def preset_mode(self) -> str | None:
        """Return 'Auto' when thermostat mode is desired active."""
        return PRESET_MODE_AUTO if self.controller.desired.auto else None

    @property
    @override
    def current_direction(self) -> str:
        """Return the desired airflow direction."""
        return TRANSOM_TO_HA_DIRECTION[self.controller.desired.direction]

    @override
    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan, optionally into a speed or the auto preset."""
        if preset_mode == PRESET_MODE_AUTO:
            self.controller.request(power=True, auto=True)
        elif percentage is not None:
            await self.async_set_percentage(percentage)
        else:
            self.controller.request(power=True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        self.controller.request(power=False)

    @override
    async def async_set_percentage(self, percentage: int) -> None:
        """Set the fan speed; 0 turns it off. Speed does not affect auto mode."""
        if percentage == 0:
            self.controller.request(power=False)
            return
        speed = math.ceil(percentage_to_ranged_value(SPEED_RANGE, percentage))
        self.controller.request(power=True, speed=speed)

    @override
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Activate the auto (thermostat) preset."""
        self.controller.request(power=True, auto=preset_mode == PRESET_MODE_AUTO)

    @override
    async def async_set_direction(self, direction: str) -> None:
        """Set airflow direction (forward=direct/in, reverse=exhaust/out)."""
        self.controller.request(
            power=True, direction=HA_TO_TRANSOM_DIRECTION[direction]
        )

    async def async_service_set_assumed_state(
        self,
        power: bool | None = None,
        speed: int | None = None,
        direction: str | None = None,
        auto: bool | None = None,
        target_temp: int | None = None,
    ) -> None:
        """Correct the tracked state without sending IR."""
        await self.controller.async_set_assumed_state(
            power=power,
            speed=speed,
            direction=direction,
            auto=auto,
            target_temp=target_temp,
        )

    async def async_service_send_button(self, button: str, presses: int) -> None:
        """Send raw remote button presses (does not update assumed state)."""
        await self.controller.async_send_button(BUTTON_CODES[button], presses)

    async def async_service_calibrate(self) -> None:
        """Clamp-to-boundary resync of speed (auto off) or temp (auto on)."""
        await self.controller.async_calibrate()
