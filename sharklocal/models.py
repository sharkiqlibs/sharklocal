"""Data models for vacuum state and device information."""

from __future__ import annotations

import base64
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# The app models a Spot Clean as an extra room of this name: a ~1.5 m square
# around the pin. The robot keeps it in its saved map afterwards, marked as the
# room the last job cleaned, until another room definition replaces it.
SPOT_ROOM_NAME = "PinDrop"


class VacuumMode(str, Enum):
    """Normalized operating modes across all transports."""

    UNKNOWN = "unknown"
    CLEANING = "cleaning"
    RETURNING_TO_DOCK = "returning_to_dock"
    DOCKING = "docking"
    DOCKED = "docked"
    IDLE = "idle"  # Powered on but not cleaning and not on the charging dock
    EXPLORING = "exploring"  # Mapping/exploration run in progress
    PAUSED = "paused"  # A job paused mid-way
    ERROR = "error"  # Stopped by a fault


class SuctionLevel(str, Enum):
    """Suction power levels, named as in the SharkClean app."""

    ECO = "eco"
    NORMAL = "normal"
    MAX = "max"


@dataclass
class VacuumStatus:
    """Normalized vacuum status, independent of transport protocol.

    The optional fields after ``raw`` are only populated by transports that
    carry them (currently the SharkIQ MQTT protocol) and stay ``None``
    otherwise. ``map`` is set only on frames that include map data.
    """

    mode: VacuumMode
    battery_level: Optional[int] = None
    charging: Optional[bool] = None
    raw: Dict[str, Any] = field(default_factory=dict)
    job_active: Optional[bool] = None
    deep_clean: Optional[bool] = None  # Matrix / spot clean in progress
    recharge_resume: Optional[bool] = None
    evac_resume: Optional[bool] = None
    map: Optional["VacuumMap"] = None
    # Codes active now (SharkIQ fields 5 and 6); names in sharklocal.codes.
    errors: Optional[List[int]] = None
    warnings: Optional[List[int]] = None
    # SharkIQ device info (field 9), live motor speeds (field 16) and feature
    # status, each None when the frame does not carry it.
    state: Optional[int] = None  # system state (codes.SYSTEM_STATES)
    temperature: Optional[int] = None  # degrees C
    wifi_state: Optional[int] = None  # codes.WIFI_STATES
    wifi_link_quality: Optional[int] = None
    wifi_signal: Optional[int] = None
    water_level: Optional[int] = None
    dust_level: Optional[int] = None
    ip_address: Optional[str] = None
    fan_speed: Optional[int] = None  # suction motor, live
    brushroll_speed: Optional[int] = None
    side_brush_speed: Optional[int] = None
    clean_edge: Optional[bool] = None  # CleanEdge (fan jet) enabled
    carpet_detect: Optional[int] = None  # codes.CARPET_DETECT_MODES
    relocation: Optional[int] = None  # codes.RELOCATION_STATES
    # Event-log entries streamed mid-job (field 34), when the frame has any.
    log_entries: Optional[List["VacuumLogEntry"]] = None

    @property
    def is_cleaning(self) -> bool:
        return self.mode == VacuumMode.CLEANING

    @property
    def is_docked(self) -> bool:
        return self.mode in (VacuumMode.DOCKED, VacuumMode.DOCKING)


# ---------------------------------------------------------------------------
# Map models (SharkIQ MQTT map frames)
# ---------------------------------------------------------------------------


@dataclass
class MapPoint:
    """A point in map world coordinates, in metres."""

    x: float
    y: float


@dataclass
class MapPose:
    """A position with heading, in metres and radians (0 = +x, anticlockwise)."""

    x: float
    y: float
    heading: float


