"""Assumed-state tracking and IR press orchestration for the Transom."""

import asyncio
from collections.abc import Callable
from dataclasses import asdict, dataclass
import logging

from homeassistant.components.infrared import async_send_command
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.storage import Store

from .const import (
    CODE_AUTO,
    CODE_DIRECTION,
    CODE_DOWN,
    CODE_POWER,
    CODE_UP,
    DIRECTION_DIRECT,
    DIRECTION_EXHAUST,
    DOMAIN,
    INTER_PRESS_DELAY,
    POST_MODE_DELAY,
    SPEED_MAX,
    SPEED_MIN,
    TEMP_MAX,
    TEMP_MIN,
)
from .ir import TransomCommand

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1


@dataclass
class TransomState:
    """Assumed state of the fan; there is no feedback channel to confirm it."""

    power: bool = False
    speed: int = 1
    direction: str = DIRECTION_DIRECT
    auto: bool = False
    target_temp: int = 70


class TransomController:
    """Single source of truth shared by the fan, climate, and number entities.

    Every IR command the fan understands is a toggle or a stepper, so this
    tracks what the device is assumed to be doing and emits the minimal press
    sequence to move from the assumed state to the requested one. A lock
    serializes sequences so overlapping service calls can't interleave presses.
    """

    def __init__(
        self, hass: HomeAssistant, entry_id: str, emitter_entity_id: str
    ) -> None:
        """Initialize the controller."""
        self._hass = hass
        self.emitter_entity_id = emitter_entity_id
        self.state = TransomState()
        self._store: Store[dict] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry_id}"
        )
        self._lock = asyncio.Lock()
        self._listeners: set[Callable[[], None]] = set()

    async def async_load(self) -> None:
        """Restore assumed state from disk."""
        if (data := await self._store.async_load()) is not None:
            self.state = TransomState(**data)

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Subscribe to state changes; returns an unsubscribe callable."""
        self._listeners.add(listener)
        return lambda: self._listeners.discard(listener)

    async def _commit(self) -> None:
        """Persist state and notify entities."""
        await self._store.async_save(asdict(self.state))
        for listener in tuple(self._listeners):
            listener()

    async def _press(self, code: int, times: int = 1) -> None:
        """Send `times` distinct presses of a button."""
        for i in range(times):
            if i:
                await asyncio.sleep(INTER_PRESS_DELAY)
            await async_send_command(
                self._hass, self.emitter_entity_id, TransomCommand(code)
            )

    # The _locked_* methods assume the lock is held and do the actual work;
    # the public methods take the lock and commit once at the end, so compound
    # operations (e.g. set temp -> power on + auto on + arrows) stay atomic.

    async def _locked_set_power(self, on: bool) -> None:
        if self.state.power == on:
            return
        await self._press(CODE_POWER)
        self.state.power = on
        await asyncio.sleep(POST_MODE_DELAY)

    async def _locked_set_auto(self, auto: bool) -> None:
        await self._locked_set_power(True)
        if self.state.auto == auto:
            return
        # One press of the thermometer button enables auto mode; from the
        # remote it takes two presses to disable it (the first only flips the
        # display between room temp and set temp).
        await self._press(CODE_AUTO, times=1 if auto else 2)
        self.state.auto = auto
        await asyncio.sleep(POST_MODE_DELAY)

    async def _locked_step(self, delta: int) -> None:
        if delta:
            await self._press(CODE_UP if delta > 0 else CODE_DOWN, times=abs(delta))

    async def async_set_power(self, on: bool) -> None:
        """Turn the fan on or off."""
        async with self._lock:
            await self._locked_set_power(on)
            await self._commit()

    async def async_set_speed(self, speed: int) -> None:
        """Set fan speed 1-4; exits auto mode (arrows adjust temp in auto)."""
        speed = max(SPEED_MIN, min(SPEED_MAX, speed))
        async with self._lock:
            await self._locked_set_power(True)
            await self._locked_set_auto(False)
            await self._locked_step(speed - self.state.speed)
            self.state.speed = speed
            await self._commit()

    async def async_set_direction(self, direction: str) -> None:
        """Set airflow direction; powers on first (a press while off is lost)."""
        async with self._lock:
            await self._locked_set_power(True)
            if self.state.direction != direction:
                await self._press(CODE_DIRECTION)
                self.state.direction = direction
            await self._commit()

    async def async_set_auto(self, auto: bool) -> None:
        """Enable or disable auto (thermostat) mode."""
        async with self._lock:
            await self._locked_set_auto(auto)
            await self._commit()

    async def async_set_target_temp(self, temp: int) -> None:
        """Set the auto-mode target temperature, enabling auto if needed."""
        temp = max(TEMP_MIN, min(TEMP_MAX, temp))
        async with self._lock:
            await self._locked_set_auto(True)
            await self._locked_step(temp - self.state.target_temp)
            self.state.target_temp = temp
            await self._commit()

    async def async_send_button(self, code: int, presses: int) -> None:
        """Send raw button presses without touching assumed state."""
        async with self._lock:
            await self._press(code, times=presses)

    async def async_calibrate(self) -> None:
        """Re-sync the steppable value in the current mode by clamping.

        With auto off, 3 down presses guarantee speed 1 regardless of drift,
        then we step up to the assumed speed. With auto on, 30 down presses
        guarantee 60F, then we step up to the assumed target. Power, direction,
        and auto itself are blind toggles with no boundary, so they can only be
        corrected via set_assumed_state.
        """
        async with self._lock:
            if not self.state.power:
                raise ServiceValidationError(
                    "Calibration needs the fan powered on (assumed off); "
                    "use set_assumed_state first if that is wrong"
                )
            if self.state.auto:
                await self._press(CODE_DOWN, times=TEMP_MAX - TEMP_MIN)
                await self._locked_step(self.state.target_temp - TEMP_MIN)
            else:
                await self._press(CODE_DOWN, times=SPEED_MAX - SPEED_MIN)
                await self._locked_step(self.state.speed - SPEED_MIN)
            await self._commit()

    async def async_set_assumed_state(
        self,
        power: bool | None = None,
        speed: int | None = None,
        direction: str | None = None,
        auto: bool | None = None,
        target_temp: int | None = None,
    ) -> None:
        """Overwrite assumed state without sending IR (drift correction)."""
        async with self._lock:
            if power is not None:
                self.state.power = power
            if speed is not None:
                self.state.speed = max(SPEED_MIN, min(SPEED_MAX, speed))
            if direction is not None:
                if direction not in (DIRECTION_DIRECT, DIRECTION_EXHAUST):
                    raise ServiceValidationError(f"Unknown direction {direction}")
                self.state.direction = direction
            if auto is not None:
                self.state.auto = auto
            if target_temp is not None:
                self.state.target_temp = max(TEMP_MIN, min(TEMP_MAX, target_temp))
            await self._commit()
