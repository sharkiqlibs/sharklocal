"""Base dataclasses for REST and MQTT mapping configurations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class RESTActionSpec:
    """Specification for a single REST action."""

    method: str
    path: str
    response_map: Optional[str] = None
    body: Optional[Dict[str, Any]] = None
    headers: Optional[Dict[str, str]] = None


@dataclass
class MQTTActionSpec:
    """Specification for a single MQTT action."""

    type: str  # "command" or "status_request"
    payload: str
    timeout: float = 5.0


@dataclass
class RESTMappingConfig:
    """Full configuration for a REST transport mapping."""

    id: str
    description: str
    transport: str  # "http" or "https"
    port: int
    verify_ssl: bool
    actions: Dict[str, RESTActionSpec]
    mode_map: Dict[str, str] = field(default_factory=dict)
    priority: int = 0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RESTMappingConfig:
        actions = {
            name: RESTActionSpec(
                method=spec["method"],
                path=spec["path"],
                response_map=spec.get("response_map"),
                body=spec.get("body"),
                headers=spec.get("headers"),
            )
            for name, spec in data.get("actions", {}).items()
        }
        conn = data.get("connection", {})
        return cls(
            id=data["id"],
            description=data.get("description", ""),
            transport=data.get("transport", "https"),
            port=conn.get("port", 443),
            verify_ssl=conn.get("verify_ssl", True),
            actions=actions,
            mode_map=data.get("mode_map", {}),
            priority=int(data.get("priority", 0)),
        )


@dataclass
class MQTTMappingConfig:
    """Full configuration for an MQTT transport mapping."""

    id: str
    description: str
    port: int
    command_topic: str
    status_topic: str
    encoding: str
    status_decoder: str
    actions: Dict[str, MQTTActionSpec]
    modes: Dict[int, str]
    priority: int = 0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MQTTMappingConfig:
        actions = {
            name: MQTTActionSpec(
                type=spec["type"],
                payload=spec["payload"],
                timeout=float(spec.get("timeout", 5.0)),
            )
            for name, spec in data.get("actions", {}).items()
        }
        conn = data.get("connection", {})
        topics = data.get("topics", {})
        modes = {int(k): v for k, v in data.get("modes", {}).items()}
        return cls(
            id=data["id"],
            description=data.get("description", ""),
            port=conn.get("port", 1883),
            command_topic=topics.get("command", "/qfeel/PbInput"),
            status_topic=topics.get("status", "/qfeel/PbOutput"),
            encoding=data.get("encoding", "base64"),
            status_decoder=data.get("status_decoder", ""),
            actions=actions,
            modes=modes,
            priority=int(data.get("priority", 0)),
        )
