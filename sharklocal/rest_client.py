"""Async REST client for local vacuum control."""

from __future__ import annotations

import ssl
from typing import Any, Dict, List, Optional

import aiohttp

from .exceptions import ActionNotSupportedError, CommandError, ConnectError
from .mappings.base import RESTMappingConfig
from .models import DeviceInfo, VacuumEvent, VacuumMode, VacuumStatus


class RESTVacuumClient:
    """Async HTTP/HTTPS client for local vacuum control via the REST API.

    Transport (``http`` vs ``https``) and SSL verification are driven by the
    mapping configuration, so different models can use different settings
    without code changes.
    """

    def __init__(self, host: str, mapping: RESTMappingConfig) -> None:
        self.host = host
        self.mapping = mapping
        self._session: Optional[aiohttp.ClientSession] = None
        # Building an SSL context reads the system certificate store, which is
        # blocking I/O; doing it here keeps it out of the event loop for callers
        # (Home Assistant) that construct clients in an executor.
        self._ssl_context: Optional[ssl.SSLContext] = None
        if mapping.transport != "http":
            self._ssl_context = ssl.create_default_context()
            if not mapping.verify_ssl:
                self._ssl_context.check_hostname = False
                self._ssl_context.verify_mode = ssl.CERT_NONE

    @property
    def base_url(self) -> str:
        return f"{self.mapping.transport}://{self.host}:{self.mapping.port}"

    def supports(self, action: str) -> bool:
        """Return ``True`` if the mapping defines *action*."""
        return action in self.mapping.actions

    def _make_connector(self) -> aiohttp.TCPConnector:
        """Build a ``TCPConnector`` with SSL settings from the mapping."""
        if self._ssl_context is None:
            return aiohttp.TCPConnector()
        return aiohttp.TCPConnector(ssl=self._ssl_context)

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(connector=self._make_connector())
        return self._session

    async def close(self) -> None:
        """Close the underlying HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def call(self, action: str) -> Any:
        """Execute a named action and return a normalized result.

        Args:
            action: Action name as defined in the mapping (e.g. ``"get_status"``).

        Returns:
            A normalized model object for query actions, or ``True`` for
            fire-and-forget command actions.

        Raises:
            ActionNotSupportedError: If *action* is not in the mapping.
            ConnectError: If the vacuum host cannot be reached.
            CommandError: If the vacuum returns an HTTP error response.
        """
        if not self.supports(action):
            raise ActionNotSupportedError(
                f"REST mapping '{self.mapping.id}' does not support '{action}'"
            )

        spec = self.mapping.actions[action]
        url = f"{self.base_url}{spec.path}"
        session = await self._get_session()

        try:
            async with session.request(
                method=spec.method,
                url=url,
                json=spec.body,
                headers=spec.headers,
            ) as resp:
                resp.raise_for_status()

                if spec.response_map:
                    data = await resp.json(content_type=None)
                    return self._parse_response(spec.response_map, data)

                # Command endpoints may return minimal or empty bodies.
                try:
                    return await resp.json(content_type=None)
                except Exception:
                    return True

        except (aiohttp.ClientConnectionError, TimeoutError) as exc:
            # Not just a refused connection: a robot that drops packets (seen
            # during the nightly network restart) times out instead, and that
            # is just as unreachable. Anything else escaping here skips the
            # MQTT fallback and fails the caller's setup outright.
            raise ConnectError(
                f"Cannot connect to vacuum at {self.host}:{self.mapping.port}"
            ) from exc
        except aiohttp.ClientResponseError as exc:
            raise CommandError(
                f"REST request to {spec.path} failed with HTTP {exc.status}"
            ) from exc

    # ------------------------------------------------------------------
    # Response parsers
    # ------------------------------------------------------------------

    def _parse_response(self, response_map: str, data: Dict[str, Any]) -> Any:
        """Dispatch to the appropriate parser for *response_map*."""
        parsers = {
            "status": self._parse_status,
            "events": self._parse_events,
            "robot_id": self._parse_robot_id,
            "wifi_status": self._parse_wifi_status,
        }
        parser = parsers.get(response_map)
        return parser(data) if parser else data

    def _parse_status(self, data: Dict[str, Any]) -> VacuumStatus:
        raw_mode = str(data.get("mode", "")).lower()
        charging_raw = str(data.get("charging", "")).lower()

        # The API returns "connected" when charging and "unconnected" when not.
        charging = charging_raw == "connected"

        # "ready" is context-dependent: combined with "unconnected" it means the
        # vacuum is stopped and away from the dock (e.g. paused mid-run), not docked.
        if raw_mode == "ready" and not charging:
            mode = VacuumMode.IDLE
        else:
            mode_str = self.mapping.mode_map.get(raw_mode, "unknown")
            try:
                mode = VacuumMode(mode_str)
            except ValueError:
                mode = VacuumMode.UNKNOWN

        return VacuumStatus(
            mode=mode,
            battery_level=data.get("battery_level"),
            charging=charging,
            raw=data,
        )

    def _parse_events(self, data: Dict[str, Any]) -> List[VacuumEvent]:
        return [
            VacuumEvent(
                id=evt.get("id", 0),
                type=evt.get("type", ""),
                type_id=evt.get("type_id", 0),
                timestamp=evt.get("timestamp", {}),
                current_status=evt.get("current_status", ""),
                source_type=evt.get("source_type", ""),
                raw=evt,
            )
            for evt in data.get("robot_events", [])
        ]

    def _parse_robot_id(self, data: Dict[str, Any]) -> DeviceInfo:
        # Per the API docs, use the top-level 'firmware' value for diagnostics.
        # Per-device entries in the 'devices' array can be ignored.
        firmware = data.get("firmware") or None
        return DeviceInfo(firmware=firmware, raw=data)

    def _parse_wifi_status(self, data: Dict[str, Any]) -> DeviceInfo:
        return DeviceInfo(
            mac_address=data.get("mac_address"),
            ip_address=data.get("ip_address"),
            ssid=data.get("ssid"),
            rssi=data.get("rssi"),
            raw=data,
        )
