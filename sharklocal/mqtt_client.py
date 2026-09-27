"""Async MQTT client for local vacuum control."""

from __future__ import annotations

import asyncio
import inspect
import base64
from typing import Any, Callable, Dict, List, Optional

from .exceptions import ActionNotSupportedError, CommandError, ConnectError, DecoderError
from .mappings.base import MQTTMappingConfig
from .models import VacuumMode, VacuumStatus
from . import protobuf, vacuum_map

# Imported once, here, rather than at first use: importing reads the package
# from disk, and a first use inside Home Assistant's event loop is flagged as a
# blocking call. Still optional, so a REST-only install works without it.
try:
    import aiomqtt
except ImportError:  # pragma: no cover - exercised by patching this name
    aiomqtt = None  # type: ignore[assignment]


def _require_aiomqtt() -> Any:
    if aiomqtt is None:
        raise ConnectError("aiomqtt is required for MQTT support. Install with: pip install aiomqtt")
    return aiomqtt


# Registry mapping decoder name -> callable(payload_bytes, modes) -> VacuumStatus.
# Additional decoders for new models can be registered with @register_decoder.
_STATUS_DECODERS: Dict[str, Callable[..., VacuumStatus]] = {}


def register_decoder(name: str) -> Callable:
    """Decorator to register a named MQTT status decoder function.

    Usage::

        @register_decoder("my_model_v1")
        def _decode_my_model(payload: bytes, modes: Dict[int, str]) -> VacuumStatus:
            ...
    """

    def decorator(fn: Callable) -> Callable:
        _STATUS_DECODERS[name] = fn
        return fn

    return decorator


@register_decoder("sharkiq_protobuf_v1")
def _decode_sharkiq_protobuf_v1(
    payload: bytes,
    modes: Dict[int, str],
) -> VacuumStatus:
    """Decode a SharkIQ MQTT status message (raw protobuf bytes).

    Field reference:

    * Field 4  — system state (``SysStateT``, see :mod:`sharklocal.codes`)
    * Field 5  — error codes active now (repeated ``ErrorCodeT``)
    * Field 6  — warning codes active now (repeated ``WarningCodeT``)
    * Field 9  — ``BatteryInfo`` nested message

      * Field 1 — ``ChargingState`` (3 = ``CHARGING_ON_DOCK``)
      * Field 8 — ``battery_percent`` (0–100)

    * Field 35 — present (``2``) while Recharge & Resume is enabled
    * Field 36 — present (``2``) while Evac & Resume is enabled
    * Field 40 — ``2`` normal clean / ``1`` Matrix or Spot clean (during a job)
    * Field 45 — ``2`` while a job is active, ``0`` otherwise
    * Field 7  — map data on map-bearing frames (see :mod:`sharklocal.vacuum_map`)
    """
    fields = protobuf.decode_fields(payload)

    # Map frames are large binary blobs that decode_raw would mis-parse as
    # nested messages; decode them separately and keep them out of ``raw``.
    map_blob = fields.pop(vacuum_map.FIELD_MAP, None)
    decoded_map = None
    if map_blob is not None:
        decoded_map = vacuum_map.decode_map({vacuum_map.FIELD_MAP: map_blob, **fields})
        payload = protobuf.remove_field(payload, vacuum_map.FIELD_MAP)

    raw = protobuf.decode_raw(payload)
    errors = _repeated_varints(fields.get(5, []))
    warnings = _repeated_varints(fields.get(6, []))

    mode_int = raw.get(4, 0)
    mode_str = modes.get(mode_int, "unknown")
    try:
        mode = VacuumMode(mode_str)
    except ValueError:
        mode = VacuumMode.UNKNOWN

    # Field 9 is device info. Its field 1 is the Wi-Fi state, not a charging
    # state (it reads 3, WIFI_CONNECTED, while the robot cleans); charging is
    # the system state SYS_ST_CHARGING.
    device = _submessage(fields, 9)
    battery_percent: Optional[int] = _first_int(device, 8)
    charging: Optional[bool] = (mode_int == 13) if 4 in raw else None
    base = _submessage(fields, 16)

    # Settings are reflected by presence: the field disappears when switched off.
    recharge_resume = 35 in raw
    evac_resume = 36 in raw
    job_active = raw.get(45) == 2
    deep_clean: Optional[bool] = None
    if 40 in raw:
        deep_clean = raw[40] == 1

    return VacuumStatus(
        mode=mode,
        battery_level=battery_percent,
        charging=charging,
        raw={"protobuf_fields": raw},
        job_active=job_active,
        deep_clean=deep_clean,
        recharge_resume=recharge_resume,
        evac_resume=evac_resume,
        map=decoded_map,
        errors=errors,
        warnings=warnings,
        state=raw.get(4),
        temperature=_first_int(device, 11),
        wifi_state=_first_int(device, 1),
        wifi_link_quality=_first_int(device, 2),
        wifi_signal=_first_int(device, 3),
        water_level=_first_int(device, 9),
        dust_level=_first_int(device, 10),
        ip_address=_first_text(device, 17),
        fan_speed=_first_int(base, 3),
        brushroll_speed=_first_int(base, 5),
        side_brush_speed=_first_int(base, 6),
        clean_edge=_toggle(raw.get(43)),
        carpet_detect=raw.get(44),
        relocation=raw.get(41),
        log_entries=_diagnose_entries(fields.get(34)),
    )


