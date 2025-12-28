"""
JSON Schema - Data structures for experiment serialization.

Defines the schema for .glider experiment files following the
structure specified in the design document.
"""

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
from datetime import datetime
import json


# Current schema version
SCHEMA_VERSION = "1.0.0"


@dataclass
class PortSchema:
    """Schema for a node port definition."""
    name: str
    type: str  # "data" or "exec"
    data_type: Optional[str] = None  # e.g., "int", "float", "bool", "any"


@dataclass
class NodeSchema:
    """Schema for a node in the flow graph."""
    id: str
    type: str  # Full node type path, e.g., "glider.nodes.hardware.DigitalWriteNode"
    title: str
    position: Dict[str, float]  # {"x": float, "y": float}
    properties: Dict[str, Any] = field(default_factory=dict)
    inputs: List[PortSchema] = field(default_factory=list)
    outputs: List[PortSchema] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "type": self.type,
            "title": self.title,
            "position": self.position,
            "properties": self.properties,
            "inputs": [{"name": p.name, "type": p.type, "data_type": p.data_type} for p in self.inputs],
            "outputs": [{"name": p.name, "type": p.type, "data_type": p.data_type} for p in self.outputs],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NodeSchema":
        """Create from dictionary."""
        inputs = [PortSchema(**p) for p in data.get("inputs", [])]
        outputs = [PortSchema(**p) for p in data.get("outputs", [])]
        return cls(
            id=data["id"],
            type=data["type"],
            title=data["title"],
            position=data["position"],
            properties=data.get("properties", {}),
            inputs=inputs,
            outputs=outputs,
        )


@dataclass
class ConnectionSchema:
    """Schema for a connection between nodes."""
    id: str
    from_node: str
    from_port: int
    to_node: str
    to_port: int
    connection_type: str = "data"  # "data" or "exec"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConnectionSchema":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class BoardConfigSchema:
    """Schema for a hardware board configuration."""
    id: str
    type: str  # e.g., "telemetrix", "pigpio"
    port: Optional[str] = None  # Serial port for Arduino
    settings: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BoardConfigSchema":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class DeviceConfigSchema:
    """Schema for a hardware device configuration."""
    id: str
    type: str  # e.g., "digital_output", "analog_input", "servo"
    board_id: str
    pin: int
    name: Optional[str] = None
    settings: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DeviceConfigSchema":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class HardwareConfigSchema:
    """Schema for hardware configuration."""
    boards: List[BoardConfigSchema] = field(default_factory=list)
    devices: List[DeviceConfigSchema] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "boards": [b.to_dict() for b in self.boards],
            "devices": [d.to_dict() for d in self.devices],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HardwareConfigSchema":
        """Create from dictionary."""
        boards = [BoardConfigSchema.from_dict(b) for b in data.get("boards", [])]
        devices = [DeviceConfigSchema.from_dict(d) for d in data.get("devices", [])]
        return cls(boards=boards, devices=devices)


@dataclass
class DashboardWidgetSchema:
    """Schema for a dashboard widget configuration."""
    node_id: str
    position: int  # Order in the dashboard
    size: str = "normal"  # "small", "normal", "large"
    visible: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DashboardWidgetSchema":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class DashboardConfigSchema:
    """Schema for dashboard configuration."""
    layout_mode: str = "vertical"  # "vertical", "horizontal", "grid"
    columns: int = 1
    widgets: List[DashboardWidgetSchema] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "layout_mode": self.layout_mode,
            "columns": self.columns,
            "widgets": [w.to_dict() for w in self.widgets],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DashboardConfigSchema":
        """Create from dictionary."""
        widgets = [DashboardWidgetSchema.from_dict(w) for w in data.get("widgets", [])]
        return cls(
            layout_mode=data.get("layout_mode", "vertical"),
            columns=data.get("columns", 1),
            widgets=widgets,
        )


@dataclass
class FlowConfigSchema:
    """Schema for flow graph configuration."""
    nodes: List[NodeSchema] = field(default_factory=list)
    connections: List[ConnectionSchema] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "nodes": [n.to_dict() for n in self.nodes],
            "connections": [c.to_dict() for c in self.connections],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FlowConfigSchema":
        """Create from dictionary."""
        nodes = [NodeSchema.from_dict(n) for n in data.get("nodes", [])]
        connections = [ConnectionSchema.from_dict(c) for c in data.get("connections", [])]
        return cls(nodes=nodes, connections=connections)


@dataclass
class MetadataSchema:
    """Schema for experiment metadata."""
    name: str
    description: str = ""
    author: str = ""
    created: str = ""
    modified: str = ""
    tags: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.created:
            self.created = datetime.now().isoformat()
        if not self.modified:
            self.modified = self.created

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MetadataSchema":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class ExperimentSchema:
    """
    Root schema for a GLIDER experiment file.

    This is the top-level structure saved as a .glider file.
    """
    schema_version: str = SCHEMA_VERSION
    metadata: MetadataSchema = field(default_factory=lambda: MetadataSchema(name="Untitled"))
    hardware: HardwareConfigSchema = field(default_factory=HardwareConfigSchema)
    flow: FlowConfigSchema = field(default_factory=FlowConfigSchema)
    dashboard: DashboardConfigSchema = field(default_factory=DashboardConfigSchema)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "schema_version": self.schema_version,
            "metadata": self.metadata.to_dict(),
            "hardware": self.hardware.to_dict(),
            "flow": self.flow.to_dict(),
            "dashboard": self.dashboard.to_dict(),
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExperimentSchema":
        """Create from dictionary."""
        return cls(
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            metadata=MetadataSchema.from_dict(data.get("metadata", {"name": "Untitled"})),
            hardware=HardwareConfigSchema.from_dict(data.get("hardware", {})),
            flow=FlowConfigSchema.from_dict(data.get("flow", {})),
            dashboard=DashboardConfigSchema.from_dict(data.get("dashboard", {})),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "ExperimentSchema":
        """Create from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)

    def update_modified(self) -> None:
        """Update the modified timestamp."""
        self.metadata.modified = datetime.now().isoformat()
