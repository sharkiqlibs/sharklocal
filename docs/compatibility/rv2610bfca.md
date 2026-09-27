# RV2610BFCA (Shark Matrix Plus) — Compatibility Matrix

---

## Actions

| Feature | REST | MQTT | Supported mappings |
|---------|:----:|:----:|--------------------|
| Start cleaning | ❌ | ✅ | MQTT: `sharkiq_v1` |
| Stop | ❌ | ✅ | MQTT: `sharkiq_v1` |
| Return to dock | ❌ | ✅ | MQTT: `sharkiq_v1` |
| Explore / Map | ❌ | 🟡 ³ | MQTT: `sharkiq_v1` |
| Get status | ❌ | ✅ | MQTT: `sharkiq_v1` |
| Get event log | ❌ | ✅ ¹ | MQTT: `sharkiq_v1` |
| Get robot ID | ❌ | ❌ | |
| Get Wi-Fi status | ❌ | ❌ | |
| Find robot | ❌ | ✅ | MQTT: `sharkiq_v1` |
| Set suction (eco / normal / max) | ❌ | ✅ | MQTT: `sharkiq_v1` |
| Recharge & Resume on / off | ❌ | ✅ | MQTT: `sharkiq_v1` |
| Evac & Resume on / off | ❌ | ✅ | MQTT: `sharkiq_v1` |
| Clean rooms (incl. Matrix Clean) | ❌ | ✅ | MQTT: `sharkiq_v1` |
| Spot clean | ❌ | ✅ | MQTT: `sharkiq_v1` |
| Pause / resume | ❌ | 🟡 ³ | MQTT: `sharkiq_v1` |
| Do not disturb, volume | ❌ | 🟡 ³ | MQTT: `sharkiq_v1` |

> ¹ Via the event log embedded in the persisted map frame the robot publishes when it docks (`VacuumMap.log`), not via a request. Entries are also streamed during a job (`VacuumStatus.log_entries`).
>
> ³ Sent in the same format as the verified commands, but not yet run on this robot.

---

## Status Fields

| Field | REST | MQTT | Supported mappings |
|-------|:----:|:----:|--------------------|
| Operating mode | ❌ | ✅ | MQTT: `sharkiq_v1` |
| Battery level | ❌ | ✅ | MQTT: `sharkiq_v1` |
| Charging status | ❌ | ✅ ² | MQTT: `sharkiq_v1` |
| Job active / deep clean | ❌ | ✅ | MQTT: `sharkiq_v1` |
| Recharge & Resume / Evac & Resume | ❌ | ✅ | MQTT: `sharkiq_v1` |
| Warnings active now | ❌ | ✅ | MQTT: `sharkiq_v1` |
| Faults active now | ❌ | 🟡 ⁴ | MQTT: `sharkiq_v1` |
| Temperature, Wi-Fi state | ❌ | ✅ | MQTT: `sharkiq_v1` |
| Suction / brushroll / side-brush motor speeds | ❌ | ✅ | MQTT: `sharkiq_v1` |
| Live map (grid, cleaned path, robot pose with heading) | ❌ | ✅ | MQTT: `sharkiq_v1` |
| Persisted map (rooms, room raster, walls, doors, dock, cleaned area, clean time, event log) | ❌ | ✅ | MQTT: `sharkiq_v1` |
| Persisted map on request (`request_map`: the same, less the event log) | ❌ | ✅ | MQTT: `sharkiq_v1` |
| Firmware versions | ❌ | ✅ ⁵ | MQTT: `sharkiq_v1` |

> ² Derived from the robot's system state (charging on the dock). The device-info field once read as a charging state is the Wi-Fi state: it reads `3` in every frame, including mid-clean.
>
> ⁴ Decoded from the status frame; no fault occurred during testing, so not yet seen with a value.
>
> ⁵ From the event log (`DT_VERSION_L01`, `DT_VERSION_MCU`).

---

## Operating Modes

| Mode | REST | MQTT | Supported mappings |
|------|:----:|:----:|--------------------|
| `cleaning` | ❌ | ✅ | MQTT: `sharkiq_v1` |
| `returning_to_dock` | ❌ | ✅ | MQTT: `sharkiq_v1` |
| `docking` | ❌ | ❌ | |
| `docked` | ❌ | ✅ | MQTT: `sharkiq_v1` |
| `idle` | ❌ | ❌ | |
| `paused` | ❌ | ✅ | MQTT: `sharkiq_v1` |
| `error` | ❌ | ❌ | |
| `exploring` | ❌ | ❌ | |

---

## Known Issues / Notes

- **Robot type:** `lidar` in `sharklocal.compat` terms, with a self-emptying dock. The retail SKU is not in the SharkClean app's model table (the app keys it by the robot's cloud model string); the firmware line (`P7`) is the app's Three60 lidar platform.
- **REST API:** Port 443 is closed/refused. Port 80 is open, but `/get/status` and `/get/wifi_status` return `404 Not Found`, and `/` returns a forbidden HTML page.
- **MQTT:** Uses standard `sharkiq_v1` protobuf format. Status requests, passive monitoring, and commands work.
- **Command test:** `start_cleaning` returned `True` and status changed to `cleaning` within about 2 seconds. `stop` returned `True` and status changed to `returning_to_dock` within about 2 seconds. `go_home` returned `True`; the robot reported `docked` about 28 seconds after the first return-to-dock command. Room clean, Matrix room clean and spot clean each cleaned the right area and returned to the dock on their own.
- **Lifecycle** (firmware `V6.6.10-P7.N3308.17.0`): battery full on the dock (`14`) → cleaning (`6`) → returning (`7`) → charging on the dock (`13`) → battery full (`14`). The persisted map frame is published as it reaches the dock. State `4` (paused) is reported when stopped off the dock or lifted.
- **Suction:** accepted while docked (the app only greys the control out). Echoed once on change; no status field.
- **Battery:** counts down through a job and snaps back to 100 within seconds of docking.
- **Maps:** a ~27 KB live frame every ~4 s during a job (0.06 m grid, cleaned path, pose log with heading); a ~92 KB persisted frame on docking with rooms, room-id raster, wall/door polylines, dock pose, job start time and the event log. Cleaned floor is marked `0x00` in the grid (every point of the cleaned path lands on one), and the log's `DT_*_CLEAN_TIME` entries give the time spent cleaning. The persisted frame's field 11 also carries two counters that look like a duration and a cell count, but they barely move between different jobs, so they are not decoded.
- **Spot clean:** the robot keeps the spot square in its saved map as a room named `PinDrop`, marked as the room the last job cleaned. `VacuumMap.named_rooms` leaves it out.
- **Warnings:** a dark room reports `WARN_LOW_LIGHT` live and logs `WARN_MM_LOWLIGHT` for the job.
- **Room commands re-upload the room definition**, names included. Build them from the latest persisted map.
- **Single map only:** every map seen carried one floor; the app's rules give multi-floor maps only to newer lines.
