"""
Tests for glider.serialization.schema module.

Tests the experiment schema dataclasses and validation.
"""

import pytest

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
    SchemaValidationError,
)


class TestSchemaVersion:
    """Tests for schema version constant."""

    def test_version_exists(self):
        """Test that SCHEMA_VERSION is defined."""
        assert SCHEMA_VERSION is not None
        assert isinstance(SCHEMA_VERSION, str)

    def test_version_format(self):
        """Test that version follows semver format."""
        parts = SCHEMA_VERSION.split(".")
        assert len(parts) >= 2  # At least major.minor


class TestMetadataSchema:
    """Tests for MetadataSchema dataclass."""

    def test_creation(self):
        """Test MetadataSchema creation."""
        metadata = MetadataSchema(
            name="Test Experiment",
            description="A test experiment",
            author="Test Author"
        )

        assert metadata.name == "Test Experiment"
        assert metadata.description == "A test experiment"
        assert metadata.author == "Test Author"

    def test_to_dict(self):
        """Test MetadataSchema serialization."""
        metadata = MetadataSchema(
            name="Test",
            description="Description",
            author="Author"
        )

        data = metadata.to_dict()

        assert data["name"] == "Test"
        assert data["description"] == "Description"
        assert "created" in data
        assert "modified" in data

    def test_from_dict(self):
        """Test MetadataSchema deserialization."""
        data = {
            "name": "Loaded",
            "description": "Loaded desc",
            "author": "Loaded author",
            "created": "2024-01-01T00:00:00Z",
            "modified": "2024-01-02T00:00:00Z"
        }

        metadata = MetadataSchema.from_dict(data)

        assert metadata.name == "Loaded"
        assert metadata.description == "Loaded desc"


class TestNodeSchema:
    """Tests for NodeSchema dataclass."""

    def test_creation(self):
        """Test NodeSchema creation."""
        node = NodeSchema(
            id="node_1",
            node_type="Delay",
            position=(100, 200),
            state={"duration": 1.0}
        )

        assert node.id == "node_1"
        assert node.node_type == "Delay"
        assert node.position == (100, 200)
        assert node.state["duration"] == 1.0

    def test_to_dict(self):
        """Test NodeSchema serialization."""
        node = NodeSchema(
            id="node_1",
            node_type="Output",
            position=(50, 75),
            state={"value": True}
        )

        data = node.to_dict()

        assert data["id"] == "node_1"
        assert data["type"] == "Output"
        assert data["position"] == [50, 75]
        assert data["state"]["value"] is True

    def test_from_dict(self):
        """Test NodeSchema deserialization."""
        data = {
            "id": "n1",
            "type": "Loop",
            "position": [200, 300],
            "state": {"iterations": 10}
        }

        node = NodeSchema.from_dict(data)

        assert node.id == "n1"
        assert node.node_type == "Loop"
        assert node.position == (200, 300)
        assert node.state["iterations"] == 10

    def test_validation_missing_id(self):
        """Test that validation fails for missing ID."""
        with pytest.raises(SchemaValidationError):
            NodeSchema.from_dict({
                "type": "Delay",
                "position": [0, 0]
            })

    def test_validation_missing_type(self):
        """Test that validation fails for missing type."""
        with pytest.raises(SchemaValidationError):
            NodeSchema.from_dict({
                "id": "n1",
                "position": [0, 0]
            })


class TestConnectionSchema:
    """Tests for ConnectionSchema dataclass."""

    def test_creation(self):
        """Test ConnectionSchema creation."""
        connection = ConnectionSchema(
            source_node="node_1",
            source_port="exec_out",
            target_node="node_2",
            target_port="exec_in"
        )

        assert connection.source_node == "node_1"
        assert connection.source_port == "exec_out"
        assert connection.target_node == "node_2"
        assert connection.target_port == "exec_in"

    def test_to_dict(self):
        """Test ConnectionSchema serialization."""
        connection = ConnectionSchema(
            source_node="n1",
            source_port="out",
            target_node="n2",
            target_port="in"
        )

        data = connection.to_dict()

        assert data["source_node"] == "n1"
        assert data["source_port"] == "out"
        assert data["target_node"] == "n2"
        assert data["target_port"] == "in"

    def test_from_dict(self):
        """Test ConnectionSchema deserialization."""
        data = {
            "source_node": "a",
            "source_port": "x",
            "target_node": "b",
            "target_port": "y"
        }

        connection = ConnectionSchema.from_dict(data)

        assert connection.source_node == "a"
        assert connection.target_node == "b"


