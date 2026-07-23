"""Pure state-transition planning for the Vornado Transom.

No Home Assistant imports, so it can be unit-tested on its own. Given the
assumed current state and a desired state, ``plan_presses`` returns the ordered
button presses that move the fan from one to the other.

The ordering encodes what we learned from the real remote and the fan's
behaviour:

- **Power first.** The fan ignores commands while off; turning it off ends the
  transition (its other settings are remembered for next power-on).
- **Speed any time.** The arrows control fan speed whenever the temperature
  window is closed, and changing speed never affects auto mode. So speed is
  stepped before auto is touched, while the window is still closed.
- **Temperature last.** The target temp is only adjustable for a few seconds
  after auto is (re)entered, which opens the "temp window". Entering auto opens
  it; if already in auto the window has closed, so we leave and re-enter. Any
  arrow press after that window opens would change temp, which is exactly why
  speed must come first.
"""

from dataclasses import dataclass

from .const import (
    CODE_AUTO,
    CODE_DIRECTION,
    CODE_DOWN,
    CODE_POWER,
    CODE_UP,
    DIRECTION_DIRECT,
)


@dataclass
class TransomState:
    """A full fan state; used for both the assumed-current and desired states."""

    power: bool = False
    speed: int = 1
    direction: str = DIRECTION_DIRECT
    auto: bool = False
    target_temp: int = 70


def _step(code_up: int, code_down: int, delta: int) -> tuple[int, int] | None:
    if delta == 0:
        return None
    return (code_up if delta > 0 else code_down, abs(delta))


def plan_presses(
    current: TransomState, desired: TransomState
) -> list[tuple[int, int]]:
    """Return an ordered list of ``(button_code, press_count)`` steps.

    Each tuple is one button pressed ``count`` times. ``desired`` is assumed
    already clamped to valid ranges.
    """
    presses: list[tuple[int, int]] = []

    if desired.power != current.power:
        presses.append((CODE_POWER, 1))
    if not desired.power:
        # Off: nothing else applies, and the fan remembers its other settings.
        return presses

    if desired.direction != current.direction:
        presses.append((CODE_DIRECTION, 1))

    if step := _step(CODE_UP, CODE_DOWN, desired.speed - current.speed):
        presses.append(step)

    if desired.auto:
        if desired.target_temp != current.target_temp:
            # (Re)open the temp window: entering auto opens it; if we are
            # already in auto it has since closed, so leave first (2 presses).
            presses.append((CODE_AUTO, 2 if current.auto else 1))
            step = _step(
                CODE_UP, CODE_DOWN, desired.target_temp - current.target_temp
            )
            if step:
                presses.append(step)
        elif not current.auto:
            presses.append((CODE_AUTO, 1))
    elif current.auto:
        presses.append((CODE_AUTO, 1))

    return presses
