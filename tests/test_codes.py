"""Tests for sharklocal.codes and the live error/warning fields."""

import base64
from pathlib import Path

import pytest

from sharklocal import codes, protobuf
from sharklocal.mappings import load_mqtt_mapping
from sharklocal.models import VacuumMode
from sharklocal.mqtt_client import _decode_sharkiq_protobuf_v1

FIXTURES = Path(__file__).parent / "fixtures"


def _status_frame() -> bytes:
    return base64.b64decode((FIXTURES / "sharkiq_status_frame.b64").read_text().strip())


def test_names_agree_with_the_event_log():
    # The log writes these as strings; the schema numbers them.
    assert codes.WARNING_CODES[43] == "WARN_MM_LOWLIGHT"
    assert codes.DOCK_EVENTS[7] == "DE_USR_CTR_DOCK"
    assert codes.DOCK_EVENTS[8] == "DE_CLEAN_FINISH"
    assert codes.SYSTEM_STATES[13] == "SYS_ST_CHARGING"
    assert codes.ERROR_CODES[0] == "ERROR_NONE"


def test_unknown_numbers_stay_visible():
    assert codes.names(codes.WARNING_CODES, [43, 9999]) == ["WARN_MM_LOWLIGHT", "UNKNOWN_9999"]


def _decode(extra: bytes):
    mapping = load_mqtt_mapping("sharkiq_v1")
    return _decode_sharkiq_protobuf_v1(_status_frame() + extra, mapping.modes)


def test_a_real_status_frame_has_no_active_errors():
    status = _decode(b"")
    assert status.errors == []
    assert status.warnings == []


def test_packed_errors_and_warnings_are_decoded():
    packed = protobuf.encode_bytes_field(5, bytes([21, 64])) + protobuf.encode_bytes_field(6, bytes([43]))
    status = _decode(packed)
    assert status.errors == [21, 64]
    assert codes.names(codes.ERROR_CODES, status.errors)[0] == codes.ERROR_CODES[21]
    assert status.warnings == [43]


def test_unpacked_errors_are_decoded():
    status = _decode(protobuf.encode_varint_field(5, 64) + protobuf.encode_varint_field(5, 150))
    assert status.errors == [64, 150]


@pytest.mark.parametrize(
    "state, mode",
    [
        (3, VacuumMode.IDLE),
        (4, VacuumMode.PAUSED),
        (5, VacuumMode.ERROR),
        (6, VacuumMode.CLEANING),
        (7, VacuumMode.RETURNING_TO_DOCK),
        (8, VacuumMode.CLEANING),
        (13, VacuumMode.DOCKED),  # charging on the dock: observed after every job
        (14, VacuumMode.DOCKED),
        (16, VacuumMode.CLEANING),
    ],
)
def test_system_states_map_to_modes(state, mode):
    assert load_mqtt_mapping("sharkiq_v1").modes[state] == mode.value


def _fixture_status(name: str):
    mapping = load_mqtt_mapping("sharkiq_v1")
    payload = base64.b64decode((FIXTURES / name).read_text().strip())
    return _decode_sharkiq_protobuf_v1(payload, mapping.modes)


def test_live_frame_mid_clean():
    status = _fixture_status("sharkiq_live_map_frame.b64")
    assert status.state == 6
    assert status.mode == VacuumMode.CLEANING
    assert status.charging is False
    assert (status.fan_speed, status.brushroll_speed, status.side_brush_speed) == (82, 54, 44)
    assert codes.RELOCATION_STATES[status.relocation] == "RS_SUCCESS"
    # A dark basement: the live warning field reports low light.
    assert codes.names(codes.WARNING_CODES, status.warnings) == ["WARN_LOW_LIGHT", "WARN_LOW_LIGHT"]


def test_end_of_job_frame_agrees_with_its_own_log():
    status = _fixture_status("sharkiq_persisted_map_frame.b64")
    assert codes.SYSTEM_STATES[status.state] == "SYS_ST_CHARGING"
    assert status.mode == VacuumMode.DOCKED
    assert status.charging is True
    # The live warning code and the event log's DT_WARNING_CODE name agree.
    assert codes.names(codes.WARNING_CODES, status.warnings) == ["WARN_MM_LOWLIGHT"]
    assert [e.code for e in status.map.log if e.key == "DT_WARNING_CODE"] == ["WARN_MM_LOWLIGHT"]


def test_docked_and_full():
    status = _fixture_status("sharkiq_status_frame.b64")
    assert codes.SYSTEM_STATES[status.state] == "SYS_ST_BATTERY_FULL"
    assert status.charging is False
    assert status.battery_level == 100
    assert status.temperature == 20
    assert codes.WIFI_STATES[status.wifi_state] == "WIFI_CONNECTED"
    assert status.fan_speed == 0


def test_feature_toggles():
    status = _decode(protobuf.encode_varint_field(43, 1) + protobuf.encode_varint_field(44, 2))
    assert status.clean_edge is True
    assert codes.CARPET_DETECT_MODES[status.carpet_detect] == "CD_AUTO"
    assert _decode(protobuf.encode_varint_field(43, 2)).clean_edge is False


def test_mid_job_log_entries_are_decoded():
    # A real frame from a spot clean: field 34 streams event-log entries.
    status = _fixture_status("sharkiq_diagnose_frame.b64")
    assert status.log_entries
    assert all(e.key.startswith("DT_") for e in status.log_entries)
    assert any(e.key == "DT_WATER_TANK" for e in status.log_entries)


def test_frames_without_log_entries_say_so():
    assert _fixture_status("sharkiq_status_frame.b64").log_entries is None
    garbled = protobuf.encode_bytes_field(34, b"\xff\xff") + protobuf.encode_varint_field(34, 1)
    assert _decode(garbled).log_entries == []
    not_a_list = protobuf.encode_bytes_field(34, protobuf.encode_bytes_field(5, b'{"key": "x"}'))
    assert _decode(not_a_list).log_entries == []