class TestBoardConfigSchema:
    """Tests for BoardConfigSchema dataclass."""

    def test_creation(self):
        """Test BoardConfigSchema creation."""
        board = BoardConfigSchema(
            id="board_1",
            driver="arduino",
            name="Arduino Uno",
            port="/dev/ttyUSB0"
        )

        assert board.id == "board_1"
        assert board.driver == "arduino"
        assert board.port == "/dev/ttyUSB0"

    def test_to_dict(self):
        """Test BoardConfigSchema serialization."""
        board = BoardConfigSchema(
            id="b1",
            driver="raspberry_pi",
            name="Pi",
            settings={"gpio_mode": "BCM"}
        )

        data = board.to_dict()

        assert data["id"] == "b1"
        assert data["driver"] == "raspberry_pi"
        assert data["settings"]["gpio_mode"] == "BCM"

    def test_from_dict(self):
        """Test BoardConfigSchema deserialization."""
        data = {
            "id": "b1",
            "driver": "arduino",
            "name": "Board",
            "port": "COM3",
            "settings": {}
        }

        board = BoardConfigSchema.from_dict(data)

        assert board.id == "b1"
        assert board.port == "COM3"


class TestDeviceConfigSchema:
    """Tests for DeviceConfigSchema dataclass."""

    def test_creation(self):
        """Test DeviceConfigSchema creation."""
        device = DeviceConfigSchema(
            id="led_1",
            board_id="board_1",
            device_type="DigitalOutput",
            name="Status LED",
            pin=13
        )

        assert device.id == "led_1"
        assert device.board_id == "board_1"
        assert device.device_type == "DigitalOutput"
        assert device.pin == 13

    def test_to_dict(self):
        """Test DeviceConfigSchema serialization."""
        device = DeviceConfigSchema(
            id="d1",
            board_id="b1",
            device_type="AnalogInput",
            name="Sensor",
            pin=0,
            settings={"smoothing": True}
        )

        data = device.to_dict()

        assert data["id"] == "d1"
        assert data["pin"] == 0
        assert data["settings"]["smoothing"] is True

    def test_from_dict(self):
        """Test DeviceConfigSchema deserialization."""
        data = {
            "id": "d1",
            "board_id": "b1",
            "device_type": "PWMOutput",
            "name": "Motor",
            "pin": 9,
            "settings": {"frequency": 1000}
        }

        device = DeviceConfigSchema.from_dict(data)

        assert device.id == "d1"
        assert device.device_type == "PWMOutput"


class TestFlowConfigSchema:
    """Tests for FlowConfigSchema dataclass."""

    def test_creation(self):
        """Test FlowConfigSchema creation."""
        flow = FlowConfigSchema(
            nodes=[
                NodeSchema(id="n1", node_type="Start", position=(0, 0)),
                NodeSchema(id="n2", node_type="End", position=(100, 0)),
            ],
            connections=[
                ConnectionSchema(
                    source_node="n1", source_port="out",
                    target_node="n2", target_port="in"
                )
            ]
        )

        assert len(flow.nodes) == 2
        assert len(flow.connections) == 1

    def test_to_dict(self):
        """Test FlowConfigSchema serialization."""
        flow = FlowConfigSchema(
            nodes=[NodeSchema(id="n1", node_type="Delay", position=(0, 0))],
            connections=[]
        )

        data = flow.to_dict()

        assert "nodes" in data
        assert "connections" in data
        assert len(data["nodes"]) == 1

    def test_from_dict(self):
        """Test FlowConfigSchema deserialization."""
        data = {
            "nodes": [
                {"id": "n1", "type": "Start", "position": [0, 0], "state": {}}
            ],
            "connections": []
        }

        flow = FlowConfigSchema.from_dict(data)

        assert len(flow.nodes) == 1
        assert flow.nodes[0].node_type == "Start"


class TestHardwareConfigSchema:
    """Tests for HardwareConfigSchema dataclass."""

    def test_creation(self):
        """Test HardwareConfigSchema creation."""
        hardware = HardwareConfigSchema(
            boards=[
                BoardConfigSchema(id="b1", driver="arduino", name="Board")
            ],
            devices=[
                DeviceConfigSchema(
                    id="d1", board_id="b1",
                    device_type="DigitalOutput", name="LED"
                )
            ]
        )

        assert len(hardware.boards) == 1
        assert len(hardware.devices) == 1

    def test_to_dict(self):
        """Test HardwareConfigSchema serialization."""
        hardware = HardwareConfigSchema(boards=[], devices=[])

        data = hardware.to_dict()

        assert "boards" in data
        assert "devices" in data


