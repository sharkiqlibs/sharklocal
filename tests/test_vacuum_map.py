"""Tests for sharklocal.vacuum_map."""

from __future__ import annotations

import base64
import dataclasses
import json
import struct
from pathlib import Path

import pytest

from sharklocal import protobuf
from sharklocal.models import MapGrid, MapPoint, MapPose, MapRoom, VacuumMap
from sharklocal.vacuum_map import (
    FIELD_MAP,
    FIELD_PERSISTED_FLAG,
    SPOT_HALF_SIZE,
    SPOT_ROOM_NAME,
    spot_polygon,
    decode_map,
    encode_room_selection,
    encode_spot_selection,
    has_map,
)

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Helpers — real captured frames and hand-built messages
# ---------------------------------------------------------------------------


def _fixture(name: str) -> bytes:
    """Return the decoded bytes of a base64 fixture captured from a real robot."""
    return base64.b64decode((FIXTURES / name).read_text().strip())


def _fields(data: bytes):
    return protobuf.decode_fields(data)


def _point_f32(x: float, y: float) -> bytes:
    return protobuf.encode_bytes_field(
        1, protobuf.encode_float_field(1, x) + protobuf.encode_float_field(2, y)
    )


def _grid_message(width: int = 2, height: int = 2, cells: bytes = b"\x0f\x64\x4b\x00") -> bytes:
    origin = protobuf.encode_float_field(1, -1.0) + protobuf.encode_float_field(2, 0.5)
    return (
        protobuf.encode_float_field(1, 0.06)
        + protobuf.encode_bytes_field(2, origin)
        + protobuf.encode_varint_field(3, width)
        + protobuf.encode_varint_field(4, height)
        + protobuf.encode_bytes_field(6, cells)
    )


def _int16_list(values: list, scale: float = 0.002) -> bytes:
    raw = struct.pack(f"<{len(values)}h", *values)
    return (
        protobuf.encode_float_field(1, scale)
        + protobuf.encode_varint_field(2, 2)
        + protobuf.encode_bytes_field(3, raw)
    )


def _frame(map_fields: bytes, *, persisted: bool = False) -> dict:
    frame = protobuf.encode_varint_field(4, 6) + protobuf.encode_bytes_field(FIELD_MAP, map_fields)
    if persisted:
        frame = protobuf.encode_varint_field(FIELD_PERSISTED_FLAG, 1) + frame
    return _fields(frame)


# ---------------------------------------------------------------------------
# has_map / decode_map — frames without a grid
# ---------------------------------------------------------------------------


def test_has_map_false_without_field_7():
    assert has_map(_fields(protobuf.encode_varint_field(4, 14))) is False


def test_has_map_false_when_field_7_has_no_grid():
    frame = _fields(protobuf.encode_bytes_field(FIELD_MAP, protobuf.encode_varint_field(1, 1)))
    assert has_map(frame) is False


def test_has_map_false_when_field_7_is_not_bytes():
    assert has_map({FIELD_MAP: [5]}) is False


def test_decode_map_returns_none_without_field_7():
    assert decode_map(_fields(protobuf.encode_varint_field(4, 14))) is None


def test_decode_map_returns_none_when_field_7_is_not_bytes():
    assert decode_map({FIELD_MAP: [5]}) is None


def test_decode_map_returns_none_without_grid():
    frame = _fields(protobuf.encode_bytes_field(FIELD_MAP, protobuf.encode_varint_field(1, 1)))
    assert decode_map(frame) is None


# ---------------------------------------------------------------------------
# decode_map — minimal hand-built frames
# ---------------------------------------------------------------------------


def test_decode_grid_geometry_and_cells():
    vacuum_map = decode_map(_frame(protobuf.encode_bytes_field(5, _grid_message())))
    grid = vacuum_map.grid
    assert (grid.width, grid.height) == (2, 2)
    assert grid.resolution == pytest.approx(0.06)
    assert (grid.origin.x, grid.origin.y) == (-1.0, 0.5)
    assert grid.cells == b"\x0f\x64\x4b\x00"
    assert grid.room_ids is None
    assert grid.cell(1, 0) == 0x64
    assert grid.room_id(0, 0) is None


