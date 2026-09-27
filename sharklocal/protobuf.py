"""Pure-Python protobuf codec for SharkIQ MQTT messages.

Decodes raw protobuf wire format without a compiled schema, and encodes the
few field shapes needed to build command payloads.
Adapted for the SharkIQ local MQTT protocol.
"""

from __future__ import annotations

import struct
from typing import Any, Dict, List, Tuple

# Wire types, per the protobuf encoding specification.
WIRE_VARINT = 0
WIRE_FIXED64 = 1
WIRE_LENGTH_DELIMITED = 2
WIRE_FIXED32 = 5


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


def decode_fields(data: bytes) -> Dict[int, List[Any]]:
    """Decode one protobuf message level, keeping every occurrence of a field.

    Unlike :func:`decode_raw`, this does **not** recurse into length-delimited
    fields and does **not** collapse repeated fields — each field number maps
    to the list of values in wire order. Length-delimited values are returned
    as ``bytes`` for the caller to interpret (nested message, string, or a
    packed binary blob such as a map raster), and 32-bit fixed values are
    returned as the raw unsigned integer (see :func:`float32`).

    Use this for messages whose layout is known, where ``decode_raw``'s
    heuristics would mis-parse binary blobs or drop repeated entries.
    """
    result: Dict[int, List[Any]] = {}
    pos = 0

    while pos < len(data):
        tag, pos = _decode_varint(data, pos)
        field_num = tag >> 3
        wire_type = tag & 0x7

        if wire_type == WIRE_VARINT:
            value, pos = _decode_varint(data, pos)
        elif wire_type == WIRE_FIXED64:
            value = struct.unpack("<Q", data[pos : pos + 8])[0]
            pos += 8
        elif wire_type == WIRE_LENGTH_DELIMITED:
            length, pos = _decode_varint(data, pos)
            value = data[pos : pos + length]
            pos += length
        elif wire_type == WIRE_FIXED32:
            value = struct.unpack("<I", data[pos : pos + 4])[0]
            pos += 4
        else:
            # Unknown wire type — cannot continue parsing safely.
            break

        result.setdefault(field_num, []).append(value)

    return result


def float32(value: int) -> float:
    """Reinterpret a decoded 32-bit fixed field as an IEEE-754 ``float``."""
    return struct.unpack("<f", struct.pack("<I", value))[0]


def remove_field(data: bytes, field_num: int) -> bytes:
    """Return *data* with every top-level occurrence of *field_num* removed.

    Other fields are copied byte-for-byte, so the result decodes identically
    apart from the dropped field. Parsing stops at an unknown wire type, and
    the remainder is kept as-is.
    """
    out = bytearray()
    pos = 0

    while pos < len(data):
        start = pos
        tag, pos = _decode_varint(data, pos)
        wire_type = tag & 0x7

        if wire_type == WIRE_VARINT:
            _, pos = _decode_varint(data, pos)
        elif wire_type == WIRE_FIXED64:
            pos += 8
        elif wire_type == WIRE_LENGTH_DELIMITED:
            length, pos = _decode_varint(data, pos)
            pos += length
        elif wire_type == WIRE_FIXED32:
            pos += 4
        else:
            out += data[start:]
            break

        if (tag >> 3) != field_num:
            out += data[start:pos]

    return bytes(out)


# ---------------------------------------------------------------------------
# Encoding — enough to build command payloads
# ---------------------------------------------------------------------------


def encode_varint(value: int) -> bytes:
    """Encode a non-negative integer as a protobuf varint."""
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def encode_varint_field(field_num: int, value: int) -> bytes:
    """Encode ``field_num`` as a varint field."""
    return encode_varint((field_num << 3) | WIRE_VARINT) + encode_varint(value)


def encode_float_field(field_num: int, value: float) -> bytes:
    """Encode ``field_num`` as a 32-bit ``float`` field."""
    return encode_varint((field_num << 3) | WIRE_FIXED32) + struct.pack("<f", value)


def encode_bytes_field(field_num: int, content: bytes) -> bytes:
    """Encode ``field_num`` as a length-delimited field (nested message or bytes)."""
    return (
        encode_varint((field_num << 3) | WIRE_LENGTH_DELIMITED)
        + encode_varint(len(content))
        + content
    )


def encode_string_field(field_num: int, text: str) -> bytes:
    """Encode ``field_num`` as a UTF-8 string field."""
    return encode_bytes_field(field_num, text.encode("utf-8"))
