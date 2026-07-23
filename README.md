# Vornado Transom for Home Assistant

Controls a Vornado Transom window fan over IR through Home Assistant's
`infrared` building-block integration (any IR blaster that exposes an
infrared emitter entity, e.g. Broadlink).

Provides one device with:

- **Fan** — power, 4 speeds, direction (forward = direct/in, reverse =
  exhaust/out), and an "Auto" preset for thermostat mode
- **Climate** — off / fan-only / auto, target temperature 60–90 °F, fan speeds
- **Number** — auto-mode target temperature

The Transom's IR commands are all stateless toggles and steppers with no
feedback channel, so the integration tracks an *assumed* state (persisted
across restarts) and sends the minimal press sequence to reach the requested
state. If the physical remote or panel is used, correct drift with the
`vornado_transom.set_assumed_state` or `vornado_transom.calibrate` services;
`vornado_transom.send_button` sends raw button presses.

IR protocol reverse-engineered by
[elementcarbon12/vornado_transom_remote_test](https://github.com/elementcarbon12/vornado_transom_remote_test).
The owner's manual behavior notes live in [TRANSOM_IR.md](TRANSOM_IR.md).
