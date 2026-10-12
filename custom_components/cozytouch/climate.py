from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import CozytouchConfigEntry
from .const import (
    CAP_COOLING_TARGET,
    CAP_FAN_SPEED,
    CAP_HEATING_TARGET,
    CAP_HVAC_MODE,
    CAP_QUIET_MODE,
    DOMAIN,
    EXECUTION_ERROR,
    FAN_SPEED_MAP,
    FAN_SPEED_REVERSE,
    PRESET_NONE,
    PRESET_QUIET,
    SYSTEM_MODE_MAP,
    SYSTEM_MODE_REVERSE,
)
from .coordinator import CozytouchCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CozytouchConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: CozytouchCoordinator = entry.runtime_data
    async_add_entities(
        CozytouchClimate(coordinator, device)
        for device in coordinator.devices
    )


class CozytouchClimate(CoordinatorEntity[CozytouchCoordinator], ClimateEntity):
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL, HVACMode.AUTO, HVACMode.FAN_ONLY, HVACMode.DRY]
    _attr_fan_modes = ["low", "medium", "high", "auto"]
    _attr_preset_modes = [PRESET_NONE, PRESET_QUIET]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.PRESET_MODE
    )
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, coordinator: CozytouchCoordinator, device: dict) -> None:
        super().__init__(coordinator)
        self._device_id: int = device["deviceId"]
        fallback = (
            device.get("name") or device.get("customName") or device.get("longName") or str(self._device_id)
        )
        self._attr_unique_id = f"cozytouch_{self._device_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(self._device_id))},
            name=fallback,
            manufacturer="Atlantic",
            model="Cozytouch ROOM zone",
        )

    @property
    def _zone(self) -> dict:
        return self.coordinator.data.get(self._device_id, {})

    @property
    def current_temperature(self) -> float | None:
        return self._zone.get("ambient_temp")

    @property
    def target_temperature(self) -> float | None:
        mode = self.hvac_mode
        if mode == HVACMode.COOL:
            return self._zone.get("cooling_target")
        return self._zone.get("heating_target")

    @property
    def min_temp(self) -> float:
        mode = self.hvac_mode
        if mode == HVACMode.COOL:
            return self._zone.get("cooling_min") or 16.0
        return self._zone.get("heating_min") or 7.0

    @property
    def max_temp(self) -> float:
        mode = self.hvac_mode
        if mode == HVACMode.COOL:
            return self._zone.get("cooling_max") or 30.0
        return self._zone.get("heating_max") or 30.0

    @property
    def hvac_mode(self) -> HVACMode:
        raw = self._zone.get("system_mode")
        if raw is None:
            return HVACMode.OFF
        return SYSTEM_MODE_MAP.get(raw, HVACMode.OFF)

    @property
    def hvac_action(self) -> HVACAction | None:
        status = self._zone.get("heating_status")
        if status is None:
            return None
        if self.hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        if status != 0:
            return HVACAction.HEATING if self.hvac_mode != HVACMode.COOL else HVACAction.COOLING
        return HVACAction.IDLE

    @property
    def fan_mode(self) -> str | None:
        raw = self._zone.get("fan_speed")
        if raw is None:
            return None
        return FAN_SPEED_MAP.get(raw, str(raw))

    @property
    def preset_mode(self) -> str:
        return PRESET_QUIET if self._zone.get("quiet_mode") == 1 else PRESET_NONE

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        # When the cloud last heard from the unit — goes stale if the gateway stops reporting
        return {"last_update": self._zone.get("last_update")}

    async def _async_write(self, capability_id: int, value: Any) -> None:
        """Write, wait for the gateway to apply it, then pull the new value back."""
        api = self.coordinator.api
        execution_id = await api.write_capability(self._device_id, capability_id, value)
        if await api.wait_execution(execution_id) == EXECUTION_ERROR:
            raise HomeAssistantError(f"Cozytouch reported an error writing capability {capability_id}")
        # The cloud keeps the old value until the gateway re-reports it
        await api.wait_execution(await api.refresh_capability(self._device_id, capability_id))
        await self.coordinator.async_refresh_zone(self._device_id)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        raw = SYSTEM_MODE_REVERSE.get(hvac_mode)
        if raw is None:
            _LOGGER.warning("Unsupported hvac_mode: %s", hvac_mode)
            return
        await self._async_write(CAP_HVAC_MODE, raw)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        raw = FAN_SPEED_REVERSE.get(fan_mode)
        if raw is None:
            _LOGGER.warning("Unsupported fan_mode: %s", fan_mode)
            return
        await self._async_write(CAP_FAN_SPEED, str(raw))

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        value = "1" if preset_mode == PRESET_QUIET else "0"
        await self._async_write(CAP_QUIET_MODE, value)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temp = kwargs.get("temperature")
        if temp is None:
            return
        cap = CAP_COOLING_TARGET if self.hvac_mode == HVACMode.COOL else CAP_HEATING_TARGET
        await self._async_write(cap, temp)
