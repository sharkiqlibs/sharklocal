"""Tests for sharklocal.mappings (loader utilities)."""

from pathlib import Path

import pytest
import yaml

from sharklocal.exceptions import MappingNotFoundError
from sharklocal.mappings import (
    list_mqtt_mappings,
    list_rest_mappings,
    load_mqtt_mapping,
    load_rest_mapping,
)
from sharklocal.mappings.base import MQTTMappingConfig, RESTMappingConfig


# ---------------------------------------------------------------------------
# Built-in REST mapping
# ---------------------------------------------------------------------------


def test_load_rest_mapping_builtin():
    cfg = load_rest_mapping("sharkiq_v1")
    assert isinstance(cfg, RESTMappingConfig)


def test_load_rest_mapping_builtin_id():
    cfg = load_rest_mapping("sharkiq_v1")
    assert cfg.id == "sharkiq_v1"


def test_load_rest_mapping_builtin_has_get_status():
    cfg = load_rest_mapping("sharkiq_v1")
    assert "get_status" in cfg.actions


def test_load_rest_mapping_builtin_has_commands():
    cfg = load_rest_mapping("sharkiq_v1")
    for action in ("start_cleaning", "stop", "go_home", "explore"):
        assert action in cfg.actions


def test_load_rest_mapping_not_found_raises():
    with pytest.raises(MappingNotFoundError):
        load_rest_mapping("nonexistent_mapping_xyz")


def test_load_rest_mapping_not_found_message():
    with pytest.raises(MappingNotFoundError, match="nonexistent_mapping_xyz"):
        load_rest_mapping("nonexistent_mapping_xyz")


# ---------------------------------------------------------------------------
# Built-in MQTT mapping
# ---------------------------------------------------------------------------


def test_load_mqtt_mapping_builtin():
    cfg = load_mqtt_mapping("sharkiq_v1")
    assert isinstance(cfg, MQTTMappingConfig)


def test_load_mqtt_mapping_builtin_id():
    cfg = load_mqtt_mapping("sharkiq_v1")
    assert cfg.id == "sharkiq_v1"


def test_load_mqtt_mapping_builtin_has_get_status():
    cfg = load_mqtt_mapping("sharkiq_v1")
    assert "get_status" in cfg.actions


def test_load_mqtt_mapping_not_found_raises():
    with pytest.raises(MappingNotFoundError):
        load_mqtt_mapping("nonexistent_mapping_xyz")


def test_load_mqtt_mapping_not_found_message():
    with pytest.raises(MappingNotFoundError, match="nonexistent_mapping_xyz"):
        load_mqtt_mapping("nonexistent_mapping_xyz")


# ---------------------------------------------------------------------------
# list_rest_mappings / list_mqtt_mappings
# ---------------------------------------------------------------------------


def test_list_rest_mappings_contains_builtin():
    names = list_rest_mappings()
    assert "sharkiq_v1" in names


def test_list_rest_mappings_is_sorted():
    names = list_rest_mappings()
    assert names == sorted(names)


def test_list_mqtt_mappings_contains_builtin():
    names = list_mqtt_mappings()
    assert "sharkiq_v1" in names


def test_list_mqtt_mappings_is_sorted():
    names = list_mqtt_mappings()
    assert names == sorted(names)


# ---------------------------------------------------------------------------
# Custom search_paths
# ---------------------------------------------------------------------------


_CUSTOM_REST_YAML = {
    "id": "custom_rest_v1",
    "description": "Custom REST",
    "transport": "http",
    "connection": {"port": 8080, "verify_ssl": False},
    "actions": {
        "get_status": {"method": "GET", "path": "/status", "response_map": "status"}
    },
    "mode_map": {},
}

_CUSTOM_MQTT_YAML = {
    "id": "custom_mqtt_v1",
    "description": "Custom MQTT",
    "connection": {"port": 1883},
    "topics": {"command": "/cmd", "status": "/status"},
    "encoding": "base64",
    "status_decoder": "sharkiq_protobuf_v1",
    "modes": {},
    "actions": {
        "start_cleaning": {"type": "command", "payload": "AAAA"},
    },
}


def test_load_rest_mapping_from_custom_path(tmp_path):
    rest_dir = tmp_path / "rest"
    rest_dir.mkdir()
    (rest_dir / "custom_rest_v1.yaml").write_text(yaml.dump(_CUSTOM_REST_YAML))
    cfg = load_rest_mapping("custom_rest_v1", search_paths=[rest_dir])
    assert cfg.id == "custom_rest_v1"
    assert cfg.transport == "http"


def test_load_mqtt_mapping_from_custom_path(tmp_path):
    mqtt_dir = tmp_path / "mqtt"
    mqtt_dir.mkdir()
    (mqtt_dir / "custom_mqtt_v1.yaml").write_text(yaml.dump(_CUSTOM_MQTT_YAML))
    cfg = load_mqtt_mapping("custom_mqtt_v1", search_paths=[mqtt_dir])
    assert cfg.id == "custom_mqtt_v1"


def test_list_rest_mappings_with_custom_path(tmp_path):
    rest_dir = tmp_path / "rest"
    rest_dir.mkdir()
    (rest_dir / "custom_rest_v1.yaml").write_text(yaml.dump(_CUSTOM_REST_YAML))
    names = list_rest_mappings(search_paths=[rest_dir])
    assert "custom_rest_v1" in names
    assert "sharkiq_v1" in names


def test_list_mqtt_mappings_with_custom_path(tmp_path):
    mqtt_dir = tmp_path / "mqtt"
    mqtt_dir.mkdir()
    (mqtt_dir / "custom_mqtt_v1.yaml").write_text(yaml.dump(_CUSTOM_MQTT_YAML))
    names = list_mqtt_mappings(search_paths=[mqtt_dir])
    assert "custom_mqtt_v1" in names
    assert "sharkiq_v1" in names


def test_load_rest_mapping_builtin_takes_priority_over_custom(tmp_path):
    """Built-in sharkiq_v1 is found before the custom path is searched."""
    rest_dir = tmp_path / "rest"
    rest_dir.mkdir()
    # Write a different YAML under the same name in the custom path
    shadow = {**_CUSTOM_REST_YAML, "id": "sharkiq_v1", "description": "shadow"}
    (rest_dir / "sharkiq_v1.yaml").write_text(yaml.dump(shadow))
    cfg = load_rest_mapping("sharkiq_v1", search_paths=[rest_dir])
    # Should load the built-in version (description won't be "shadow")
    assert cfg.description != "shadow"


def test_load_rest_mapping_nonexistent_custom_path_skipped(tmp_path):
    """Non-existent custom directory does not raise; falls through to not-found."""
    with pytest.raises(MappingNotFoundError):
        load_rest_mapping("custom_rest_v1", search_paths=[tmp_path / "no_such_dir"])


def test_list_rest_mappings_nonexistent_dir_skipped(tmp_path):
    """A non-existent custom search path is silently skipped; built-ins are still returned."""
    names = list_rest_mappings(search_paths=[tmp_path / "no_such_dir"])
    assert "sharkiq_v1" in names


def test_list_mqtt_mappings_nonexistent_dir_skipped(tmp_path):
    """A non-existent custom search path is silently skipped; built-ins are still returned."""
    names = list_mqtt_mappings(search_paths=[tmp_path / "no_such_dir"])
    assert "sharkiq_v1" in names