def test_decode_live_frame_defaults():
    vacuum_map = decode_map(_frame(protobuf.encode_bytes_field(5, _grid_message())))
    assert vacuum_map.persisted is False
    assert vacuum_map.path == []
    assert vacuum_map.poses == []
    assert vacuum_map.robot is None
    assert vacuum_map.dock is None
    assert vacuum_map.rooms == []
    assert vacuum_map.features == []
    assert vacuum_map.log == []
    assert vacuum_map.clean_time is None
    assert vacuum_map.map_id is None
    assert vacuum_map.name is None


def test_decode_path_and_poses_scale_int16():
    # path: (100, -50) -> (0.2, -0.1); poses: (10, 20, 1570) -> heading ~ pi
    fields = (
        protobuf.encode_bytes_field(5, _grid_message())
        + protobuf.encode_bytes_field(8, _int16_list([100, -50]))
        + protobuf.encode_bytes_field(10, _int16_list([10, 20, 1570]))
    )
    vacuum_map = decode_map(_frame(fields))
    assert vacuum_map.path == [MapPoint(pytest.approx(0.2), pytest.approx(-0.1))]
    assert vacuum_map.robot.x == pytest.approx(0.02)
    assert vacuum_map.robot.y == pytest.approx(0.04)
    assert vacuum_map.robot.heading == pytest.approx(3.14)


def test_decode_ignores_trailing_partial_tuple():
    # Five int16s cannot make whole (x, y) pairs — the odd one is dropped.
    fields = protobuf.encode_bytes_field(5, _grid_message()) + protobuf.encode_bytes_field(
        8, _int16_list([1, 2, 3, 4, 5])
    )
    assert len(decode_map(_frame(fields)).path) == 2


def test_decode_persisted_flag_id_name_and_dock():
    dock = (
        protobuf.encode_float_field(1, -0.5)
        + protobuf.encode_float_field(2, 0.25)
        + protobuf.encode_float_field(3, -0.05)
    )
    fields = (
        protobuf.encode_string_field(2, "unnamed")
        + protobuf.encode_string_field(3, "3CDBBC59")
        + protobuf.encode_bytes_field(5, _grid_message())
        + protobuf.encode_bytes_field(7, dock)
    )
    vacuum_map = decode_map(_frame(fields, persisted=True))
    assert vacuum_map.persisted is True
    assert vacuum_map.map_id == "3CDBBC59"
    assert vacuum_map.name == "unnamed"
    assert vacuum_map.dock == MapPose(-0.5, 0.25, pytest.approx(-0.05))


def test_decode_room_record():
    polygon = _point_f32(0.0, 0.0) + _point_f32(1.0, 0.0) + _point_f32(1.0, 1.0) + _point_f32(0.0, 1.0)
    room = (
        protobuf.encode_string_field(2, "Kitchen")
        + protobuf.encode_string_field(3, "Kitchen")
        + protobuf.encode_bytes_field(4, polygon)
        + protobuf.encode_varint_field(5, 1)
        + protobuf.encode_float_field(6, 0.5)
    )
    bare = protobuf.encode_bytes_field(4, b"")
    fields = (
        protobuf.encode_bytes_field(5, _grid_message())
        + protobuf.encode_bytes_field(15, room)
        + protobuf.encode_bytes_field(15, bare)
    )
    rooms = decode_map(_frame(fields)).rooms
    assert rooms[0].name == "Kitchen"
    assert rooms[0].selected is True
    assert rooms[0].coverage == pytest.approx(0.5)
    assert rooms[0].polygon == [MapPoint(0.0, 0.0), MapPoint(1.0, 0.0), MapPoint(1.0, 1.0), MapPoint(0.0, 1.0)]
    # A record with no name, no selection and no coverage decodes to safe defaults.
    assert rooms[1] == MapRoom(name="", polygon=[], selected=False, coverage=None)


