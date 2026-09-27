# Mappings

Mappings are YAML files that describe how to communicate with a specific vacuum model over a given transport (REST or MQTT). Each mapping defines the connection parameters, the actions it supports, and how to interpret responses.

Built-in mappings live in `sharklocal/mappings/rest/` and `sharklocal/mappings/mqtt/`. Custom mappings can be loaded from additional directories via the `mapping_search_paths` argument on `VacuumClient`.

---

## Mapping Strategy

`VacuumClient` evaluates which transport to use at action call time:

1. **REST is tried first** if the loaded REST mapping defines the action.
2. **MQTT is the fallback** — used only when REST raises `ConnectError` (host unreachable).
3. If neither transport supports the action, `ActionNotSupportedError` is raised.

All other exceptions (`CommandError`, `DecoderError`, etc.) propagate immediately without attempting the fallback.

When multiple mapping candidates are supplied, call `probe()` during setup. It tests each mapping by requesting the vacuum status and pins the first one that responds.

---

## Feature Comparison — `sharkiq_v1`

The table below shows which features are available per transport for the built-in `sharkiq_v1` mapping. Use this to decide which transports to configure and whether `probe()` is needed.

| Feature | `sharkiq_v1` REST | `sharkiq_v1` MQTT |
|---|:---:|:---:|
| **Commands** | | |
| Start cleaning | ✅ | ✅ |
| Stop (pause) | ✅ | ✅ |
| Return to dock | ✅ | ✅ |
| Explore / map room | ✅ | ❌ |
| Find robot | ❌ | ✅ |
| Suction level (eco / normal / max) | ❌ | ✅ |
| Recharge & Resume, Evac & Resume | ❌ | ✅ |
| Clean rooms / Matrix Clean / spot clean | ❌ | ✅ ² |
| **Status** | | |
| Polling status (mode + battery) | ✅ | ✅ |
| Real-time status (mode) | ❌  | ✅ |
| Job active, deep clean, settings | ❌ | ✅ |
| Live map (grid, cleaned path, robot pose) | ❌ | ✅ |
| Persisted map (rooms, walls, doors, dock, job stats) | ❌ | ✅ ³ |
| Event log | ✅ | ✅ ³ |
| **Device info** | | |
| Firmware version | ✅ | ❌ |
| MAC address / unique ID | ✅ | ❌ |
| Wi-Fi SSID + RSSI | ✅ | ❌ |
| IP address | ✅ | ❌ |
| **Reported modes** | | |
| Cleaning | ✅ | ✅ |
| Returning to dock | ✅ | ✅ |
| Docking | ❌ | ✅ |
| Docked (calculated) | ✅ ¹ | ✅ |
| Idle / stopped off dock | ✅ ¹ | ✅ |
| Exploring / mapping | ✅ | ❌ |
| **Connection** | | |
| Protocol | HTTPS | MQTT |
| Port | 443 | 1883 |
| SSL | Self-signed (verify disabled) | None |

> ¹ `DOCKED` and `IDLE` are derived from the combination of `mode` and `charging` fields in the REST response — neither is reported directly by the API. Charging reports connected or not connected, not active charging of the battery.
>
> ² Built at runtime from the persisted map's room definition (`VacuumClient.clean_rooms()` / `clean_spot()`), not a fixed mapping action.
>
> ³ Carried by the persisted map frame the robot publishes when it docks, available through monitoring (`VacuumStatus.map`). `VacuumClient.request_map()` makes the robot publish it again, without the event log.

**Recommendations:**
- Configure **both transports** (`rest_mappings` + `mqtt_mappings`) to get full feature coverage: REST for device info and explore; MQTT for real-time monitoring, maps, rooms and settings.
- If only one transport is available, **MQTT** now provides the broader feature coverage on models that publish map frames, and is the only source of real-time status. **REST** remains the only source of device info (firmware, MAC address) where it is reachable.
- Use `probe()` when the correct mapping is not known ahead of time.

---

For annotated YAML examples, the full field reference, and instructions for adding a new model, see [mapping-configuration.md](mapping-configuration.md).