def _diagnose_entries(values: Optional[list]) -> Optional[list]:
    """Field 34 (repeated PbDiagnoseInfo): its field 5 holds JSON log entries."""
    if not values:
        return None
    entries = []
    for value in values:
        if not isinstance(value, bytes):
            continue
        try:
            info = protobuf.decode_fields(value)
        except Exception:  # noqa: BLE001 - a malformed record is skipped
            continue
        for text in info.get(5, []):
            if isinstance(text, bytes):
                entries.extend(vacuum_map.parse_log_json(text))
    return entries


def _submessage(fields: Dict[int, list], num: int) -> Dict[int, list]:
    """The fields of a nested message, or an empty dict."""
    value = fields.get(num, [None])[0]
    if not isinstance(value, bytes):
        return {}
    try:
        return protobuf.decode_fields(value)
    except Exception:  # noqa: BLE001 - a malformed sub-message is just absent
        return {}


def _first_int(fields: Dict[int, list], num: int) -> Optional[int]:
    value = fields.get(num, [None])[0]
    return value if isinstance(value, int) else None


def _first_text(fields: Dict[int, list], num: int) -> Optional[str]:
    value = fields.get(num, [None])[0]
    if not isinstance(value, bytes):
        return None
    try:
        return value.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _toggle(value: Any) -> Optional[bool]:
    """A PbToggleT: 1 on, 2 off, anything else unknown."""
    return {1: True, 2: False}.get(value)


def _repeated_varints(values: list) -> List[int]:
    """Values of a repeated varint field, packed (one bytes blob) or not."""
    out: List[int] = []
    for value in values:
        if isinstance(value, int):
            out.append(value)
            continue
        pos = 0
        while pos < len(value):
            number, pos = protobuf._decode_varint(value, pos)
            out.append(number)
    return out