def test_decode_features_edge_and_door_and_skips_malformed():
    polyline = _point_f32(0.0, 0.0) + _point_f32(2.0, 0.0)
    edge = protobuf.encode_string_field(2, "edge") + protobuf.encode_bytes_field(4, polyline)
    door = protobuf.encode_string_field(2, "door") + protobuf.encode_bytes_field(4, polyline)
    no_kind = protobuf.encode_bytes_field(4, polyline)
    no_points = protobuf.encode_string_field(2, "edge")
    fields = protobuf.encode_bytes_field(5, _grid_message())
    for record in (edge, door, no_kind, no_points):
        fields += protobuf.encode_bytes_field(28, record)
    features = decode_map(_frame(fields)).features
    assert [(f.kind, len(f.points)) for f in features] == [("edge", 2), ("door", 2)]


def test_decode_room_ids_only_when_sizes_match():
    grid = _grid_message()
    matching = protobuf.encode_bytes_field(21, protobuf.encode_bytes_field(19, b"\x01\x01\x02\x00"))
    wrong_size = protobuf.encode_bytes_field(21, protobuf.encode_bytes_field(19, b"\x01"))
    no_raster = protobuf.encode_bytes_field(21, protobuf.encode_varint_field(1, 1))

    with_ids = decode_map(_frame(protobuf.encode_bytes_field(5, grid) + matching))
    assert with_ids.grid.room_ids == b"\x01\x01\x02\x00"
    assert with_ids.grid.room_id(0, 1) == 2

    assert decode_map(_frame(protobuf.encode_bytes_field(5, grid) + wrong_size)).grid.room_ids is None
    assert decode_map(_frame(protobuf.encode_bytes_field(5, grid) + no_raster)).grid.room_ids is None


def test_decode_job_start_only():
    stats = (
        protobuf.encode_varint_field(1, 1789867008)
        + protobuf.encode_varint_field(3, 335)
        + protobuf.encode_varint_field(6, 100)
    )
    fields = protobuf.encode_bytes_field(5, _grid_message()) + protobuf.encode_bytes_field(11, stats)
    vacuum_map = decode_map(_frame(fields))
    assert vacuum_map.job_started == 1789867008
    assert vacuum_map.job_minutes is None
    assert not hasattr(vacuum_map, "job_duration")


def test_decode_job_minutes_and_clean_time_without_a_log():
    stats = protobuf.encode_varint_field(1, 1790503168) + protobuf.encode_varint_field(2, 33)
    fields = protobuf.encode_bytes_field(5, _grid_message()) + protobuf.encode_bytes_field(11, stats)
    vacuum_map = decode_map(_frame(fields))
    assert vacuum_map.job_minutes == 33
    assert vacuum_map.clean_time == 33 * 60  # no log: the summary's minutes


@pytest.mark.parametrize("map_type, persisted", [(4, True), (1, False), (2, False)])
def test_floor_type_4_is_persisted_without_the_report_flag(map_type, persisted):
    fields = protobuf.encode_varint_field(4, map_type) + protobuf.encode_bytes_field(5, _grid_message())
    vacuum_map = decode_map(_frame(fields))
    assert vacuum_map.persisted is persisted
    assert vacuum_map.report is False


def test_report_flag_marks_a_report():
    vacuum_map = decode_map(_frame(protobuf.encode_bytes_field(5, _grid_message()), persisted=True))
    assert vacuum_map.persisted is True
    assert vacuum_map.report is True


# ---------------------------------------------------------------------------
# decode_map — event log (field 20.3.6)
# ---------------------------------------------------------------------------


def _log_frame(log_field_20: bytes) -> dict:
    return _frame(protobuf.encode_bytes_field(5, _grid_message()) + protobuf.encode_bytes_field(20, log_field_20))


def _log_message(text: bytes) -> bytes:
    return protobuf.encode_bytes_field(3, protobuf.encode_bytes_field(6, text))


