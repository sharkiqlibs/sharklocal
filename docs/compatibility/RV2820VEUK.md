# RV2820VEUK — Compatibility Matrix

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
| `cleaning`           | ❌ | ❌ | REST: `sharkiq_v1`<br/> REST: `sharkiq_v2`<br/> MQTT: `sharkiq_v1` |
| `returning_to_dock`  | ❌ | ❌ | REST: `sharkiq_v1`<br/> REST: `sharkiq_v2`<br/> MQTT: `sharkiq_v1` |
| `docking`            | ❌ | ❌ | MQTT: `sharkiq_v1` |
| `docked`             | ❌ | ❌ | REST: `sharkiq_v1`<br/> REST: `sharkiq_v2`<br/> MQTT: `sharkiq_v1` |
| `idle`               | ❌ | ❌ | REST: `sharkiq_v1`<br/> REST: `sharkiq_v2` |
| `exploring`          | ❌ | ❌ | REST: `sharkiq_v1`<br/> REST: `sharkiq_v2` |

---

## Known Issues / Notes
- **Local Control Disabled:** Both REST and MQTT ports appear locked down or unreachable.
- `nmap` report:
   - 80 (filtered)
   - 5555 (open)
   - 8080 (filtered)
