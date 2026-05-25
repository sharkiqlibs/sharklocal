# Mapping Configuration

Mappings are YAML files that describe how to communicate with a specific vacuum model over each transport. Built-in mappings live inside the package. Custom mappings can be placed in any directory and discovered via `mapping_search_paths`.

---

## REST Mapping

```yaml
id: sharkiq_v1
description: "SharkIQ vacuum local REST API (HTTPS with self-signed certificate)"
transport: https        # "http" or "https"
connection:
  port: 443
  verify_ssl: false     # Set true for CA-signed certs; false for self-signed

# Maps raw mode strings from /get/status to normalized VacuumMode values.
# Note: "ready" cannot be resolved by this map alone — it requires the
# "charging" field. The library evaluates both fields together:
#   mode=ready + charging=connected   → DOCKED
#   mode=ready + charging=unconnected → IDLE
# The "ready": "docked" entry below is a fallback and is overridden in code.
mode_map:
  "ready": "docked"
  "cleaning": "cleaning"
  "go_home": "returning_to_dock"
  "exploring": "exploring"

actions:
  start_cleaning:
    method: GET
    path: "/set/clean_all"

  get_status:
    method: GET
    path: "/get/status"
    response_map: status   # Triggers normalized response parsing
```

**`response_map` values** that trigger normalized parsing:

| Value | Return type |
|---|---|
| `status` | `VacuumStatus` |
| `events` | `list[VacuumEvent]` |
| `robot_id` | `DeviceInfo` |
| `wifi_status` | `DeviceInfo` |

Omitting `response_map` returns the raw parsed JSON.

---

## MQTT Mapping

```yaml
id: sharkiq_v1
description: "SharkIQ vacuum local MQTT protocol"
connection:
  port: 1883

topics:
  command: "/qfeel/PbInput"
  status:  "/qfeel/PbOutput"

encoding: base64         # Payload encoding for both send and receive

# Name of the registered decoder function (see Extending below)
status_decoder: sharkiq_protobuf_v1

# Maps protobuf OperatingMode integers to normalized VacuumMode strings
modes:
  6: cleaning
  7: returning_to_dock
  13: docking
  14: docked

actions:
  start_cleaning:
    type: command          # Fire-and-forget MQTT publish
    payload: "OgQKAhBLgAEJ"

  get_status:
    type: status_request   # Publish then wait for a response message
    payload: "QgIIAw=="
    timeout: 5.0
```

**Action types:**

- `command` — publishes the payload and returns `True`
- `status_request` — publishes the payload, then subscribes and waits up to `timeout` seconds for the first response; returns the decoded `VacuumStatus`

---

## Listing and Loading Mappings

```python
from sharklocal import list_rest_mappings, list_mqtt_mappings
from sharklocal import load_rest_mapping, load_mqtt_mapping

list_rest_mappings()                           # ["sharkiq_v1"]
list_mqtt_mappings()                           # ["sharkiq_v1"]
list_rest_mappings(["/custom/mappings"])       # includes custom dir

cfg = load_rest_mapping("sharkiq_v1")
cfg = load_mqtt_mapping("my_model", ["/custom/mappings"])
```

---

## Adding a New Mapping

Mappings are YAML files. No code changes are required to add support for a new vacuum model or firmware revision — only a new YAML file (and optionally a decoder function for MQTT).

### Step 1 — Create the YAML file(s)

Place files under `sharklocal/mappings/rest/` and/or `sharklocal/mappings/mqtt/`. The filename stem becomes the mapping name used in `VacuumClient`.

**Minimal REST mapping** (`sharklocal/mappings/rest/mymodel_v1.yaml`):

```yaml
id: mymodel_v1
description: "My vacuum REST API"
transport: https        # "http" or "https"
connection:
  port: 443
  verify_ssl: true      # false for self-signed certificates

# Map raw mode strings returned by /get/status to normalized VacuumMode values.
mode_map:
  "idle": "docked"
  "cleaning": "cleaning"
  "returning": "returning_to_dock"

actions:
  get_status:
    method: GET
    path: "/api/status"
    response_map: status   # Parses response into VacuumStatus

  start_cleaning:
    method: GET
    path: "/api/clean"

  stop:
    method: POST
    path: "/api/stop"
    body:                  # Optional JSON request body
      force: true
    headers:               # Optional per-action headers
      X-Auth: "token"

  go_home:
    method: GET
    path: "/api/dock"
```

**Minimal MQTT mapping** (`sharklocal/mappings/mqtt/mymodel_v1.yaml`):

