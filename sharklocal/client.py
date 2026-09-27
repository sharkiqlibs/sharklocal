"""Unified VacuumClient with automatic transport selection."""

from __future__ import annotations

import asyncio
import inspect
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from . import protobuf
from .exceptions import ActionNotSupportedError, ConnectError, SharklocalError
from .mappings import load_mqtt_mapping, load_rest_mapping
from .models import (
    DeviceInfo,
    ProbeResult,
    SuctionLevel,
    VacuumEvent,
    VacuumMap,
    VacuumStatus,
)
from .mqtt_client import MQTTVacuumClient
from .rest_client import RESTVacuumClient
from .vacuum_map import encode_room_selection, encode_spot_selection


# On/off settings in the SharkIQ settings block (PbConfig), by field number,
# from the app's protobuf schema. Written as PbToggleT: 1 on, 2 off. Field 8
# (Recharge & Resume) and 7 (Evac & Resume) match the app captures exactly.
CONFIG_TOGGLES: Dict[str, int] = {
    "evac_resume": 7,
    "recharge_resume": 8,
    "room_by_room": 12,
    "continuous_cross_hatch": 13,
    "clean_edge": 14,
    "do_not_disturb": 18,
    "carpet_boost": 19,
    "child_lock": 24,
    "silent_mode": 25,
    "underglow_lights": 26,
    "button_sounds": 27,
}
CONFIG_VOLUME = 2
CONFIG_CARPET_DETECT = 15


