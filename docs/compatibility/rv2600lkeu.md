# RV2600LKEU — Compatibility Matrix

---

## Actions

| Feature | REST | MQTT | Supported mappings |
|---------|:----:|:----:|--------------------|
| Start cleaning | ❌ | ✅ | MQTT: `sharkiq_v1` |
| Stop | ❌ | ✅ | MQTT: `sharkiq_v1` |
| Return to dock | ❌ | ✅ | MQTT: `sharkiq_v1` |
| Explore / Map | ❌ | ✅ | MQTT: observed (`16: 38` sent by the app; live map frames decoded) |
| Get status | ❌ | ✅ | MQTT: `sharkiq_v1` |
| Get event log | ❌ | ❌ | None (not tested) |
| Get robot ID | ❌ | ❌ | None (not tested) |
| Get Wi-Fi status | ❌ | ❌ | None (not tested) |

---

## Status Fields

| Field | REST | MQTT | Supported mappings |
|-------|:----:|:----:|--------------------|
| Operating mode | ❌ | ✅ | MQTT: `sharkiq_v1` |
| Battery level | ❌ | ✅ | MQTT: `sharkiq_v1` (field 9.8) |
| Charging status | ❌ | ⚠️ | Field 9.1 is **not** charging (constant `3`, also while cleaning) — derive from mode 13/14 |

---

## Operating Modes

| Mode | REST | MQTT | Supported mappings |
|------|:----:|:----:|--------------------|
| `cleaning` | ❌ | ✅ | MQTT: `sharkiq_v1` (6) |
| `returning_to_dock` | ❌ | ✅ | MQTT: `sharkiq_v1` (7) |
| `docking` | ❌ | ❌ | not observed as a separate state |
| `docked` | ❌ | ✅ | MQTT: 13 (charging), 14 (battery full) |
| `idle` | ❌ | ❌ | not observed |
| `exploring` | ❌ | ✅ | MQTT: 24 (observed during the app's explore run) |

---

## Known Issues / Notes

- **Model:** Shark RV2600LKEU (EU variant of the RV26xx family), tested 2026-11-04. Firmware version not recorded.
- **REST API:** Port 80 is open but `/` returns a "Forbidden" HTML page and `/get/status`, `/status`, `/info` return `404`. Port 443 closed. Same behaviour as RV2610BFCA.
- **MQTT:** Broker on port 1883 without authentication; standard `sharkiq_v1` base64 protobuf on `/qfeel/PbOutput` / `/qfeel/PbInput`.
- **Command test:** `start_cleaning` → mode 6 within ~1 s; `go_home` → mode 7, mode 14 about 30 s later.
- **Commands captured from the SharkClean app on this model** (field layout identical to what PR #34 documents for the RV2610BFCA):
  - room clean: `16: 11`, `39: 2`, `41: {1: <room name>, 3: <map id>}`; the short form without the room definitions in field 6 works (robot drove into the named room)
  - several rooms: one field 41 with field 1 repeated
  - spot: temporary room `PinDrop0` (1.524 m square, extra fields `7: 2, 8: 1, 9: 0, 10: 2`) appended to the room list in field 6, then cleaned like a room
  - explore: `16: 38`; app dock: `7: {1: {2: 50, 3: 0}}`, `16: 17`
- **Live map** (long `PbOutput` frames, field 7.5): 0.06 m cells, origin and grid size change between frames; field 7.8 holds the current run's path (int16 pairs × 0.002 m, absolute; last point = robot). Room outlines from field 6 line up exactly with the grid.