class TestExperimentSchema:
    """Tests for ExperimentSchema dataclass."""

    def test_creation(self):
        """Test ExperimentSchema creation."""
        schema = ExperimentSchema(
            schema_version=SCHEMA_VERSION,
            metadata=MetadataSchema(name="Test"),
            hardware=HardwareConfigSchema(boards=[], devices=[]),
            flow=FlowConfigSchema(nodes=[], connections=[]),
            dashboard=DashboardConfigSchema(widgets=[], layout={})
        )

        assert schema.schema_version == SCHEMA_VERSION
        assert schema.metadata.name == "Test"

    def test_to_dict(self):
        """Test ExperimentSchema serialization."""
        schema = ExperimentSchema(
            schema_version=SCHEMA_VERSION,
            metadata=MetadataSchema(name="Full Test"),
            hardware=HardwareConfigSchema(
                boards=[BoardConfigSchema(id="b1", driver="arduino", name="Board")],
                devices=[]
            ),
            flow=FlowConfigSchema(
                nodes=[NodeSchema(id="n1", node_type="Start", position=(0, 0))],
                connections=[]
            ),
            dashboard=DashboardConfigSchema(widgets=[], layout={})
        )

        data = schema.to_dict()

        assert data["schema_version"] == SCHEMA_VERSION
        assert data["metadata"]["name"] == "Full Test"
        assert len(data["hardware"]["boards"]) == 1
        assert len(data["flow"]["nodes"]) == 1

    def test_from_dict(self):
        """Test ExperimentSchema deserialization."""
        data = {
            "schema_version": SCHEMA_VERSION,
            "metadata": {
                "name": "Loaded Experiment",
                "description": "Test"
            },
            "hardware": {
                "boards": [],
                "devices": []
            },
            "flow": {
                "nodes": [],
                "connections": []
            },
            "dashboard": {
                "widgets": [],
                "layout": {}
            },
            "custom_devices": [],
            "flow_functions": []
        }

        schema = ExperimentSchema.from_dict(data)

        assert schema.metadata.name == "Loaded Experiment"
        assert schema.schema_version == SCHEMA_VERSION

    def test_roundtrip(self):
        """Test serialization roundtrip."""
        original = ExperimentSchema(
            schema_version=SCHEMA_VERSION,
            metadata=MetadataSchema(
                name="Roundtrip Test",
                description="Testing roundtrip serialization"
            ),
            hardware=HardwareConfigSchema(
                boards=[
                    BoardConfigSchema(
                        id="arduino_1",
                        driver="arduino",
                        name="Arduino Uno",
                        port="/dev/ttyUSB0"
                    )
                ],
                devices=[
                    DeviceConfigSchema(
                        id="led_1",
                        board_id="arduino_1",
                        device_type="DigitalOutput",
                        name="Status LED",
                        pin=13
                    )
                ]
            ),
            flow=FlowConfigSchema(
                nodes=[
                    NodeSchema(id="start", node_type="StartExperiment", position=(0, 0)),
                    NodeSchema(id="delay", node_type="Delay", position=(100, 0),
                               state={"duration": 1.0}),
                    NodeSchema(id="end", node_type="EndExperiment", position=(200, 0)),
                ],
                connections=[
                    ConnectionSchema(
                        source_node="start", source_port="exec_out",
                        target_node="delay", target_port="exec_in"
                    ),
                    ConnectionSchema(
                        source_node="delay", source_port="exec_out",
                        target_node="end", target_port="exec_in"
                    ),
                ]
            ),
            dashboard=DashboardConfigSchema(widgets=[], layout={})
        )

        data = original.to_dict()
        restored = ExperimentSchema.from_dict(data)

        assert restored.metadata.name == original.metadata.name
        assert len(restored.hardware.boards) == len(original.hardware.boards)
        assert len(restored.hardware.devices) == len(original.hardware.devices)
        assert len(restored.flow.nodes) == len(original.flow.nodes)
        assert len(restored.flow.connections) == len(original.flow.connections)


class TestSchemaValidationError:
    """Tests for SchemaValidationError exception."""

    def test_error_message(self):
        """Test SchemaValidationError message."""
        error = SchemaValidationError("Invalid field: name")

        assert "Invalid field: name" in str(error)

    def test_error_with_path(self):
        """Test SchemaValidationError with path context."""
        error = SchemaValidationError(
            "Missing required field",
            path="hardware.boards[0].driver"
        )

        assert "hardware.boards[0].driver" in str(error)
