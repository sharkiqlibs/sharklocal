"""Pure-Python protobuf decoder for SharkIQ MQTT messages.

Decodes raw protobuf wire format without a compiled schema.
Adapted for the SharkIQ local MQTT protocol.
"""

from __future__ import annotations

import struct
from typing import Any, Dict, Tuple


def _decode_varint(data: bytes, pos: int) -> Tuple[int, int]:
    """Decode a protobuf varint. Returns (value, next_position)."""
    result = 0
    shift = 0
    while pos < len(data):
        byte = data[pos]
        result |= (byte & 0x7F) << shift
        pos += 1
        if not (byte & 0x80):
            break
        shift += 7
    return result, pos


def decode_raw(data: bytes) -> Dict[int, Any]:
    """Decode protobuf-encoded bytes without a schema.

    Returns a dict mapping field numbers to values. Nested length-delimited
    fields are decoded recursively when they contain valid protobuf data.

    Wire types handled:
      0 - Varint
      1 - 64-bit fixed
      2 - Length-delimited (bytes / string / nested message)
      5 - 32-bit fixed
    """
    result: Dict[int, Any] = {}
    pos = 0

    while pos < len(data):
        if pos >= len(data):  # pragma: no cover
            break  # pragma: no cover

        tag, pos = _decode_varint(data, pos)
        field_num = tag >> 3
        wire_type = tag & 0x7

        if wire_type == 0:  # Varint
            value, pos = _decode_varint(data, pos)
            result[field_num] = value

        elif wire_type == 1:  # 64-bit fixed
            value = struct.unpack("<Q", data[pos : pos + 8])[0]
            pos += 8
            result[field_num] = value

        elif wire_type == 2:  # Length-delimited
            length, pos = _decode_varint(data, pos)
            raw_bytes = data[pos : pos + length]
            pos += length
            try:
                nested = decode_raw(raw_bytes)
                result[field_num] = nested if nested else raw_bytes
            except Exception:
                result[field_num] = raw_bytes

        elif wire_type == 5:  # 32-bit fixed
            value = struct.unpack("<I", data[pos : pos + 4])[0]
            pos += 4
            result[field_num] = value

        else:  # pragma: no cover
            # Unknown wire type — cannot continue parsing safely.
            break  # pragma: no cover

    return result
