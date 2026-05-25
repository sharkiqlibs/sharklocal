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
| **Status** | | |
| Polling status (mode + battery) | ✅ | ✅ |
| Real-time status (mode) | ❌  | ✅ |
| Event log | ✅ | ❌ |
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
| Idle / stopped off dock (calculated) | ✅ ¹ | ❌ |
| Exploring / mapping | ✅ | ❌ |
| **Connection** | | |
| Protocol | HTTPS | MQTT |
| Port | 443 | 1883 |
| SSL | Self-signed (verify disabled) | None |

> ¹ `DOCKED` and `IDLE` are derived from the combination of `mode` and `charging` fields in the REST response — neither is reported directly by the API. Charging reports connected or not connected, not active charging of the battery.

**Recommendations:**
- Configure **both transports** (`rest_mappings` + `mqtt_mappings`) to get full feature coverage: REST for device info, events, and explore; MQTT for real-time monitoring and docking state.
- If only one transport is available, **REST** provides broader feature coverage. **MQTT** is the better choice when real-time status updates without polling are required.
- Use `probe()` when the correct mapping is not known ahead of time.

---

For annotated YAML examples, the full field reference, and instructions for adding a new model, see [mapping-configuration.md](mapping-configuration.md).
