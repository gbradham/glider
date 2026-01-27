"""
Tests for glider.core.experiment_session module.

Tests the ExperimentSession state machine and session management.
"""


from glider.core.experiment_session import (
    BoardConfig,
    DeviceConfig,
    ExperimentSession,
    SessionMetadata,
    SessionState,
)


class TestSessionMetadata:
    """Tests for SessionMetadata dataclass."""

    def test_default_values(self):
        """Test SessionMetadata default values."""
        metadata = SessionMetadata(name="Test")

        assert metadata.name == "Test"
        assert metadata.description == ""
        assert metadata.author == ""

    def test_to_dict(self):
        """Test SessionMetadata serialization."""
        metadata = SessionMetadata(
            name="Test Session",
            description="A test description",
            author="Test Author"
        )
        data = metadata.to_dict()

        assert data["name"] == "Test Session"
        assert data["description"] == "A test description"
        assert data["author"] == "Test Author"

    def test_from_dict(self):
        """Test SessionMetadata deserialization."""
        data = {
            "name": "Loaded Session",
            "description": "Loaded description",
            "author": "Loaded Author",
            "version": "1.0.0"
        }
        metadata = SessionMetadata.from_dict(data)

        assert metadata.name == "Loaded Session"
        assert metadata.description == "Loaded description"
        assert metadata.author == "Loaded Author"


class TestBoardConfig:
    """Tests for BoardConfig dataclass."""

    def test_creation(self):
        """Test BoardConfig creation."""
        config = BoardConfig(
            id="board_1",
            driver="arduino",
            name="Arduino Uno"
        )

        assert config.id == "board_1"
        assert config.driver == "arduino"
        assert config.name == "Arduino Uno"

    def test_to_dict(self):
        """Test BoardConfig serialization."""
        config = BoardConfig(
            id="board_1",
            driver="arduino",
            name="Arduino",
            port="/dev/ttyUSB0",
            settings={"baud_rate": 115200}
        )
        data = config.to_dict()

        assert data["id"] == "board_1"
        assert data["driver"] == "arduino"
        assert data["port"] == "/dev/ttyUSB0"

    def test_from_dict(self):
        """Test BoardConfig deserialization."""
        data = {
            "id": "board_2",
            "driver": "raspberry_pi",
            "name": "Pi Board",
            "port": None,
            "settings": {}
        }
        config = BoardConfig.from_dict(data)

        assert config.id == "board_2"
        assert config.driver == "raspberry_pi"
        assert config.name == "Pi Board"


class TestDeviceConfig:
    """Tests for DeviceConfig dataclass."""

    def test_creation(self):
        """Test DeviceConfig creation."""
        config = DeviceConfig(
            id="device_1",
            board_id="board_1",
            device_type="DigitalOutput",
            name="LED"
        )

        assert config.id == "device_1"
        assert config.board_id == "board_1"
        assert config.device_type == "DigitalOutput"
        assert config.name == "LED"

    def test_to_dict(self):
        """Test DeviceConfig serialization."""
        config = DeviceConfig(
            id="device_1",
            board_id="board_1",
            device_type="DigitalOutput",
            name="LED",
            pin=13,
            settings={"inverted": False}
        )
        data = config.to_dict()

        assert data["id"] == "device_1"
        assert data["pin"] == 13

    def test_from_dict(self):
        """Test DeviceConfig deserialization."""
        data = {
            "id": "sensor_1",
            "board_id": "board_1",
            "device_type": "AnalogInput",
            "name": "Temperature Sensor",
            "pin": 0,
            "settings": {"smoothing": True}
        }
        config = DeviceConfig.from_dict(data)

        assert config.id == "sensor_1"
        assert config.device_type == "AnalogInput"
        assert config.pin == 0