class MQTTVacuumClient:
    """Async MQTT client for local vacuum control.

    Requires ``aiomqtt`` (``pip install aiomqtt``).
    """

    def __init__(self, host: str, mapping: MQTTMappingConfig) -> None:
        self.host = host
        self.mapping = mapping

    def supports(self, action: str) -> bool:
        """Return ``True`` if the mapping defines *action*."""
        return action in self.mapping.actions

    def _decode_incoming(self, raw_payload: bytes) -> bytes:
        """Decode a received MQTT payload per the mapping's encoding setting."""
        if self.mapping.encoding == "base64":
            return base64.b64decode(raw_payload)
        return raw_payload

    def _decode_status(self, raw_payload: bytes) -> VacuumStatus:
        """Decode a raw MQTT payload into a normalized ``VacuumStatus``."""
        decoder = _STATUS_DECODERS.get(self.mapping.status_decoder)
        if decoder is None:
            raise DecoderError(
                f"No decoder registered for '{self.mapping.status_decoder}'. "
                f"Available decoders: {list(_STATUS_DECODERS)}"
            )
        payload = self._decode_incoming(raw_payload)
        return decoder(payload, self.mapping.modes)

    async def call(self, action: str) -> Any:
        """Execute a named action from the mapping.

        Args:
            action: Action name as defined in the mapping (e.g. ``"start_cleaning"``).

        Returns:
            ``True`` for ``command`` actions, or a ``VacuumStatus`` for
            ``status_request`` actions.

        Raises:
            ActionNotSupportedError: If *action* is not in the mapping.
            ConnectError: If the MQTT broker cannot be reached.
            CommandError: If a status response is not received within the timeout.
        """
        if not self.supports(action):
            raise ActionNotSupportedError(
                f"MQTT mapping '{self.mapping.id}' does not support '{action}'"
            )

        spec = self.mapping.actions[action]

        mqtt = _require_aiomqtt()

        try:
            if spec.type == "command":
                async with mqtt.Client(self.host, port=self.mapping.port) as client:
                    await client.publish(self.mapping.command_topic, payload=spec.payload)
                return True

            if spec.type == "status_request":
                return await self._request_status(spec.payload, spec.timeout)

        except (ActionNotSupportedError, CommandError, ConnectError, DecoderError):
            raise
        except Exception as exc:
            raise ConnectError(
                f"MQTT error connecting to {self.host}:{self.mapping.port}: {exc}"
            ) from exc

        raise CommandError(f"Unrecognised MQTT action type '{spec.type}'")

    async def send(self, payload: bytes) -> bool:
        """Publish a raw command payload that is built at runtime.

        Used for commands whose content depends on state — room selection
        carries the map's room definition — and so cannot be a fixed mapping
        action. *payload* is the protobuf message bytes; it is encoded per the
        mapping's ``encoding`` before publishing.

        Raises:
            ConnectError: If the MQTT broker cannot be reached.
        """
        mqtt = _require_aiomqtt()

        encoded: Any = payload
        if self.mapping.encoding == "base64":
            encoded = base64.b64encode(payload).decode("ascii")

        try:
            async with mqtt.Client(self.host, port=self.mapping.port) as client:
                await client.publish(self.mapping.command_topic, payload=encoded)
        except Exception as exc:
            raise ConnectError(
                f"MQTT error connecting to {self.host}:{self.mapping.port}: {exc}"
            ) from exc
        return True

    async def _request_status(self, command_payload: str, timeout: float) -> VacuumStatus:
        """Publish a status-request command and return the decoded first response."""
        mqtt = _require_aiomqtt()

        async with mqtt.Client(self.host, port=self.mapping.port) as client:
            await client.subscribe(self.mapping.status_topic)
            await client.publish(self.mapping.command_topic, payload=command_payload)
            try:
                async with asyncio.timeout(timeout):
                    async for message in client.messages:
                        return self._decode_status(bytes(message.payload))
            except TimeoutError:
                raise CommandError(
                    f"Timed out after {timeout}s waiting for MQTT status response"
                )

        raise CommandError("No status message received from vacuum")

    async def monitor(
        self,
        callback: Callable[[VacuumStatus], None],
        *,
        stop_event: Optional[asyncio.Event] = None,
    ) -> None:
        """Subscribe to the vacuum's status topic and invoke *callback* per update.

        Runs indefinitely until *stop_event* is set or the task is cancelled.
        Both synchronous and ``async`` callbacks are supported.

        Args:
            callback: Called with each decoded ``VacuumStatus``.
            stop_event: Optional ``asyncio.Event``; when set, monitoring stops
                cleanly after the current message.
        """
        mqtt = _require_aiomqtt()

        try:
            async with mqtt.Client(self.host, port=self.mapping.port) as client:
                await client.subscribe(self.mapping.status_topic)
                async for message in client.messages:
                    if stop_event and stop_event.is_set():
                        return
                    try:
                        status = self._decode_status(bytes(message.payload))
                    except (DecoderError, CommandError):
                        continue  # Skip malformed messages silently
                    if inspect.iscoroutinefunction(callback):
                        await callback(status)
                    else:
                        callback(status)

        except (ActionNotSupportedError, CommandError, ConnectError, DecoderError):
            raise
        except Exception as exc:
            raise ConnectError(
                f"MQTT monitor lost connection to {self.host}: {exc}"
            ) from exc
