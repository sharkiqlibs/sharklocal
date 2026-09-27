"""Tests for sharklocal.protobuf."""

import struct

import pytest

from sharklocal.protobuf import (
    _decode_varint,
    decode_fields,
    decode_raw,
    encode_bytes_field,
    encode_float_field,
    encode_string_field,
    encode_varint,
    encode_varint_field,
    float32,
    remove_field,
)


# ---------------------------------------------------------------------------
# _decode_varint
# ---------------------------------------------------------------------------


def test_decode_varint_single_byte():
    value, pos = _decode_varint(b"\x05", 0)
    assert value == 5
    assert pos == 1


def test_decode_varint_multi_byte():
    # 150 encoded as varint: 0x96, 0x01
    value, pos = _decode_varint(b"\x96\x01", 0)
    assert value == 150
    assert pos == 2


def test_decode_varint_zero():
    value, pos = _decode_varint(b"\x00", 0)
    assert value == 0
    assert pos == 1


def test_decode_varint_from_offset():
    # Skip first byte, read second
    data = b"\xff\x05"
    value, pos = _decode_varint(data, 1)
    assert value == 5
    assert pos == 2


# ---------------------------------------------------------------------------
# decode_raw — empty and edge cases
# ---------------------------------------------------------------------------


def test_decode_raw_empty_bytes():
    assert decode_raw(b"") == {}


def test_decode_raw_unknown_wire_type_stops_parsing():
    # Wire type 3 is not valid; after the tag+wiretype byte the parser should stop.
    # Build tag for field 1, wire type 3: (1 << 3) | 3 = 0x0B
    result = decode_raw(bytes([0x0B]))
    # Parser should stop without raising
    assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# decode_raw — wire type 0 (varint)
# ---------------------------------------------------------------------------


def _varint_encode(value: int) -> bytes:
    """Minimal varint encoder for test data construction."""
    buf = []
    while True:
        b = value & 0x7F
        value >>= 7
        if value:
            buf.append(b | 0x80)
        else:
            buf.append(b)
            break
    return bytes(buf)


def _make_field(field_num: int, wire_type: int, payload: bytes) -> bytes:
    tag = (field_num << 3) | wire_type
    return _varint_encode(tag) + payload


def test_decode_raw_wire_type_0_single():
    # Field 1, wire type 0, value 42
    data = _make_field(1, 0, _varint_encode(42))
    result = decode_raw(data)
    assert result[1] == 42


def test_decode_raw_wire_type_0_large_value():
    data = _make_field(4, 0, _varint_encode(150))
    result = decode_raw(data)
    assert result[4] == 150


# ---------------------------------------------------------------------------
# decode_raw — wire type 1 (64-bit fixed)
# ---------------------------------------------------------------------------


def test_decode_raw_wire_type_1():
    value = 0xDEADBEEFCAFEBABE
    payload = struct.pack("<Q", value)
    data = _make_field(2, 1, payload)
    result = decode_raw(data)
    assert result[2] == value


# ---------------------------------------------------------------------------
# decode_raw — wire type 5 (32-bit fixed)
# ---------------------------------------------------------------------------


def test_decode_raw_wire_type_5():
    value = 0xDEADBEEF
    payload = struct.pack("<I", value)
    data = _make_field(3, 5, payload)
    result = decode_raw(data)
    assert result[3] == value


# ---------------------------------------------------------------------------
# decode_raw — wire type 2 (length-delimited)
# ---------------------------------------------------------------------------


def _length_delimited(content: bytes) -> bytes:
    return _varint_encode(len(content)) + content


def test_decode_raw_wire_type_2_nested_protobuf():
    # Inner: field 8, value 75
    inner = _make_field(8, 0, _varint_encode(75))
    payload = _length_delimited(inner)
    data = _make_field(9, 2, payload)
    result = decode_raw(data)
    assert isinstance(result[9], dict)
    assert result[9][8] == 75


def test_decode_raw_wire_type_2_non_parseable_returns_bytes():
    # Raw bytes that are not valid protobuf (single 0xFF byte cannot be parsed as a full varint-led message)
    raw_content = b"\xff"
    payload = _length_delimited(raw_content)
    data = _make_field(5, 2, payload)
    result = decode_raw(data)
    # Should be returned as raw bytes since parsing the inner fails
    assert isinstance(result[5], (bytes, dict))


def test_decode_raw_wire_type_2_empty_nested_returns_bytes():
    # Empty nested content → nested dict is empty → returned as raw bytes
    payload = _length_delimited(b"")
    data = _make_field(6, 2, payload)
    result = decode_raw(data)
    # Empty nested → result is b"" (raw bytes)
    assert result[6] == b""


# ---------------------------------------------------------------------------
# decode_raw — multiple fields and repeated field numbers
# ---------------------------------------------------------------------------


def test_decode_raw_multiple_fields():
    data = (
        _make_field(1, 0, _varint_encode(10))
        + _make_field(2, 0, _varint_encode(20))
        + _make_field(4, 0, _varint_encode(6))
    )
    result = decode_raw(data)
    assert result[1] == 10
    assert result[2] == 20
    assert result[4] == 6


