from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

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
    POLL_REFRESH_CAPS,
    REFRESH_STALE_SECONDS,
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


def _last_update(items: dict[int, dict]) -> datetime | None:
    """Most recent modificationDate (epoch seconds) among the polled capabilities."""
    stamps = [_float(items[cap].get("modificationDate")) for cap in POLL_REFRESH_CAPS if cap in items]
    stamps = [s for s in stamps if s]
    if not stamps:
        return None
    return dt_util.utc_from_timestamp(max(stamps))


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
        self._refreshed_at: dict[int, float] = {}

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
            result[device["deviceId"]] = await self._async_fetch_zone(device)
        await self._async_refresh_stale(result)
        return result

    async def _async_refresh_stale(self, zones: dict[int, dict]) -> None:
        """Ask the gateway to re-report zones it hasn't reported for a while.

        The new values land on the next poll. A zone is refreshed at most once
        per REFRESH_STALE_SECONDS, even if the refresh never completes.
        """
        now = time.monotonic()
        for device_id, zone in zones.items():
            last_update = zone["last_update"]
            if last_update and (dt_util.utcnow() - last_update).total_seconds() < REFRESH_STALE_SECONDS:
                continue
            if now - self._refreshed_at.get(device_id, -REFRESH_STALE_SECONDS) < REFRESH_STALE_SECONDS:
                continue
            self._refreshed_at[device_id] = now
            for cap in POLL_REFRESH_CAPS:
                try:
                    await self.api.refresh_capability(device_id, cap)
                except (aiohttp.ClientError, asyncio.TimeoutError) as err:
                    _LOGGER.debug("Refresh of capability %s on %s failed: %s", cap, device_id, err)

    async def async_refresh_zone(self, device_id: int) -> None:
        """Re-read one zone and push it to the entities, without a full poll."""
        device = next(d for d in self.devices if d["deviceId"] == device_id)
        zone = await self._async_fetch_zone(device)
        self.async_set_updated_data({**self.data, device_id: zone})

    async def _async_fetch_zone(self, device: dict) -> dict:
        device_id: int = device.get("deviceId")
        fallback_name = (
            device.get("name") or device.get("customName") or device.get("longName") or str(device_id)
        )
        try:
            items = await self.api.get_capabilities(device_id)
        except Exception as err:
            raise UpdateFailed(f"Error fetching capabilities for {device_id}: {err}") from err
        caps = {cap_id: item.get("value") for cap_id, item in items.items()}

        return {
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
            "last_update":    _last_update(items),
        }
