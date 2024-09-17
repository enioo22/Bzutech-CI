"""Binary sensor for BzuTech Integration."""

from datetime import timedelta
import logging

from bzutech import BzuTech
import yaml.dumper

from homeassistant.components import mqtt
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)

from homeassistant.const import SERVICE_RELOAD
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util
from homeassistant.util.json import json_loads_object, JsonObjectType

from .const import CONF_CHIPID, CONF_ENTITY, CONF_SENSORNAME, DOMAIN

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
    numero = 0
    for char in name:
        numero = numero + ord(char)

    return numero


def get_sensortype(hass: HomeAssistant, entity: str):
    """Get the type of sensor that is being registered."""
    if hass.states.get(entity) is not State:
        return sensortypes[
            hass.states.get(entity).as_dict()["attributes"]["device_class"]
        ]
    return ""


def get_triggers(event: JsonObjectType):
    t = "  trigger:\n"
    if "trigger" in event:
        for e in event["trigger"]:
            t = (
                t
                + f"  - platform: {e["platform"]}\n    entity_id:\n    - {e["entity_id"]}\n"
            )
            if "above" in e:
                t = t + f"    above: {e["above"]}\n"
            if "below" in e:
                t = t + f"    below: {e["below"]}\n"
    return t


def get_conditions(event: JsonObjectType):
    c = "  condition:\n"
    if "condition" not in event:
        return "  - condition: []"
    if len(event["condition"]) == 0:
        return "  - condition: []"

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
            a = a + f"  - action: {e["service"]}\n"
            a = a + "    data:\n"
            a = a + f"      message: {e["data"]["message"]}\n"
            a = a + f"      title: {e["data"]["title"]}\n"

    return a


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Setup binary sensor entity."""
    api: BzuTech = hass.data[DOMAIN][entry.entry_id]
    sensors = []

    if not await mqtt.async_wait_for_mqtt_client(hass):
        logging.error("MQTT integration is not available")
        return

    @callback
    async def async_create_automation(msg: mqtt.ReceiveMessage) -> None:
        automation = "\n"
        event = json_loads_object(msg.payload)

        necessary_keys = [
            "id",
            "alias",
            "description",
            "trigger",
            "action",
            "mode",
        ]

        if all(k in event for k in necessary_keys):
            automation = automation + f"- id: '{event["id"]}'\n"
            automation = automation + f"  alias: {event["alias"]}\n"
            automation = automation + f"  description: '{event["description"]}'\n"
            automation = automation + get_triggers(event)
            automation = automation + get_conditions(event)
            automation = automation + get_actions(event)
            automation = automation + f"  mode: {event["mode"]}"
            # print(automation)

        f = open(r"config/automations.yaml", mode="r+", encoding="utf-8")
        size = len(f.read())
        f.close()
        print(automation)
        f = open(r"config/automations.yaml", "a+", encoding="utf-8")
        if size < 5:
            f.truncate(0)
        f.write(automation)
        f.close()
        await hass.services.async_call("automation", "reload")

    await mqtt.async_subscribe(hass, "teste/ha/criaralerta", async_create_automation, 1)

    sensors.append(BzuBinarySensorEntity(api, entry))
    async_add_entities(sensors, update_before_add=True)


class BzuBinarySensorEntity(BinarySensorEntity):
    """Bzutech binary sensor entity."""

    def __init__(self, api, entry: ConfigEntry) -> None:
        self.api = api
        self.sendall = entry.data["todos"]
        if self.sendall == 0:
            self.entidades = [entry.data[CONF_ENTITY]]

        self.chipid = entry.data[CONF_CHIPID]
        self.entityID = entry.data[CONF_ENTITY].replace(" ", "_")
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

    async def async_update(self) -> None:
        """Upload Readings to cloud."""

        date = str(dt_util.as_local(dt_util.now()))[:19]
        counter = 1
        if self.sendall == 1 or self.entidades == ["Add all"]:
            self.entidades = [
                x
                for x in self.hass.states.async_entity_ids(["sensor"])
                if self.hass.states.get(x).as_dict()["attributes"]["device_class"]
                != "timestamp"
                and self.hass.states.get(x).name
            ]

        readings = {}
        readings["Records"] = []
        readings["Records"].append({})
        readings["Records"][0]["bci"] = self.chipid
        readings["Records"][0]["date"] = date
        data = []
        if await mqtt.async_wait_for_mqtt_client(self.hass):
            for entity in self.entidades:
                try:
                    reading = float(self.hass.states.get(entity).as_dict()["state"])
                except (AttributeError, ValueError):
                    return
                sensor = f"HA-{get_sensortype(self.hass, entity)}-{stringtoint(entity)}"
                counter = counter + 1
                data.append({"ref": sensor, "med": reading})
                # mqtt.publish(self.hass, "teste", str(readings))
            readings["Records"][0]["data"] = str(data).replace("'", r'*"')
            # print(readings)

            logging.warning(data)
            mqtt.publish(self.hass, "data_send", str(readings))

        self._attr_is_on = True
