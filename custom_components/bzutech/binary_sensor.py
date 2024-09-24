"""Binary sensor for BzuTech Integration."""

from datetime import timedelta
import logging
from typing import Any

from bzutech import BzuTech

from homeassistant.components import mqtt
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .config_flow import get_entities, get_sensortype
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


class BzuBinarySensorEntity(BinarySensorEntity):
    """Bzutech binary sensor entity."""

    sent_updatechannels = False
    number_entities = 0

    def __init__(self, api, entry: ConfigEntry) -> None:
        """Set up binary sensor."""
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
        entidades = []
        if self.sendall == 1:
            entidades = get_entities(self.hass)[1:]

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

        if await mqtt.async_wait_for_mqtt_client(self.hass):
            for entity in entidades:
                try:
                    stt = self.hass.states.get(entity)
                    if stt is not None:
                        reading = stt.as_dict()["state"]
                except (AttributeError, ValueError):
                    logging.error("Sensor name error")
                    return
                sensor = f"HA-{get_sensortype(self.hass, entity)}-{stringtoint(entity)}"
                chs.append(sensor)
                counter = counter + 1
                data.append({"ref": sensor, "med": reading})
            channels["Records"][0]["channels"] = str(chs).replace("'", r'*"')
            readings["Records"][0]["data"] = str(data).replace("'", r'*"')
            if len(entidades) != self.number_entities:
                self.number_entities = len(entidades)
                mqtt.publish(self.hass, "UpdateChannels", str(channels))
            mqtt.publish(self.hass, "data_send", str(readings))

        self._attr_is_on = True