@dataclass
class MapGrid:
    """An occupancy grid, row-major from the map origin (bottom-left).

    ``cells`` holds one byte per cell; ``room_ids`` (persisted maps only) holds
    one room segment id per cell, ``0`` meaning unassigned. World-to-cell:
    ``col = (x - origin.x) / resolution``, ``row = (y - origin.y) / resolution``.
    """

    resolution: float  # metres per cell
    width: int
    height: int
    origin: MapPoint
    cells: bytes
    room_ids: Optional[bytes] = None

    # Cell values observed in SharkIQ grids. ``CLEANED`` marks floor covered
    # by the current (or, on a persisted map, the last) job: every point of
    # the cleaned path lands on one, in every captured frame.
    UNKNOWN = 0x4B
    CLEANED = 0x00

    @staticmethod
    def is_wall(value: int) -> bool:
        """``True`` for wall/obstacle cells (``0x50`` and above)."""
        return value >= 0x50

    @staticmethod
    def is_floor(value: int) -> bool:
        """``True`` for free-floor cells (explored, not wall), cleaned or not."""
        return value < 0x4B

    @staticmethod
    def is_cleaned(value: int) -> bool:
        """``True`` for floor covered by the job."""
        return value == MapGrid.CLEANED

    @property
    def cleaned_cells(self) -> int:
        """Number of cells covered by the job."""
        return self.cells.count(MapGrid.CLEANED)

    def cell(self, col: int, row: int) -> int:
        """Return the occupancy value at ``(col, row)``."""
        return self.cells[row * self.width + col]

    def room_id(self, col: int, row: int) -> Optional[int]:
        """Return the room segment id at ``(col, row)``, or ``None`` if unavailable."""
        if self.room_ids is None:
            return None
        return self.room_ids[row * self.width + col]


@dataclass
class MapRoom:
    """A named room as drawn in the app, with its bounding polygon."""

    name: str
    polygon: List[MapPoint]
    selected: bool = False  # Included in the most recent job
    coverage: Optional[float] = None  # Fraction cleaned in the most recent job


@dataclass
class MapFeature:
    """A vector feature of the persisted map — a wall outline or a door."""

    kind: str  # "edge" or "door"
    points: List[MapPoint]


@dataclass
class VacuumLogEntry:
    """One entry of the robot's own event log, carried in the persisted map."""

    key: str  # e.g. "DT_STATE_CHANGE", "DT_WARNING_CODE"
    time: int  # Unix epoch seconds as reported by the robot
    code: str


