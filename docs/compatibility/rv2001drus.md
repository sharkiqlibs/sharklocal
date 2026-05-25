# RV2001DRUS — Compatibility Matrix

---

## Actions

| Feature | REST | MQTT | Supported mappings |
|---------|:----:|:----:|--------------------|
| Start cleaning | ✅ | ❌ | REST: `sharkiq_v1`, `sharkiq_v2` |
| Stop | ✅ | ❌ | REST: `sharkiq_v1`, `sharkiq_v2` |
| Return to dock | ✅ | ❌ | REST: `sharkiq_v1`, `sharkiq_v2` |
| Explore / Map | ✅ | ❌ | REST: `sharkiq_v1`, `sharkiq_v2` |
| Get status | ✅ | ❌ | REST: `sharkiq_v1`, `sharkiq_v2` |
| Get event log | ✅ | ❌ | REST: `sharkiq_v1`, `sharkiq_v2` |
| Get robot ID | ✅ | ❌ | REST: `sharkiq_v1`, `sharkiq_v2` |
| Get Wi-Fi status | ✅ | ❌ | REST: `sharkiq_v1`, `sharkiq_v2` |

---

## Status Fields

| Field | REST | MQTT | Supported mappings |
|-------|:----:|:----:|--------------------|
| Operating mode | ✅ | ❌ | REST: `sharkiq_v1`, `sharkiq_v2` |
| Battery level | ✅ | ❌ | REST: `sharkiq_v1`, `sharkiq_v2` |
| Charging status | ✅ | ❌ | REST: `sharkiq_v1`, `sharkiq_v2` |

---

## Operating Modes

| Mode | REST | MQTT | Supported mappings |
|------|:----:|:----:|--------------------|
| `cleaning`           | ✅ | ❌ | REST: `sharkiq_v1`, `sharkiq_v2` |
| `returning_to_dock`  | ✅ | ❌ | REST: `sharkiq_v1`, `sharkiq_v2` |
| `docking`            | ❌ | ❌ | None |
| `docked`             | ✅ | ❌ | REST: `sharkiq_v1`, `sharkiq_v2` |
| `idle`               | ✅ | ❌ | REST: `sharkiq_v1`, `sharkiq_v2` |
| `exploring`          | ✅ | ❌ | REST: `sharkiq_v1`, `sharkiq_v2` |

---

## Known Issues / Notes
- **MQTT:** Local MQTT broker (Port 1883) is closed or unreachable.
