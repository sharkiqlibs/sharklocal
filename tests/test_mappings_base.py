"""Tests for sharklocal.mappings.base (RESTMappingConfig and MQTTMappingConfig)."""

import pytest

from sharklocal.mappings.base import (
    MQTTActionSpec,
    MQTTMappingConfig,
    RESTActionSpec,
    RESTMappingConfig,
)


# ---------------------------------------------------------------------------
# RESTActionSpec
# ---------------------------------------------------------------------------


def test_rest_action_spec_required_fields():
    spec = RESTActionSpec(method="GET", path="/get/status")
    assert spec.method == "GET"
    assert spec.path == "/get/status"
    assert spec.response_map is None
    assert spec.body is None
    assert spec.headers is None


def test_rest_action_spec_all_fields():
    spec = RESTActionSpec(
        method="POST",
        path="/set/clean",
        response_map="status",
        body={"key": "val"},
        headers={"X-Custom": "yes"},
    )
    assert spec.response_map == "status"
    assert spec.body == {"key": "val"}
    assert spec.headers == {"X-Custom": "yes"}


# ---------------------------------------------------------------------------
# MQTTActionSpec
# ---------------------------------------------------------------------------


def test_mqtt_action_spec_defaults():
    spec = MQTTActionSpec(type="command", payload="AAAA")
    assert spec.type == "command"
    assert spec.payload == "AAAA"
    assert spec.timeout == pytest.approx(5.0)


def test_mqtt_action_spec_custom_timeout():
    spec = MQTTActionSpec(type="status_request", payload="BBBB", timeout=10.0)
    assert spec.timeout == pytest.approx(10.0)


# ---------------------------------------------------------------------------
# RESTMappingConfig.from_dict
# ---------------------------------------------------------------------------


_REST_DICT = {
    "id": "sharkiq_v1",
    "description": "SharkIQ REST v1",
    "transport": "https",
    "connection": {"port": 443, "verify_ssl": False},
    "mode_map": {
        "ready": "docked",
        "cleaning": "cleaning",
        "go_home": "returning_to_dock",
    },
    "actions": {
        "get_status": {"method": "GET", "path": "/get/status", "response_map": "status"},
        "start_cleaning": {"method": "GET", "path": "/set/clean_all"},
        "with_body": {"method": "POST", "path": "/set/x", "body": {"a": 1}, "headers": {"X-H": "v"}},
    },
}


def test_rest_mapping_from_dict_id():
    cfg = RESTMappingConfig.from_dict(_REST_DICT)
    assert cfg.id == "sharkiq_v1"


def test_rest_mapping_from_dict_description():
    cfg = RESTMappingConfig.from_dict(_REST_DICT)
    assert cfg.description == "SharkIQ REST v1"


def test_rest_mapping_from_dict_transport():
    cfg = RESTMappingConfig.from_dict(_REST_DICT)
    assert cfg.transport == "https"


def test_rest_mapping_from_dict_port():
    cfg = RESTMappingConfig.from_dict(_REST_DICT)
    assert cfg.port == 443


def test_rest_mapping_from_dict_verify_ssl():
    cfg = RESTMappingConfig.from_dict(_REST_DICT)
    assert cfg.verify_ssl is False


def test_rest_mapping_from_dict_mode_map():
    cfg = RESTMappingConfig.from_dict(_REST_DICT)
    assert cfg.mode_map["ready"] == "docked"
    assert cfg.mode_map["cleaning"] == "cleaning"


def test_rest_mapping_from_dict_actions_count():
    cfg = RESTMappingConfig.from_dict(_REST_DICT)
    assert len(cfg.actions) == 3


def test_rest_mapping_from_dict_action_with_response_map():
    cfg = RESTMappingConfig.from_dict(_REST_DICT)
    spec = cfg.actions["get_status"]
    assert spec.method == "GET"
    assert spec.path == "/get/status"
    assert spec.response_map == "status"
    assert spec.body is None
    assert spec.headers is None


def test_rest_mapping_from_dict_command_action_no_response_map():
    cfg = RESTMappingConfig.from_dict(_REST_DICT)
    spec = cfg.actions["start_cleaning"]
    assert spec.response_map is None


def test_rest_mapping_from_dict_action_with_body_and_headers():
    cfg = RESTMappingConfig.from_dict(_REST_DICT)
    spec = cfg.actions["with_body"]
    assert spec.body == {"a": 1}
    assert spec.headers == {"X-H": "v"}


def test_rest_mapping_from_dict_defaults_when_keys_absent():
    minimal = {"id": "test", "actions": {}}
    cfg = RESTMappingConfig.from_dict(minimal)
    assert cfg.transport == "https"
    assert cfg.port == 443
    assert cfg.verify_ssl is True
    assert cfg.mode_map == {}
    assert cfg.description == ""


