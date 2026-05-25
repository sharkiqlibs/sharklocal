"""sharklocal — Local control library for Shark robot vacuums.

Designed for use with Home Assistant integrations. Supports both REST and MQTT
transports with YAML-configurable action mappings per vacuum model.

Basic usage::

    from sharklocal import VacuumClient

    async with VacuumClient(
        "192.168.1.100",
        rest_mapping="sharkiq_v1",
        mqtt_mapping="sharkiq_v1",
    ) as vacuum:
        status = await vacuum.get_status()
        print(status.mode, status.battery_level)
        await vacuum.start_cleaning()

Direct transport access::

    from sharklocal import RESTVacuumClient, load_rest_mapping

    mapping = load_rest_mapping("sharkiq_v1")
    client = RESTVacuumClient("192.168.1.100", mapping)
    status = await client.call("get_status")
    await client.close()
"""

from .client import VacuumClient
from .exceptions import (
    ActionNotSupportedError,
    CommandError,
    ConnectError,
    DecoderError,
    MappingNotFoundError,
    SharklocalError,
)
from .mappings import (
    list_mqtt_mappings,
    list_rest_mappings,
    load_mqtt_mapping,
    load_rest_mapping,
)
from .models import DeviceInfo, ProbeResult, VacuumEvent, VacuumMode, VacuumStatus
from .mqtt_client import MQTTVacuumClient, register_decoder
from .rest_client import RESTVacuumClient

try:
    from importlib.metadata import version, PackageNotFoundError
except ImportError:  # pragma: no cover
    # Python < 3.8
    from importlib_metadata import version, PackageNotFoundError  # pragma: no cover

try:
    __version__ = version("sharkiq")
except PackageNotFoundError:
    # Package is not installed
    __version__ = "unknown"

__all__ = [
    # Main client
    "VacuumClient",
    # Direct transport clients
    "RESTVacuumClient",
    "MQTTVacuumClient",
    # Models
    "VacuumStatus",
    "VacuumMode",
    "VacuumEvent",
    "DeviceInfo",
    "ProbeResult",
    # Exceptions
    "SharklocalError",
    "ConnectError",
    "CommandError",
    "ActionNotSupportedError",
    "MappingNotFoundError",
    "DecoderError",
    # Mapping utilities
    "load_rest_mapping",
    "load_mqtt_mapping",
    "list_rest_mappings",
    "list_mqtt_mappings",
    # Extension points
    "register_decoder",
]
