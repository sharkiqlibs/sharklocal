"""Tests for sharklocal.rest_client.RESTVacuumClient."""

from __future__ import annotations

import ssl
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from sharklocal.exceptions import ActionNotSupportedError, CommandError, ConnectError
from sharklocal.mappings.base import RESTMappingConfig
from sharklocal.models import DeviceInfo, VacuumEvent, VacuumMode, VacuumStatus
from sharklocal.rest_client import RESTVacuumClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_response(json_data: Any = None, status: int = 200, raise_for_status=None) -> AsyncMock:
    """Build an AsyncMock that behaves like an aiohttp ClientResponse."""
    resp = AsyncMock()
    resp.status = status
    if raise_for_status:
        resp.raise_for_status = MagicMock(side_effect=raise_for_status)
    else:
        resp.raise_for_status = MagicMock()
    resp.json = AsyncMock(return_value=json_data)
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=False)
    return resp


def _patch_session(client: RESTVacuumClient, response: AsyncMock) -> None:
    """Inject a mock session into the client."""
    session = AsyncMock()
    session.closed = False
    session.request = MagicMock(return_value=response)
    client._session = session


# ---------------------------------------------------------------------------
# base_url
# ---------------------------------------------------------------------------


def test_base_url_https(rest_mapping):
    client = RESTVacuumClient("192.168.1.100", rest_mapping)
    assert client.base_url == "https://192.168.1.100:443"


def test_base_url_http(rest_mapping):
    rest_mapping.transport = "http"
    rest_mapping.port = 80
    client = RESTVacuumClient("192.168.1.100", rest_mapping)
    assert client.base_url == "http://192.168.1.100:80"


# ---------------------------------------------------------------------------
# supports()
# ---------------------------------------------------------------------------


def test_supports_known_action(rest_mapping):
    client = RESTVacuumClient("host", rest_mapping)
    assert client.supports("get_status") is True


def test_supports_unknown_action(rest_mapping):
    client = RESTVacuumClient("host", rest_mapping)
    assert client.supports("fly_to_moon") is False


# ---------------------------------------------------------------------------
# _make_connector()
# ---------------------------------------------------------------------------


async def test_make_connector_http(rest_mapping):
    rest_mapping.transport = "http"
    client = RESTVacuumClient("host", rest_mapping)
    connector = client._make_connector()
    assert isinstance(connector, aiohttp.TCPConnector)
    await connector.close()


async def test_make_connector_https_no_ssl_verify(rest_mapping):
    rest_mapping.transport = "https"
    rest_mapping.verify_ssl = False
    client = RESTVacuumClient("host", rest_mapping)
    connector = client._make_connector()
    assert isinstance(connector, aiohttp.TCPConnector)
    await connector.close()


async def test_make_connector_https_with_ssl_verify(rest_mapping):
    rest_mapping.transport = "https"
    rest_mapping.verify_ssl = True
    client = RESTVacuumClient("host", rest_mapping)
    connector = client._make_connector()
    assert isinstance(connector, aiohttp.TCPConnector)
    await connector.close()


async def test_ssl_context_is_built_at_construction_not_in_the_event_loop(rest_mapping):
    rest_mapping.transport = "https"
    rest_mapping.verify_ssl = False
    with patch("sharklocal.rest_client.ssl.create_default_context", wraps=ssl.create_default_context) as create:
        client = RESTVacuumClient("host", rest_mapping)
        assert create.call_count == 1
        connector = client._make_connector()
        assert create.call_count == 1
    assert client._ssl_context.verify_mode == ssl.CERT_NONE
    await connector.close()


# ---------------------------------------------------------------------------
# _get_session()
# ---------------------------------------------------------------------------


async def test_get_session_creates_new(rest_mapping):
    client = RESTVacuumClient("host", rest_mapping)
    with patch("sharklocal.rest_client.aiohttp.ClientSession") as mock_cls:
        mock_session = AsyncMock()
        mock_session.closed = False
        mock_cls.return_value = mock_session
        session = await client._get_session()
        assert session is mock_session
        mock_cls.assert_called_once()
    await client.close()


async def test_get_session_reuses_existing(rest_mapping):
    client = RESTVacuumClient("host", rest_mapping)
    mock_session = AsyncMock()
    mock_session.closed = False
    client._session = mock_session
    with patch("sharklocal.rest_client.aiohttp.ClientSession") as mock_cls:
        session = await client._get_session()
        assert session is mock_session
        mock_cls.assert_not_called()


async def test_get_session_recreates_if_closed(rest_mapping):
    client = RESTVacuumClient("host", rest_mapping)
    closed_session = AsyncMock()
    closed_session.closed = True
    client._session = closed_session
    with patch("sharklocal.rest_client.aiohttp.ClientSession") as mock_cls:
        new_session = AsyncMock()
        new_session.closed = False
        mock_cls.return_value = new_session
        session = await client._get_session()
        assert session is new_session


