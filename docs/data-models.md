# Data Models

All transport clients return normalized model objects independent of the underlying protocol.

---

## VacuumStatus

```python
@dataclass
class VacuumStatus:
    mode: VacuumMode           # Normalized operating mode
    battery_level: int | None  # 0–100, or None if unavailable
    charging: bool | None      # True = "connected", False = "unconnected"
    raw: dict                  # Full original response

    @property
    def is_cleaning(self) -> bool: ...
    @property
    def is_docked(self) -> bool: ...  # True for DOCKED and DOCKING only
```

---

## VacuumMode

```python
class VacuumMode(str, Enum):
    UNKNOWN           = "unknown"
    CLEANING          = "cleaning"
    RETURNING_TO_DOCK = "returning_to_dock"
    DOCKING           = "docking"
    DOCKED            = "docked"
    IDLE              = "idle"       # Stopped and off the dock (mode=ready, charging=unconnected)
    EXPLORING         = "exploring"  # Mapping/exploration run in progress
```

The REST API does not expose `docked` directly. `DOCKED` is derived automatically from two fields:
- `mode: "ready"` **and** `charging: "connected"` → `DOCKED`
- `mode: "ready"` **and** `charging: "unconnected"` → `IDLE` (stopped, off dock)

This combined evaluation is handled automatically by the library — `mode_map` alone is insufficient for the `"ready"` state.

`is_docked` returns `True` only for `DOCKED` and `DOCKING`. `IDLE` and `EXPLORING` vacuums are not considered docked.

---

## VacuumEvent

```python
@dataclass
class VacuumEvent:
    id: int
    type: str              # e.g. "status_water_tank_removed" (also dustbin on vacuums)
    type_id: int
    timestamp: dict        # {"year": ..., "month": ..., ...}
    current_status: str
    source_type: str
    raw: dict
```

---

## DeviceInfo

```python
@dataclass
class DeviceInfo:
    firmware: str | None
    mac_address: str | None  # Use this as unique_id in Home Assistant
    ip_address: str | None
    ssid: str | None
    rssi: int | None
    raw: dict
```

> **Note:** The MAC address returned by `get_wifi_status()` is the recommended value to use as `unique_id` when configuring a Home Assistant device. The robot ID endpoint does not expose a serial number.