@dataclass
class VacuumMap:
    """Map data decoded from a SharkIQ MQTT map frame.

    Live frames (every few seconds during a job) carry the grid, the path
    cleaned so far and the robot's pose history. The larger *persisted* frame,
    published once when the robot reaches the dock, adds rooms, wall and door
    vectors, the dock pose, job statistics and the robot's event log.
    """

    grid: MapGrid
    path: List[MapPoint] = field(default_factory=list)
    poses: List[MapPose] = field(default_factory=list)
    persisted: bool = False
    # The end-of-job frame, which alone carries the event log. A persisted map
    # sent on request is not a report.
    report: bool = False
    map_id: Optional[str] = None
    name: Optional[str] = None
    dock: Optional[MapPose] = None
    rooms: List[MapRoom] = field(default_factory=list)
    features: List[MapFeature] = field(default_factory=list)
    log: List[VacuumLogEntry] = field(default_factory=list)
    job_started: Optional[int] = None  # Unix epoch seconds
    job_minutes: Optional[int] = None  # whole minutes, docking included
    raw: Dict[str, Any] = field(default_factory=dict)

    @property
    def robot(self) -> Optional[MapPose]:
        """Current robot pose: the last recorded pose, if any."""
        return self.poses[-1] if self.poses else None

    @property
    def named_rooms(self) -> List[MapRoom]:
        """The rooms as the app names them — every room except a spot zone."""
        return [room for room in self.rooms if room.name != SPOT_ROOM_NAME]

    @property
    def spot(self) -> Optional[MapRoom]:
        """The spot-clean zone the robot saved, if the map carries one."""
        return next((room for room in self.rooms if room.name == SPOT_ROOM_NAME), None)

    @property
    def cleaned_area(self) -> float:
        """Area covered by the job in square metres, counted from the grid."""
        return self.grid.cleaned_cells * self.grid.resolution**2

    @property
    def clean_time(self) -> Optional[int]:
        """Seconds spent cleaning in the last job.

        The sum of the event log's ``DT_*_CLEAN_TIME`` entries (normal,
        wall-follow and escape cleaning; docking is logged separately). A map
        without a log (one sent on request) falls back to the job summary's
        whole minutes, which include docking. ``None`` when neither is there.
        """
        times = [
            int(entry.code)
            for entry in self.log
            if entry.key.endswith("_CLEAN_TIME") and entry.code.isdigit()
        ]
        if times:
            return sum(times)
        return self.job_minutes * 60 if self.job_minutes else None

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serialisable form of the map, for storage.

        The persisted map arrives only when the robot docks, but room and spot
        cleaning need its room definition at any time — so a caller that
        restarts wants to keep it. Byte rasters are base64-encoded and ``raw``
        is dropped. :meth:`from_dict` reverses this.
        """
        data = asdict(self)
        data.pop("raw", None)
        grid = data["grid"]
        grid["cells"] = base64.b64encode(self.grid.cells).decode("ascii")
        if self.grid.room_ids is not None:
            grid["room_ids"] = base64.b64encode(self.grid.room_ids).decode("ascii")
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VacuumMap":
        """Rebuild a map from :meth:`to_dict` output."""
        g = data["grid"]
        grid = MapGrid(
            resolution=g["resolution"],
            width=g["width"],
            height=g["height"],
            origin=MapPoint(**g["origin"]),
            cells=base64.b64decode(g["cells"]),
            room_ids=base64.b64decode(g["room_ids"]) if g.get("room_ids") else None,
        )
        dock = data.get("dock")
        return cls(
            grid=grid,
            path=[MapPoint(**p) for p in data.get("path", [])],
            poses=[MapPose(**p) for p in data.get("poses", [])],
            persisted=data.get("persisted", False),
            # Stored before this field existed: only reports were persisted then.
            report=data.get("report", data.get("persisted", False)),
            map_id=data.get("map_id"),
            name=data.get("name"),
            dock=MapPose(**dock) if dock else None,
            rooms=[
                MapRoom(
                    name=r["name"],
                    polygon=[MapPoint(**p) for p in r["polygon"]],
                    selected=r.get("selected", False),
                    coverage=r.get("coverage"),
                )
                for r in data.get("rooms", [])
            ],
            features=[
                MapFeature(kind=f["kind"], points=[MapPoint(**p) for p in f["points"]])
                for f in data.get("features", [])
            ],
            log=[VacuumLogEntry(**e) for e in data.get("log", [])],
            job_started=data.get("job_started"),
            job_minutes=data.get("job_minutes"),
        )


@dataclass
class VacuumEvent:
    """A single event from the vacuum event log."""

    id: int
    type: str
    type_id: int
    timestamp: Dict[str, int]
    current_status: str
    source_type: str
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DeviceInfo:
    """Device identity and connectivity information."""

    firmware: Optional[str] = None
    mac_address: Optional[str] = None
    ip_address: Optional[str] = None
    ssid: Optional[str] = None
    rssi: Optional[int] = None
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProbeResult:
    """Result of a :meth:`VacuumClient.probe` call."""

    rest_mapping: Optional[str] = None
    """``id`` of the REST mapping that responded successfully, or ``None``."""

    mqtt_mapping: Optional[str] = None
    """``id`` of the MQTT mapping that responded successfully, or ``None``."""

    @property
    def has_rest(self) -> bool:
        """``True`` if a working REST mapping was found."""
        return self.rest_mapping is not None

    @property
    def has_mqtt(self) -> bool:
        """``True`` if a working MQTT mapping was found."""
        return self.mqtt_mapping is not None

    @property
    def is_connected(self) -> bool:
        """``True`` if at least one transport responded successfully."""
        return self.has_rest or self.has_mqtt
