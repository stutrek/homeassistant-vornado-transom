"""IR encoding for the Vornado Transom's PWM protocol.

Pure encoding, no Home Assistant imports. Protocol reverse-engineered in
https://github.com/elementcarbon12/vornado_transom_remote_test and confirmed
against a learned capture of a real Transom remote — its POWER button decodes
to 0xD84 three times, matching the published code, with these exact timings:

- 38 kHz carrier, 12-bit commands sent MSB first
- bit 1 = long mark + short space, bit 0 = short mark + long space
- one button press = the command frame sent three times, ~9 ms apart

Notably the real remote sends NO wake/dummy prefix — just the command frames.
An earlier version prefixed two 0xDDD "wake" frames (from the reference sketch);
on real hardware the fan locked onto the leading dummy and never registered the
command (it woke the display but did nothing), so the dummy is gone.
"""

from typing import override

from infrared_protocols.commands import Command

CARRIER_HZ = 38000

# Timings measured from a learned capture of the physical remote (microseconds).
BIT_ONE_MARK = 1350
BIT_ONE_SPACE = -430
BIT_ZERO_MARK = 460
BIT_ZERO_SPACE = -1320

COMMAND_BITS = 12
FRAME_REPEATS = 3
# Silence between the three frames of a single press, folded into a frame's
# trailing space (matches the ~9 ms gap the real remote leaves between frames).
INTER_FRAME_GAP_US = 9200
# Silence between repeated presses of the same button, sent as ONE burst train
# in a single transmission. The real remote leaves ~85-110 ms between presses
# (a 3-quick-taps capture measured 84/107/109 ms); a separate transmission per
# press dropped presses, so we emit them all in one blob like the remote does.
INTER_PRESS_GAP_US = 100000


def _frame(code: int) -> list[int]:
    """Encode a 12-bit code as alternating +mark/-space timings."""
    timings: list[int] = []
    for bit_index in range(COMMAND_BITS - 1, -1, -1):
        if code >> bit_index & 1:
            timings += [BIT_ONE_MARK, BIT_ONE_SPACE]
        else:
            timings += [BIT_ZERO_MARK, BIT_ZERO_SPACE]
    return timings


def _append_frame(timings: list[int], code: int, gap_after_us: int | None) -> None:
    """Append a frame, folding any following silence into its trailing space.

    The timing list must strictly alternate mark/space, so inter-frame gaps
    extend the frame's final space rather than adding a second space element.
    """
    frame = _frame(code)
    if gap_after_us is not None:
        frame[-1] -= gap_after_us
    timings += frame


class TransomCommand(Command):
    """One or more presses of a Vornado Transom button, as one transmission.

    ``presses`` repeats the button like tapping it that many times: each press
    is the command frame sent three times ~9 ms apart, and presses are ~100 ms
    apart, all in a single burst train (see the module docstring).
    """

    def __init__(self, code: int, presses: int = 1) -> None:
        """Initialize with a 12-bit button code and a press count."""
        super().__init__(modulation=CARRIER_HZ)
        self.code = code
        self.presses = presses

    @override
    def get_raw_timings(self) -> list[int]:
        """Return the raw timings for ``presses`` presses of the button."""
        timings: list[int] = []
        for press in range(self.presses):
            last_press = press == self.presses - 1
            for repeat in range(FRAME_REPEATS):
                last_frame = repeat == FRAME_REPEATS - 1
                if last_frame:
                    gap = None if last_press else INTER_PRESS_GAP_US
                else:
                    gap = INTER_FRAME_GAP_US
                _append_frame(timings, self.code, gap)
        return timings
