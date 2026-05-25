"""Tests for sharklocal.mqtt_client."""

from __future__ import annotations

import asyncio
import base64
import struct
import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers — asyncio.timeout compatibility shim for Python < 3.11
# ---------------------------------------------------------------------------

@asynccontextmanager
async def _noop_timeout(secs):
    """Pass-through async context manager simulating asyncio.timeout."""
    yield


@asynccontextmanager
async def _immediate_timeout(secs):
    """Raise TimeoutError immediately, simulating an elapsed asyncio.timeout."""
    raise TimeoutError(f"Simulated timeout after {secs}s")
    yield  # required by asynccontextmanager, never reached

from sharklocal.exceptions import (
    ActionNotSupportedError,
    CommandError,
    ConnectError,
    DecoderError,
)
from sharklocal.mappings.base import MQTTActionSpec, MQTTMappingConfig
from sharklocal.models import VacuumMode, VacuumStatus
from sharklocal.mqtt_client import (
    MQTTVacuumClient,
    _STATUS_DECODERS,
    _decode_sharkiq_protobuf_v1,
    register_decoder,
)


# ---------------------------------------------------------------------------
# Helpers — protobuf encoding
# ---------------------------------------------------------------------------


def _varint(value: int) -> bytes:
    buf = []
    while True:
        b = value & 0x7F
        value >>= 7
        if value:
            buf.append(b | 0x80)
        else:
            buf.append(b)
            break
    return bytes(buf)


def _field(num: int, wire: int, payload: bytes) -> bytes:
    return _varint((num << 3) | wire) + payload


def _ld(content: bytes) -> bytes:
    return _varint(len(content)) + content


def _build_status_payload(mode: int, charging_state: int, battery_pct: int) -> bytes:
    battery_inner = _field(1, 0, _varint(charging_state)) + _field(8, 0, _varint(battery_pct))
    return _field(4, 0, _varint(mode)) + _field(9, 2, _ld(battery_inner))


# ---------------------------------------------------------------------------
# register_decoder
# ---------------------------------------------------------------------------


def test_register_decoder_adds_to_registry():
    @register_decoder("_test_decoder_sentinel")
    def _my_decoder(payload, modes):
        return VacuumStatus(mode=VacuumMode.IDLE)

    assert "_test_decoder_sentinel" in _STATUS_DECODERS
    # Cleanup
    del _STATUS_DECODERS["_test_decoder_sentinel"]


def test_register_decoder_returns_original_function():
    def _fn(payload, modes):
        pass

    result = register_decoder("_test_fn_return")(_fn)
    assert result is _fn
    del _STATUS_DECODERS["_test_fn_return"]


# ---------------------------------------------------------------------------
# _decode_sharkiq_protobuf_v1 — directly
# ---------------------------------------------------------------------------


_MODES = {6: "cleaning", 7: "returning_to_dock", 13: "docking", 14: "docked"}


@pytest.mark.parametrize(
    "mode_int, expected_mode",
    [
        (6, VacuumMode.CLEANING),
        (7, VacuumMode.RETURNING_TO_DOCK),
        (13, VacuumMode.DOCKING),
        (14, VacuumMode.DOCKED),
        (99, VacuumMode.UNKNOWN),  # Not in modes dict → unknown
        (0, VacuumMode.UNKNOWN),   # 0 not in modes → unknown int→ str "unknown" → valid enum
    ],
)
def test_decode_sharkiq_mode_int(mode_int, expected_mode):
    payload = _build_status_payload(mode_int, 0, 50)
    result = _decode_sharkiq_protobuf_v1(payload, _MODES)
    assert result.mode == expected_mode


def test_decode_sharkiq_charging_state_3_means_charging():
    payload = _build_status_payload(6, 3, 80)
    result = _decode_sharkiq_protobuf_v1(payload, _MODES)
    assert result.charging is True


def test_decode_sharkiq_charging_state_0_not_charging():
    payload = _build_status_payload(6, 0, 80)
    result = _decode_sharkiq_protobuf_v1(payload, _MODES)
    assert result.charging is False


def test_decode_sharkiq_battery_percent():
    payload = _build_status_payload(6, 3, 75)
    result = _decode_sharkiq_protobuf_v1(payload, _MODES)
    assert result.battery_level == 75


