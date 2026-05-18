from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import CozytouchAPI
from .const import (
    CAP_AMBIENT_TEMP,
    CAP_COOLING_MAX,
    CAP_COOLING_MIN,
    CAP_COOLING_TARGET,
    CAP_FAN_SPEED,
    CAP_HEATING_MAX,
    CAP_HEATING_MIN,
    CAP_HEATING_STATUS,
    CAP_HEATING_TARGET,
    CAP_HVAC_MODE,
    CAP_QUIET_MODE,
    CAP_ROOM_NAME,
    DOMAIN,
    POLL_INTERVAL_SECONDS,
)

_LOGGER = logging.getLogger(__name__)


def _is_room_device(device: dict) -> bool:
    model = str(device.get("modelFamily") or "").upper()
    name = str(device.get("name") or device.get("longName") or "").upper()
    return "ROOM" in model or "ROOM" in name


def _float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class CozytouchCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, api: CozytouchAPI) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=POLL_INTERVAL_SECONDS),
        )
        self.api = api
        self.devices: list[dict] = []

    async def _async_setup(self) -> None:
        """Fetch and cache the ROOM device list once at startup."""
        setups = await self.api.get_setup_view()
        all_devices: list[dict] = []
        for setup in setups:
            all_devices.extend(setup.get("devices") or [])
        self.devices = [d for d in all_devices if _is_room_device(d)]
        _LOGGER.debug("Found %d ROOM zone(s): %s", len(self.devices), [
            d.get("deviceId") for d in self.devices
        ])

    async def _async_update_data(self) -> dict[int, dict]:
        if not self.devices:
            await self._async_setup()

        result: dict[int, dict] = {}
        for device in self.devices:
            device_id: int = device.get("deviceId")
            fallback_name = (
                device.get("name") or device.get("customName") or device.get("longName") or str(device_id)
            )
            try:
                caps = await self.api.get_capabilities(device_id)
            except Exception as err:
                raise UpdateFailed(f"Error fetching capabilities for {device_id}: {err}") from err

            result[device_id] = {
                "name":           caps.get(CAP_ROOM_NAME) or fallback_name,
                "ambient_temp":   _float(caps.get(CAP_AMBIENT_TEMP)),
                "heating_target": _float(caps.get(CAP_HEATING_TARGET)),
                "cooling_target": _float(caps.get(CAP_COOLING_TARGET)),
                "system_mode":    _int(caps.get(CAP_HVAC_MODE)),
                "heating_status": _int(caps.get(CAP_HEATING_STATUS)),
                "heating_min":    _float(caps.get(CAP_HEATING_MIN)),
                "heating_max":    _float(caps.get(CAP_HEATING_MAX)),
                "cooling_min":    _float(caps.get(CAP_COOLING_MIN)),
                "cooling_max":    _float(caps.get(CAP_COOLING_MAX)),
                "fan_speed":      _int(caps.get(CAP_FAN_SPEED)),
                "quiet_mode":     _int(caps.get(CAP_QUIET_MODE)),
            }

        return result
