"""Tests for sharklocal.__main__ CLI utility."""

from __future__ import annotations

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

import pytest

from sharklocal.__main__ import (
    generate_markdown_report,
    main,
    print_status,
    run_command,
    run_probe,
    run_test_logic,
    save_report,
    setup_argparse,
    monitor_vacuum,
)
from sharklocal.models import DeviceInfo, ProbeResult, VacuumMode, VacuumStatus


# ---------------------------------------------------------------------------
# generate_markdown_report
# ---------------------------------------------------------------------------

def test_generate_markdown_report_success():
    """Test report generation with successful results."""
    results = {
        "host": "1.2.3.4",
        "model": "TEST_MODEL",
        "fw": "v1.2.3",
        "rest": {
            "m1": {"actions": {"get_status": True, "get_robot_id": True}, "modes": {"cleaning", "docked"}}
        },
        "mqtt": {
            "m1": {"actions": {"get_status": True, "start_cleaning": True}, "fields": {"battery": True, "charging": True}, "modes": {"cleaning", "docked", "docking"}}
        }
    }
    report = generate_markdown_report(results)
    assert "# TEST_MODEL — Compatibility Matrix" in report
    assert "Start cleaning" in report and "MQTT: `m1`" in report
    assert "Get status" in report and "REST: `m1`" in report and "MQTT: `m1`" in report
    assert "Battery level" in report and "✅" in report
    assert "docking" in report and "MQTT: `m1`" in report


def test_generate_markdown_report_partial_rest():
    """Test report generation with only REST working."""
    results = {
        "host": "1.2.3.4",
        "model": "M1",
        "fw": "v1",
        "rest": {"m1": {"actions": {"get_status": True}, "modes": {"docked"}}},
        "mqtt": {}
    }
    report = generate_markdown_report(results)
    assert "- **MQTT:** Local MQTT broker (Port 1883) is closed or unreachable." in report


def test_generate_markdown_report_partial_mqtt():
    """Test report generation with only MQTT working."""
    results = {
        "host": "1.2.3.4",
        "model": "M1",
        "fw": "v1",
        "rest": {},
        "mqtt": {"m1": {"actions": {"get_status": True}, "fields": {"battery": True}, "modes": {"docked"}}}
    }
    report = generate_markdown_report(results)
    assert "- **REST API:** Local REST API (Ports 443/80) is closed or non-responsive." in report


def test_generate_markdown_report_none():
    """Test report generation with no supported mappings."""
    results = {
        "host": "1.2.3.4",
        "model": None,
        "fw": None,
        "rest": {},
        "mqtt": {}
    }
    report = generate_markdown_report(results)
    assert "# {model} — Compatibility Matrix" in report
    assert "Start cleaning" in report and "None" in report
    assert "**Local Control Disabled:**" in report


# ---------------------------------------------------------------------------
# run_command
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_command_rest():
    """Test executing a command via REST."""
    mock_mapping = MagicMock()
    mock_mapping.actions = {"get_robot_id": MagicMock()}
    mock_client = AsyncMock()
    mock_client.call.return_value = DeviceInfo(firmware="v1")
    
    with patch("sharklocal.__main__.list_rest_mappings", return_value=["m1"]), \
         patch("sharklocal.__main__.load_rest_mapping", return_value=mock_mapping), \
         patch("sharklocal.__main__.RESTVacuumClient", return_value=mock_client):
        await run_command("1.2.3.4", "info", "rest")
        
    mock_client.call.assert_called_once_with("get_robot_id")
    mock_client.close.assert_called_once()


@pytest.mark.asyncio
async def test_run_command_rest_no_action():
    """Test run_command when action is not in mapping."""
    mock_mapping = MagicMock()
    mock_mapping.actions = {}
    
    with patch("sharklocal.__main__.list_rest_mappings", return_value=["m1"]), \
         patch("sharklocal.__main__.load_rest_mapping", return_value=mock_mapping):
        await run_command("1.2.3.4", "info", "rest")


@pytest.mark.asyncio
async def test_run_command_rest_failed():
    """Test run_command when REST fails."""
    mock_mapping = MagicMock()
    mock_mapping.actions = {"get_robot_id": MagicMock()}
    mock_client = AsyncMock()
    mock_client.call.side_effect = Exception("error")
    
    with patch("sharklocal.__main__.list_rest_mappings", return_value=["m1"]), \
         patch("sharklocal.__main__.load_rest_mapping", return_value=mock_mapping), \
         patch("sharklocal.__main__.RESTVacuumClient", return_value=mock_client), \
         patch("builtins.print") as mock_print:
        await run_command("1.2.3.4", "info", "rest")
    
    mock_print.assert_any_call("REST m1 failed: error")