def test_decode_log_entries():
    entries = [
        {"key": "DT_STATE_CHANGE", "time": "1789867007s", "code": "SYS_ST_CLEANING"},
        {"key": "DT_WARNING_CODE", "time": "1789867008s", "code": "WARN_MM_LOWLIGHT"},
        {"key": "DT_VERSION_MCU", "time": "0s", "code": "Lidar2_0M1.0.91"},
        "not-a-dict",
        {"key": "DT_ODD_TIME", "time": "soon", "code": "x"},
    ]
    log = decode_map(_log_frame(_log_message(json.dumps(entries).encode()))).log
    assert [(e.key, e.time, e.code) for e in log] == [
        ("DT_STATE_CHANGE", 1789867007, "SYS_ST_CLEANING"),
        ("DT_WARNING_CODE", 1789867008, "WARN_MM_LOWLIGHT"),
        ("DT_VERSION_MCU", 0, "Lidar2_0M1.0.91"),
        ("DT_ODD_TIME", 0, "x"),
    ]


def test_decode_log_tolerates_missing_or_invalid_parts():
    assert decode_map(_log_frame(protobuf.encode_varint_field(1, 1))).log == []
    assert decode_map(_log_frame(protobuf.encode_bytes_field(3, protobuf.encode_varint_field(1, 1)))).log == []
    assert decode_map(_log_frame(_log_message(b"{not json"))).log == []


# ---------------------------------------------------------------------------
# decode_map — real captured frames
# ---------------------------------------------------------------------------


def test_empty_grid_at_job_start_is_no_map():
    # The first live frame of a job carries a grid with no resolution, size or
    # cells; drawing it divided by zero.
    fields = _fields(_fixture("sharkiq_empty_live_map_frame.b64"))
    assert 7 in fields
    assert has_map(fields) is False
    assert decode_map(fields) is None


def test_decode_real_live_frame():
    vacuum_map = decode_map(_fields(_fixture("sharkiq_live_map_frame.b64")))
    assert vacuum_map.persisted is False
    assert (vacuum_map.grid.width, vacuum_map.grid.height) == (191, 106)
    assert len(vacuum_map.grid.cells) == 191 * 106
    assert vacuum_map.grid.resolution == pytest.approx(0.06, abs=1e-6)
    assert len(vacuum_map.path) == 486
    assert len(vacuum_map.poses) == 254
    # Path and pose logs describe the same trajectory; both end at the robot.
    assert vacuum_map.path[-1].x == pytest.approx(vacuum_map.robot.x, abs=0.2)
    assert vacuum_map.path[-1].y == pytest.approx(vacuum_map.robot.y, abs=0.2)
    assert vacuum_map.rooms == []


def test_decode_real_persisted_frame():
    vacuum_map = decode_map(_fields(_fixture("sharkiq_persisted_map_frame.b64")))
    assert vacuum_map.persisted is True
    assert vacuum_map.map_id == "3CDBBC59"
    assert vacuum_map.name == "unnamed"
    assert [room.name for room in vacuum_map.rooms] == ["Bathroom. ", "Room", "Laundry Room", "Hallway"]
    assert vacuum_map.rooms[0].selected is True
    assert vacuum_map.rooms[0].coverage == pytest.approx(0.848, abs=1e-3)
    assert all(len(room.polygon) == 4 for room in vacuum_map.rooms)
    assert [(f.kind, len(f.points)) for f in vacuum_map.features] == [
        ("edge", 119), ("edge", 31), ("edge", 105), ("door", 2), ("door", 2),
    ]
    assert vacuum_map.dock.x == pytest.approx(-0.52, abs=0.01)
    assert len(vacuum_map.grid.room_ids) == len(vacuum_map.grid.cells)
    assert set(vacuum_map.grid.room_ids) == {0, 1, 2, 3}
    # The robot's log says 28 s normal + 73 s wall-follow cleaning.
    assert vacuum_map.clean_time == 101
    assert vacuum_map.cleaned_area == pytest.approx(3.17, abs=0.01)
    assert len(vacuum_map.log) == 83
    assert [e.code for e in vacuum_map.log if e.key == "DT_WARNING_CODE"] == ["WARN_MM_LOWLIGHT"]
    assert vacuum_map.report is True
    assert vacuum_map.job_minutes == 3  # a 216 s job, docking included


