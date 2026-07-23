# Vornado Transom for Home Assistant

Controls a Vornado Transom window fan over IR through Home Assistant's
`infrared` building-block integration (any IR blaster that exposes an
infrared emitter entity, e.g. Broadlink).

Fans with thermostats don't fit cleanly into any one Home Assistant entity
type, so this provides three:

- **Fan** — power, 4 speeds, direction (forward = direct/in, reverse =
  exhaust/out), and an "Auto" preset for thermostat mode
- **Climate** — off / fan-only / auto, target temperature 60–90 °F, fan speeds,
  and airflow direction as the swing control (**In** / **Out**)
- **Number** — auto-mode target temperature

## Installation

This is a custom integration installed through [HACS](https://hacs.xyz/).

[![Open your Home Assistant instance and open this repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=stutrek&repository=homeassistant-vornado-transom&category=Integration)

1. Click the button above to open this repository in HACS (or add
   `https://github.com/stutrek/homeassistant-vornado-transom` manually as a
   custom repository of type **Integration**), then download **Vornado Transom**.
2. Restart Home Assistant.
3. Add the integration and pick the IR blaster with line-of-sight to the fan:

   [![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=vornado_transom)

You need an IR blaster that exposes an infrared *emitter* entity through Home
Assistant's `infrared` integration (e.g. Broadlink) before adding this.

The Transom's IR commands are all stateless toggles and steppers with no
feedback channel, so the integration tracks an *assumed* state (persisted
across restarts) and sends the minimal press sequence to reach the requested
state. If the physical remote or panel is used, correct drift with the
`vornado_transom.set_assumed_state` or `vornado_transom.calibrate` services;
`vornado_transom.send_button` sends raw button presses.

IR protocol reverse-engineered by
[elementcarbon12/vornado_transom_remote_test](https://github.com/elementcarbon12/vornado_transom_remote_test).
The owner's manual behavior notes live in [TRANSOM_IR.md](TRANSOM_IR.md).
