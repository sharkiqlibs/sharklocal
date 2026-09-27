"""Tests for sharklocal.models."""

import pytest

from sharklocal.models import (
    DeviceInfo,
    MapFeature,
    MapGrid,
    MapPoint,
    MapPose,
    MapRoom,
    ProbeResult,
    SuctionLevel,
    VacuumEvent,
    VacuumLogEntry,
    VacuumMap,
    VacuumMode,
    VacuumStatus,
)


# ---------------------------------------------------------------------------
# VacuumMode
# ---------------------------------------------------------------------------


def test_vacuum_mode_all_values():
    expected = {"unknown", "cleaning", "returning_to_dock", "docking", "docked", "idle", "exploring", "paused", "error"}
    actual = {m.value for m in VacuumMode}
    assert actual == expected


def test_vacuum_mode_count():
    assert len(VacuumMode) == 9


def test_vacuum_mode_is_str_enum():
    assert VacuumMode.CLEANING == "cleaning"


# ---------------------------------------------------------------------------
# VacuumStatus
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "mode, expected_cleaning",
    [
        (VacuumMode.CLEANING, True),
        (VacuumMode.DOCKED, False),
        (VacuumMode.DOCKING, False),
        (VacuumMode.RETURNING_TO_DOCK, False),
        (VacuumMode.IDLE, False),
        (VacuumMode.EXPLORING, False),
        (VacuumMode.UNKNOWN, False),
    ],
)
def test_vacuum_status_is_cleaning(mode, expected_cleaning):
    status = VacuumStatus(mode=mode)
    assert status.is_cleaning is expected_cleaning


@pytest.mark.parametrize(
    "mode, expected_docked",
    [
        (VacuumMode.DOCKED, True),
        (VacuumMode.DOCKING, True),
        (VacuumMode.CLEANING, False),
        (VacuumMode.RETURNING_TO_DOCK, False),
        (VacuumMode.IDLE, False),
        (VacuumMode.EXPLORING, False),
        (VacuumMode.UNKNOWN, False),
    ],
)
def test_vacuum_status_is_docked(mode, expected_docked):
    status = VacuumStatus(mode=mode)
    assert status.is_docked is expected_docked


def test_vacuum_status_optional_fields_default_none():
    status = VacuumStatus(mode=VacuumMode.IDLE)
    assert status.battery_level is None
    assert status.charging is None


def test_vacuum_status_raw_default_empty_dict():
    status = VacuumStatus(mode=VacuumMode.IDLE)
    assert status.raw == {}


def test_vacuum_status_fields_set():
    status = VacuumStatus(mode=VacuumMode.CLEANING, battery_level=75, charging=False, raw={"x": 1})
    assert status.mode == VacuumMode.CLEANING
    assert status.battery_level == 75
    assert status.charging is False
    assert status.raw == {"x": 1}


# ---------------------------------------------------------------------------
# VacuumEvent
# ---------------------------------------------------------------------------


def test_vacuum_event_fields():
    ts = {"year": 2026, "month": 5, "day": 1}
    event = VacuumEvent(
        id=42,
        type="status_battery_low",
        type_id=1001,
        timestamp=ts,
        current_status="low",
        source_type="operation_unit",
        raw={"extra": True},
    )
    assert event.id == 42
    assert event.type == "status_battery_low"
    assert event.type_id == 1001
    assert event.timestamp == ts
    assert event.current_status == "low"
    assert event.source_type == "operation_unit"
    assert event.raw == {"extra": True}


def test_vacuum_event_raw_default():
    ts = {}
    event = VacuumEvent(id=1, type="t", type_id=0, timestamp=ts, current_status="", source_type="s")
    assert event.raw == {}


# ---------------------------------------------------------------------------
# DeviceInfo
# ---------------------------------------------------------------------------


def test_device_info_all_optional():
    info = DeviceInfo()
    assert info.firmware is None
    assert info.mac_address is None
    assert info.ip_address is None
    assert info.ssid is None
    assert info.rssi is None
    assert info.raw == {}


def test_device_info_fields_set():
    info = DeviceInfo(
        firmware="v1.0",
        mac_address="AA:BB:CC:DD:EE:FF",
        ip_address="192.168.1.10",
        ssid="HomeNet",
        rssi=-50,
        raw={"status": "connected"},
    )
    assert info.firmware == "v1.0"
    assert info.mac_address == "AA:BB:CC:DD:EE:FF"
    assert info.ip_address == "192.168.1.10"
    assert info.ssid == "HomeNet"
    assert info.rssi == -50


# ---------------------------------------------------------------------------
# ProbeResult
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "rest_mapping, mqtt_mapping, has_rest, has_mqtt, is_connected",
    [
        ("sharkiq_v1", "sharkiq_v1", True, True, True),
        ("sharkiq_v1", None, True, False, True),
        (None, "sharkiq_v1", False, True, True),
        (None, None, False, False, False),
    ],
)
def test_probe_result_properties(rest_mapping, mqtt_mapping, has_rest, has_mqtt, is_connected):
    result = ProbeResult(rest_mapping=rest_mapping, mqtt_mapping=mqtt_mapping)
    assert result.has_rest is has_rest
    assert result.has_mqtt is has_mqtt
    assert result.is_connected is is_connected