# ---------------------------------------------------------------------------
# close()
# ---------------------------------------------------------------------------


async def test_close_closes_session(rest_mapping):
    client = RESTVacuumClient("host", rest_mapping)
    mock_session = AsyncMock()
    mock_session.closed = False
    client._session = mock_session
    await client.close()
    mock_session.close.assert_awaited_once()
    assert client._session is None


async def test_close_idempotent_no_session(rest_mapping):
    client = RESTVacuumClient("host", rest_mapping)
    await client.close()  # Should not raise


async def test_close_idempotent_already_closed(rest_mapping):
    client = RESTVacuumClient("host", rest_mapping)
    mock_session = AsyncMock()
    mock_session.closed = True
    client._session = mock_session
    await client.close()
    mock_session.close.assert_not_awaited()


# ---------------------------------------------------------------------------
# call() — ActionNotSupportedError
# ---------------------------------------------------------------------------


async def test_call_unsupported_action_raises(rest_mapping):
    client = RESTVacuumClient("host", rest_mapping)
    with pytest.raises(ActionNotSupportedError, match="fly_to_moon"):
        await client.call("fly_to_moon")


# ---------------------------------------------------------------------------
# call() — ConnectError
# ---------------------------------------------------------------------------


async def test_call_connect_error_on_connector_error(rest_mapping):
    client = RESTVacuumClient("host", rest_mapping)
    with patch.object(client, "_get_session") as mock_get:
        session = AsyncMock()
        session.request = MagicMock(
            return_value=MagicMock(
                __aenter__=AsyncMock(
                    side_effect=aiohttp.ClientConnectorError(
                        connection_key=MagicMock(), os_error=OSError("refused")
                    )
                ),
                __aexit__=AsyncMock(return_value=False),
            )
        )
        mock_get.return_value = session
        with pytest.raises(ConnectError):
            await client.call("get_status")


@pytest.mark.parametrize(
    "error",
    [
        aiohttp.ConnectionTimeoutError("Connection timeout to host"),
        aiohttp.ServerDisconnectedError(),
        TimeoutError(),
    ],
    ids=["connection-timeout", "server-disconnected", "total-timeout"],
)
async def test_call_connect_error_on_unreachable_host(rest_mapping, error):
    client = RESTVacuumClient("host", rest_mapping)
    with patch.object(client, "_get_session") as mock_get:
        session = AsyncMock()
        session.request = MagicMock(
            return_value=MagicMock(
                __aenter__=AsyncMock(side_effect=error),
                __aexit__=AsyncMock(return_value=False),
            )
        )
        mock_get.return_value = session
        with pytest.raises(ConnectError):
            await client.call("get_status")


# ---------------------------------------------------------------------------
# call() — CommandError on HTTP error
# ---------------------------------------------------------------------------


async def test_call_command_error_on_http_error(rest_mapping):
    client = RESTVacuumClient("host", rest_mapping)
    resp = _make_mock_response(
        raise_for_status=aiohttp.ClientResponseError(
            request_info=MagicMock(), history=(), status=500
        )
    )
    _patch_session(client, resp)
    with pytest.raises(CommandError):
        await client.call("get_status")


# ---------------------------------------------------------------------------
# call() — status response_map
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "mode_str, charging_str, expected_mode",
    [
        ("ready", "connected", VacuumMode.DOCKED),       # ready + connected (charging) → docked
        ("ready", "unconnected", VacuumMode.IDLE),      # ready + not charging → idle
        ("ready", "", VacuumMode.IDLE),                  # ready + no charging → idle
        ("cleaning", "unconnected", VacuumMode.CLEANING),
        ("go_home", "unconnected", VacuumMode.RETURNING_TO_DOCK),
        ("exploring", "unconnected", VacuumMode.EXPLORING),
        ("unknown_mode_xyz", "unconnected", VacuumMode.UNKNOWN),
    ],
)
async def test_call_parse_status_modes(rest_mapping, mode_str, charging_str, expected_mode):
    client = RESTVacuumClient("host", rest_mapping)
    response_data = {
        "mode": mode_str,
        "charging": charging_str,
        "battery_level": 77,
    }
    resp = _make_mock_response(json_data=response_data)
    _patch_session(client, resp)
    result = await client.call("get_status")
    assert isinstance(result, VacuumStatus)
    assert result.mode == expected_mode


async def test_call_parse_status_battery_level(rest_mapping):
    client = RESTVacuumClient("host", rest_mapping)
    resp = _make_mock_response(json_data={"mode": "cleaning", "battery_level": 55, "charging": "unconnected"})
    _patch_session(client, resp)
    result = await client.call("get_status")
    assert result.battery_level == 55


async def test_call_parse_status_charging_true(rest_mapping):
    client = RESTVacuumClient("host", rest_mapping)
    # The code treats "connected" as charging=True
    resp = _make_mock_response(json_data={"mode": "ready", "charging": "connected", "battery_level": 77})
    _patch_session(client, resp)
    result = await client.call("get_status")
    assert result.charging is True


