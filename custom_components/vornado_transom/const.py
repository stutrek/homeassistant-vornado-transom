"""Constants for the Vornado Transom integration."""

from typing import Final

DOMAIN: Final = "vornado_transom"

CONF_INFRARED_ENTITY_ID: Final = "infrared_entity_id"
CONF_TEMPERATURE_SENSOR_ENTITY_ID: Final = "temperature_sensor_entity_id"

# 12-bit button codes captured from the OEM remote
# (https://github.com/elementcarbon12/vornado_transom_remote_test)
CODE_POWER: Final = 0xD84
CODE_UP: Final = 0xDC6
CODE_DOWN: Final = 0xD82
CODE_DIRECTION: Final = 0xD81
CODE_AUTO: Final = 0xDC3

BUTTON_CODES: Final = {
    "power": CODE_POWER,
    "up": CODE_UP,
    "down": CODE_DOWN,
    "direction": CODE_DIRECTION,
    "auto": CODE_AUTO,
}

SPEED_MIN: Final = 1
SPEED_MAX: Final = 4
TEMP_MIN: Final = 60
TEMP_MAX: Final = 90

DIRECTION_DIRECT: Final = "direct"
DIRECTION_EXHAUST: Final = "exhaust"

# Settle time between distinct press groups (e.g. after a power/auto press
# before the next button). Repeated presses of the SAME button are not spaced
# by this — they go out as one burst train inside a single transmission (see
# INTER_PRESS_GAP_US in ir.py).
POST_MODE_DELAY: Final = 0.5

# How long to collect changes before emitting one transition. Covers slider
# drags and multi-control edits (e.g. set speed then temp) so they coalesce
# into a single planned press sequence instead of several.
DEBOUNCE_DELAY: Final = 2.0

SERVICE_SET_ASSUMED_STATE: Final = "set_assumed_state"
SERVICE_SEND_BUTTON: Final = "send_button"
SERVICE_CALIBRATE: Final = "calibrate"