def test_probe_result_defaults_none():
    result = ProbeResult()
    assert result.rest_mapping is None
    assert result.mqtt_mapping is None


# ---------------------------------------------------------------------------
# SuctionLevel
# ---------------------------------------------------------------------------


def test_suction_level_values():
    assert {level.value for level in SuctionLevel} == {"eco", "normal", "max"}


def test_suction_level_is_str_enum():
    assert SuctionLevel.MAX == "max"


# ---------------------------------------------------------------------------
# VacuumStatus — MQTT-only optional fields
# ---------------------------------------------------------------------------


def test_vacuum_status_mqtt_fields_default_none():
    status = VacuumStatus(mode=VacuumMode.IDLE)
    assert status.job_active is None
    assert status.deep_clean is None
    assert status.recharge_resume is None
    assert status.evac_resume is None
    assert status.map is None


# ---------------------------------------------------------------------------
# MapGrid
# ---------------------------------------------------------------------------


def _grid(room_ids=None) -> MapGrid:
    return MapGrid(
        resolution=0.06,
        width=2,
        height=2,
        origin=MapPoint(-1.0, 0.5),
        cells=b"\x0f\x64\x4b\x00",
        room_ids=room_ids,
    )


@pytest.mark.parametrize(
    "value, wall, floor",
    [
        (0x00, False, True),  # cleaned floor
        (0x0A, False, True),  # floor
        (0x0F, False, True),  # floor
        (0x19, False, True),  # floor
        (0x4B, False, False),  # unknown
        (0x5C, True, False),  # wall
        (0x64, True, False),  # wall
    ],
)
def test_map_grid_cell_classification(value, wall, floor):
    assert MapGrid.is_wall(value) is wall
    assert MapGrid.is_floor(value) is floor


def test_map_grid_cell_lookup_is_row_major():
    grid = _grid()
    assert grid.cell(0, 0) == 0x0F
    assert grid.cell(1, 0) == 0x64
    assert grid.cell(0, 1) == 0x4B
    assert grid.cell(1, 1) == 0x00


def test_map_grid_room_id_lookup():
    assert _grid().room_id(1, 1) is None
    assert _grid(room_ids=b"\x01\x01\x02\x00").room_id(0, 1) == 2


def test_map_grid_constants():
    assert MapGrid.UNKNOWN == 0x4B
    assert MapGrid.CLEANED == 0x00


def test_map_grid_counts_cleaned_cells():
    assert MapGrid.is_cleaned(0x00) is True
    assert MapGrid.is_cleaned(0x0F) is False
    assert _grid().cleaned_cells == 1


# ---------------------------------------------------------------------------
# VacuumMap
# ---------------------------------------------------------------------------


def test_vacuum_map_defaults():
    vacuum_map = VacuumMap(grid=_grid())
    assert vacuum_map.path == []
    assert vacuum_map.poses == []
    assert vacuum_map.persisted is False
    assert vacuum_map.rooms == []
    assert vacuum_map.features == []
    assert vacuum_map.log == []
    assert vacuum_map.robot is None
    assert vacuum_map.clean_time is None


def test_vacuum_map_robot_is_last_pose():
    poses = [MapPose(0.0, 0.0, 0.0), MapPose(1.0, 2.0, 3.1)]
    assert VacuumMap(grid=_grid(), poses=poses).robot == poses[-1]


def test_vacuum_map_cleaned_area_counts_cleaned_cells():
    # _grid() has one cleaned cell.
    assert VacuumMap(grid=_grid()).cleaned_area == pytest.approx(0.06 * 0.06)


def test_vacuum_map_clean_time_sums_the_logged_clean_times():
    log = [
        VacuumLogEntry("DT_NORMAL_CLEAN_TIME", 0, "28"),
        VacuumLogEntry("DT_FOLLOW_CLEAN_TIME", 0, "73"),
        VacuumLogEntry("DT_ESCAPE_CLEAN_TIME", 0, "0"),
        VacuumLogEntry("DT_NORMAL_DOCK_TIME", 0, "42"),
        VacuumLogEntry("DT_WARNING_CODE", 0, "WARN_MM_LOWLIGHT"),
    ]
    assert VacuumMap(grid=_grid(), log=log).clean_time == 101


def test_map_room_and_feature_and_log_entry_fields():
    room = MapRoom(name="Kitchen", polygon=[MapPoint(0, 0)])
    assert room.selected is False
    assert room.coverage is None
    feature = MapFeature(kind="door", points=[MapPoint(0, 0), MapPoint(1, 0)])
    assert feature.kind == "door"
    entry = VacuumLogEntry(key="DT_WARNING_CODE", time=1789867008, code="WARN_MM_LOWLIGHT")
    assert entry.code == "WARN_MM_LOWLIGHT"