def test_decode_real_requested_frame():
    # The reply to request_map() while docked, after a whole-home job whose
    # end-of-job frame Home Assistant missed: the same saved map with that
    # job's path and summary, but no event log and no report flag.
    vacuum_map = decode_map(_fields(_fixture("sharkiq_requested_map_frame.b64")))
    assert vacuum_map.persisted is True
    assert vacuum_map.report is False
    assert vacuum_map.map_id == "3CDBBC59"
    assert [room.name for room in vacuum_map.rooms] == ["Bathroom. ", "Room", "Laundry Room", "Hallway"]
    assert vacuum_map.job_started == 1790503168
    assert vacuum_map.job_minutes == 33
    assert vacuum_map.log == []
    assert vacuum_map.clean_time == 33 * 60
    assert len(vacuum_map.path) == 1671
    assert vacuum_map.cleaned_area == pytest.approx(25.61, abs=0.01)
    # A whole-home run: all but 3 of its 1671 path points land on cleaned cells.
    grid = vacuum_map.grid
    on_cleaned = sum(
        grid.cell(int((p.x - grid.origin.x) / grid.resolution), int((p.y - grid.origin.y) / grid.resolution))
        == MapGrid.CLEANED
        for p in vacuum_map.path
    )
    assert on_cleaned == 1668


@pytest.mark.parametrize("name", ["sharkiq_live_map_frame.b64", "sharkiq_persisted_map_frame.b64"])
def test_cleaned_cells_are_where_the_robot_went(name):
    # The evidence for CLEANED = 0x00: every point of the cleaned path, in
    # every captured frame, lands on a cell of that value.
    vacuum_map = decode_map(_fields(_fixture(name)))
    grid = vacuum_map.grid
    for point in vacuum_map.path:
        col = int((point.x - grid.origin.x) / grid.resolution)
        row = int((point.y - grid.origin.y) / grid.resolution)
        assert grid.cell(col, row) == MapGrid.CLEANED


def _with_saved_spot(vacuum_map: VacuumMap) -> VacuumMap:
    """The map as the robot saves it after a Spot Clean (measured 2026-09-26)."""
    spot = MapRoom(SPOT_ROOM_NAME, spot_polygon(2.74, 0.02), selected=True, coverage=1.0)
    return dataclasses.replace(vacuum_map, rooms=[*vacuum_map.rooms, spot])


def test_saved_spot_zone_is_not_a_room(persisted_map):
    saved = _with_saved_spot(persisted_map)
    assert saved.spot.name == SPOT_ROOM_NAME
    assert saved.spot.selected is True
    assert [r.name for r in saved.named_rooms] == [r.name for r in persisted_map.rooms]
    assert persisted_map.spot is None


def test_saved_spot_zone_is_not_uploaded_with_a_room_clean(persisted_map):
    saved = _with_saved_spot(persisted_map)
    assert encode_room_selection(saved, ["Bathroom. "]) == _fixture("sharkiq_cmd_room_clean.b64")
    with pytest.raises(ValueError, match="PinDrop"):
        encode_room_selection(saved, [SPOT_ROOM_NAME])


def test_new_spot_replaces_a_saved_one(persisted_map):
    saved = _with_saved_spot(persisted_map)
    assert encode_spot_selection(saved, 1.0, 2.0) == encode_spot_selection(persisted_map, 1.0, 2.0)


# ---------------------------------------------------------------------------
# encode_room_selection / encode_spot_selection
# ---------------------------------------------------------------------------


@pytest.fixture()
def persisted_map() -> VacuumMap:
    return decode_map(_fields(_fixture("sharkiq_persisted_map_frame.b64")))


def test_encode_room_selection_matches_app_capture(persisted_map):
    assert encode_room_selection(persisted_map, ["Bathroom. "]) == _fixture("sharkiq_cmd_room_clean.b64")