async def test_call_parse_status_raw_preserved(rest_mapping):
    client = RESTVacuumClient("host", rest_mapping)
    data = {"mode": "cleaning", "charging": "unconnected", "battery_level": 40, "extra": True}
    resp = _make_mock_response(json_data=data)
    _patch_session(client, resp)
    result = await client.call("get_status")
    assert result.raw == data


# ---------------------------------------------------------------------------
# call() — events response_map
# ---------------------------------------------------------------------------


async def test_call_parse_events(rest_mapping, events_json):
    client = RESTVacuumClient("host", rest_mapping)
    resp = _make_mock_response(json_data=events_json)
    _patch_session(client, resp)
    result = await client.call("get_events")
    assert isinstance(result, list)
    assert len(result) == 2
    assert all(isinstance(e, VacuumEvent) for e in result)


async def test_call_parse_events_field_mapping(rest_mapping, events_json):
    client = RESTVacuumClient("host", rest_mapping)
    resp = _make_mock_response(json_data=events_json)
    _patch_session(client, resp)
    result = await client.call("get_events")
    event = result[0]
    assert event.id == 1
    assert event.type == "status_robot_lifted"
    assert event.type_id == 2010
    assert event.source_type == "operation_unit"


async def test_call_parse_events_empty_list(rest_mapping):
    client = RESTVacuumClient("host", rest_mapping)
    resp = _make_mock_response(json_data={"robot_events": []})
    _patch_session(client, resp)
    result = await client.call("get_events")
    assert result == []


# ---------------------------------------------------------------------------
# call() — robot_id response_map
# ---------------------------------------------------------------------------


async def test_call_parse_robot_id(rest_mapping, robot_id_json):
    client = RESTVacuumClient("host", rest_mapping)
    resp = _make_mock_response(json_data=robot_id_json)
    _patch_session(client, resp)
    result = await client.call("get_robot_id")
    assert isinstance(result, DeviceInfo)
    assert result.firmware == "RV2000-1.15.0-release:3.10.2821"


async def test_call_parse_robot_id_empty_firmware_becomes_none(rest_mapping):
    client = RESTVacuumClient("host", rest_mapping)
    resp = _make_mock_response(json_data={"firmware": "", "devices": []})
    _patch_session(client, resp)
    result = await client.call("get_robot_id")
    assert result.firmware is None


async def test_call_parse_robot_id_missing_firmware_becomes_none(rest_mapping):
    client = RESTVacuumClient("host", rest_mapping)
    resp = _make_mock_response(json_data={"devices": []})
    _patch_session(client, resp)
    result = await client.call("get_robot_id")
    assert result.firmware is None


# ---------------------------------------------------------------------------
# call() — wifi_status response_map
# ---------------------------------------------------------------------------


async def test_call_parse_wifi_status(rest_mapping, wifi_json):
    client = RESTVacuumClient("host", rest_mapping)
    resp = _make_mock_response(json_data=wifi_json)
    _patch_session(client, resp)
    result = await client.call("get_wifi_status")
    assert isinstance(result, DeviceInfo)
    assert result.mac_address == "AA:BB:CC:DD:EE:FF"
    assert result.ip_address == "192.168.1.100"
    assert result.ssid == "MyWifi"
    assert result.rssi == -45


# ---------------------------------------------------------------------------
# call() — command actions (no response_map)
# ---------------------------------------------------------------------------


async def test_call_command_returns_json_if_present(rest_mapping):
    client = RESTVacuumClient("host", rest_mapping)
    resp = _make_mock_response(json_data={"result": "ok"})
    _patch_session(client, resp)
    result = await client.call("start_cleaning")
    assert result == {"result": "ok"}


async def test_call_command_returns_true_when_json_fails(rest_mapping):
    client = RESTVacuumClient("host", rest_mapping)
    resp = _make_mock_response(json_data=None)
    resp.json = AsyncMock(side_effect=Exception("not JSON"))
    _patch_session(client, resp)
    result = await client.call("start_cleaning")
    assert result is True


# ---------------------------------------------------------------------------
# _parse_response — unknown response_map returns raw dict
# ---------------------------------------------------------------------------


def test_parse_response_unknown_key_returns_data(rest_mapping):
    client = RESTVacuumClient("host", rest_mapping)
    data = {"some": "data"}
    result = client._parse_response("unknown_map_type", data)
    assert result == data


async def test_parse_status_mode_map_maps_to_invalid_enum_value(rest_mapping):
    """mode_map returns a string that's not in VacuumMode → ValueError → UNKNOWN."""
    rest_mapping.mode_map["broken_mode"] = "not_a_real_vacuum_mode"
    client = RESTVacuumClient("host", rest_mapping)
    resp = _make_mock_response(json_data={"mode": "broken_mode", "charging": "unconnected"})
    _patch_session(client, resp)
    result = await client.call("get_status")
    assert result.mode == VacuumMode.UNKNOWN
