# UR1100SRUS (Shark Robotic Vacuum) — Compatibility Matrix

---

## Actions

| Feature | REST | MQTT | Supported mappings |
|---------|:----:|:----:|--------------------|
| Start cleaning | ❌ | ✅ | MQTT: `sharkiq_v1` |
| Stop | ❌ | ✅ | MQTT: `sharkiq_v1` |
| Return to dock | ❌ | ✅ | MQTT: `sharkiq_v1` |
| Explore / Map | ❌ | ❌ | None |
| Get status | ❌ | ✅ | MQTT: `sharkiq_v1` |
| Get event log | ❌ | ❌ | None |
| Get robot ID | ❌ | ❌ | None |
| Get Wi-Fi status | ❌ | ❌ | None |

---

## Status Fields

| Field | REST | MQTT | Supported mappings |
|-------|:----:|:----:|--------------------|
| Operating mode | ❌ | ✅ | MQTT: `sharkiq_v1` |
| Battery level | ❌ | ✅ | MQTT: `sharkiq_v1` |
| Charging status | ❌ | ✅ | MQTT: `sharkiq_v1` |

---

## Operating Modes

| Mode | REST | MQTT | Supported mappings |
|------|:----:|:----:|--------------------|
| `cleaning`           | ❌ | ✅ | REST: `sharkiq_v1`<br/> REST: `sharkiq_v2`<br/> MQTT: `sharkiq_v1` |
| `returning_to_dock`  | ❌ | ✅ | REST: `sharkiq_v1`<br/> REST: `sharkiq_v2`<br/> MQTT: `sharkiq_v1` |
| `docking`            | ❌ | ✅ | MQTT: `sharkiq_v1` |
| `docked`             | ❌ | ✅ | REST: `sharkiq_v1`<br/> REST: `sharkiq_v2`<br/> MQTT: `sharkiq_v1` |
| `idle`               | ❌ | ❌ | REST: `sharkiq_v1`<br/> REST: `sharkiq_v2` |
| `exploring`          | ❌ | ❌ | REST: `sharkiq_v1`<br/> REST: `sharkiq_v2` |

---

## Known Issues / Notes
- **REST API:** Local REST API (Ports 443/80) is closed or non-responsive.