def test_decode_sharkiq_missing_battery_field():
    """No field 9 in payload → battery_level=None, charging=False (empty dict default → state 0 → not charging)."""
    payload = _field(4, 0, _varint(6))  # Only mode field
    result = _decode_sharkiq_protobuf_v1(payload, _MODES)
    assert result.battery_level is None
    assert result.charging is False


def test_decode_sharkiq_battery_info_not_dict():
    """Field 9 present but decodes as raw bytes (not nested dict) due to non-parseable content."""
    from sharklocal import protobuf
    with patch.object(protobuf, "decode_raw", return_value={4: 6, 9: b"\xff\xff"}):
        result = _decode_sharkiq_protobuf_v1(b"\x00", _MODES)
        assert result.battery_level is None
        assert result.charging is None


def test_decode_sharkiq_raw_contains_protobuf_fields():
    payload = _build_status_payload(6, 3, 80)
    result = _decode_sharkiq_protobuf_v1(payload, _MODES)
    assert "protobuf_fields" in result.raw


# ---------------------------------------------------------------------------
# MQTTVacuumClient — supports()
# ---------------------------------------------------------------------------


def test_mqtt_client_supports_known_action(mqtt_mapping):
    client = MQTTVacuumClient("host", mqtt_mapping)
    assert client.supports("start_cleaning") is True


def test_mqtt_client_supports_unknown_action(mqtt_mapping):
    client = MQTTVacuumClient("host", mqtt_mapping)
    assert client.supports("fly_to_moon") is False


# ---------------------------------------------------------------------------
# _decode_incoming()
# ---------------------------------------------------------------------------


def test_decode_incoming_base64(mqtt_mapping):
    client = MQTTVacuumClient("host", mqtt_mapping)
    raw = base64.b64encode(b"hello world")
    result = client._decode_incoming(raw)
    assert result == b"hello world"


def test_decode_incoming_non_base64_passthrough(mqtt_mapping):
    mqtt_mapping.encoding = "raw"
    client = MQTTVacuumClient("host", mqtt_mapping)
    raw = b"\x01\x02\x03"
    result = client._decode_incoming(raw)
    assert result == raw


# ---------------------------------------------------------------------------
# _decode_status()
# ---------------------------------------------------------------------------


def test_decode_status_no_decoder_raises(mqtt_mapping):
    mqtt_mapping.status_decoder = "nonexistent_decoder_xyz"
    client = MQTTVacuumClient("host", mqtt_mapping)
    with pytest.raises(DecoderError, match="nonexistent_decoder_xyz"):
        client._decode_status(b"\x00")


def test_decode_status_calls_registered_decoder(mqtt_mapping):
    """Registered decoder is called with decoded (non-base64) bytes."""
    expected = VacuumStatus(mode=VacuumMode.DOCKED, battery_level=90, charging=True, raw={})

    @register_decoder("_test_decode_status")
    def _decoder(payload, modes):
        return expected

    mqtt_mapping.status_decoder = "_test_decode_status"
    mqtt_mapping.encoding = "raw"
    client = MQTTVacuumClient("host", mqtt_mapping)
    try:
        result = client._decode_status(b"\x00")
        assert result is expected
    finally:
        del _STATUS_DECODERS["_test_decode_status"]


# ---------------------------------------------------------------------------
# call() — ActionNotSupportedError
# ---------------------------------------------------------------------------


async def test_call_unsupported_action_raises(mqtt_mapping):
    client = MQTTVacuumClient("host", mqtt_mapping)
    with pytest.raises(ActionNotSupportedError, match="fly_to_moon"):
        await client.call("fly_to_moon")


# ---------------------------------------------------------------------------
# call() — command type
# ---------------------------------------------------------------------------


async def test_call_command_publishes_and_returns_true(mqtt_mapping):
    client = MQTTVacuumClient("host", mqtt_mapping)
    mock_inner_client = AsyncMock()
    mock_aiomqtt_client = AsyncMock()
    mock_aiomqtt_client.__aenter__ = AsyncMock(return_value=mock_inner_client)
    mock_aiomqtt_client.__aexit__ = AsyncMock(return_value=False)

    with patch("aiomqtt.Client", return_value=mock_aiomqtt_client):
        result = await client.call("start_cleaning")

    assert result is True
    mock_inner_client.publish.assert_awaited_once_with(
        mqtt_mapping.command_topic, payload=mqtt_mapping.actions["start_cleaning"].payload
    )