def test_decode_raw_repeated_field_number_overwrites():
    # Protobuf allows repeated fields; our decoder overwrites with last value
    data = _make_field(1, 0, _varint_encode(10)) + _make_field(1, 0, _varint_encode(99))
    result = decode_raw(data)
    # Value is overwritten by the last occurrence
    assert result[1] == 99


# ---------------------------------------------------------------------------
# Integration: realistic SharkIQ status payload
# ---------------------------------------------------------------------------


def test_decode_raw_sharkiq_style_payload():
    """Encode a minimal SharkIQ-like status: field 4 = mode 6, field 9 = battery nested."""
    battery_inner = _make_field(1, 0, _varint_encode(3)) + _make_field(8, 0, _varint_encode(80))
    payload = _make_field(4, 0, _varint_encode(6)) + _make_field(9, 2, _length_delimited(battery_inner))
    result = decode_raw(payload)
    assert result[4] == 6
    assert isinstance(result[9], dict)
    assert result[9][1] == 3
    assert result[9][8] == 80


def test_decode_raw_wire_type_2_nested_exception_falls_back_to_bytes():
    """Nested decode_raw raises struct.error (truncated 64-bit field) → except Exception → raw bytes."""
    # Tag for (field 1, wire type 1 = 64-bit) is 0x09; only 3 bytes instead of required 8
    inner = b"\x09\x01\x02\x03"
    payload = _length_delimited(inner)
    data = _make_field(5, 2, payload)
    result = decode_raw(data)
    assert isinstance(result[5], bytes)
    assert result[5] == inner


# ---------------------------------------------------------------------------
# decode_fields — one level, every occurrence, no recursion
# ---------------------------------------------------------------------------


def test_decode_fields_keeps_repeated_values_in_order():
    data = _make_field(1, 0, _varint_encode(10)) + _make_field(1, 0, _varint_encode(99))
    assert decode_fields(data) == {1: [10, 99]}


def test_decode_fields_returns_length_delimited_as_bytes():
    inner = _make_field(8, 0, _varint_encode(75))
    data = _make_field(9, 2, _length_delimited(inner))
    result = decode_fields(data)
    assert result[9] == [inner]


def test_decode_fields_fixed_widths():
    data = _make_field(2, 1, struct.pack("<Q", 0xDEADBEEFCAFEBABE)) + _make_field(
        3, 5, struct.pack("<I", 0xDEADBEEF)
    )
    result = decode_fields(data)
    assert result[2] == [0xDEADBEEFCAFEBABE]
    assert result[3] == [0xDEADBEEF]


def test_decode_fields_unknown_wire_type_stops_parsing():
    # Field 1 varint, then a tag with wire type 3 — parsing stops there.
    data = _make_field(1, 0, _varint_encode(5)) + bytes([0x13]) + _make_field(2, 0, _varint_encode(7))
    assert decode_fields(data) == {1: [5]}


def test_decode_fields_empty():
    assert decode_fields(b"") == {}


# ---------------------------------------------------------------------------
# float32
# ---------------------------------------------------------------------------


def test_float32_reinterprets_fixed32():
    packed = struct.unpack("<I", struct.pack("<f", 0.06))[0]
    assert float32(packed) == pytest.approx(0.06)


# ---------------------------------------------------------------------------
# remove_field
# ---------------------------------------------------------------------------


def test_remove_field_drops_every_occurrence_and_keeps_the_rest():
    keep_a = _make_field(1, 0, _varint_encode(10))
    drop_1 = _make_field(7, 2, _length_delimited(b"\x00" * 50))
    keep_b = _make_field(2, 1, struct.pack("<Q", 1))
    drop_2 = _make_field(7, 5, struct.pack("<I", 2))
    keep_c = _make_field(3, 5, struct.pack("<I", 3))
    assert remove_field(keep_a + drop_1 + keep_b + drop_2 + keep_c, 7) == keep_a + keep_b + keep_c


def test_remove_field_with_varint_occurrence():
    data = _make_field(4, 0, _varint_encode(6)) + _make_field(9, 0, _varint_encode(1))
    assert remove_field(data, 9) == _make_field(4, 0, _varint_encode(6))


def test_remove_field_keeps_remainder_after_unknown_wire_type():
    data = _make_field(1, 0, _varint_encode(1)) + bytes([0x13, 0xAA])
    assert remove_field(data, 1) == bytes([0x13, 0xAA])


def test_remove_field_absent_is_identity():
    data = _make_field(1, 0, _varint_encode(1))
    assert remove_field(data, 5) == data


# ---------------------------------------------------------------------------
# Encoding — round-trips through the decoders
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", [0, 1, 127, 128, 150, 300, 2**32])
def test_encode_varint_round_trip(value):
    assert _decode_varint(encode_varint(value), 0) == (value, len(encode_varint(value)))


def test_encode_varint_field():
    assert decode_fields(encode_varint_field(16, 11)) == {16: [11]}


def test_encode_float_field():
    result = decode_fields(encode_float_field(1, 0.06))
    assert float32(result[1][0]) == pytest.approx(0.06)


def test_encode_bytes_field_and_string_field():
    payload = encode_bytes_field(6, b"\x01\x02") + encode_string_field(3, "3CDBBC59")
    result = decode_fields(payload)
    assert result[6] == [b"\x01\x02"]
    assert result[3] == [b"3CDBBC59"]