class VacuumClient:
    """Unified vacuum client with automatic transport selection.

    REST is preferred when both transports support an action. MQTT is used as a
    fallback only when REST is unreachable (``ConnectError``). If a transport is
    not configured, or does not define an action, it is skipped automatically.

    Pass a list of mapping names to enable auto-detection: call :meth:`probe`
    during setup to test each mapping against the device and pin the working one
    for all subsequent calls. With a single mapping per transport the client
    works immediately without probing.

    Example — single mapping (no probe required)::

        async with VacuumClient(
            "192.168.1.100",
            rest_mappings="sharkiq_v1",
            mqtt_mappings="sharkiq_v1",
        ) as vacuum:
            status = await vacuum.get_status()
            await vacuum.start_cleaning()

    Example — multiple candidates with probe::

        async with VacuumClient(
            "192.168.1.100",
            rest_mappings=["sharkiq_v1", "other_model_v1"],
            mqtt_mappings=["sharkiq_v1"],
        ) as vacuum:
            result = await vacuum.probe()
            print(result.rest_mapping)   # e.g. "sharkiq_v1"
            status = await vacuum.get_status()

    Args:
        host: IP address or hostname of the vacuum.
        rest_mappings: One REST mapping name, or a list of candidates to probe.
        mqtt_mappings: One MQTT mapping name, or a list of candidates to probe.
        mapping_search_paths: Additional directories to search for mapping files
            before falling back to built-in mappings.
    """

    def __init__(
        self,
        host: str,
        *,
        rest_mappings: Optional[Union[str, List[str]]] = None,
        mqtt_mappings: Optional[Union[str, List[str]]] = None,
        mapping_search_paths: Optional[List[Union[str, Path]]] = None,
    ) -> None:
        self.host = host
        paths = mapping_search_paths or []

        # Active (pinned) transport clients. Set immediately when a single
        # mapping is provided; set by probe() when multiple are configured.
        self._rest: Optional[RESTVacuumClient] = None
        self._mqtt: Optional[MQTTVacuumClient] = None
        self._status_callback: Optional[Callable[[VacuumStatus], None]] = None
        self._monitor_stop: Optional[asyncio.Event] = None
        self._monitor_task: Optional[asyncio.Task] = None

        # Most recent status and map seen while monitoring. ``last_map`` keeps
        # the latest *persisted* map (rooms, dock, vectors) — room and spot
        # cleaning need its room definition — and is not replaced by the
        # room-less live frames a job produces.
        self.last_status: Optional[VacuumStatus] = None
        self.last_map: Optional[VacuumMap] = None

        # Primary transport in use. "REST" when REST is pinned and reachable,
        # "MQTT" when only MQTT is available, "NONE" until probe() confirms a
        # working transport (or a single mapping is auto-pinned).
        self.via: str = "NONE"

        def _to_list(val: Optional[Union[str, List[str]]]) -> List[str]:
            if val is None:
                return []
            return [val] if isinstance(val, str) else list(val)

        self._rest_candidates: List[RESTVacuumClient] = [
            RESTVacuumClient(host, load_rest_mapping(name, paths))
            for name in _to_list(rest_mappings)
        ]
        self._mqtt_candidates: List[MQTTVacuumClient] = [
            MQTTVacuumClient(host, load_mqtt_mapping(name, paths))
            for name in _to_list(mqtt_mappings)
        ]

        # Auto-pin when only one candidate is loaded — no probe() required.
        if len(self._rest_candidates) == 1:
            self._rest = self._rest_candidates[0]
            self.via = "REST"
        if len(self._mqtt_candidates) == 1:
            self._mqtt = self._mqtt_candidates[0]
            if self.via == "NONE":
                self.via = "MQTT"

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> VacuumClient:
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    async def close(self) -> None:
        """Stop monitoring and close all underlying connections."""
        await self.stop_monitoring()
        for client in self._rest_candidates:
            await client.close()

    # ------------------------------------------------------------------
    # High-level action API
    # ------------------------------------------------------------------

    async def start_cleaning(self) -> bool:
        """Start a full cleaning run."""
        return await self._execute("start_cleaning")

    async def stop(self) -> bool:
        """Pause the current cleaning task."""
        return await self._execute("stop")

    async def go_home(self) -> bool:
        """Send the vacuum back to its dock."""
        return await self._execute("go_home")

    async def explore(self) -> bool:
        """Begin a mapping/exploration run."""
        return await self._execute("explore")

    async def request_map(self) -> bool:
        """Ask the robot to publish its persisted map (MQTT only).

        The reply arrives through monitoring like any other map frame, and
        carries the last job's path and summary but no event log — a way to
        recover a job whose end-of-job frame was missed. Sent while docked; not
        tried mid-job.
        """
        return await self._execute("request_map")

    async def get_status(self) -> VacuumStatus:
        """Return the current vacuum status."""
        return await self._execute("get_status")

    async def get_events(self) -> List[VacuumEvent]:
        """Return the event log since last startup."""
        return await self._execute("get_events")

    async def get_device_info(self) -> DeviceInfo:
        """Return firmware and device identity information."""
        return await self._execute("get_robot_id")

    async def get_wifi_status(self) -> DeviceInfo:
        """Return Wi-Fi connection details including MAC address."""
        return await self._execute("get_wifi_status")

    async def pause(self) -> bool:
        """Pause the current job (resume it with :meth:`start_cleaning`)."""
        return await self._execute("pause")

    async def edge_clean(self) -> bool:
        """Clean along the walls."""
        return await self._execute("edge_clean")

    async def set_config(self, field_num: int, value: int) -> bool:
        """Write one field of the robot's settings block (``PbConfig``).

        MQTT-only and SharkIQ-specific: the command is field 7 carrying the one
        setting. :data:`CONFIG_TOGGLES` names the on/off settings; suction and
        the resume settings have their own methods.
        """
        payload = protobuf.encode_bytes_field(7, protobuf.encode_varint_field(field_num, value))
        return await self._send(payload)

    async def set_toggle(self, name: str, enabled: bool) -> bool:
        """Switch a named on/off setting (see :data:`CONFIG_TOGGLES`)."""
        if name not in CONFIG_TOGGLES:
            raise ValueError(f"Unknown setting {name!r}; known: {sorted(CONFIG_TOGGLES)}")
        return await self.set_config(CONFIG_TOGGLES[name], 1 if enabled else 2)

    async def set_carpet_detect(self, mode: int) -> bool:
        """Set carpet detection (1 disabled, 2 automatic; codes.CARPET_DETECT_MODES)."""
        return await self.set_config(CONFIG_CARPET_DETECT, mode)

    async def set_volume(self, volume: int) -> bool:
        """Set the robot's voice volume."""
        return await self.set_config(CONFIG_VOLUME, volume)

    async def find_robot(self) -> bool:
        """Make the vacuum play its locate sound."""
        return await self._execute("find_robot")

    async def set_suction(self, level: SuctionLevel) -> bool:
        """Set the suction power level (``eco``, ``normal`` or ``max``).

        The setting has no field in the status message — the robot only echoes
        it once on change — so callers wanting to display it should remember
        the last level they set.
        """
        return await self._execute(f"set_suction_{SuctionLevel(level).value}")

    async def set_recharge_resume(self, enabled: bool) -> bool:
        """Enable or disable Recharge & Resume (finish the job after charging)."""
        return await self._execute(f"recharge_resume_{'on' if enabled else 'off'}")

    async def set_evac_resume(self, enabled: bool) -> bool:
        """Enable or disable Evac & Resume (empty the bin mid-job, then continue)."""
        return await self._execute(f"evac_resume_{'on' if enabled else 'off'}")

    async def clean_rooms(
        self,
        room_names: List[str],
        *,
        deep: bool = False,
        vacuum_map: Optional[VacuumMap] = None,
    ) -> bool:
        """Clean the named rooms, then start.

        Room cleaning is an MQTT-only, two-message sequence: the map's room
        definition with the selection, then ``start_cleaning``. It needs a
        persisted map for the room definition — pass one, or let the client use
        the latest seen while monitoring (:attr:`last_map`).

        Args:
            room_names: Room names exactly as shown in the app.
            deep: Request a Matrix (two-pass) clean of those rooms.
            vacuum_map: The persisted map to take the room definition from.

        Raises:
            SharklocalError: If no persisted map is available.
            ValueError: If a room name is not on the map.
            ActionNotSupportedError: If no MQTT mapping is configured.
        """
        payload = self._room_definition_payload(
            vacuum_map, lambda m: encode_room_selection(m, room_names, deep=deep)
        )
        await self._send(payload)
        return await self.start_cleaning()

    async def clean_spot(
        self,
        x: float,
        y: float,
        *,
        vacuum_map: Optional[VacuumMap] = None,
    ) -> bool:
        """Spot-clean a ~1.5 m square centred on ``(x, y)`` metres, then start.

        Same requirements as :meth:`clean_rooms`. The coordinates are in the
        map frame — the one :class:`~sharklocal.models.VacuumMap` reports.
        """
        payload = self._room_definition_payload(
            vacuum_map, lambda m: encode_spot_selection(m, x, y)
        )
        await self._send(payload)
        return await self.start_cleaning()

    def _room_definition_payload(
        self,
        vacuum_map: Optional[VacuumMap],
        build: Callable[[VacuumMap], bytes],
    ) -> bytes:
        chosen = vacuum_map or self.last_map
        if chosen is None or not chosen.persisted:
            raise SharklocalError(
                "A persisted map is required for room or spot cleaning; the robot "
                "publishes one each time it docks — monitor until last_map is set"
            )
        return build(chosen)

    # ------------------------------------------------------------------
    # Mapping probe
    # ------------------------------------------------------------------

    async def probe(self) -> ProbeResult:
        """Test all configured mappings and pin the best working one per transport.

        Each REST mapping is tested in the order supplied by calling
        ``get_status``. The first mapping that responds successfully is pinned
        as the active REST transport. The same process is then repeated for
        MQTT. Previously pinned transports are replaced if probe is called again.

        Call this during integration setup when multiple mapping candidates are
        configured. With a single mapping per transport the client works without
        calling probe.

        Returns:
            :class:`ProbeResult` with the ``id`` of each selected mapping, or
            ``None`` for a transport where no mapping succeeded.
        """
        rest_id: Optional[str] = None
        mqtt_id: Optional[str] = None

        best_rest: Optional[RESTVacuumClient] = None
        for client in self._rest_candidates:
            try:
                await client.call("get_status")
                if best_rest is None or client.mapping.priority > best_rest.mapping.priority:
                    best_rest = client
            except SharklocalError:
                continue

        if best_rest is not None:
            self._rest = best_rest
            rest_id = best_rest.mapping.id

        best_mqtt: Optional[MQTTVacuumClient] = None
        for client in self._mqtt_candidates:
            try:
                await client.call("get_status")
                if best_mqtt is None or client.mapping.priority > best_mqtt.mapping.priority:
                    best_mqtt = client
            except SharklocalError:
                continue

        if best_mqtt is not None:
            self._mqtt = best_mqtt
            mqtt_id = best_mqtt.mapping.id

        if rest_id is not None:
            self.via = "REST"
        elif mqtt_id is not None:
            self.via = "MQTT"
        else:
            self.via = "NONE"

        return ProbeResult(rest_mapping=rest_id, mqtt_mapping=mqtt_id)

    # ------------------------------------------------------------------
    # Real-time monitoring (MQTT only)
    # ------------------------------------------------------------------

    def on_status_update(self, callback: Callable[[VacuumStatus], None]) -> None:
        """Register a callback to receive real-time status updates via MQTT.

        The callback receives a ``VacuumStatus`` on every status message.
        Both synchronous and ``async`` callables are accepted.

        Must be called before :meth:`start_monitoring`.
        """
        if not self._mqtt_candidates:
            raise SharklocalError(
                "An MQTT mapping is required for real-time monitoring"
            )
        self._status_callback = callback

    async def start_monitoring(self) -> None:
        """Begin monitoring the vacuum status in the background via MQTT.

        Call :meth:`on_status_update` first to register a callback. When
        multiple MQTT mappings are configured, call :meth:`probe` first to
        determine the active mapping. Safe to call repeatedly; a second call
        while already running is a no-op.
        """
        if not self._mqtt_candidates:
            raise SharklocalError("An MQTT mapping is required for monitoring")
        if self._mqtt is None:
            raise SharklocalError(
                "Call probe() first to determine the active MQTT mapping "
                "when multiple MQTT mappings are configured"
            )
        if self._status_callback is None:
            raise SharklocalError(
                "Register a callback with on_status_update() before starting monitoring"
            )
        if self._monitor_task and not self._monitor_task.done():
            return  # Already running

        self._monitor_stop = asyncio.Event()
        self._monitor_task = asyncio.ensure_future(
            self._mqtt.monitor(self._on_monitor_status, stop_event=self._monitor_stop)
        )

    async def _on_monitor_status(self, status: VacuumStatus) -> None:
        """Cache the latest status and persisted map, then forward to the callback."""
        self.last_status = status
        if status.map is not None and status.map.persisted and not self._same_job_poorer(status.map):
            self.last_map = status.map
        callback = self._status_callback
        if inspect.iscoroutinefunction(callback):
            await callback(status)
        else:
            callback(status)  # type: ignore[misc]

    def _same_job_poorer(self, vacuum_map: VacuumMap) -> bool:
        """``True`` if *vacuum_map* would replace a report of the same job.

        A requested map repeats the last job without its event log, so it only
        supersedes the cached map when it records a different job.
        """
        current = self.last_map
        return (
            not vacuum_map.report
            and current is not None
            and current.report
            and current.job_started == vacuum_map.job_started
        )

    async def stop_monitoring(self) -> None:
        """Stop background status monitoring if it is running."""
        if self._monitor_stop:
            self._monitor_stop.set()
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except (asyncio.CancelledError, Exception):
                pass
        self._monitor_task = None
        self._monitor_stop = None

    # ------------------------------------------------------------------
    # Transport inspection
    # ------------------------------------------------------------------

    def supported_actions(self) -> List[str]:
        """Return all action names supported by any configured transport."""
        actions: set[str] = set()
        rest_opts = [self._rest] if self._rest else self._rest_candidates
        mqtt_opts = [self._mqtt] if self._mqtt else self._mqtt_candidates
        for client in rest_opts:
            actions.update(client.mapping.actions)
        for client in mqtt_opts:
            actions.update(client.mapping.actions)
        return sorted(actions)

    def transports_for(self, action: str) -> List[str]:
        """Return which transports support *action*, in evaluation priority order.

        REST is listed before MQTT. When multiple candidates exist for a
        transport, any candidate supporting the action counts.
        """
        result = []
        rest_opts = [self._rest] if self._rest else self._rest_candidates
        mqtt_opts = [self._mqtt] if self._mqtt else self._mqtt_candidates
        if any(c.supports(action) for c in rest_opts):
            result.append("rest")
        if any(c.supports(action) for c in mqtt_opts):
            result.append("mqtt")
        return result

    @property
    def active_rest_mapping(self) -> Optional[str]:
        """The ``id`` of the currently pinned REST mapping, or ``None``."""
        return self._rest.mapping.id if self._rest else None

    @property
    def active_mqtt_mapping(self) -> Optional[str]:
        """The ``id`` of the currently pinned MQTT mapping, or ``None``."""
        return self._mqtt.mapping.id if self._mqtt else None

    # ------------------------------------------------------------------
    # Internal transport evaluation
    # ------------------------------------------------------------------

    async def _send(self, payload: bytes) -> bool:
        """Publish a runtime-built payload over the active MQTT transport.

        Only MQTT can carry these, so REST is never consulted. With several
        MQTT candidates and no pinned client, each is tried in order.
        """
        mqtt_options: List[MQTTVacuumClient] = (
            [self._mqtt] if self._mqtt is not None else self._mqtt_candidates
        )
        if not mqtt_options:
            raise ActionNotSupportedError(
                "Room and spot cleaning need an MQTT mapping; none is configured"
            )

        last_connect_error: Optional[ConnectError] = None
        for client in mqtt_options:
            try:
                return await client.send(payload)
            except ConnectError as exc:
                last_connect_error = exc
        raise last_connect_error  # type: ignore[misc]

    async def _execute(self, action: str) -> Any:
        """Execute *action* using the best available transport.

        When a transport has been pinned (single mapping configured, or after
        :meth:`probe` ran), only that client is tried for its transport.
        When no client is pinned (multiple candidates, probe not yet called),
        all candidates for that transport are tried in the supplied order.

        Evaluation order:

        1. REST candidates — tried left to right; ``ConnectError`` moves to the
           next candidate. Any other exception propagates immediately.
        2. MQTT candidates — tried when all REST candidates raise ``ConnectError``
           or no REST candidate supports the action.

        The ``ConnectError`` from the last exhausted candidate is re-raised when
        no transport can complete the action.
        """
        rest_options: List[RESTVacuumClient] = (
            [self._rest] if self._rest is not None else self._rest_candidates
        )
        mqtt_options: List[MQTTVacuumClient] = (
            [self._mqtt] if self._mqtt is not None else self._mqtt_candidates
        )
        rest_options = [c for c in rest_options if c.supports(action)]
        mqtt_options = [c for c in mqtt_options if c.supports(action)]

        if not rest_options and not mqtt_options:
            raise ActionNotSupportedError(
                f"Action '{action}' is not supported by any configured mapping. "
                f"Supported actions: {self.supported_actions()}"
            )

        last_connect_error: Optional[ConnectError] = None

        for client in rest_options:
            try:
                return await client.call(action)
            except ConnectError as exc:
                last_connect_error = exc

        for client in mqtt_options:
            try:
                return await client.call(action)
            except ConnectError as exc:
                last_connect_error = exc

        if last_connect_error:
            raise last_connect_error
        raise ActionNotSupportedError(  # pragma: no cover
            f"No configured transport could execute action '{action}'"  # pragma: no cover
        )  # pragma: no cover