async def test_call_command_connection_failure_raises_connect_error(mqtt_mapping):
    client = MQTTVacuumClient("host", mqtt_mapping)
    mock_aiomqtt_client = AsyncMock()
    mock_aiomqtt_client.__aenter__ = AsyncMock(side_effect=Exception("connection refused"))
    mock_aiomqtt_client.__aexit__ = AsyncMock(return_value=False)

    with patch("aiomqtt.Client", return_value=mock_aiomqtt_client):
        with pytest.raises(ConnectError):
            await client.call("start_cleaning")


# ---------------------------------------------------------------------------
# call() — unrecognised spec type
# ---------------------------------------------------------------------------


async def test_call_unknown_spec_type_raises_command_error(mqtt_mapping):
    mqtt_mapping.actions["start_cleaning"] = MQTTActionSpec(
        type="unknown_type", payload="AAAA"
    )
    client = MQTTVacuumClient("host", mqtt_mapping)
    mock_inner_client = AsyncMock()
    mock_aiomqtt_client = AsyncMock()
    mock_aiomqtt_client.__aenter__ = AsyncMock(return_value=mock_inner_client)
    mock_aiomqtt_client.__aexit__ = AsyncMock(return_value=False)

    with patch("aiomqtt.Client", return_value=mock_aiomqtt_client):
        with pytest.raises(CommandError, match="unknown_type"):
            await client.call("start_cleaning")


# ---------------------------------------------------------------------------
# _request_status() — happy path
# ---------------------------------------------------------------------------


async def _make_mqtt_message(payload_bytes: bytes) -> MagicMock:
    msg = MagicMock()
    msg.payload = bytearray(payload_bytes)
    return msg


class _AsyncMessageIterator:
    """Async iterator that yields a fixed list of messages then stops."""

    def __init__(self, messages):
        self._messages = iter(messages)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._messages)
        except StopIteration:
            raise StopAsyncIteration


async def test_request_status_returns_decoded_status(mqtt_mapping):
    client = MQTTVacuumClient("host", mqtt_mapping)
    payload = _build_status_payload(6, 3, 80)
    # Base64-encode the payload as the client will base64-decode it
    encoded = base64.b64encode(payload)

    msg = MagicMock()
    msg.payload = bytearray(encoded)

    mock_inner = AsyncMock()
    mock_inner.messages = _AsyncMessageIterator([msg])
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_inner)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch.object(asyncio, "timeout", _noop_timeout, create=True):
        with patch("aiomqtt.Client", return_value=mock_ctx):
            result = await client.call("get_status")

    assert isinstance(result, VacuumStatus)
    assert result.mode == VacuumMode.CLEANING
    assert result.battery_level == 80
    assert result.charging is True


# ---------------------------------------------------------------------------
# _request_status() — timeout
# ---------------------------------------------------------------------------


async def test_request_status_timeout_raises_command_error(mqtt_mapping):
    client = MQTTVacuumClient("host", mqtt_mapping)

    mock_inner = AsyncMock()
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_inner)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    mqtt_mapping.actions["get_status"] = MQTTActionSpec(
        type="status_request", payload="DDDD", timeout=0.01
    )

    with patch.object(asyncio, "timeout", _immediate_timeout, create=True):
        with patch("aiomqtt.Client", return_value=mock_ctx):
            with pytest.raises(CommandError, match="Timed out"):
                await client.call("get_status")


# ---------------------------------------------------------------------------
# monitor() — sync callback
# ---------------------------------------------------------------------------


async def test_monitor_invokes_sync_callback(mqtt_mapping):
    client = MQTTVacuumClient("host", mqtt_mapping)
    payload = base64.b64encode(_build_status_payload(6, 3, 80))

    msg = MagicMock()
    msg.payload = bytearray(payload)

    received = []

    def callback(status):
        received.append(status)

    class _OneMessage:
        """Yields exactly one message, then ends iteration."""
        def __init__(self):
            self._done = False

        def __aiter__(self):
            return self

        async def __anext__(self):
            if not self._done:
                self._done = True
                return msg
            raise StopAsyncIteration

    mock_inner = AsyncMock()
    mock_inner.messages = _OneMessage()
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_inner)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("aiomqtt.Client", return_value=mock_ctx):
        await client.monitor(callback)

    assert len(received) == 1
    assert received[0].mode == VacuumMode.CLEANING