@pytest.mark.asyncio
async def test_run_command_mqtt():
    """Test executing a command via MQTT."""
    mock_mapping = MagicMock()
    mock_mapping.actions = {"go_home": MagicMock()}
    mock_client = AsyncMock()
    mock_client.call.return_value = True
    
    with patch("sharklocal.__main__.list_mqtt_mappings", return_value=["m1"]), \
         patch("sharklocal.__main__.load_mqtt_mapping", return_value=mock_mapping), \
         patch("sharklocal.__main__.MQTTVacuumClient", return_value=mock_client):
        await run_command("1.2.3.4", "dock", "mqtt")
        
    mock_client.call.assert_called_once_with("go_home")


@pytest.mark.asyncio
async def test_run_command_mqtt_no_action():
    """Test run_command when action is not in MQTT mapping."""
    mock_mapping = MagicMock()
    mock_mapping.actions = {}
    
    with patch("sharklocal.__main__.list_mqtt_mappings", return_value=["m1"]), \
         patch("sharklocal.__main__.load_mqtt_mapping", return_value=mock_mapping):
        await run_command("1.2.3.4", "dock", "mqtt")


@pytest.mark.asyncio
async def test_run_command_mqtt_failed():
    """Test run_command when MQTT fails."""
    mock_mapping = MagicMock()
    mock_mapping.actions = {"go_home": MagicMock()}
    mock_client = AsyncMock()
    mock_client.call.side_effect = Exception("error")
    
    with patch("sharklocal.__main__.list_mqtt_mappings", return_value=["m1"]), \
         patch("sharklocal.__main__.load_mqtt_mapping", return_value=mock_mapping), \
         patch("sharklocal.__main__.MQTTVacuumClient", return_value=mock_client), \
         patch("builtins.print") as mock_print:
        await run_command("1.2.3.4", "dock", "mqtt")
    
    mock_print.assert_any_call("MQTT m1 failed: error")


# ---------------------------------------------------------------------------
# run_probe
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_probe_success():
    """Test the probe command."""
    probe_res = ProbeResult(rest_mapping="r1", mqtt_mapping="m1")
    mock_vacuum = AsyncMock()
    mock_vacuum.probe.return_value = probe_res
    mock_vacuum.via = "REST"
    mock_vacuum.__aenter__.return_value = mock_vacuum

    with patch("sharklocal.__main__.VacuumClient", return_value=mock_vacuum):
        await run_probe("1.2.3.4")
        
    mock_vacuum.probe.assert_called_once()


@pytest.mark.asyncio
async def test_run_probe_not_connected():
    """Test the probe command when no transport works."""
    probe_res = ProbeResult()
    mock_vacuum = AsyncMock()
    mock_vacuum.probe.return_value = probe_res
    mock_vacuum.via = "NONE"
    mock_vacuum.__aenter__.return_value = mock_vacuum

    with patch("sharklocal.__main__.VacuumClient", return_value=mock_vacuum), \
         patch("builtins.print") as mock_print:
        await run_probe("1.2.3.4")
        
    mock_print.assert_any_call("\nSuggestion: Verify that the vacuum is online and reachable at this IP.")


@pytest.mark.asyncio
async def test_run_probe_failed():
    """Test the probe command when it fails."""
    mock_vacuum = AsyncMock()
    mock_vacuum.probe.side_effect = Exception("error")
    mock_vacuum.__aenter__.return_value = mock_vacuum

    with patch("sharklocal.__main__.VacuumClient", return_value=mock_vacuum), \
         patch("builtins.print") as mock_print:
        await run_probe("1.2.3.4")
    
    mock_print.assert_any_call("\nError: error")


@pytest.mark.asyncio
async def test_run_probe_timeout():
    """Test the probe command when it times out."""
    mock_vacuum = AsyncMock()
    mock_vacuum.probe.side_effect = asyncio.TimeoutError()
    mock_vacuum.__aenter__.return_value = mock_vacuum

    with patch("sharklocal.__main__.VacuumClient", return_value=mock_vacuum), \
         patch("builtins.print") as mock_print:
        await run_probe("1.2.3.4")
    
    mock_print.assert_any_call("\nError: Probe timed out. The device may be offline or blocking local ports.")


