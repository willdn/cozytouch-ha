from __future__ import annotations

import asyncio
import time
from base64 import b64encode
from typing import Any

import aiohttp
from homeassistant.exceptions import ConfigEntryAuthFailed

from .const import (
    BASE_URL,
    CLIENT_ID,
    CLIENT_SECRET,
    EXECUTION_DONE,
    EXECUTION_ERROR,
    EXECUTION_POLL_SECONDS,
    EXECUTION_TIMEOUT_SECONDS,
    MAGELLAN_PATH,
    REQUEST_DELAY_SECONDS,
    TOKEN_PATH,
    TOKEN_REFRESH_BUFFER,
)


class CozytouchAPI:
    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session
        self._access_token: str = ""
        self._refresh_token: str = ""
        self._expires_at: float = 0.0
        self._lock = asyncio.Lock()
        self._last_request: float = 0.0

    # ── Auth ──────────────────────────────────────────────────────────────────

    @staticmethod
    def _basic_auth() -> str:
        raw = f"{CLIENT_ID}:{CLIENT_SECRET}".encode()
        return "Basic " + b64encode(raw).decode()

    async def login(self, email: str, password: str) -> None:
        ts = int(time.time())
        data = await self._token_request({
            "grant_type": "password",
            "username": f"GA-PRIVATEPERSON/{email}",
            "password": password,
            "scope": f"openid device_{ts}",
        })
        self._store_token(data)

    async def refresh(self) -> None:
        try:
            data = await self._token_request({
                "grant_type": "refresh_token",
                "refresh_token": self._refresh_token,
            })
            self._store_token(data)
        except aiohttp.ClientResponseError as err:
            raise ConfigEntryAuthFailed("Token refresh failed") from err

    async def _token_request(self, body: dict) -> dict:
        async with self._session.post(
            BASE_URL + TOKEN_PATH,
            headers={
                "Authorization": self._basic_auth(),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data=body,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    def _store_token(self, data: dict) -> None:
        self._access_token = data["access_token"]
        self._refresh_token = data.get("refresh_token", self._refresh_token)
        self._expires_at = time.time() + data.get("expires_in", 300)

    async def ensure_token(self) -> None:
        async with self._lock:
            if time.time() >= self._expires_at - TOKEN_REFRESH_BUFFER:
                await self.refresh()

    # ── HTTP helpers ──────────────────────────────────────────────────────────

    async def _wait(self) -> None:
        elapsed = time.time() - self._last_request
        if elapsed < REQUEST_DELAY_SECONDS:
            await asyncio.sleep(REQUEST_DELAY_SECONDS - elapsed)
        self._last_request = time.time()

    @property
    def _auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

    async def _get(self, path: str) -> Any:
        await self.ensure_token()
        await self._wait()
        async with self._session.get(
            BASE_URL + MAGELLAN_PATH + path,
            headers=self._auth_headers,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def _post(self, path: str, body: dict) -> Any:
        await self.ensure_token()
        await self._wait()
        async with self._session.post(
            BASE_URL + MAGELLAN_PATH + path,
            headers=self._auth_headers,
            json=body,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    # ── API operations ────────────────────────────────────────────────────────

    async def get_setup_view(self) -> list[dict]:
        data = await self._get("/cozytouch/setupviewv2")
        if isinstance(data, list):
            return data
        return [data]

    async def get_capabilities(self, device_id: int) -> dict[int, dict]:
        """capabilityId → {capabilityId, value, modificationDate (epoch seconds)}"""
        data = await self._get(f"/capabilities/?deviceId={device_id}")
        if not isinstance(data, list):
            data = data.get("capabilities") or data.get("data") or []
        return {int(item["capabilityId"]): item for item in data}

    async def write_capability(
        self, device_id: int, capability_id: int, value: Any
    ) -> int:
        """Returns the execution id."""
        return await self._post("/executions/writecapability", {
            "value": str(value),
            "deviceId": device_id,
            "capabilityId": capability_id,
        })

    async def refresh_capability(self, device_id: int, capability_id: int) -> int:
        """Ask the gateway to re-report a capability. Returns the execution id."""
        return await self._post("/executions/refreshcapability", {
            "deviceId": device_id,
            "capabilityId": capability_id,
        })

    async def wait_execution(self, execution_id: int) -> int | None:
        """Poll an execution until done/error; returns the last state seen."""
        deadline = time.monotonic() + EXECUTION_TIMEOUT_SECONDS
        state = None
        while time.monotonic() < deadline:
            execution = await self._get(f"/executions/{execution_id}")
            state = execution.get("state")
            if state in (EXECUTION_DONE, EXECUTION_ERROR):
                return state
            await asyncio.sleep(EXECUTION_POLL_SECONDS)
        return state