# ---------------------------------------------------------------------------
# MQTTMappingConfig.from_dict
# ---------------------------------------------------------------------------


_MQTT_DICT = {
    "id": "sharkiq_v1",
    "description": "SharkIQ MQTT v1",
    "connection": {"port": 1883},
    "topics": {"command": "/qfeel/PbInput", "status": "/qfeel/PbOutput"},
    "encoding": "base64",
    "status_decoder": "sharkiq_protobuf_v1",
    "modes": {6: "cleaning", 7: "returning_to_dock", 13: "docking", 14: "docked"},
    "actions": {
        "start_cleaning": {"type": "command", "payload": "AAAA"},
        "get_status": {"type": "status_request", "payload": "BBBB", "timeout": 3.0},
    },
}


def test_mqtt_mapping_from_dict_id():
    cfg = MQTTMappingConfig.from_dict(_MQTT_DICT)
    assert cfg.id == "sharkiq_v1"


def test_mqtt_mapping_from_dict_port():
    cfg = MQTTMappingConfig.from_dict(_MQTT_DICT)
    assert cfg.port == 1883


def test_mqtt_mapping_from_dict_topics():
    cfg = MQTTMappingConfig.from_dict(_MQTT_DICT)
    assert cfg.command_topic == "/qfeel/PbInput"
    assert cfg.status_topic == "/qfeel/PbOutput"


def test_mqtt_mapping_from_dict_encoding():
    cfg = MQTTMappingConfig.from_dict(_MQTT_DICT)
    assert cfg.encoding == "base64"


def test_mqtt_mapping_from_dict_status_decoder():
    cfg = MQTTMappingConfig.from_dict(_MQTT_DICT)
    assert cfg.status_decoder == "sharkiq_protobuf_v1"


def test_mqtt_mapping_from_dict_modes_are_int_keyed():
    cfg = MQTTMappingConfig.from_dict(_MQTT_DICT)
    assert cfg.modes[6] == "cleaning"
    assert cfg.modes[14] == "docked"
    for k in cfg.modes:
        assert isinstance(k, int)


def test_mqtt_mapping_from_dict_actions_command():
    cfg = MQTTMappingConfig.from_dict(_MQTT_DICT)
    spec = cfg.actions["start_cleaning"]
    assert spec.type == "command"
    assert spec.payload == "AAAA"
    assert spec.timeout == pytest.approx(5.0)


def test_mqtt_mapping_from_dict_actions_status_request_with_timeout():
    cfg = MQTTMappingConfig.from_dict(_MQTT_DICT)
    spec = cfg.actions["get_status"]
    assert spec.type == "status_request"
    assert spec.timeout == pytest.approx(3.0)


def test_mqtt_mapping_from_dict_defaults_when_keys_absent():
    minimal = {"id": "test", "actions": {}, "status_decoder": ""}
    cfg = MQTTMappingConfig.from_dict(minimal)
    assert cfg.port == 1883
    assert cfg.command_topic == "/qfeel/PbInput"
    assert cfg.status_topic == "/qfeel/PbOutput"
    assert cfg.encoding == "base64"
    assert cfg.modes == {}
    assert cfg.description == ""


# ---------------------------------------------------------------------------
# priority field
# ---------------------------------------------------------------------------


def test_rest_mapping_priority_default_is_zero():
    minimal = {"id": "test", "actions": {}}
    cfg = RESTMappingConfig.from_dict(minimal)
    assert cfg.priority == 0


def test_rest_mapping_priority_parsed_from_dict():
    data = dict(_REST_DICT, priority=20)
    cfg = RESTMappingConfig.from_dict(data)
    assert cfg.priority == 20


def test_rest_mapping_priority_coerced_to_int():
    data = dict(_REST_DICT, priority="15")
    cfg = RESTMappingConfig.from_dict(data)
    assert cfg.priority == 15
    assert isinstance(cfg.priority, int)


def test_mqtt_mapping_priority_default_is_zero():
    minimal = {"id": "test", "actions": {}, "status_decoder": ""}
    cfg = MQTTMappingConfig.from_dict(minimal)
    assert cfg.priority == 0


def test_mqtt_mapping_priority_parsed_from_dict():
    data = dict(_MQTT_DICT, priority=30)
    cfg = MQTTMappingConfig.from_dict(data)
    assert cfg.priority == 30


def test_mqtt_mapping_priority_coerced_to_int():
    data = dict(_MQTT_DICT, priority="5")
    cfg = MQTTMappingConfig.from_dict(data)
    assert cfg.priority == 5
    assert isinstance(cfg.priority, int)
