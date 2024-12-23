"""Config flow for BZUTech integration."""

from __future__ import annotations

import logging
import re
from typing import Any

from bzutech import BzuTech
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_CHIPID,
    CONF_ENDPOINT,
    CONF_ENTITY,
    CONF_SENDALL,
    CONF_SENSORNAME,
    CONF_SENSORPORT,
    CONF_TYPE,
    DOMAIN,
)

sensortypes = {
    "temperature": "TMP",
    "humidity": "HUM",
    "battery": "BAT",
    "voltage": "VOT",
    "carbon_monoxide": "CO1",
    "carbon_dioxide": "CO2",
    "current": "CUR",
    "illuminance": "LUX",
    "pm1": "P01",
    "pm10": "P10",
    "pm25": "P25",
    "signal_strength": "DBM",
    "aqi": "DOR",
    "switch": "SWT",
    "light": "LIT",
    "remote": "RMT",
}


_LOGGER = logging.getLogger(__name__)

STEP_USER_LOGIN_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    },
    True,
)


async def get_api(hass: HomeAssistant, data: dict[str, Any]) -> BzuTech:
    """Validate the user input allows us to connect."""
    return BzuTech(data[CONF_EMAIL], data[CONF_PASSWORD])


def get_ports(api: BzuTech, chipid: str) -> list[str]:
    """Get ports with the endpoints connected to each port."""
    return [f"Port {i} {api.get_endpoint_on(chipid, i)}" for i in range(1, 5)]


def get_all_entities(hass: HomeAssistant) -> dict[str, str]:
    entitylist = get_entities(hass)[1:]
    for x in hass.states.async_entity_ids(["switch", "light", "remote"]):
        entitylist.append(x)
    return entitylist


def get_entities(hass: HomeAssistant) -> dict[str, str]:
    """Get every entity name to send them to bzucloud."""
    entityList = []
    for x in hass.states.async_entity_ids(["sensor"]):
        try:
            attr = hass.states.get(x).as_dict()["attributes"]
            if "device_class" in attr:
                if attr["device_class"] != "timestamp":
                    entityList.append(x)
        except:
            continue

    entityList.insert(0, "Add all")
    return entityList


def get_sensortype(hass: HomeAssistant, entity: str):
    """Get the sensor type to be send."""
    if entity.split(".")[0] == "sensor":
        try:
            return sensortypes[
                hass.states.get(entity).as_dict()["attributes"]["device_class"]
            ]
        except:
            return "GEN"
    return sensortypes[entity.split(".")[0]]


def get_sensornumber(hass: HomeAssistant):
    """Get the number of the sensor to be send."""
    return str(hass.states.async_entity_ids_count("binary_sensor") + 1)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BZUTech."""

    VERSION = 1
    api: BzuTech
    email = ""
    password = ""
    actual = 0
    selecteddevice = 0
    selectedtype = 0
    selectedentity = ""
    selectedport = 0

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self.api = await get_api(self.hass, user_input)
                if not await self.api.start():
                    raise InvalidAuth("Invalid Auth")
            except InvalidAuth:
                _LOGGER.exception("Invalid Auth")
                errors["base"] = "Invalid Auth"
                return self.async_abort(reason=errors["base"])

            self.email = user_input[CONF_EMAIL]
            self.password = user_input[CONF_PASSWORD]
            if not self.hass.states.get("binary_sensor.bzu_cloud"):
                return await self.async_step_typeselect(user_input=user_input)
            return await self.async_step_deviceselect(user_input)
        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_LOGIN_SCHEMA,
            errors=errors,
            last_step=False,
        )

    async def async_step_addentities(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select entities to be send."""
        if CONF_ENTITY in user_input or CONF_SENDALL in user_input:
            user_input = {
                CONF_PASSWORD: self.password,
                CONF_TYPE: self.selectedtype,
                CONF_EMAIL: self.email,
                CONF_SENDALL: user_input[CONF_SENDALL],
                CONF_ENTITY: user_input[CONF_ENTITY],
                CONF_CHIPID: f"HA-{re.sub("[a-zA-z]", "", self.hass.data["core.uuid"][-7:])}",
                CONF_SENSORNAME: "Bzu Cloud",
            }
            return self.async_create_entry(
                title=user_input[CONF_CHIPID],
                data=user_input,
            )

        return self.async_show_form(
            step_id="addentities",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SENDALL, default=False, msg="Send every entity"
                    ): bool,
                    vol.Required(
                        CONF_ENTITY,
                    ): EntitySelector(
                        EntitySelectorConfig(
                            domain=["sensor", "light", "switch"],
                            multiple=True,
                        )
                    ),
                }
            ),
        )

    async def async_step_typeselect(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        "Select if data will be gotten or sent."
        if CONF_TYPE in user_input:
            self.selectedtype = user_input[CONF_TYPE]
            if self.selectedtype == "0":
                return await self.async_step_deviceselect(user_input=user_input)
            if await mqtt.async_wait_for_mqtt_client(self.hass):
                return await self.async_step_addentities(user_input=user_input)

            return self.async_abort(
                reason="""MQTT not configured, follow the steps in:
                https://www.home-assistant.io/integrations/mqtt
                to connect to Bzu broker."""
            )

        return self.async_show_form(
            step_id="typeselect",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_TYPE): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value="1", label="Send data to Bzu"),
                                SelectOptionDict(
                                    value="0",
                                    label="Receive data from Bzu",
                                ),
                            ],
                            mode=SelectSelectorMode.LIST,
                        )
                    ),
                }
            ),
        )

    async def async_step_deviceselect(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set up the selection of the device from a list ."""
        if self.selecteddevice != 0 and user_input is not None:
            self.selecteddevice = user_input[CONF_CHIPID]
            return await self.async_step_portselect(user_input=user_input)
        self.selecteddevice = 1
        return self.async_show_form(
            step_id="deviceselect",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CHIPID): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=key, label=key)
                                for key in self.api.get_device_names()
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )

    async def async_step_portselect(self, user_input) -> ConfigFlowResult:
        """Set up the device port selection."""
        if self.selectedport != 0:
            user_input = {
                CONF_ENDPOINT: user_input[CONF_SENSORPORT].split(" ")[2],
                CONF_SENSORPORT: user_input[CONF_SENSORPORT][5],
                CONF_PASSWORD: self.password,
                CONF_TYPE: self.selectedtype,
                CONF_EMAIL: self.email,
                CONF_CHIPID: self.selecteddevice,
            }
            return self.async_create_entry(
                title=f"BZUGW-{self.selecteddevice}-{user_input[CONF_SENSORPORT]}",
                data=user_input,
            )

        self.selectedport = 1
        return self.async_show_form(
            step_id="portselect",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SENSORPORT): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=k, label=k)
                                for k in get_ports(self.api, user_input[CONF_CHIPID])
                            ],
                            mode=SelectSelectorMode.LIST,
                        )
                    ),
                }
            ),
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidSensor(HomeAssistantError):
    """Error to indicate there is invalid Sensor."""
