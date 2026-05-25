# sharklocal
[![codecov](https://codecov.io/gh/sharkiqlibs/sharklocal/graph/badge.svg?token=kLonrWzpxx)](https://codecov.io/gh/sharkiqlibs/sharklocal)
[![PyPI](https://img.shields.io/pypi/v/sharklocal?color=blue)](https://pypi.org/project/sharklocal/)
[![GitHub](https://img.shields.io/github/license/sharkiqlibs/sharklocal)](https://github.com/sharkiqlibs/sharklocal)
[![Documentation](https://img.shields.io/badge/Documentation-2c3e50)](https://sharkiqlibs.github.io/sharklocal/)

A Python library for local control of Shark robot vacuums, designed for use with Home Assistant integrations. No cloud connection required.

Supports two transport protocols:

- **REST** — Onboard HTTP API
- **MQTT** — Onboard broker on port 1883 using base64-encoded protobuf messages

## Requirements

- Python 3.11+
- `aiohttp` — HTTP/S transport
- `aiomqtt` — MQTT transport
- `PyYAML` — mapping configuration loading

```
pip install sharklocal
```

---

## Quickstart

```python
import asyncio
from sharklocal import VacuumClient

async def main():
    async with VacuumClient(
        "192.168.1.100",
        rest_mappings="sharkiq_v1",
        mqtt_mappings="sharkiq_v1",
    ) as vacuum:
        status = await vacuum.get_status()
        print(status.mode, status.battery_level)

        await vacuum.start_cleaning()

asyncio.run(main())
```

---

## CLI

The library includes a built-in CLI utility for discovering, testing, and controlling your vacuum. Common entry points:

```bash
python -m sharklocal <IP_ADDRESS> --probe       # identify the correct mapping for your model
python -m sharklocal <IP_ADDRESS> --monitor     # stream real-time MQTT status updates
python -m sharklocal <IP_ADDRESS> --cmd dock    # send a direct command
```

See [docs/cli.md](docs/cli.md) for the full command reference.

---

## Architecture

```
sharklocal/
├── client.py          # VacuumClient — unified entry point with transport selection
├── rest_client.py     # RESTVacuumClient — async HTTPS/HTTP client (aiohttp)
├── mqtt_client.py     # MQTTVacuumClient — async MQTT client (aiomqtt)
├── protobuf.py        # Pure-Python schema-free protobuf decoder
├── models.py          # VacuumStatus, VacuumEvent, DeviceInfo, VacuumMode
├── exceptions.py      # Typed exception hierarchy
└── mappings/
    ├── __init__.py    # load_* / list_* utilities
    ├── base.py        # RESTMappingConfig, MQTTMappingConfig dataclasses
    ├── rest/
    │   └── sharkiq_v1.yaml
    └── mqtt/
        └── sharkiq_v1.yaml
```

### Transport Selection

`VacuumClient` evaluates which transport to use at action call time:

1. **REST is tried first** if the loaded REST mapping defines the action.
2. **MQTT is the fallback** — used only when REST raises `ConnectError` (host unreachable).
3. If neither transport supports the action, `ActionNotSupportedError` is raised.

All other exceptions (`CommandError`, `DecoderError`, etc.) propagate immediately without attempting the fallback.

---

## Mappings

Mappings are YAML files that describe how to communicate with a specific vacuum model over REST or MQTT. Each mapping defines the connection parameters, supported actions, and response interpretation. `VacuumClient` tries REST first, falls back to MQTT on `ConnectError`, and raises `ActionNotSupportedError` if neither transport defines the action.

See [docs/mappings.md](docs/mappings.md) for the full feature comparison table, transport recommendations, and details on how transport selection works.

## Compatibility

Not all vacuum models support both transports, and feature coverage varies by model. See [docs/COMPATIBILITY.md](docs/COMPATIBILITY.md) for the list of known models and links to per-model compatibility matrices.

---

## VacuumClient

`VacuumClient` is the recommended entry point. It wraps both transport clients, handles transport selection automatically, and supports real-time MQTT monitoring alongside polled REST calls.

See [docs/vacuum-client.md](docs/vacuum-client.md) for the full API reference: constructor options, `probe()`, `via`, the actions table, return types, real-time monitoring, and transport introspection.

---

## Direct Transport Clients

Use the transport clients directly when you need full control.

### RESTVacuumClient

```python
from sharklocal import RESTVacuumClient, load_rest_mapping

mapping = load_rest_mapping("sharkiq_v1")
client = RESTVacuumClient("192.168.1.100", mapping)

status = await client.call("get_status")        # VacuumStatus
events = await client.call("get_events")        # list[VacuumEvent]
wifi   = await client.call("get_wifi_status")   # DeviceInfo

await client.call("start_cleaning")             # True
await client.close()
```

### MQTTVacuumClient

```python
from sharklocal import MQTTVacuumClient, load_mqtt_mapping

mapping = load_mqtt_mapping("sharkiq_v1")
client = MQTTVacuumClient("192.168.1.100", mapping)

status = await client.call("get_status")       # VacuumStatus
await client.call("start_cleaning")            # True

# Monitor with a callback
stop = asyncio.Event()
await client.monitor(lambda s: print(s.mode), stop_event=stop)
```

---

## Data Models

All transport clients return normalized model objects. See [docs/data-models.md](docs/data-models.md) for field definitions, `VacuumMode` values, and notes on derived states like `DOCKED` and `IDLE`.

---

## Mapping Configuration

See [docs/mapping-configuration.md](docs/mapping-configuration.md) for annotated YAML examples for both transports, the full field reference, instructions for adding support for a new model, and how to register a custom MQTT decoder.

---

## Exceptions

All exceptions inherit from `SharklocalError`.

| Exception | When raised |
|---|---|
| `ConnectError` | Host unreachable or connection refused |
| `CommandError` | HTTP error response or MQTT timeout waiting for status |
| `ActionNotSupportedError` | Action not defined in the configured mapping(s) |
| `MappingNotFoundError` | YAML mapping file not found |
| `DecoderError` | MQTT payload cannot be decoded |

```python
from sharklocal import SharklocalError, ConnectError, ActionNotSupportedError

try:
    status = await vacuum.get_status()
except ConnectError:
    # Vacuum is offline
    ...
except ActionNotSupportedError:
    # Mapping doesn't define this action
    ...
except SharklocalError:
    # Catch-all for any library error
    ...
```

---

## Testing

Install dev dependencies and run the test suite with coverage:

```bash
pip install -e ".[dev]"
python3 -m pytest --cov=sharklocal --cov-report=term-missing
```

The minimum required coverage is **95%**. All PRs must pass before merging. See [docs/testcoverage.md](docs/testcoverage.md) for the full testing guide, including how to write new tests.

---

## Known Quirks

- The `status_water_tank_removed` event type is fired for dustbin removal on vacuums, not only water tank removal on mops. Handle accordingly in Home Assistant event translation.
- The `/get/robot_id` endpoint does not expose a serial number. Use the `mac_address` from `/get/wifi_status` as the device `unique_id`.
- MQTT `go_home` and `stop` send identical payloads in the `sharkiq_v1` mapping — both issue the protobuf stop-and-return command.
- The REST API uses a self-signed TLS certificate. SSL verification is disabled in the `sharkiq_v1` mapping (`verify_ssl: false`).
- The REST `charging` field returns `"connected"` or `"unconnected"` as strings, not a boolean. The library normalises this to `True`/`False` on `VacuumStatus.charging`.
- The REST `mode` field alone is insufficient to determine if a vacuum is docked. `mode: "ready"` with `charging: "connected"` means docked (`VacuumMode.DOCKED`); `mode: "ready"` with `charging: "unconnected"` means the vacuum is stopped but off the dock (`VacuumMode.IDLE`). This combined evaluation is handled automatically by the library.
- `mode: "exploring"` means the vacuum is performing a mapping run, not cleaning. It maps to `VacuumMode.EXPLORING`, not `VacuumMode.CLEANING`.