```yaml
id: mymodel_v1
description: "My vacuum MQTT protocol"
connection:
  port: 1883

topics:
  command: "/device/cmd"     # Topic to publish commands to
  status:  "/device/status"  # Topic to subscribe to for status

encoding: base64             # "base64" or "raw"
status_decoder: sharkiq_protobuf_v1  # See Step 2 if you need a custom decoder

# Map integer mode values in the payload to normalized VacuumMode strings.
modes:
  1: cleaning
  2: docked
  3: returning_to_dock

actions:
  start_cleaning:
    type: command            # Fire-and-forget publish
    payload: "BASE64_HERE"

  get_status:
    type: status_request     # Publish then wait for a status message
    payload: "BASE64_HERE"
    timeout: 5.0
```

### Step 2 — Register a custom MQTT decoder (if needed)

Skip this step if your model's MQTT messages use the same protobuf layout as the SharkIQ (`sharkiq_protobuf_v1`) and you can reuse that decoder.

If the payload format differs, register a named decoder in your integration's setup code:

```python
from sharklocal import register_decoder
from sharklocal.models import VacuumMode, VacuumStatus

@register_decoder("mymodel_v1_decoder")
def _decode_mymodel(payload: bytes, modes: dict[int, str]) -> VacuumStatus:
    # payload is the already-decoded bytes (base64 unwrapped if encoding=base64)
    # modes is the dict from the YAML mapping: {int_value: "mode_string", ...}
    mode_int = payload[0]  # example — parse however your protocol requires
    mode_str = modes.get(mode_int, "unknown")
    battery  = payload[1]
    return VacuumStatus(
        mode=VacuumMode(mode_str),
        battery_level=battery,
        raw={"raw_bytes": list(payload)},
    )
```

Then set `status_decoder: mymodel_v1_decoder` in the MQTT YAML.

### Step 3 — Use the mapping

```python
from sharklocal import VacuumClient

async with VacuumClient(
    "192.168.1.100",
    rest_mappings="mymodel_v1",
    mqtt_mappings="mymodel_v1",
) as vacuum:
    status = await vacuum.get_status()
```

If the YAML files are not inside the package (e.g. shipped alongside a custom integration), pass their directory via `mapping_search_paths`:

```python
VacuumClient(
    "192.168.1.100",
    rest_mappings="mymodel_v1",
    mapping_search_paths=["/config/custom_components/my_integration/mappings"],
)
```

Built-in mappings are always searched before custom paths. If a name matches in both locations, the built-in mapping takes precedence.

---

## Reference — All YAML Fields

**REST mapping**

| Field | Required | Default | Description |
|---|---|---|---|
| `id` | yes | — | Unique identifier (should match filename stem) |
| `description` | no | `""` | Human-readable description |
| `transport` | no | `https` | `"http"` or `"https"` |
| `connection.port` | no | `443` | TCP port |
| `connection.verify_ssl` | no | `true` | Disable for self-signed certs |
| `mode_map` | no | `{}` | Raw mode string → `VacuumMode` string |
| `actions.<name>.method` | yes | — | HTTP verb (`GET`, `POST`, etc.) |
| `actions.<name>.path` | yes | — | URL path (e.g. `/get/status`) |
| `actions.<name>.response_map` | no | — | Parser to apply: `status`, `events`, `robot_id`, `wifi_status` |
| `actions.<name>.body` | no | — | JSON body to send with the request |
| `actions.<name>.headers` | no | — | Additional HTTP headers for the action |

**MQTT mapping**

| Field | Required | Default | Description |
|---|---|---|---|
| `id` | yes | — | Unique identifier |
| `description` | no | `""` | Human-readable description |
| `connection.port` | no | `1883` | MQTT broker port |
| `topics.command` | no | `/qfeel/PbInput` | Topic for outbound commands |
| `topics.status` | no | `/qfeel/PbOutput` | Topic for inbound status |
| `encoding` | no | `base64` | `"base64"` or `"raw"` |
| `status_decoder` | yes | — | Name of registered decoder function |
| `modes` | no | `{}` | Integer mode → `VacuumMode` string |
| `actions.<name>.type` | yes | — | `"command"` or `"status_request"` |
| `actions.<name>.payload` | yes | — | Payload string to publish |
| `actions.<name>.timeout` | no | `5.0` | Seconds to wait for `status_request` response |

---

## Custom Mapping Search Path

```python
VacuumClient(
    "192.168.1.100",
    rest_mappings="my_model_v1",
    mapping_search_paths=["/etc/sharklocal/mappings"],
)
```

Built-in mappings are always searched before custom paths.
