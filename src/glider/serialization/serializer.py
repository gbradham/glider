"""
Experiment Serializer - Save and load experiment files.

Handles conversion between GLIDER runtime objects and
JSON-serializable schema objects.
"""

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from glider.serialization.atomic import atomic_write_text
from glider.serialization.schema import (
    SCHEMA_VERSION,
    BoardConfigSchema,
    ConnectionSchema,
    DashboardConfigSchema,
    DeviceConfigSchema,
    ExperimentSchema,
    FlowConfigSchema,
    HardwareConfigSchema,
    MetadataSchema,
    NodeSchema,
    PortSchema,
    SchemaValidationError,
)

if TYPE_CHECKING:
    from glider.core.experiment_session import ExperimentSession
    from glider.core.flow_engine import FlowEngine
    from glider.core.hardware_manager import HardwareManager
    from glider.nodes.base_node import GliderNode

logger = logging.getLogger(__name__)


class ExperimentSerializer:
    """
    Serializer for GLIDER experiment files.

    Provides save/load functionality with schema validation
    and version migration support.
    """

    # File extension for GLIDER experiments
    FILE_EXTENSION = ".glider"

    def __init__(self):
        self._node_registry: dict[str, type[GliderNode]] = {}

    def register_node_type(self, node_type: str, node_class: type["GliderNode"]) -> None:
        """
        Register a node type for deserialization.

        Args:
            node_type: Full type path (e.g., "glider.nodes.hardware.DigitalWriteNode")
            node_class: The node class
        """
        self._node_registry[node_type] = node_class

    def save(
        self,
        path: Path,
        session: "ExperimentSession",
        flow_engine: Optional["FlowEngine"] = None,
        hardware_manager: Optional["HardwareManager"] = None,
    ) -> None:
        """
        Save an experiment session to a file.

        Args:
            path: File path to save to
            session: The experiment session to save
            flow_engine: Optional flow engine for node/connection data
            hardware_manager: Optional hardware manager for device config
        """
        # Build schema from session
        schema = self._session_to_schema(session, flow_engine, hardware_manager)

        # Update modified timestamp
        schema.update_modified()

        # Ensure .glider extension
        if path.suffix != self.FILE_EXTENSION:
            path = path.with_suffix(self.FILE_EXTENSION)

        # Atomic write: temp file + fsync + os.replace. A crash mid-write
        # leaves either the prior version or the new one — never a truncated
        # file. The .glider file is the experiment's design notebook;
        # corrupting it on power loss is the worst failure mode for a
        # scientific tool.
        atomic_write_text(path, schema.to_json(indent=2))

        logger.info(f"Saved experiment to {path}")

    def load(self, path: Path) -> ExperimentSchema:
        """
        Load an experiment schema from a file.

        Args:
            path: File path to load from

        Returns:
            The loaded experiment schema

        Raises:
            FileNotFoundError: If the file doesn't exist
            PermissionError: If the file cannot be read
            SchemaValidationError: If the file is malformed or invalid
            ValueError: If schema validation fails
        """
        try:
            with open(path, encoding="utf-8") as f:
                content = f.read()
        except FileNotFoundError:
            logger.error(f"Experiment file not found: {path}")
            raise
        except PermissionError:
            logger.error(f"Permission denied reading experiment file: {path}")
            raise
        except UnicodeDecodeError as e:
            logger.error(f"Encoding error reading {path}: {e}")
            raise SchemaValidationError(
                f"File encoding error: {e}. Ensure the file is UTF-8 encoded.",
                path=str(path),
            ) from e
        except OSError as e:
            logger.error(f"Error reading experiment file {path}: {e}")
            raise SchemaValidationError(
                f"Error reading file: {e}",
                path=str(path),
            ) from e

        # Validate file is not empty
        if not content.strip():
            raise SchemaValidationError(
                "File is empty",
                path=str(path),
            )

        try:
            schema = ExperimentSchema.from_json(content)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {path}: line {e.lineno}, column {e.colno}")
            raise SchemaValidationError(
                f"Invalid JSON at line {e.lineno}, column {e.colno}: {e.msg}",
                path=str(path),
            ) from e
        except SchemaValidationError:
            # Re-raise with file path context
            raise

        # Validate and migrate if needed
        try:
            schema = self._validate_and_migrate(schema)
        except ValueError as e:
            raise SchemaValidationError(str(e), path=str(path)) from e

        logger.info(f"Loaded experiment from {path}")
        return schema

    def apply_to_session(
        self,
        schema: ExperimentSchema,
        session: "ExperimentSession",
        flow_engine: Optional["FlowEngine"] = None,
        hardware_manager: Optional["HardwareManager"] = None,
    ) -> None:
        """
        Apply a loaded schema to a session.

        Args:
            schema: The experiment schema to apply
            session: The session to update
            flow_engine: Optional flow engine to populate
            hardware_manager: Optional hardware manager to configure
        """
        # Apply metadata
        session.name = schema.metadata.name
        session.description = schema.metadata.description
        session.author = schema.metadata.author
        session.tags = schema.metadata.tags.copy()

        # Apply hardware config
        if hardware_manager:
            self._apply_hardware_config(schema.hardware, hardware_manager)

        # Apply flow config
        if flow_engine:
            self._apply_flow_config(schema.flow, flow_engine)

        # Apply dashboard config
        session.dashboard_config = schema.dashboard.to_dict()

        logger.info(f"Applied schema to session: {session.name}")

    def _session_to_schema(
        self,
        session: "ExperimentSession",
        flow_engine: Optional["FlowEngine"],
        hardware_manager: Optional["HardwareManager"],
    ) -> ExperimentSchema:
        """Convert a session to a schema."""
        # Build metadata
        metadata = MetadataSchema(
            name=session.name,
            description=session.description,
            author=session.author,
            tags=session.tags.copy(),
        )

        # Build hardware config
        hardware = HardwareConfigSchema()
        if hardware_manager:
            hardware = self._extract_hardware_config(hardware_manager)

        # Build flow config
        flow = FlowConfigSchema()
        if flow_engine:
            flow = self._extract_flow_config(flow_engine)

        # Build dashboard config
        dashboard = DashboardConfigSchema.from_dict(session.dashboard_config)

        return ExperimentSchema(
            metadata=metadata,
            hardware=hardware,
            flow=flow,
            dashboard=dashboard,
        )

    def _extract_hardware_config(self, hardware_manager: "HardwareManager") -> HardwareConfigSchema:
        """Extract hardware configuration from manager."""
        boards = []
        devices = []

        # Extract board configs
        for board_id, board in hardware_manager.boards.items():
            board_config = BoardConfigSchema(
                id=board_id,
                type=type(board).__name__.lower().replace("board", ""),
                port=getattr(board, "port", None),
                settings=getattr(board, "settings", {}),
            )
            boards.append(board_config)

        # Extract device configs
        for device_id, device in hardware_manager.devices.items():
            device_config = DeviceConfigSchema(
                id=device_id,
                type=getattr(device, "device_type", "unknown"),
                board_id=getattr(device, "board_id", ""),
                pin=getattr(device, "pin", 0),
                name=getattr(device, "name", None),
                settings=getattr(device, "settings", {}),
            )
            devices.append(device_config)

        return HardwareConfigSchema(boards=boards, devices=devices)

    def _extract_flow_config(self, flow_engine: "FlowEngine") -> FlowConfigSchema:
        """Extract flow configuration from engine."""
        nodes = []
        connections = []

        # Extract nodes
        for node_id, node in flow_engine.nodes.items():
            # Get position from GUI metadata if available
            position = getattr(node, "gui_position", {"x": 0.0, "y": 0.0})

            # Build input ports
            inputs = []
            for i, inp in enumerate(getattr(node, "inputs", [])):
                port = PortSchema(
                    name=getattr(inp, "name", f"in_{i}"),
                    type="exec" if getattr(inp, "is_exec", False) else "data",
                    data_type=getattr(inp, "data_type", "any"),
                )
                inputs.append(port)

            # Build output ports
            outputs = []
            for i, out in enumerate(getattr(node, "outputs", [])):
                port = PortSchema(
                    name=getattr(out, "name", f"out_{i}"),
                    type="exec" if getattr(out, "is_exec", False) else "data",
                    data_type=getattr(out, "data_type", "any"),
                )
                outputs.append(port)

            node_schema = NodeSchema(
                id=node_id,
                type=f"{type(node).__module__}.{type(node).__name__}",
                title=getattr(node, "title", type(node).__name__),
                position=position,
                properties=self._extract_node_properties(node),
                inputs=inputs,
                outputs=outputs,
            )
            nodes.append(node_schema)

        # Extract connections
        for conn_id, conn in flow_engine.connections.items():
            conn_schema = ConnectionSchema(
                id=conn_id,
                from_node=conn.from_node_id,
                from_port=conn.from_port,
                to_node=conn.to_node_id,
                to_port=conn.to_port,
                connection_type="exec" if getattr(conn, "is_exec", False) else "data",
            )
            connections.append(conn_schema)

        return FlowConfigSchema(nodes=nodes, connections=connections)

    def _extract_node_properties(self, node: "GliderNode") -> dict[str, Any]:
        """Extract serializable properties from a node.

        Properties are sourced from the node's ``get_state()`` method (returns
        the per-node ``_state`` dict, plus any typed-attribute mixins
        subclasses include in their override) **plus** a small set of common
        attributes (``visible_in_runner``, ``enabled``) that live outside
        ``_state``.

        The state payload is stored under the ``"state"`` key. Loaders that
        understand this key pass it through to ``flow_engine.create_node(...,
        state=...)`` which calls ``node.set_state(state)``. Older saves that
        used flat top-level properties continue to load because
        ``create_node`` falls back to setting ``self._state`` directly when
        ``set_state`` is absent.

        This fixes the prior bug where ``getattr(node, "property_names", [])``
        always returned ``[]`` (no node class defined ``property_names``), so
        every node-local property was silently dropped on every save.
        """
        properties: dict[str, Any] = {}

        # Common attributes that live outside the per-node state dict.
        if hasattr(node, "visible_in_runner"):
            properties["visible_in_runner"] = bool(node.visible_in_runner)
        elif hasattr(node, "_visible_in_runner"):
            # Third-party and older built-in nodes may expose only the
            # backing attribute. Preserve runner-dashboard visibility for
            # those nodes as well.
            properties["visible_in_runner"] = bool(node._visible_in_runner)
        if hasattr(node, "_enabled"):
            properties["enabled"] = bool(node._enabled)

        # The node's authoritative serializable state. Use get_state() rather
        # than to_dict() so we only embed what's actually needed to restore
        # the node — the ID, title, position are owned by the NodeSchema.
        if hasattr(node, "get_state") and callable(node.get_state):
            try:
                state = node.get_state()
            except Exception as e:
                logger.warning(
                    "get_state() raised on %s (%s); node state will be empty",
                    getattr(node, "_glider_id", "?"), type(node).__name__, exc_info=e,
                )
                state = {}
            if isinstance(state, dict) and state:
                properties["state"] = state

        return properties

    def _apply_hardware_config(
        self, config: HardwareConfigSchema, hardware_manager: "HardwareManager"
    ) -> None:
        """Apply hardware configuration to manager."""
        # Clear existing config
        hardware_manager.clear()

        # Add boards
        for board_config in config.boards:
            hardware_manager.add_board(
                board_id=board_config.id,
                board_type=board_config.type,
                port=board_config.port,
                **board_config.settings,
            )

        # Add devices
        for device_config in config.devices:
            hardware_manager.add_device(
                device_id=device_config.id,
                device_type=device_config.type,
                board_id=device_config.board_id,
                pin=device_config.pin,
                name=device_config.name,
                **device_config.settings,
            )

    def _apply_flow_config(self, config: FlowConfigSchema, flow_engine: "FlowEngine") -> None:
        """Apply flow configuration to engine."""
        # Clear existing flow
        flow_engine.clear()

        # Create nodes. The persisted node state lives under
        # node_schema.properties["state"] (written by _extract_node_properties).
        # We pass it through to create_node which calls node.set_state(state)
        # internally; this is the round-trip path that restores camera
        # indices, GPIO pins, thresholds, ITI durations, etc. — every node
        # parameter is preserved.
        #
        # Other keys in properties (visible_in_runner, enabled) are applied to
        # the constructed node directly.
        for node_schema in config.nodes:
            node_type = node_schema.type
            props = dict(node_schema.properties or {})
            state = props.pop("state", None)
            visible_in_runner = props.pop("visible_in_runner", None)
            enabled = props.pop("enabled", None)

            try:
                node = flow_engine.create_node(
                    node_id=node_schema.id,
                    node_type=node_type,
                    position=(
                        node_schema.position.get("x", 0.0),
                        node_schema.position.get("y", 0.0),
                    ),
                    state=state,
                )
            except (ValueError, KeyError) as e:
                logger.warning(f"Skipping node {node_schema.id} ({node_type}): {e}")
                continue

            if node is None:
                continue

            if visible_in_runner is not None and hasattr(node, "_visible_in_runner"):
                node._visible_in_runner = bool(visible_in_runner)
            if enabled is not None and hasattr(node, "_enabled"):
                node._enabled = bool(enabled)

            # Preserve GUI position metadata as dict for downstream consumers.
            node.gui_position = node_schema.position

        # Create connections
        for conn_schema in config.connections:
            try:
                flow_engine.create_connection(
                    connection_id=conn_schema.id,
                    from_node_id=conn_schema.from_node,
                    from_output=conn_schema.from_port,
                    to_node_id=conn_schema.to_node,
                    to_input=conn_schema.to_port,
                    connection_type=conn_schema.connection_type,
                )
            except (AttributeError, ValueError, KeyError) as e:
                logger.warning(
                    f"Skipping connection {conn_schema.from_node}->{conn_schema.to_node}: {e}"
                )

    def _validate_and_migrate(self, schema: ExperimentSchema) -> ExperimentSchema:
        """
        Validate schema and migrate from older versions if needed.

        Args:
            schema: The schema to validate

        Returns:
            Validated (and possibly migrated) schema

        Raises:
            ValueError: If schema is invalid and cannot be migrated
        """
        version = schema.schema_version

        # Check version compatibility
        major, minor, patch = map(int, version.split("."))
        current_major, current_minor, current_patch = map(int, SCHEMA_VERSION.split("."))

        if major > current_major:
            raise ValueError(f"Schema version {version} is newer than supported {SCHEMA_VERSION}")

        # Apply migrations for older versions
        if major < current_major or (major == current_major and minor < current_minor):
            schema = self._migrate_schema(schema, version, SCHEMA_VERSION)

        return schema

    def _migrate_schema(
        self, schema: ExperimentSchema, from_version: str, to_version: str
    ) -> ExperimentSchema:
        """
        Migrate schema from one version to another.

        Args:
            schema: The schema to migrate
            from_version: Source version
            to_version: Target version

        Returns:
            Migrated schema
        """
        logger.info(f"Migrating schema from {from_version} to {to_version}")

        # Migration logic would go here for specific version upgrades
        # For now, just update the version
        schema.schema_version = to_version

        return schema


# Global serializer instance
_serializer: Optional[ExperimentSerializer] = None


def get_serializer() -> ExperimentSerializer:
    """Get the global serializer instance."""
    global _serializer
    if _serializer is None:
        _serializer = ExperimentSerializer()
    return _serializer
