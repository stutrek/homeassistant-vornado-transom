"""IR encoding for the Vornado Transom's PWM protocol.

Pure encoding, no Home Assistant imports. Protocol reverse-engineered in
https://github.com/elementcarbon12/vornado_transom_remote_test:

- 38 kHz carrier, 12-bit commands sent MSB first
- bit 1 = 1260 us mark + 400 us space, bit 0 = 420 us mark + 1260 us space
- a "press" is a dummy wake frame twice (the panel sleeps; an invalid but
  well-formed frame wakes it and is otherwise a no-op), a release gap, then
  the command frame three times
- frames within a press are separated by ~7 ms of silence; a gap longer than
  ~8 ms reads as the button being released
"""

from typing import override

from infrared_protocols.commands import Command

CARRIER_HZ = 38000

BIT_ONE_MARK = 1260
BIT_ONE_SPACE = -400
BIT_ZERO_MARK = 420
BIT_ZERO_SPACE = -1260

COMMAND_BITS = 12
FRAME_REPEATS = 3
# Silence appended to a frame's trailing space, mirroring the reference
# implementation's delay() calls between sendRaw() bursts.
REPEAT_GAP_US = 7000
RELEASE_GAP_US = 9000

DUMMY_CODE = 0xDDD


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
        """Return the raw timings for one press: wake, release, command x3."""
        timings: list[int] = []
        _append_frame(timings, DUMMY_CODE, REPEAT_GAP_US)
        _append_frame(timings, DUMMY_CODE, RELEASE_GAP_US)
        for repeat in range(FRAME_REPEATS):
            last = repeat == FRAME_REPEATS - 1
            _append_frame(timings, self.code, None if last else REPEAT_GAP_US)
        return timings
