"""Tests for sharklocal.client.VacuumClient."""

from __future__ import annotations

import asyncio
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sharklocal.client import VacuumClient
from sharklocal.exceptions import (
    ActionNotSupportedError,
    CommandError,
    ConnectError,
    SharklocalError,
)
from sharklocal.models import DeviceInfo, ProbeResult, VacuumEvent, VacuumMode, VacuumStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_rest_client_mock(action_result=None, raises=None, supports_actions=None, priority=0):
    """Return a mock RESTVacuumClient."""
    mock = AsyncMock()
    mock.mapping = MagicMock()
    mock.mapping.id = "test_rest_v1"
    mock.mapping.priority = priority
    _default_rest_actions = ["get_status", "start_cleaning", "stop", "go_home", "explore", "get_events", "get_robot_id", "get_wifi_status"]
    _actions = supports_actions if supports_actions is not None else _default_rest_actions
    mock.mapping.actions = {a: MagicMock() for a in _actions}
    mock.supports = MagicMock(side_effect=lambda a: a in mock.mapping.actions)
    if raises:
        mock.call = AsyncMock(side_effect=raises)
    else:
        mock.call = AsyncMock(return_value=action_result)
    mock.close = AsyncMock()
    return mock


def _make_mqtt_client_mock(action_result=None, raises=None, supports_actions=None, priority=0):
    """Return a mock MQTTVacuumClient."""
    mock = MagicMock()
    mock.mapping = MagicMock()
    mock.mapping.id = "test_mqtt_v1"
    mock.mapping.priority = priority
    _default_mqtt_actions = ["get_status", "start_cleaning", "stop", "go_home"]
    _actions = supports_actions if supports_actions is not None else _default_mqtt_actions
    mock.mapping.actions = {a: MagicMock() for a in _actions}
    mock.supports = MagicMock(side_effect=lambda a: a in mock.mapping.actions)
    if raises:
        mock.call = AsyncMock(side_effect=raises)
    else:
        mock.call = AsyncMock(return_value=action_result)
    mock.monitor = AsyncMock()
    return mock


def _make_vacuum_client_with_mocks(rest_mock=None, mqtt_mock=None):
    """Create a VacuumClient and directly inject pre-built transport mocks."""
    with patch("sharklocal.client.load_rest_mapping"), patch("sharklocal.client.load_mqtt_mapping"):
        with patch("sharklocal.client.RESTVacuumClient") as MockREST:
            with patch("sharklocal.client.MQTTVacuumClient") as MockMQTT:
                MockREST.return_value = rest_mock or _make_rest_client_mock()
                MockMQTT.return_value = mqtt_mock or _make_mqtt_client_mock()
                client = VacuumClient(
                    "192.168.1.100",
                    rest_mappings="test_rest_v1",
                    mqtt_mappings="test_mqtt_v1",
                )
    return client


# ---------------------------------------------------------------------------
# __init__ — auto-pinning
# ---------------------------------------------------------------------------


def test_init_single_rest_pins_immediately():
    rest_mock = _make_rest_client_mock()
    with patch("sharklocal.client.load_rest_mapping"), \
         patch("sharklocal.client.RESTVacuumClient", return_value=rest_mock):
        client = VacuumClient("host", rest_mappings="test_rest_v1")
    assert client._rest is rest_mock
    assert client.via == "REST"


def test_init_single_mqtt_pins_immediately():
    mqtt_mock = _make_mqtt_client_mock()
    with patch("sharklocal.client.load_mqtt_mapping"), \
         patch("sharklocal.client.MQTTVacuumClient", return_value=mqtt_mock):
        client = VacuumClient("host", mqtt_mappings="test_mqtt_v1")
    assert client._mqtt is mqtt_mock
    assert client.via == "MQTT"


def test_init_both_single_mappings_via_is_rest():
    rest_mock = _make_rest_client_mock()
    mqtt_mock = _make_mqtt_client_mock()
    with patch("sharklocal.client.load_rest_mapping"), \
         patch("sharklocal.client.load_mqtt_mapping"), \
         patch("sharklocal.client.RESTVacuumClient", return_value=rest_mock), \
         patch("sharklocal.client.MQTTVacuumClient", return_value=mqtt_mock):
        client = VacuumClient("host", rest_mappings="test_rest_v1", mqtt_mappings="test_mqtt_v1")
    assert client.via == "REST"
    assert client._rest is rest_mock
    assert client._mqtt is mqtt_mock


