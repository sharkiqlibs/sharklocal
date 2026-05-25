# AV2001DRUS — Compatibility Matrix

---

## Actions

| Feature | REST | MQTT | Supported mappings |
|---------|:----:|:----:|--------------------|
| Start cleaning | ✅ | ❌ | REST: `sharkiq_v1` |
| Stop | ✅ | ❌ | REST: `sharkiq_v1` |
| Return to dock | ✅ | ❌ | REST: `sharkiq_v1` |
| Explore / Map | ✅ | ❌ | REST: `sharkiq_v1` |
| Get status | ✅ | ❌ | REST: `sharkiq_v1` |
| Get event log | ✅ | ❌ | REST: `sharkiq_v1` |
| Get robot ID | ✅ | ❌ | REST: `sharkiq_v1` |
| Get Wi-Fi status | ✅ | ❌ | REST: `sharkiq_v1` |

---

## Status Fields

| Field | REST | MQTT | Supported mappings |
|-------|:----:|:----:|--------------------|
| Operating mode | ✅ | ❌ | REST: `sharkiq_v1` |
| Battery level | ✅ | ❌ | REST: `sharkiq_v1` |
| Charging status | ✅ | ❌ | REST: `sharkiq_v1` |

---

## Operating Modes

| Mode | REST | MQTT | Supported mappings |
|------|:----:|:----:|--------------------|
| `cleaning`           | ✅ | ❌ | REST: `sharkiq_v1` |
| `returning_to_dock`  | ✅ | ❌ | REST: `sharkiq_v1` |
| `docking`            | ❌ | ❌ | None |
| `docked`             | ✅ | ❌ | REST: `sharkiq_v1` |
| `idle`               | ✅ | ❌ | REST: `sharkiq_v1` |
| `exploring`          | ✅ | ❌ | REST: `sharkiq_v1` |

---

## Known Issues / Notes
- **MQTT:** Local MQTT broker (Port 1883) is closed or unreachable.