def test_encode_room_selection_deep_matches_app_capture(persisted_map):
    expected = _fixture("sharkiq_cmd_room_clean_matrix.b64")
    assert encode_room_selection(persisted_map, ["Bathroom. "], deep=True) == expected


def test_map_survives_json_round_trip(persisted_map):
    restored = VacuumMap.from_dict(json.loads(json.dumps(persisted_map.to_dict())))
    persisted_map.raw = {}
    assert restored == persisted_map


def test_map_stored_before_report_existed_reads_as_a_report(persisted_map):
    # Before request_map() only end-of-job reports were persisted.
    stored = json.loads(json.dumps(persisted_map.to_dict()))
    del stored["report"], stored["job_minutes"]
    restored = VacuumMap.from_dict(stored)
    assert restored.report is True
    assert restored.job_minutes is None


def test_requested_map_survives_json_round_trip():
    requested = decode_map(_fields(_fixture("sharkiq_requested_map_frame.b64")))
    restored = VacuumMap.from_dict(json.loads(json.dumps(requested.to_dict())))
    assert (restored.report, restored.job_minutes) == (False, 33)


def test_stored_map_still_builds_the_app_room_command(persisted_map):
    # The reason the map is stored at all: after a restart, room cleaning must
    # send exactly what the app sends, from the stored copy.
    restored = VacuumMap.from_dict(json.loads(json.dumps(persisted_map.to_dict())))
    expected = _fixture("sharkiq_cmd_room_clean_matrix.b64")
    assert encode_room_selection(restored, ["Bathroom. "], deep=True) == expected


def test_encode_room_selection_lists_every_chosen_room(persisted_map):
    payload = encode_room_selection(persisted_map, ["Bathroom. ", "Hallway"])
    selection = _fields(_fields(payload)[41][0])
    assert selection[1] == [b"Bathroom. ", b"Hallway"]
    assert selection[3] == [b"3CDBBC59"]
    assert _fields(payload)[16] == [11]


def test_encode_room_selection_rejects_unknown_room(persisted_map):
    with pytest.raises(ValueError, match="Unknown room"):
        encode_room_selection(persisted_map, ["Attic"])


def test_encode_room_selection_requires_map_id(persisted_map):
    persisted_map.map_id = None
    with pytest.raises(ValueError, match="no id"):
        encode_room_selection(persisted_map, ["Bathroom. "])


def test_encode_spot_selection_appends_pindrop_room(persisted_map):
    app = _fixture("sharkiq_cmd_spot_clean.b64")
    app_rooms = _fields(_fields(app)[6][0])[15]
    app_spot = _fields(app_rooms[-1])
    app_polygon = [_fields(p) for p in _fields(app_spot[4][0])[1]]
    centre_x = sum(protobuf.float32(p[1][0]) for p in app_polygon) / 4
    centre_y = sum(protobuf.float32(p[2][0]) for p in app_polygon) / 4

    ours = encode_spot_selection(persisted_map, centre_x, centre_y)
    our_rooms = _fields(_fields(ours)[6][0])[15]
    assert our_rooms[:-1] == app_rooms[:-1]

    spot = _fields(our_rooms[-1])
    assert spot[2] == [SPOT_ROOM_NAME.encode()]
    assert (spot[7], spot[8], spot[9], spot[10]) == ([2], [1], [0], [2])
    corners = [_fields(p) for p in _fields(spot[4][0])[1]]
    assert protobuf.float32(corners[0][1][0]) == pytest.approx(centre_x - SPOT_HALF_SIZE, abs=1e-5)
    assert protobuf.float32(corners[2][2][0]) == pytest.approx(centre_y - SPOT_HALF_SIZE, abs=1e-5)
    assert _fields(_fields(ours)[41][0])[1] == [SPOT_ROOM_NAME.encode()]


def test_encode_spot_selection_requires_map_id(persisted_map):
    persisted_map.map_id = None
    with pytest.raises(ValueError, match="no id"):
        encode_spot_selection(persisted_map, 0.0, 0.0)