def test_init_multiple_rest_candidates_no_pin():
    rest_a = _make_rest_client_mock()
    rest_b = _make_rest_client_mock()
    with patch("sharklocal.client.load_rest_mapping"), \
         patch("sharklocal.client.RESTVacuumClient", side_effect=[rest_a, rest_b]):
        client = VacuumClient("host", rest_mappings=["test_a", "test_b"])
    assert client._rest is None
    assert client.via == "NONE"
    assert len(client._rest_candidates) == 2


def test_init_no_mappings_via_none():
    client = VacuumClient("host")
    assert client.via == "NONE"
    assert client._rest is None
    assert client._mqtt is None


# ---------------------------------------------------------------------------
# active_rest_mapping / active_mqtt_mapping properties
# ---------------------------------------------------------------------------


def test_active_rest_mapping_not_pinned():
    client = VacuumClient("host")
    assert client.active_rest_mapping is None


def test_active_mqtt_mapping_not_pinned():
    client = VacuumClient("host")
    assert client.active_mqtt_mapping is None


def test_active_rest_mapping_when_pinned():
    client = _make_vacuum_client_with_mocks()
    assert client.active_rest_mapping == "test_rest_v1"


def test_active_mqtt_mapping_when_pinned():
    client = _make_vacuum_client_with_mocks()
    assert client.active_mqtt_mapping == "test_mqtt_v1"


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------


async def test_context_manager_returns_self():
    client = _make_vacuum_client_with_mocks()
    async with client as vc:
        assert vc is client


async def test_context_manager_calls_close_on_exit():
    client = _make_vacuum_client_with_mocks()
    with patch.object(client, "close", new_callable=AsyncMock) as mock_close:
        async with client:
            pass
        mock_close.assert_awaited_once()


# ---------------------------------------------------------------------------
# close()
# ---------------------------------------------------------------------------


async def test_close_stops_monitoring_and_closes_rest_clients():
    rest_mock = _make_rest_client_mock()
    client = _make_vacuum_client_with_mocks(rest_mock=rest_mock)
    with patch.object(client, "stop_monitoring", new_callable=AsyncMock) as mock_stop:
        await client.close()
        mock_stop.assert_awaited_once()
    rest_mock.close.assert_awaited_once()