# ---------------------------------------------------------------------------
# monitor() — async callback
# ---------------------------------------------------------------------------


async def test_monitor_invokes_async_callback(mqtt_mapping):
    client = MQTTVacuumClient("host", mqtt_mapping)
    payload = base64.b64encode(_build_status_payload(14, 3, 90))

    msg = MagicMock()
    msg.payload = bytearray(payload)

    received = []
    stop = asyncio.Event()

    class _OneMsgIter:
        def __init__(self):
            self._done = False
        def __aiter__(self):
            return self
        async def __anext__(self):
            if not self._done:
                self._done = True
                return msg
            raise StopAsyncIteration

    async def async_callback(status):
        received.append(status)

    mock_inner = AsyncMock()
    mock_inner.messages = _OneMsgIter()
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_inner)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("aiomqtt.Client", return_value=mock_ctx):
        await client.monitor(async_callback)

    assert len(received) == 1
    assert received[0].mode == VacuumMode.DOCKED


# ---------------------------------------------------------------------------
# monitor() — stop_event halts after message
# ---------------------------------------------------------------------------


async def test_monitor_stops_when_stop_event_is_set(mqtt_mapping):
    client = MQTTVacuumClient("host", mqtt_mapping)
    payload = base64.b64encode(_build_status_payload(6, 0, 50))
    stop = asyncio.Event()

    msg = MagicMock()
    msg.payload = bytearray(payload)

    call_count = 0

    class _InfiniteMessages:
        def __aiter__(self):
            return self
        async def __anext__(self):
            return msg

    def callback(status):
        nonlocal call_count
        call_count += 1
        stop.set()  # Stop after first callback

    mock_inner = AsyncMock()
    mock_inner.messages = _InfiniteMessages()
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_inner)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("aiomqtt.Client", return_value=mock_ctx):
        await client.monitor(callback, stop_event=stop)

    assert call_count == 1


# ---------------------------------------------------------------------------
# monitor() — malformed messages are skipped
# ---------------------------------------------------------------------------


async def test_monitor_skips_malformed_messages(mqtt_mapping):
    """Messages where _decode_status raises DecoderError are skipped; valid ones produce a callback."""
    client = MQTTVacuumClient("host", mqtt_mapping)
    stop = asyncio.Event()
    received = []

    good_payload = base64.b64encode(_build_status_payload(6, 3, 80))
    good_msg = MagicMock()
    good_msg.payload = bytearray(good_payload)

    class _TwoMessages:
        def __init__(self):
            self._msgs = [good_msg, good_msg]  # deliver two identical good messages
            self._idx = 0
        def __aiter__(self):
            return self
        async def __anext__(self):
            if self._idx >= len(self._msgs):
                raise StopAsyncIteration
            m = self._msgs[self._idx]
            self._idx += 1
            return m

    # Patch _decode_status to raise DecoderError on first call, succeed on second.
    original_decode = client._decode_status
    call_count = 0
    def _side_effect(raw):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            from sharklocal.exceptions import DecoderError
            raise DecoderError("simulated decode failure")
        return original_decode(raw)

    def callback(status):
        received.append(status)
        stop.set()

    mock_inner = AsyncMock()
    mock_inner.messages = _TwoMessages()
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_inner)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch.object(client, "_decode_status", side_effect=_side_effect):
        with patch("aiomqtt.Client", return_value=mock_ctx):
            await client.monitor(callback, stop_event=stop)

    # Only the second (valid) message produced a callback; the first was skipped
    assert len(received) == 1


# ---------------------------------------------------------------------------
# monitor() — connection failure propagates as ConnectError
# ---------------------------------------------------------------------------


async def test_monitor_connection_failure_raises_connect_error(mqtt_mapping):
    client = MQTTVacuumClient("host", mqtt_mapping)
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(side_effect=Exception("broker unreachable"))
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("aiomqtt.Client", return_value=mock_ctx):
        with pytest.raises(ConnectError):
            await client.monitor(lambda s: None)


# ---------------------------------------------------------------------------
# Additional coverage: ValueError branch and empty-message _request_status
# ---------------------------------------------------------------------------


