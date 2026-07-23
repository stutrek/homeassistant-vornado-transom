"""Config flow for the Vornado Transom integration."""

from typing import Any, override

import voluptuous as vol

from homeassistant.components.infrared import (
    DOMAIN as INFRARED_DOMAIN,
    async_get_emitters,
)
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.selector import EntitySelector, EntitySelectorConfig

from .const import (
    CONF_INFRARED_ENTITY_ID,
    CONF_TEMPERATURE_SENSOR_ENTITY_ID,
    DOMAIN,
)

DEFAULT_NAME = "Vornado Transom"


def _schema(emitter_entity_ids: list[str], defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_INFRARED_ENTITY_ID,
                default=defaults.get(CONF_INFRARED_ENTITY_ID, vol.UNDEFINED),
            ): EntitySelector(
                EntitySelectorConfig(
                    domain=INFRARED_DOMAIN, include_entities=emitter_entity_ids
                )
            ),
            vol.Optional(
                CONF_TEMPERATURE_SENSOR_ENTITY_ID,
                default=defaults.get(CONF_TEMPERATURE_SENSOR_ENTITY_ID, vol.UNDEFINED),
            ): EntitySelector(
                EntitySelectorConfig(
                    domain="sensor", device_class=SensorDeviceClass.TEMPERATURE
                )
            ),
        }
    )


class TransomConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup of a Transom."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select the IR emitter and optional temperature sensor."""
        emitter_entity_ids = async_get_emitters(self.hass)
        if not emitter_entity_ids:
            return self.async_abort(reason="no_emitters")

        if user_input is not None:
            return self.async_create_entry(
                title=user_input.pop(CONF_NAME, DEFAULT_NAME) or DEFAULT_NAME,
                data=user_input,
            )

        schema = _schema(emitter_entity_ids, {}).extend(
            {vol.Optional(CONF_NAME, default=DEFAULT_NAME): str}
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    @staticmethod
    @callback
    @override
    def async_get_options_flow(config_entry) -> OptionsFlow:
        """Create the options flow."""
        return TransomOptionsFlow()


class TransomOptionsFlow(OptionsFlowWithReload):
    """Allow changing the emitter or temperature sensor."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current = {**self.config_entry.data, **self.config_entry.options}
        emitter_entity_ids = async_get_emitters(self.hass)
        return self.async_show_form(
            step_id="init", data_schema=_schema(emitter_entity_ids, current)
        )