class TestExperimentSession:
    """Tests for ExperimentSession class."""

    def test_session_init(self):
        """Test ExperimentSession initialization."""
        session = ExperimentSession()

        assert session.state == SessionState.IDLE
        assert session.name == "Untitled Experiment"
        assert session.metadata.version == "1.0.0"

    def test_session_init_with_name(self):
        """Test ExperimentSession initialization with name."""
        session = ExperimentSession(name="My Experiment")

        assert session.name == "My Experiment"

    def test_session_state_transitions(self):
        """Test session state transitions."""
        session = ExperimentSession()

        session.state = SessionState.RUNNING
        assert session.state == SessionState.RUNNING

        session.state = SessionState.PAUSED
        assert session.state == SessionState.PAUSED

        session.state = SessionState.IDLE
        assert session.state == SessionState.IDLE

    def test_all_state_values(self):
        """Test all SessionState values can be set."""
        session = ExperimentSession()

        for state in SessionState:
            session.state = state
            assert session.state == state

    def test_mark_dirty(self):
        """Test marking session as dirty."""
        session = ExperimentSession()
        initial_dirty = session.is_dirty

        session.mark_dirty()
        assert session.is_dirty is True

    def test_add_board(self):
        """Test adding a board to the session."""
        session = ExperimentSession()
        config = BoardConfig(
            id="board_1",
            driver="arduino",
            name="Arduino"
        )

        session.add_board(config)

        assert "board_1" in session.boards
        assert session.boards["board_1"] == config

    def test_remove_board(self):
        """Test removing a board from the session."""
        session = ExperimentSession()
        config = BoardConfig(id="board_1", driver="arduino", name="Arduino")
        session.add_board(config)

        session.remove_board("board_1")

        assert "board_1" not in session.boards

    def test_add_device(self):
        """Test adding a device to the session."""
        session = ExperimentSession()
        config = DeviceConfig(
            id="device_1",
            board_id="board_1",
            device_type="DigitalOutput",
            name="LED"
        )

        session.add_device(config)

        assert "device_1" in session.devices
        assert session.devices["device_1"] == config

    def test_remove_device(self):
        """Test removing a device from the session."""
        session = ExperimentSession()
        config = DeviceConfig(
            id="device_1",
            board_id="board_1",
            device_type="DigitalOutput",
            name="LED"
        )
        session.add_device(config)

        session.remove_device("device_1")

        assert "device_1" not in session.devices

    def test_get_board(self):
        """Test getting a board by ID."""
        session = ExperimentSession()
        config = BoardConfig(id="board_1", driver="arduino", name="Arduino")
        session.add_board(config)

        result = session.get_board("board_1")
        assert result == config

        result = session.get_board("nonexistent")
        assert result is None

    def test_get_device(self):
        """Test getting a device by ID."""
        session = ExperimentSession()
        config = DeviceConfig(
            id="device_1",
            board_id="board_1",
            device_type="DigitalOutput",
            name="LED"
        )
        session.add_device(config)

        result = session.get_device("device_1")
        assert result == config

        result = session.get_device("nonexistent")
        assert result is None

    def test_get_devices_for_board(self):
        """Test getting all devices for a specific board."""
        session = ExperimentSession()

        # Add devices for different boards
        session.add_device(DeviceConfig(
            id="led_1", board_id="board_1", device_type="DigitalOutput", name="LED 1"
        ))
        session.add_device(DeviceConfig(
            id="led_2", board_id="board_1", device_type="DigitalOutput", name="LED 2"
        ))
        session.add_device(DeviceConfig(
            id="sensor_1", board_id="board_2", device_type="AnalogInput", name="Sensor"
        ))

        board_1_devices = session.get_devices_for_board("board_1")
        assert len(board_1_devices) == 2

        board_2_devices = session.get_devices_for_board("board_2")
        assert len(board_2_devices) == 1

    def test_to_dict(self):
        """Test session serialization."""
        session = ExperimentSession(name="Test Session")
        session.add_board(BoardConfig(
            id="board_1", driver="arduino", name="Arduino"
        ))
        session.add_device(DeviceConfig(
            id="led_1", board_id="board_1", device_type="DigitalOutput", name="LED"
        ))

        data = session.to_dict()

        assert "metadata" in data
        assert "boards" in data
        assert "devices" in data

    def test_from_dict(self):
        """Test session deserialization."""
        data = {
            "metadata": {
                "name": "Loaded Session",
                "description": "Test",
                "author": "Author",
                "version": "1.0.0"
            },
            "boards": [
                {"id": "b1", "driver": "arduino", "name": "Board"}
            ],
            "devices": [
                {"id": "d1", "board_id": "b1", "device_type": "DigitalOutput", "name": "Device"}
            ],
            "flow_config": {},
            "dashboard_config": {}
        }

        session = ExperimentSession.from_dict(data)

        assert session.name == "Loaded Session"
        assert "b1" in session.boards
        assert "d1" in session.devices

    def test_clear(self):
        """Test clearing a session."""
        session = ExperimentSession(name="Test")
        session.add_board(BoardConfig(id="b1", driver="arduino", name="Board"))
        session.add_device(DeviceConfig(
            id="d1", board_id="b1", device_type="DigitalOutput", name="Device"
        ))

        session.clear()

        assert len(session.boards) == 0
        assert len(session.devices) == 0

    def test_roundtrip(self):
        """Test serialization roundtrip."""
        original = ExperimentSession(name="Roundtrip Test")
        original.metadata.description = "Testing roundtrip"
        original.add_board(BoardConfig(
            id="board_1", driver="arduino", name="Arduino", port="/dev/ttyUSB0"
        ))
        original.add_device(DeviceConfig(
            id="led_1", board_id="board_1", device_type="DigitalOutput",
            name="Status LED", pin=13
        ))

        data = original.to_dict()
        restored = ExperimentSession.from_dict(data)

        assert restored.name == original.name
        assert len(restored.boards) == len(original.boards)
        assert len(restored.devices) == len(original.devices)


class TestSessionStateEnum:
    """Tests for SessionState enum properties."""

    def test_is_active(self):
        """Test is_active property."""
        assert SessionState.RUNNING.is_active is True
        assert SessionState.IDLE.is_active is False
        assert SessionState.PAUSED.is_active is False

    def test_can_start(self):
        """Test can_start property."""
        assert SessionState.IDLE.can_start is True
        assert SessionState.READY.can_start is True
        assert SessionState.RUNNING.can_start is False

    def test_can_stop(self):
        """Test can_stop property."""
        assert SessionState.RUNNING.can_stop is True
        assert SessionState.PAUSED.can_stop is True
        assert SessionState.IDLE.can_stop is False