# ---------------------------------------------------------------------------
# High-level action methods → _execute() call with correct action name
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "method_name, expected_action",
    [
        ("start_cleaning", "start_cleaning"),
        ("stop", "stop"),
        ("go_home", "go_home"),
        ("explore", "explore"),
        ("get_status", "get_status"),
        ("get_events", "get_events"),
        ("get_device_info", "get_robot_id"),
        ("get_wifi_status", "get_wifi_status"),
    ],
)
async def test_high_level_action_calls_execute(method_name, expected_action):
    client = _make_vacuum_client_with_mocks()
    with patch.object(client, "_execute", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = True
        method = getattr(client, method_name)
        await method()
        mock_exec.assert_awaited_once_with(expected_action)


# ---------------------------------------------------------------------------
# probe()
# ---------------------------------------------------------------------------


async def test_probe_rest_succeeds_first():
    rest_mock = _make_rest_client_mock(action_result=VacuumStatus(mode=VacuumMode.DOCKED))
    mqtt_mock = _make_mqtt_client_mock(raises=ConnectError("no mqtt"))
    with patch("sharklocal.client.load_rest_mapping"), \
         patch("sharklocal.client.load_mqtt_mapping"), \
         patch("sharklocal.client.RESTVacuumClient", return_value=rest_mock), \
         patch("sharklocal.client.MQTTVacuumClient", return_value=mqtt_mock):
        client = VacuumClient("host", rest_mappings=["test_rest_v1"], mqtt_mappings=["test_mqtt_v1"])
    result = await client.probe()
    assert result.rest_mapping == "test_rest_v1"
    assert result.mqtt_mapping is None
    assert client.via == "REST"


async def test_probe_mqtt_only_when_rest_fails():
    rest_mock = _make_rest_client_mock(raises=ConnectError("no rest"))
    mqtt_mock = _make_mqtt_client_mock(action_result=VacuumStatus(mode=VacuumMode.DOCKED))
    with patch("sharklocal.client.load_rest_mapping"), \
         patch("sharklocal.client.load_mqtt_mapping"), \
         patch("sharklocal.client.RESTVacuumClient", return_value=rest_mock), \
         patch("sharklocal.client.MQTTVacuumClient", return_value=mqtt_mock):
        client = VacuumClient("host", rest_mappings=["test_rest_v1"], mqtt_mappings=["test_mqtt_v1"])
    result = await client.probe()
    assert result.rest_mapping is None
    assert result.mqtt_mapping == "test_mqtt_v1"
    assert client.via == "MQTT"


async def test_probe_both_succeed():
    rest_mock = _make_rest_client_mock(action_result=VacuumStatus(mode=VacuumMode.DOCKED))
    mqtt_mock = _make_mqtt_client_mock(action_result=VacuumStatus(mode=VacuumMode.DOCKED))
    with patch("sharklocal.client.load_rest_mapping"), \
         patch("sharklocal.client.load_mqtt_mapping"), \
         patch("sharklocal.client.RESTVacuumClient", return_value=rest_mock), \
         patch("sharklocal.client.MQTTVacuumClient", return_value=mqtt_mock):
        client = VacuumClient("host", rest_mappings=["test_rest_v1"], mqtt_mappings=["test_mqtt_v1"])
    result = await client.probe()
    assert result.rest_mapping == "test_rest_v1"
    assert result.mqtt_mapping == "test_mqtt_v1"
    assert client.via == "REST"


async def test_probe_nothing_succeeds():
    rest_mock = _make_rest_client_mock(raises=ConnectError("no rest"))
    mqtt_mock = _make_mqtt_client_mock(raises=ConnectError("no mqtt"))
    with patch("sharklocal.client.load_rest_mapping"), \
         patch("sharklocal.client.load_mqtt_mapping"), \
         patch("sharklocal.client.RESTVacuumClient", return_value=rest_mock), \
         patch("sharklocal.client.MQTTVacuumClient", return_value=mqtt_mock):
        client = VacuumClient("host", rest_mappings=["test_rest_v1"], mqtt_mappings=["test_mqtt_v1"])
    result = await client.probe()
    assert result.rest_mapping is None
    assert result.mqtt_mapping is None
    assert client.via == "NONE"


async def test_probe_overwrites_previous_pin():
    rest_a = _make_rest_client_mock(raises=ConnectError("a fails"))
    rest_b = _make_rest_client_mock(action_result=VacuumStatus(mode=VacuumMode.DOCKED))
    rest_b.mapping.id = "test_rest_v2"

    with patch("sharklocal.client.load_rest_mapping"), \
         patch("sharklocal.client.RESTVacuumClient", side_effect=[rest_a, rest_b]):
        client = VacuumClient("host", rest_mappings=["test_a", "test_b"])

    result1 = await client.probe()
    assert result1.rest_mapping == "test_rest_v2"

    # Re-running probe should pick rest_a (now success) if we reset mock
    rest_a.call = AsyncMock(return_value=VacuumStatus(mode=VacuumMode.DOCKED))
    rest_a.mapping.id = "test_rest_v1"
    result2 = await client.probe()
    assert result2.rest_mapping == "test_rest_v1"


async def test_probe_selects_highest_priority_rest_mapping():
    low = _make_rest_client_mock(action_result=VacuumStatus(mode=VacuumMode.DOCKED), priority=10)
    low.mapping.id = "low_priority"
    high = _make_rest_client_mock(action_result=VacuumStatus(mode=VacuumMode.DOCKED), priority=20)
    high.mapping.id = "high_priority"

    with patch("sharklocal.client.load_rest_mapping"), \
         patch("sharklocal.client.RESTVacuumClient", side_effect=[low, high]):
        client = VacuumClient("host", rest_mappings=["low", "high"])

    result = await client.probe()
    assert result.rest_mapping == "high_priority"
    assert client._rest is high


async def test_probe_selects_highest_priority_mqtt_mapping():
    low = _make_mqtt_client_mock(action_result=VacuumStatus(mode=VacuumMode.DOCKED), priority=5)
    low.mapping.id = "low_priority"
    high = _make_mqtt_client_mock(action_result=VacuumStatus(mode=VacuumMode.DOCKED), priority=15)
    high.mapping.id = "high_priority"

    with patch("sharklocal.client.load_mqtt_mapping"), \
         patch("sharklocal.client.MQTTVacuumClient", side_effect=[low, high]):
        client = VacuumClient("host", mqtt_mappings=["low", "high"])

    result = await client.probe()
    assert result.mqtt_mapping == "high_priority"
    assert client._mqtt is high


async def test_probe_skips_failed_candidates_when_selecting_by_priority():
    failing = _make_rest_client_mock(raises=ConnectError("unreachable"), priority=100)
    failing.mapping.id = "high_but_fails"
    working = _make_rest_client_mock(action_result=VacuumStatus(mode=VacuumMode.DOCKED), priority=10)
    working.mapping.id = "low_but_works"

    with patch("sharklocal.client.load_rest_mapping"), \
         patch("sharklocal.client.RESTVacuumClient", side_effect=[failing, working]):
        client = VacuumClient("host", rest_mappings=["high", "low"])

    result = await client.probe()
    assert result.rest_mapping == "low_but_works"


# ---------------------------------------------------------------------------
# _execute() — REST success
# ---------------------------------------------------------------------------


async def test_execute_rest_success():
    expected = VacuumStatus(mode=VacuumMode.CLEANING)
    rest_mock = _make_rest_client_mock(action_result=expected)
    client = _make_vacuum_client_with_mocks(rest_mock=rest_mock)
    result = await client._execute("get_status")
    assert result is expected


# ---------------------------------------------------------------------------
# _execute() — REST→MQTT fallback
# ---------------------------------------------------------------------------


async def test_execute_falls_back_to_mqtt_on_connect_error():
    expected = VacuumStatus(mode=VacuumMode.DOCKED)
    rest_mock = _make_rest_client_mock(raises=ConnectError("no rest"))
    mqtt_mock = _make_mqtt_client_mock(action_result=expected)
    client = _make_vacuum_client_with_mocks(rest_mock=rest_mock, mqtt_mock=mqtt_mock)
    result = await client._execute("get_status")
    assert result is expected


# ---------------------------------------------------------------------------
# _execute() — all transports fail
# ---------------------------------------------------------------------------


async def test_execute_raises_last_connect_error_when_all_fail():
    rest_mock = _make_rest_client_mock(raises=ConnectError("rest fail"))
    mqtt_mock = _make_mqtt_client_mock(raises=ConnectError("mqtt fail"))
    client = _make_vacuum_client_with_mocks(rest_mock=rest_mock, mqtt_mock=mqtt_mock)
    with pytest.raises(ConnectError, match="mqtt fail"):
        await client._execute("get_status")


# ---------------------------------------------------------------------------
# _execute() — non-ConnectError propagates immediately
# ---------------------------------------------------------------------------


async def test_execute_non_connect_error_propagates_immediately():
    rest_mock = _make_rest_client_mock(raises=CommandError("bad command"))
    mqtt_mock = _make_mqtt_client_mock()
    client = _make_vacuum_client_with_mocks(rest_mock=rest_mock, mqtt_mock=mqtt_mock)
    with pytest.raises(CommandError, match="bad command"):
        await client._execute("get_status")
    # MQTT should NOT have been tried
    mqtt_mock.call.assert_not_awaited()


# ---------------------------------------------------------------------------
# _execute() — unsupported action
# ---------------------------------------------------------------------------


async def test_execute_unsupported_action_raises():
    client = _make_vacuum_client_with_mocks()
    with pytest.raises(ActionNotSupportedError, match="fly_to_moon"):
        await client._execute("fly_to_moon")


# ---------------------------------------------------------------------------
# _execute() — multi-REST candidate cascade
# ---------------------------------------------------------------------------


async def test_execute_cascades_through_rest_candidates():
    expected = VacuumStatus(mode=VacuumMode.IDLE)
    rest_a = _make_rest_client_mock(raises=ConnectError("a fails"))
    rest_b = _make_rest_client_mock(action_result=expected)

    with patch("sharklocal.client.load_rest_mapping"), \
         patch("sharklocal.client.RESTVacuumClient", side_effect=[rest_a, rest_b]):
        client = VacuumClient("host", rest_mappings=["test_a", "test_b"])

    result = await client._execute("get_status")
    assert result is expected


# ---------------------------------------------------------------------------
# _execute() — REST-only action (no MQTT support)
# ---------------------------------------------------------------------------


async def test_execute_rest_only_action_not_in_mqtt():
    """Actions not in MQTT mapping don't attempt MQTT."""
    expected = VacuumStatus(mode=VacuumMode.IDLE)
    rest_mock = _make_rest_client_mock(action_result=expected)
    # MQTT mock supports no actions
    mqtt_mock = _make_mqtt_client_mock(supports_actions=[])
    client = _make_vacuum_client_with_mocks(rest_mock=rest_mock, mqtt_mock=mqtt_mock)
    result = await client._execute("get_status")
    assert result is expected
    mqtt_mock.call.assert_not_awaited()


# ---------------------------------------------------------------------------
# supported_actions()
# ---------------------------------------------------------------------------


def test_supported_actions_returns_sorted_union():
    rest_mock = _make_rest_client_mock(supports_actions=["get_status", "start_cleaning", "explore"])
    mqtt_mock = _make_mqtt_client_mock(supports_actions=["get_status", "go_home"])
    client = _make_vacuum_client_with_mocks(rest_mock=rest_mock, mqtt_mock=mqtt_mock)
    actions = client.supported_actions()
    assert actions == sorted(actions)
    assert "get_status" in actions
    assert "start_cleaning" in actions
    assert "go_home" in actions
    assert "explore" in actions


# ---------------------------------------------------------------------------
# transports_for()
# ---------------------------------------------------------------------------


def test_transports_for_rest_only():
    rest_mock = _make_rest_client_mock(supports_actions=["explore"])
    mqtt_mock = _make_mqtt_client_mock(supports_actions=[])
    client = _make_vacuum_client_with_mocks(rest_mock=rest_mock, mqtt_mock=mqtt_mock)
    assert client.transports_for("explore") == ["rest"]


def test_transports_for_mqtt_only():
    rest_mock = _make_rest_client_mock(supports_actions=[])
    mqtt_mock = _make_mqtt_client_mock(supports_actions=["go_home"])
    client = _make_vacuum_client_with_mocks(rest_mock=rest_mock, mqtt_mock=mqtt_mock)
    assert client.transports_for("go_home") == ["mqtt"]


def test_transports_for_both():
    rest_mock = _make_rest_client_mock(supports_actions=["get_status"])
    mqtt_mock = _make_mqtt_client_mock(supports_actions=["get_status"])
    client = _make_vacuum_client_with_mocks(rest_mock=rest_mock, mqtt_mock=mqtt_mock)
    assert client.transports_for("get_status") == ["rest", "mqtt"]


def test_transports_for_neither():
    rest_mock = _make_rest_client_mock(supports_actions=[])
    mqtt_mock = _make_mqtt_client_mock(supports_actions=[])
    client = _make_vacuum_client_with_mocks(rest_mock=rest_mock, mqtt_mock=mqtt_mock)
    assert client.transports_for("fly_to_moon") == []


# ---------------------------------------------------------------------------
# on_status_update()
# ---------------------------------------------------------------------------


def test_on_status_update_stores_callback():
    client = _make_vacuum_client_with_mocks()
    cb = lambda s: None
    client.on_status_update(cb)
    assert client._status_callback is cb


def test_on_status_update_no_mqtt_raises():
    client = VacuumClient("host")  # No MQTT configured
    with pytest.raises(SharklocalError, match="MQTT"):
        client.on_status_update(lambda s: None)


# ---------------------------------------------------------------------------
# start_monitoring() guard conditions
# ---------------------------------------------------------------------------


async def test_start_monitoring_no_mqtt_raises():
    client = VacuumClient("host")
    with pytest.raises(SharklocalError, match="MQTT"):
        await client.start_monitoring()


async def test_start_monitoring_mqtt_not_pinned_raises():
    mqtt_a = _make_mqtt_client_mock()
    mqtt_b = _make_mqtt_client_mock()
    with patch("sharklocal.client.load_mqtt_mapping"), \
         patch("sharklocal.client.MQTTVacuumClient", side_effect=[mqtt_a, mqtt_b]):
        client = VacuumClient("host", mqtt_mappings=["test_a", "test_b"])
    client._status_callback = lambda s: None
    with pytest.raises(SharklocalError, match="probe"):
        await client.start_monitoring()


async def test_start_monitoring_no_callback_raises():
    client = _make_vacuum_client_with_mocks()
    # _status_callback is None by default
    with pytest.raises(SharklocalError, match="callback"):
        await client.start_monitoring()


async def test_start_monitoring_starts_background_task():
    client = _make_vacuum_client_with_mocks()
    client._status_callback = lambda s: None
    # Patch mqtt.monitor to be a coroutine that does nothing
    client._mqtt.monitor = AsyncMock()
    await client.start_monitoring()
    assert client._monitor_task is not None
    assert not client._monitor_task.done()
    await client.stop_monitoring()


async def test_start_monitoring_second_call_is_noop():
    client = _make_vacuum_client_with_mocks()
    client._status_callback = lambda s: None
    client._mqtt.monitor = AsyncMock()
    await client.start_monitoring()
    task1 = client._monitor_task
    await client.start_monitoring()  # Second call
    assert client._monitor_task is task1  # Same task, not replaced
    await client.stop_monitoring()


# ---------------------------------------------------------------------------
# stop_monitoring()
# ---------------------------------------------------------------------------


async def test_stop_monitoring_when_not_running_is_safe():
    client = _make_vacuum_client_with_mocks()
    await client.stop_monitoring()  # Should not raise


async def test_stop_monitoring_cancels_task():
    client = _make_vacuum_client_with_mocks()
    client._status_callback = lambda s: None
    client._mqtt.monitor = AsyncMock()
    await client.start_monitoring()
    assert client._monitor_task is not None
    await client.stop_monitoring()
    assert client._monitor_task is None
    assert client._monitor_stop is None