# ---------------------------------------------------------------------------
# run_test_logic
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_test_logic_summary():
    """Test the main test logic and result collection."""
    mock_rest_mapping = MagicMock()
    mock_rest_mapping.actions = ["get_status", "get_robot_id", "get_events", "get_wifi_status"]
    mock_rest_mapping.mode_map = {"ready": "docked"}
    
    mock_rest_client = AsyncMock()
    mock_rest_client.supports.side_effect = lambda a: True
    mock_rest_client.call.side_effect = [
        VacuumStatus(mode=VacuumMode.DOCKED, battery_level=100),
        [], # Events
        DeviceInfo(firmware="v1", mac_address="mac", raw={"robot_model": "M1"}), # Robot ID
        DeviceInfo(rssi=-50) # Wi-Fi
    ]

    mock_mqtt_mapping = MagicMock()
    mock_mqtt_mapping.actions = ["get_status", "start_cleaning"]
    mock_mqtt_mapping.modes = {1: "cleaning"}

    mock_mqtt_client = AsyncMock()
    mock_mqtt_client.call.side_effect = [
        VacuumStatus(mode=VacuumMode.CLEANING, battery_level=50),
        True
    ]

    with patch("sharklocal.__main__.list_rest_mappings", return_value=["r1"]), \
         patch("sharklocal.__main__.load_rest_mapping", return_value=mock_rest_mapping), \
         patch("sharklocal.__main__.RESTVacuumClient", return_value=mock_rest_client), \
         patch("sharklocal.__main__.list_mqtt_mappings", return_value=["m1"]), \
         patch("sharklocal.__main__.load_mqtt_mapping", return_value=mock_mqtt_mapping), \
         patch("sharklocal.__main__.MQTTVacuumClient", return_value=mock_mqtt_client):
        
        results = await run_test_logic("1.2.3.4", test_commands=True)
        
    assert results["rest"]["r1"]["actions"]["get_status"] is True
    assert results["mqtt"]["m1"]["actions"]["start_cleaning"] is True
    assert results["model"] == "M1"
    mock_rest_client.close.assert_called()


@pytest.mark.asyncio
async def test_run_test_logic_failed():
    """Test run_test_logic when actions fail."""
    mock_rest_mapping = MagicMock()
    mock_rest_mapping.actions = ["get_status"]
    mock_rest_mapping.mode_map = {}
    
    mock_rest_client = AsyncMock()
    mock_rest_client.call.side_effect = Exception("rest_error")

    mock_mqtt_mapping = MagicMock()
    mock_mqtt_mapping.actions = ["get_status"]
    mock_mqtt_mapping.modes = {}

    mock_mqtt_client = AsyncMock()
    mock_mqtt_client.call.side_effect = Exception("mqtt_error")

    with patch("sharklocal.__main__.list_rest_mappings", return_value=["r1"]), \
         patch("sharklocal.__main__.load_rest_mapping", return_value=mock_rest_mapping), \
         patch("sharklocal.__main__.RESTVacuumClient", return_value=mock_rest_client), \
         patch("sharklocal.__main__.list_mqtt_mappings", return_value=["m1"]), \
         patch("sharklocal.__main__.load_mqtt_mapping", return_value=mock_mqtt_mapping), \
         patch("sharklocal.__main__.MQTTVacuumClient", return_value=mock_mqtt_client):
        
        results = await run_test_logic("1.2.3.4", test_commands=False)
        
    assert results["rest"]["r1"]["actions"]["get_status"] is False
    assert results["mqtt"]["m1"]["actions"]["get_status"] is False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def test_print_status(capsys):
    """Test the status printing helper."""
    status = VacuumStatus(mode=VacuumMode.CLEANING, battery_level=80, charging=True)
    print_status(status)
    captured = capsys.readouterr()
    assert "[STATUS] Mode: cleaning" in captured.out
    assert "Battery: 80% (Charging)" in captured.out


def test_setup_argparse():
    """Test argument parser configuration."""
    parser = setup_argparse()
    args = parser.parse_args(["1.2.3.4", "--cmd", "start", "--transport", "mqtt"])
    assert args.host == "1.2.3.4"
    assert args.cmd == "start"
    assert args.transport == "mqtt"


