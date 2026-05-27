# UR2360EEUS — Compatibility Matrix

---

## Actions

| Feature | REST | MQTT | Supported mappings |
|---------|:----:|:----:|--------------------|
| Start cleaning | ❌ | ❌ | None |
| Stop | ❌ | ❌ | None |
| Return to dock | ❌ | ❌ | None |
| Explore / Map | ❌ | ❌ | None |
| Get status | ❌ | ❌ | None |
| Get event log | ❌ | ❌ | None |
| Get robot ID | ❌ | ❌ | None |
| Get Wi-Fi status | ❌ | ❌ | None |

---

## Status Fields

| Field | REST | MQTT | Supported mappings |
|-------|:----:|:----:|--------------------|
| Operating mode | ❌ | ❌ | None |
| Battery level | ❌ | ❌ | None |
| Charging status | ❌ | ❌ | None |

---

## Operating Modes

| Mode | REST | MQTT | Supported mappings |
|------|:----:|:----:|--------------------|
| `cleaning`           | ❌ | ❌ | None |
| `returning_to_dock`  | ❌ | ❌ | None |
| `docking`            | ❌ | ❌ | None |
| `docked`             | ❌ | ❌ | None |
| `idle`               | ❌ | ❌ | None |
| `exploring`          | ❌ | ❌ | None |

---

## Known Issues / Notes
- **Local Control Disabled:** Both REST and MQTT ports appear locked down or unreachable.
