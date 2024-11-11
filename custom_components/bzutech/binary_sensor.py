"""Binary sensor for BzuTech Integration."""

from datetime import timedelta
import json
import logging
from typing import Any

from bzutech import BzuTech

from homeassistant.components import mqtt
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.components.logbook import log_entry
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util
from homeassistant.util.json import JsonObjectType

from .config_flow import get_all_entities, get_sensortype
from .const import CONF_CHIPID, CONF_ENTITY, CONF_SENDALL, CONF_SENSORNAME, DOMAIN

SCAN_INTERVAL = timedelta(seconds=30)

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
}


def stringtoint(name: str):
    """Convert a string into a unique int value."""
    numero = 0
    for char in name:
        numero = numero + ord(char)

    return numero


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Do setup binary sensor entity."""
    api: BzuTech = hass.data[DOMAIN][entry.entry_id]
    sensors = []

    sensors.append(BzuBinarySensorEntity(api, entry))
    async_add_entities(sensors, update_before_add=True)


def get_conditions(event: JsonObjectType):
    c = "  condition:\n"
    if "condition" not in event:
        return "  - condition: []\n"
    if len(event["condition"]) == 0:
        return "  - condition: []\n"

    for e in event["condition"]:
        c = c + f"  - condition: {e["condition"]}\n"
        c = c + f"    entity_id: {e["entity_id"]}\n"
        if "above" in e:
            c = c + f"    above: {e["above"]}\n"
        if "below" in e:
            c = c + f"    below: {e["below"]}\n"

    return c


def get_actions(event: JsonObjectType):
    a = "  action:\n"
    if "action" in event:
        for e in event["action"]:
            a = a + "  - action: mqtt.publish\n"
            a = a + r"    metadata: {}"
            a = a + "    data:\n"
            a = a + "      qos: 1\n"
            a = a + "      topic: haalertreturn/"
            a = a + f"      title: {e["data"]["title"]}\n"

    return a


class BzuBinarySensorEntity(BinarySensorEntity):
    """Bzutech binary sensor entity."""

    sent_updatechannels = False
    number_entities = 0
    entity_id_bzu = {}

    def __init__(self, api, entry: ConfigEntry) -> None:
        """Set up binary sensor."""
        self.api = api
        self.sendall = entry.data[CONF_SENDALL]
        self.entidades = entry.data[CONF_ENTITY]

        self.chipid = entry.data[CONF_CHIPID]
        self.entityID = "bzu_cloud"
        self.sensor = entry.data[CONF_SENSORNAME]
        self._attr_name = entry.data[CONF_SENSORNAME]
        self._attr_device_class = BinarySensorDeviceClass.RUNNING
        self._attr_unique_id = entry.data[CONF_SENSORNAME]
        self._attr_assumed_state = False

    @property
    def device_info(self) -> DeviceInfo | None:
        """Config device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.chipid)},
            suggested_area="Room",
            name=self.chipid,
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="Bzu Tech",
            hw_version="1.0",
            model="Push data",
            serial_number=self.chipid,
            sw_version="1.0",
        )

    def get_triggers(self, event: JsonObjectType):
        t = "  trigger:\n"
        event["entity_id"] = self.entity_id_bzu[event["canal_id"]]
        t = (
            t
            + f"  - platform: numeric_state\n    entity_id:\n    - {event["entity_id"]}\n"
        )
        if event["alerta_operador"] == ">":
            t = t + f"    above: {event["alerta_valor"]}\n"
        if event["alerta_operador"] == "<":
            t = t + f"    below: {event["alerta_valor"]}\n"
        if event["alerta_operador"] == "=":
            t = t + f"    above: {event["alerta_valor"]}\n"
            t = t + f"    below: {int(event["alerta_valor"])+1}\n"

        return t

    async def async_update(
        self,
    ) -> None:
        """Upload Readings to cloud."""

        date = str(dt_util.as_local(dt_util.now()))[:19]
        if self.sendall == 1:
            self.entidades = get_all_entities(self.hass)

        readings: dict[str, Any] = {}
        readings["Records"] = []
        readings["Records"].append({})
        readings["Records"][0]["bci"] = self.chipid
        readings["Records"][0]["date"] = date
        data = []
        channels: dict[str, Any] = {}
        channels["Records"] = []
        channels["Records"].append({})
        channels["Records"][0]["bci"] = self.chipid
        chs = []

        @callback
        async def async_call_service_mqtt(msg: mqtt.ReceiveMessage) -> None:
            call = json.loads(msg.payload)

            entity = call["entity"]
            funcao = call["method"]
            entitytype = entity.split(".")[0]
            retorno = {}
            retorno["info"] = "funcao invalida"
            if funcao in self.hass.services.async_services_for_domain(entitytype):
                await self.hass.services.async_call(
                    entitytype, funcao, {ATTR_ENTITY_ID: [entity]}, True
                )
                retorno["info"] = "sucesso"
            mqtt.publish(self.hass, "hacallreturn", str(retorno))

        @callback
        async def async_create_automation(msg: mqtt.ReceiveMessage) -> None:
            automation = "\n"
            event = json.loads(msg.payload)

            necessary_keys = [
                "alerta_id",
                "alerta_valor",
                "alerta_operador",
                "canal_id",
            ]

            if all(k in event for k in necessary_keys):
                automation = automation + f"- id: '{event["alerta_id"]}'\n"
                automation = automation + "  alias: 'Alarme Bzu Cloud'\n"
                automation = (
                    automation
                    + f"  description: 'Alarme Bzu Cloud #{event["alerta_id"]}'\n"
                )
                automation = automation + "  mode: single\n"
                automation = automation + self.get_triggers(event)
                # automation = automation + get_conditions(event)
                automation = automation + "  action:\n"
                automation = automation + "  - action: mqtt.publish\n"
                automation = automation + "    metadata: {}\n"
                automation = automation + "    data:\n"
                automation = automation + "      qos: 1\n"
                automation = (
                    automation
                    + f"      topic: ha_alert_action/{self.chipid.split("-")[1]}\n"
                )

                payload = (
                    '\'{"Records": [{"alerta_id":'
                    + str(event["alerta_id"])
                    + ', "value": {{states("'
                    + self.entity_id_bzu[event["canal_id"]]
                    + "\")}} }]}'"
                )
                automation = automation + f"      payload: {payload}"

                with open(r"config/automations.yaml", mode="r+", encoding="utf-8") as f:
                    size = len(f.read())
                    f.close()
                # print(automation)
                with open(r"config/automations.yaml", "a+", encoding="utf-8") as f:
                    if size < 5:
                        f.truncate(0)
                    f.write(automation)
                    f.close()
                await self.hass.services.async_call("automation", "reload")

        if await mqtt.async_wait_for_mqtt_client(self.hass):
            await mqtt.async_subscribe(
                self.hass,
                f"hacall/{self.chipid.split("-")[1]}",
                async_call_service_mqtt,
            )
            await mqtt.async_subscribe(
                self.hass,
                f"alerta_ha/{self.chipid.split("-")[1]}",
                async_create_automation,
                2,
            )
            for entity in self.entidades:
                try:
                    stt = self.hass.states.get(entity)
                    if stt is not None:
                        reading = stt.as_dict()["state"]
                except (AttributeError, ValueError):
                    logging.error("Sensor name error")
                    return
                sensor = f"HA-{get_sensortype(self.hass, entity)}-{stringtoint(entity)}"
                self.entity_id_bzu[sensor] = entity
                chs.append(sensor)
                data.append({"ref": sensor, "med": reading})
            channels["Records"][0]["channels"] = str(chs).replace("'", r'*"')
            readings["Records"][0]["data"] = str(data).replace("'", r'*"')
            if len(self.entidades) != self.number_entities:
                self.number_entities = len(self.entidades)
                for key in self.entity_id_bzu:  # pylint: disable=consider-using-dict-items
                    log_entry(
                        self.hass,
                        "Sensor Name Bzu Cloud",
                        f"{self.entity_id_bzu[key]} -> {key}",
                        DOMAIN,
                        "binary_sensor.bzu_cloud",
                    )
                mqtt.publish(self.hass, "UpdateChannels", str(channels))
            logging.warning(self.entity_id_bzu)
            mqtt.publish(self.hass, "data_send", str(readings))
        self._attr_is_on = True