def test_save_report_custom_filename():
    """Test saving report to a custom file."""
    results = {"model": "M1", "host": "1.2", "rest": {}, "mqtt": {}, "fw": None}
    m = mock_open()
    with patch("builtins.open", m):
        save_report(results, "custom.md")
    m.assert_called_once_with("custom.md", "w")
    m().write.assert_called()


def test_save_report_default_filename():
    """Test saving report to default filename."""
    results = {"model": "M1", "host": "1.2", "rest": {}, "mqtt": {}, "fw": None}
    m = mock_open()
    with patch("builtins.open", m):
        save_report(results, True)
    m.assert_called_once_with("M1.md", "w")


def test_save_report_unknown_model():
    """Test saving report when model is unknown."""
    results = {"model": None, "host": "1.2", "rest": {}, "mqtt": {}, "fw": None}
    m = mock_open()
    with patch("builtins.open", m):
        save_report(results, True)
    # Check that it uses unknown_ prefix
    args, _ = m.call_args
    assert args[0].startswith("unknown_")


@pytest.mark.asyncio
async def test_monitor_vacuum_no_mqtt():
    """Test monitor_vacuum when no mappings are found."""
    with patch("sharklocal.__main__.list_mqtt_mappings", return_value=[]), \
         patch("builtins.print") as mock_print:
        await monitor_vacuum("1.2.3.4")
    mock_print.assert_any_call("No MQTT mappings found.")


@pytest.mark.asyncio
async def test_monitor_vacuum_success():
    """Test monitor_vacuum success (briefly)."""
    mock_vacuum = AsyncMock()
    mock_vacuum.__aenter__.return_value = mock_vacuum
    mock_vacuum.on_status_update = MagicMock()
    
    async def side_effect(*args, **kwargs):
        await asyncio.sleep(0.1)
        raise KeyboardInterrupt()

    with patch("sharklocal.__main__.list_mqtt_mappings", return_value=["m1"]), \
         patch("sharklocal.__main__.VacuumClient", return_value=mock_vacuum), \
         patch("asyncio.sleep", side_effect=side_effect):
        try:
            await monitor_vacuum("1.2.3.4")
        except KeyboardInterrupt:
            pass
    
    mock_vacuum.start_monitoring.assert_called_once()


# ---------------------------------------------------------------------------
# main (CLI entry)
# ---------------------------------------------------------------------------

def test_main_help(capsys):
    """Test that help is displayed when no args are provided."""
    with patch("sys.argv", ["sharklocal"]):
        with pytest.raises(SystemExit):
            main()
    captured = capsys.readouterr()
    assert "usage: sharklocal" in captured.err


def test_main_probe_dispatch():
    """Test that --probe flag dispatches correctly."""
    with patch("sys.argv", ["sharklocal", "1.2.3.4", "--probe"]), \
         patch("sharklocal.__main__.run_probe", new_callable=AsyncMock) as mock_run:
        main()
        mock_run.assert_called_once_with("1.2.3.4")


def test_main_save_report():
    """Test --save-report flag."""
    results = {"host": "1.2", "model": "M1", "rest": {}, "mqtt": {}, "fw": None}
    
    with patch("sys.argv", ["sharklocal", "1.2.3.4", "--save-report", "report.md"]), \
         patch("sharklocal.__main__.run_test_logic", new_callable=AsyncMock, return_value=results), \
         patch("sharklocal.__main__.save_report") as mock_save:
        main()
        
    mock_save.assert_called_once_with(results, "report.md")


def test_main_monitor_dispatch():
    """Test --monitor flag dispatches correctly."""
    with patch("sys.argv", ["sharklocal", "1.2.3.4", "--monitor"]), \
         patch("sharklocal.__main__.monitor_vacuum", new_callable=AsyncMock) as mock_run:
        main()
        mock_run.assert_called_once_with("1.2.3.4")


def test_main_cmd_dispatch():
    """Test --cmd flag dispatches correctly."""
    with patch("sys.argv", ["sharklocal", "1.2.3.4", "--cmd", "start"]), \
         patch("sharklocal.__main__.run_command", new_callable=AsyncMock) as mock_run:
        main()
        mock_run.assert_called_once_with("1.2.3.4", "start", "mqtt")


def test_main_test_dispatch():
    """Test --test flag dispatches correctly."""
    with patch("sys.argv", ["sharklocal", "1.2.3.4", "--test"]), \
         patch("sharklocal.__main__.run_test_logic", new_callable=AsyncMock) as mock_run:
        main()
        mock_run.assert_called_once_with("1.2.3.4", test_commands=False)


