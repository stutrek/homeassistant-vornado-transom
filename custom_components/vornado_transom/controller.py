"""Assumed-state tracking and debounced IR orchestration for the Transom.

The fan has no feedback channel, so we track two states:

- ``state`` — what we assume the device is actually set to.
- ``desired`` — what the user has asked for (shown in the UI immediately).

Entities call :meth:`request` to change ``desired``; after a short debounce the
controller plans the button presses from ``state`` to ``desired`` (see
:mod:`.planner`), emits them, and sets ``state = desired``. Debouncing lets a
slider drag or several quick edits collapse into one clean transition.
"""

import asyncio
from collections.abc import Callable
from dataclasses import asdict, replace
import logging

from homeassistant.components.infrared import async_send_command
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.storage import Store

from .const import (
    CODE_AUTO,
    CODE_DOWN,
    CODE_UP,
    DEBOUNCE_DELAY,
    DIRECTION_DIRECT,
    DIRECTION_EXHAUST,
    DOMAIN,
    POST_MODE_DELAY,
    SPEED_MAX,
    SPEED_MIN,
    TEMP_MAX,
    TEMP_MIN,
)
from .ir import TransomCommand
from .planner import TransomState, plan_presses

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1


def _clamp(lo: int, hi: int, value: int) -> int:
    return max(lo, min(hi, value))


