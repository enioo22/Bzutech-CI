"""Sensor for BZUTech integration."""
from dataclasses import dataclass
from datetime import date, datetime, timedelta  # noqa: D100
from decimal import Decimal
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    LIGHT_LUX,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfInformation,
    UnitOfSoundPressure,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import BzuCloudCoordinator
from .const import CONF_CHIPID, DOMAIN


@dataclass(frozen=True)
class BzuSensorEntityDescription(SensorEntityDescription):
    """Describe bzu sensor entity."""


SENSOR_TYPE: tuple[BzuSensorEntityDescription, ...] = (
    BzuSensorEntityDescription(
        key="TMP",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BzuSensorEntityDescription(
        key="HUM",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BzuSensorEntityDescription(
        key="VOT",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BzuSensorEntityDescription(
        key="CO2",
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BzuSensorEntityDescription(
        key="CUR",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BzuSensorEntityDescription(
        key="LUM",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BzuSensorEntityDescription(
        key="PIR",
        device_class=SensorDeviceClass.AQI,
        native_unit_of_measurement=None,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BzuSensorEntityDescription(
        key="DOOR",
        device_class=SensorDeviceClass.AQI,
        native_unit_of_measurement=None,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BzuSensorEntityDescription(
        key="DOR",
        device_class=SensorDeviceClass.AQI,
        native_unit_of_measurement=None,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BzuSensorEntityDescription(
        key="M10",
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BzuSensorEntityDescription(
        key="M25",
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BzuSensorEntityDescription(
        key="M40",
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BzuSensorEntityDescription(
        key="SND",
        device_class=SensorDeviceClass.SOUND_PRESSURE,
        native_unit_of_measurement=UnitOfSoundPressure.DECIBEL,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BzuSensorEntityDescription(
        key="M01",
        device_class=SensorDeviceClass.PM1,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BzuSensorEntityDescription(
        key="C01",
        device_class=SensorDeviceClass.CO,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BzuSensorEntityDescription(
        key="VOC",
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BzuSensorEntityDescription(
        key="DOS",
        device_class=SensorDeviceClass.AQI,
        native_unit_of_measurement=None,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BzuSensorEntityDescription(
        key="VOA",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BzuSensorEntityDescription(
        key="VOB",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BzuSensorEntityDescription(
        key="CRA",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BzuSensorEntityDescription(
        key="CRB",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BzuSensorEntityDescription(
        key="CRC",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BzuSensorEntityDescription(
        key="VRA",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BzuSensorEntityDescription(
        key="VRB",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BzuSensorEntityDescription(
        key="VRC",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BzuSensorEntityDescription(
        key="C05",
        device_class=SensorDeviceClass.AQI,
        native_unit_of_measurement=None,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BzuSensorEntityDescription(
        key="C25",
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BzuSensorEntityDescription(
        key="C40",
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BzuSensorEntityDescription(
        key="C10",
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BzuSensorEntityDescription(
        key="BAT",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BzuSensorEntityDescription(
        key="DBM",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BzuSensorEntityDescription(
        key="MEM",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.KILOBYTES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BzuSensorEntityDescription(
        key="UPT",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Do entry Setup."""
    coordinator: BzuCloudCoordinator = hass.data[DOMAIN][entry.entry_id]
    sensors = []
    for description in SENSOR_TYPE:
        if description.key == entry.data["sensorname"].split("-")[1]:
            if entry.data["sensorname"].split("-")[0] == "ADS7878":
                edgecase = BzuSensorEntityDescription(
                    key="VOC",
                    device_class=SensorDeviceClass.VOLTAGE,
                    native_unit_of_measurement=UnitOfElectricPotential.VOLT,
                    state_class=SensorStateClass.MEASUREMENT,
                )
                sensors.append(BzuEntity(coordinator, entry, edgecase))

            else:
                sensors.append(BzuEntity(coordinator, entry, description=description))

    async_add_entities(sensors, update_before_add=True)


class BzuCoordinator(DataUpdateCoordinator):
    """setup entity coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        cloudcoordinator: BzuCloudCoordinator,
    ) -> None:
        """Do setup coordinator."""

        super().__init__(
            hass,
            logging.getLogger("bzutech"),
            name="bzutech",
            update_interval=timedelta(seconds=30),
        )
        self.myapi = cloudcoordinator
        self.data = None


class BzuEntity(CoordinatorEntity, SensorEntity):
    """Setup sensor entity."""

    def __init__(
        self, coordinator, entry: ConfigEntry, description: BzuSensorEntityDescription
    ) -> None:
        """Do Sensor configuration."""
        super().__init__(coordinator)
        self._attr_name = (
            str(entry.data[CONF_CHIPID])
            + "-"
            + entry.data["sensorname"].split("-")[1]
            + "-"
            + str(entry.data["sensorport"])
        )
        self.chipid = entry.data[CONF_CHIPID]
        self.entity_description = description
        self._attr_unique_id = self._attr_name
        self._attr_is_on = True

    @property
    def device_info(self) -> DeviceInfo | None:
        """Setting basic device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, "ESP-" + self.chipid)},
            suggested_area="Room",
            name="Gateway " + self.chipid,
            entry_type=DeviceEntryType("service"),
            manufacturer="BZU Tecnologia",
            hw_version="1.0",
            model="ESP-" + self.chipid,
            serial_number=self.chipid,
            sw_version="1.0",
        )

    @property
    def native_value(self) -> StateType | date | datetime | Decimal:
        """Return sensor value."""
        self._attr_native_value = self.coordinator.data
        return super().native_value