def test_main_test_all_dispatch():
    """Test --test-all flag dispatches correctly."""
    with patch("sys.argv", ["sharklocal", "1.2.3.4", "--test-all"]), \
         patch("sharklocal.__main__.run_test_logic", new_callable=AsyncMock) as mock_run:
        main()
        mock_run.assert_called_once_with("1.2.3.4", test_commands=True)


def test_main_keyboard_interrupt(capsys):
    """Test main handling KeyboardInterrupt."""
    with patch("sys.argv", ["sharklocal", "1.2.3.4", "--monitor"]), \
         patch("sharklocal.__main__.monitor_vacuum", side_effect=KeyboardInterrupt):
        main()
    captured = capsys.readouterr()
    assert "Operation cancelled by user." in captured.out


def test_main_fatal_error(capsys):
    """Test main handling fatal errors."""
    with patch("sys.argv", ["sharklocal", "1.2.3.4", "--probe"]), \
         patch("sharklocal.__main__.run_probe", side_effect=Exception("fatal")):
        with pytest.raises(SystemExit):
            main()
    captured = capsys.readouterr()
    assert "FATAL: fatal" in captured.out


# ---------------------------------------------------------------------------
# run_probe — MQTT-only (covers elif res.has_rest: False branch)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_probe_mqtt_only_no_hint(capsys):
    """When only MQTT works (has_rest=False), the REST hint should NOT be printed."""
    probe_res = ProbeResult(mqtt_mapping="m1")  # no rest_mapping → has_rest=False
    mock_vacuum = AsyncMock()
    mock_vacuum.probe.return_value = probe_res
    mock_vacuum.via = "MQTT"
    mock_vacuum.__aenter__.return_value = mock_vacuum

    with patch("sharklocal.__main__.VacuumClient", return_value=mock_vacuum):
        await run_probe("1.2.3.4")

    captured = capsys.readouterr()
    assert "Run with --test" not in captured.out


# ---------------------------------------------------------------------------
# run_test_logic — mode_map branch where norm_m != docked or raw != ready
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_test_logic_mode_map_non_docked_entry(capsys):
    """A mode_map entry where norm_m is not 'docked' covers the False branch of the idle-inject check."""
    mock_rest_mapping = MagicMock()
    mock_rest_mapping.actions = ["get_status"]
    # raw_m="cleaning", norm_m="cleaning" → condition False → idle NOT added
    mock_rest_mapping.mode_map = {"cleaning": "cleaning"}

    mock_rest_client = AsyncMock()
    mock_rest_client.call.side_effect = [
        VacuumStatus(mode=VacuumMode.CLEANING, battery_level=50)
    ]

    with patch("sharklocal.__main__.list_rest_mappings", return_value=["r1"]), \
         patch("sharklocal.__main__.load_rest_mapping", return_value=mock_rest_mapping), \
         patch("sharklocal.__main__.RESTVacuumClient", return_value=mock_rest_client), \
         patch("sharklocal.__main__.list_mqtt_mappings", return_value=[]):
        results = await run_test_logic("1.2.3.4")

    assert "idle" not in results["rest"]["r1"]["modes"]
    assert "cleaning" in results["rest"]["r1"]["modes"]


# ---------------------------------------------------------------------------
# run_test_logic — explore action success (covers elif action=="get_events" False branch)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_test_logic_explore_action_success(capsys):
    """When 'explore' is in mapping.actions and succeeds, the get_events elif evaluates False."""
    mock_rest_mapping = MagicMock()
    mock_rest_mapping.actions = ["explore"]
    mock_rest_mapping.mode_map = {}

    mock_rest_client = AsyncMock()
    # explore returns a generic truthy value (not VacuumStatus/DeviceInfo)
    mock_rest_client.call.side_effect = [True]

    with patch("sharklocal.__main__.list_rest_mappings", return_value=["r1"]), \
         patch("sharklocal.__main__.load_rest_mapping", return_value=mock_rest_mapping), \
         patch("sharklocal.__main__.RESTVacuumClient", return_value=mock_rest_client), \
         patch("sharklocal.__main__.list_mqtt_mappings", return_value=[]):
        results = await run_test_logic("1.2.3.4")

    assert results["rest"]["r1"]["actions"]["explore"] is True