def test_decode_sharkiq_mode_string_invalid_enum_value():
    """modes dict maps mode_int to a string not in VacuumMode → ValueError → UNKNOWN."""
    modes_with_invalid = {99: "not_a_real_vacuum_mode"}
    payload = _build_status_payload(99, 0, 50)
    result = _decode_sharkiq_protobuf_v1(payload, modes_with_invalid)
    assert result.mode == VacuumMode.UNKNOWN


async def test_request_status_no_message_raises_command_error(mqtt_mapping):
    """Empty message iterator exits the async for without returning → fallback CommandError."""
    client = MQTTVacuumClient("host", mqtt_mapping)

    class _EmptyIterator:
        def __aiter__(self):
            return self
        async def __anext__(self):
            raise StopAsyncIteration

    mock_inner = AsyncMock()
    mock_inner.messages = _EmptyIterator()
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_inner)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    mqtt_mapping.actions["get_status"] = MQTTActionSpec(
        type="status_request", payload="DDDD", timeout=30.0
    )

    with patch.object(asyncio, "timeout", _noop_timeout, create=True):
        with patch("aiomqtt.Client", return_value=mock_ctx):
            with pytest.raises(CommandError, match="No status message"):
                await client.call("get_status")


# ---------------------------------------------------------------------------
# call() — aiomqtt ImportError raises ConnectError
# ---------------------------------------------------------------------------


async def test_call_aiomqtt_import_error_raises_connect_error(mqtt_mapping):
    """If aiomqtt cannot be imported, call() raises ConnectError."""
    client = MQTTVacuumClient("host", mqtt_mapping)

    original_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__

    def _failing_import(name, *args, **kwargs):
        if name == "aiomqtt":
            raise ImportError("No module named 'aiomqtt'")
        return original_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=_failing_import):
        with pytest.raises(ConnectError, match="aiomqtt is required"):
            await client.call("start_cleaning")


# ---------------------------------------------------------------------------
# _request_status() — aiomqtt ImportError raises ConnectError
# ---------------------------------------------------------------------------


async def test_request_status_aiomqtt_import_error_raises_connect_error(mqtt_mapping):
    """If aiomqtt cannot be imported in _request_status, ConnectError is raised."""
    client = MQTTVacuumClient("host", mqtt_mapping)

    import builtins
    real_import = builtins.__import__

    def _failing_import(name, *args, **kwargs):
        if name == "aiomqtt":
            raise ImportError("No module named 'aiomqtt'")
        return real_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=_failing_import):
        with pytest.raises(ConnectError, match="aiomqtt is required"):
            await client._request_status("DDDD", 5.0)


# ---------------------------------------------------------------------------
# monitor() — aiomqtt ImportError raises ConnectError
# ---------------------------------------------------------------------------


async def test_monitor_aiomqtt_import_error_raises_connect_error(mqtt_mapping):
    """If aiomqtt cannot be imported in monitor(), ConnectError is raised."""
    client = MQTTVacuumClient("host", mqtt_mapping)

    import builtins
    real_import = builtins.__import__

    def _failing_import(name, *args, **kwargs):
        if name == "aiomqtt":
            raise ImportError("No module named 'aiomqtt'")
        return real_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=_failing_import):
        with pytest.raises(ConnectError, match="aiomqtt is required"):
            await client.monitor(lambda s: None)


# ---------------------------------------------------------------------------
# call() — known exception re-raised without wrapping
# ---------------------------------------------------------------------------


async def test_call_reraises_command_error_from_request_status(mqtt_mapping):
    """CommandError raised inside _request_status is re-raised by call() unchanged."""
    client = MQTTVacuumClient("host", mqtt_mapping)

    with patch.object(
        client, "_request_status", side_effect=CommandError("status decode failed")
    ):
        with pytest.raises(CommandError, match="status decode failed"):
            await client.call("get_status")


# ---------------------------------------------------------------------------
# monitor() — known SharklocalError sub-type re-raised without wrapping
# ---------------------------------------------------------------------------


async def test_monitor_reraises_connect_error_from_subscribe(mqtt_mapping):
    """ConnectError raised from subscribe() inside monitor() is re-raised, not wrapped."""
    client = MQTTVacuumClient("host", mqtt_mapping)
    mock_inner = AsyncMock()
    mock_inner.subscribe.side_effect = ConnectError("broker dropped connection")
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_inner)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("aiomqtt.Client", return_value=mock_ctx):
        with pytest.raises(ConnectError, match="broker dropped connection"):
            await client.monitor(lambda s: None)
