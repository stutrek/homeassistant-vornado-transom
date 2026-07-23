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
# Silence between the three repeated command frames, folded into a frame's
# trailing space (matches the ~9 ms gap the real remote leaves between frames).
INTER_FRAME_GAP_US = 9200


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
    """A single button press for the Vornado Transom."""

    def __init__(self, code: int) -> None:
        """Initialize with a 12-bit button code."""
        super().__init__(modulation=CARRIER_HZ)
        self.code = code

    @override
    def get_raw_timings(self) -> list[int]:
        """Return the raw timings for one press: the command frame x3."""
        timings: list[int] = []
        for repeat in range(FRAME_REPEATS):
            last = repeat == FRAME_REPEATS - 1
            _append_frame(timings, self.code, None if last else INTER_FRAME_GAP_US)
        return timings