# ---------------------------------------------------------------------------
# run_test_logic — outer REST except (covers line 167 except Exception: pass)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_test_logic_load_rest_mapping_raises(capsys):
    """If load_rest_mapping raises, the outer except silently skips that mapping."""
    with patch("sharklocal.__main__.list_rest_mappings", return_value=["bad_mapping"]), \
         patch("sharklocal.__main__.load_rest_mapping", side_effect=Exception("corrupt yaml")), \
         patch("sharklocal.__main__.list_mqtt_mappings", return_value=[]):
        results = await run_test_logic("1.2.3.4")

    # bad_mapping should not appear in results (exception was swallowed)
    assert "bad_mapping" not in results["rest"]


# ---------------------------------------------------------------------------
# run_test_logic — MQTT commands skipped when test_commands=False
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_test_logic_mqtt_commands_skipped(capsys):
    """When test_commands=False and a command action is in MQTT mapping, it prints SKIPPED."""
    mock_mqtt_mapping = MagicMock()
    mock_mqtt_mapping.actions = ["get_status", "start_cleaning"]
    mock_mqtt_mapping.modes = {}

    mock_mqtt_client = AsyncMock()
    mock_mqtt_client.call.side_effect = [
        VacuumStatus(mode=VacuumMode.DOCKED, battery_level=100, charging=True)
    ]

    with patch("sharklocal.__main__.list_rest_mappings", return_value=[]), \
         patch("sharklocal.__main__.list_mqtt_mappings", return_value=["m1"]), \
         patch("sharklocal.__main__.load_mqtt_mapping", return_value=mock_mqtt_mapping), \
         patch("sharklocal.__main__.MQTTVacuumClient", return_value=mock_mqtt_client):
        results = await run_test_logic("1.2.3.4", test_commands=False)

    captured = capsys.readouterr()
    assert "SKIPPED" in captured.out
    # start_cleaning was not executed, so it should not appear in results
    assert "start_cleaning" not in results["mqtt"]["m1"]["actions"]


# ---------------------------------------------------------------------------
# run_test_logic — MQTT command failure when test_commands=True
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_test_logic_mqtt_command_fails(capsys):
    """When test_commands=True and a command fails, it is recorded as False."""
    mock_mqtt_mapping = MagicMock()
    mock_mqtt_mapping.actions = ["get_status", "start_cleaning"]
    mock_mqtt_mapping.modes = {}

    mock_mqtt_client = AsyncMock()
    mock_mqtt_client.call.side_effect = [
        VacuumStatus(mode=VacuumMode.DOCKED, battery_level=100, charging=True),
        Exception("motor jammed"),
    ]

    with patch("sharklocal.__main__.list_rest_mappings", return_value=[]), \
         patch("sharklocal.__main__.list_mqtt_mappings", return_value=["m1"]), \
         patch("sharklocal.__main__.load_mqtt_mapping", return_value=mock_mqtt_mapping), \
         patch("sharklocal.__main__.MQTTVacuumClient", return_value=mock_mqtt_client):
        results = await run_test_logic("1.2.3.4", test_commands=True)

    captured = capsys.readouterr()
    assert "FAILED" in captured.out
    assert results["mqtt"]["m1"]["actions"]["start_cleaning"] is False


# ---------------------------------------------------------------------------
# main — no action flag, only host (covers parser.print_help() else branch)
# ---------------------------------------------------------------------------


def test_main_no_action_shows_help(capsys):
    """When host is given but no action flag, print_help() is called."""
    with patch("sys.argv", ["sharklocal", "1.2.3.4"]):
        main()
    captured = capsys.readouterr()
    assert "usage: sharklocal" in captured.out or "usage: sharklocal" in captured.err


# ---------------------------------------------------------------------------
# run_test_logic — outer MQTT except (covers line 206 except Exception: pass)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_test_logic_load_mqtt_mapping_raises(capsys):
    """If load_mqtt_mapping raises, the outer except silently skips that mapping."""
    with patch("sharklocal.__main__.list_rest_mappings", return_value=[]), \
         patch("sharklocal.__main__.list_mqtt_mappings", return_value=["bad_mapping"]), \
         patch("sharklocal.__main__.load_mqtt_mapping", side_effect=Exception("bad yaml")):
        results = await run_test_logic("1.2.3.4")

    # bad_mapping should not appear in results (exception was swallowed)
    assert "bad_mapping" not in results["mqtt"]
