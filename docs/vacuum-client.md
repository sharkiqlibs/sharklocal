# VacuumClient

`VacuumClient` is the recommended entry point. It wraps both transport clients, handles transport selection automatically, and supports real-time MQTT monitoring alongside polled REST calls.

```python
from sharklocal import VacuumClient

async with VacuumClient(
    host="192.168.1.100",
    rest_mappings="sharkiq_v1",          # single string or list
    mqtt_mappings="sharkiq_v1",          # single string or list
    mapping_search_paths=["/custom/mappings"],  # optional
) as vacuum:
    ...
```

Either mapping may be omitted. If only one transport is configured, it is used exclusively.

---

## Mapping Probe

When multiple mapping candidates are supplied, call `probe()` during setup. It tests each mapping by requesting the vacuum status and pins the first one that responds. All subsequent calls use the pinned mapping.

```python
async with VacuumClient(
    "192.168.1.100",
    rest_mappings=["sharkiq_v1", "other_model_v1"],
    mqtt_mappings=["sharkiq_v1"],
) as vacuum:
    result = await vacuum.probe()

    print(result.rest_mapping)   # "sharkiq_v1" or None
    print(result.mqtt_mapping)   # "sharkiq_v1" or None
    print(result.is_connected)   # True if at least one transport responded

    if not result.is_connected:
        raise RuntimeError("Vacuum not reachable")

    status = await vacuum.get_status()
```

With a single mapping per transport, `probe()` is not required — the mapping is pinned automatically.

`probe()` can be called again to re-test and re-pin (e.g. after a firmware update changes the API).

---

## Active Mapping Inspection

```python
vacuum.active_rest_mapping   # "sharkiq_v1" or None
vacuum.active_mqtt_mapping   # "sharkiq_v1" or None
```

---

## `via` — Primary Transport in Use

`vacuum.via` is a string attribute that reflects which transport is the primary connection. It is set automatically on init (single mapping) or after `probe()` (multiple candidates).

| Value | Meaning |
|---|---|
| `"REST"` | REST mapping is pinned and was the first to respond |
| `"MQTT"` | No REST mapping responded; MQTT is the primary transport |
| `"NONE"` | No transport has been confirmed yet (multiple candidates, `probe()` not called, or all candidates failed) |

```python
# Single mapping — via is set immediately on init
vacuum = VacuumClient("192.168.1.100", rest_mappings="sharkiq_v1")
print(vacuum.via)   # "REST"

vacuum = VacuumClient("192.168.1.100", mqtt_mappings="sharkiq_v1")
print(vacuum.via)   # "MQTT"

vacuum = VacuumClient("192.168.1.100", rest_mappings="sharkiq_v1", mqtt_mappings="sharkiq_v1")
print(vacuum.via)   # "REST"  (REST takes priority)

# Multiple candidates — via is NONE until probe() runs
vacuum = VacuumClient("192.168.1.100", rest_mappings=["sharkiq_v1", "other_v1"])
print(vacuum.via)   # "NONE"

result = await vacuum.probe()
print(vacuum.via)   # "REST", "MQTT", or "NONE" depending on what responded
```

---

## Actions

| Method | REST endpoint | MQTT action |
|---|---|---|
| `get_status()` | `GET /get/status` | `get_status` (status request) |
| `start_cleaning()` | `GET /set/clean_all` | `start_cleaning` (command) |
| `stop()` | `GET /set/stop` | `stop` (command) |
| `go_home()` | `GET /set/go_home` | `go_home` (command) |
| `explore()` | `GET /set/explore` | *(not in MQTT mapping)* |
| `get_events()` | `GET /get/event_log` | *(not in MQTT mapping)* |
| `get_device_info()` | `GET /get/robot_id` | *(not in MQTT mapping)* |
| `get_wifi_status()` | `GET /get/wifi_status` | *(not in MQTT mapping)* |

### Return Types

- **`get_status()`** → `VacuumStatus`
- **`get_events()`** → `list[VacuumEvent]`
- **`get_device_info()`**, **`get_wifi_status()`** → `DeviceInfo`
- Command methods → `bool` (`True` on success)

See [data-models.md](data-models.md) for field definitions of each return type.

---

## Real-Time Monitoring (MQTT)

`VacuumClient` can subscribe to the vacuum's MQTT status topic and invoke a callback on every update. Both sync and `async` callables are supported.

```python
async with VacuumClient("192.168.1.100", mqtt_mappings="sharkiq_v1") as vacuum:
    vacuum.on_status_update(lambda s: print(s.mode, s.battery_level))
    await vacuum.start_monitoring()

    # Monitoring runs as a background task.
    await asyncio.sleep(60)

    await vacuum.stop_monitoring()
```

---

## Transport Introspection

```python
vacuum.via                              # "REST", "MQTT", or "NONE"
vacuum.active_rest_mapping              # "sharkiq_v1" or None
vacuum.active_mqtt_mapping              # "sharkiq_v1" or None
vacuum.supported_actions()              # ["explore", "get_events", "get_status", ...]
vacuum.transports_for("get_status")     # ["rest", "mqtt"]
vacuum.transports_for("explore")        # ["rest"]
```