class TransomController:
    """Single source of truth shared by the fan, climate, and number entities."""

    def __init__(
        self, hass: HomeAssistant, entry_id: str, emitter_entity_id: str
    ) -> None:
        """Initialize the controller."""
        self._hass = hass
        self.emitter_entity_id = emitter_entity_id
        self.state = TransomState()  # assumed actual device state
        self.desired = TransomState()  # what the user wants (shown in the UI)
        self._store: Store[dict] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry_id}"
        )
        self._lock = asyncio.Lock()
        self._listeners: set[Callable[[], None]] = set()
        self._cancel_flush: CALLBACK_TYPE | None = None

    async def async_load(self) -> None:
        """Restore assumed state from disk; desired starts equal to it."""
        if (data := await self._store.async_load()) is not None:
            self.state = TransomState(**data)
        self.desired = replace(self.state)

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Subscribe to state changes; returns an unsubscribe callable."""
        self._listeners.add(listener)
        return lambda: self._listeners.discard(listener)

    @callback
    def async_shutdown(self) -> None:
        """Cancel any pending debounced flush (called on unload)."""
        if self._cancel_flush is not None:
            self._cancel_flush()
            self._cancel_flush = None

    @callback
    def _notify(self) -> None:
        for listener in tuple(self._listeners):
            listener()

    # --- Requests: update desired state, show it, and arm the debounce ---

    @callback
    def request(
        self,
        *,
        power: bool | None = None,
        speed: int | None = None,
        direction: str | None = None,
        auto: bool | None = None,
        target_temp: int | None = None,
    ) -> None:
        """Set one or more desired facets and (re)arm the debounced flush."""
        if speed is not None:
            speed = _clamp(SPEED_MIN, SPEED_MAX, speed)
        if target_temp is not None:
            target_temp = _clamp(TEMP_MIN, TEMP_MAX, target_temp)
        if direction is not None and direction not in (
            DIRECTION_DIRECT,
            DIRECTION_EXHAUST,
        ):
            raise ServiceValidationError(f"Unknown direction {direction}")

        changes = {
            k: v
            for k, v in {
                "power": power,
                "speed": speed,
                "direction": direction,
                "auto": auto,
                "target_temp": target_temp,
            }.items()
            if v is not None
        }
        self.desired = replace(self.desired, **changes)
        self._notify()
        self._arm_flush()

    @callback
    def _arm_flush(self) -> None:
        if self._cancel_flush is not None:
            self._cancel_flush()
        self._cancel_flush = async_call_later(
            self._hass, DEBOUNCE_DELAY, self._flush
        )

    async def _flush(self, _now=None) -> None:
        """Plan and emit the presses to reach the desired state."""
        self._cancel_flush = None
        async with self._lock:
            await self._execute(plan_presses(self.state, self.desired))
            if self.desired.power:
                self.state = replace(self.desired)
            else:
                # The fan ignores commands while off and remembers its other
                # settings, so only power changed. Drop any pending speed/temp
                # edits back to the remembered state.
                self.state = replace(self.state, power=False)
                self.desired = replace(self.state)
            await self._commit()

    # --- IR emission ---

    async def _execute(self, presses: list[tuple[int, int]]) -> None:
        """Send each planned press group, settling between groups."""
        for i, (code, count) in enumerate(presses):
            if i:
                await asyncio.sleep(POST_MODE_DELAY)
            await self._press(code, times=count)

    async def _press(self, code: int, times: int = 1) -> None:
        """Send `times` presses of a button as one burst-train transmission."""
        await async_send_command(
            self._hass, self.emitter_entity_id, TransomCommand(code, presses=times)
        )

    async def _commit(self) -> None:
        """Persist assumed state and notify entities."""
        await self._store.async_save(asdict(self.state))
        self._notify()

    # --- Services ---

    async def async_send_button(self, code: int, presses: int) -> None:
        """Send raw button presses without touching tracked state."""
        async with self._lock:
            await self._press(code, times=presses)

    async def async_set_assumed_state(
        self,
        power: bool | None = None,
        speed: int | None = None,
        direction: str | None = None,
        auto: bool | None = None,
        target_temp: int | None = None,
    ) -> None:
        """Overwrite assumed state without sending IR (drift correction)."""
        if direction is not None and direction not in (
            DIRECTION_DIRECT,
            DIRECTION_EXHAUST,
        ):
            raise ServiceValidationError(f"Unknown direction {direction}")
        async with self._lock:
            self.async_shutdown()  # abandon any pending transition
            if power is not None:
                self.state.power = power
            if speed is not None:
                self.state.speed = _clamp(SPEED_MIN, SPEED_MAX, speed)
            if direction is not None:
                self.state.direction = direction
            if auto is not None:
                self.state.auto = auto
            if target_temp is not None:
                self.state.target_temp = _clamp(TEMP_MIN, TEMP_MAX, target_temp)
            self.desired = replace(self.state)
            await self._commit()

    async def async_calibrate(self) -> None:
        """Re-sync the steppable value in the current mode by clamping.

        Drives the value to a known boundary (arrow held to the end of its
        range) so the assumed state is certain again, then steps to the desired
        value. Temp is calibrated when in auto, speed otherwise; power,
        direction, and auto are blind toggles with no boundary.
        """
        if not self.state.power:
            raise ServiceValidationError(
                "Calibration needs the fan powered on (assumed off); "
                "use set_assumed_state first if that is wrong"
            )
        async with self._lock:
            self.async_shutdown()
            if self.state.auto:
                await self._press(CODE_AUTO, times=2)  # leave + re-enter -> window
                await asyncio.sleep(POST_MODE_DELAY)
                await self._press(CODE_DOWN, times=TEMP_MAX - TEMP_MIN)  # -> 60
                self.state.target_temp = TEMP_MIN
                if self.desired.target_temp > TEMP_MIN:
                    await self._press(
                        CODE_UP, times=self.desired.target_temp - TEMP_MIN
                    )
                self.state.target_temp = self.desired.target_temp
            else:
                await self._press(CODE_DOWN, times=SPEED_MAX - SPEED_MIN)  # -> 1
                self.state.speed = SPEED_MIN
                if self.desired.speed > SPEED_MIN:
                    await self._press(CODE_UP, times=self.desired.speed - SPEED_MIN)
                self.state.speed = self.desired.speed
            self.desired = replace(self.state)
            await self._commit()
