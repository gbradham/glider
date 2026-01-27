"""
Integration tests for experiment workflow.

Tests complete workflows from session creation through experiment execution.
"""

import json

from glider.core.experiment_session import (
    BoardConfig,
    DeviceConfig,
    ExperimentSession,
    SessionState,
)


class TestExperimentSessionWorkflow:
    """Integration tests for experiment session workflows."""

    def test_create_configure_save_load_workflow(self, temp_dir):
        """Test complete workflow: create, configure, save, load."""
        # 1. Create new session
        session = ExperimentSession(name="Integration Test")

        # 2. Configure hardware
        session.add_board(BoardConfig(
            id="arduino_1",
            driver="arduino",
            name="Arduino Uno",
            port="/dev/ttyUSB0"
        ))

        session.add_device(DeviceConfig(
            id="led_1",
            board_id="arduino_1",
            device_type="DigitalOutput",
            name="Status LED",
            pin=13
        ))

        session.add_device(DeviceConfig(
            id="sensor_1",
            board_id="arduino_1",
            device_type="AnalogInput",
            name="Temperature Sensor",
            pin=0
        ))

        # 3. Save session
        file_path = temp_dir / "test_session.json"
        data = session.to_dict()
        file_path.write_text(json.dumps(data, indent=2))

        assert file_path.exists()

        # 4. Load session
        loaded_data = json.loads(file_path.read_text())
        loaded_session = ExperimentSession.from_dict(loaded_data)

        # 5. Verify loaded session
        assert loaded_session.name == "Integration Test"
        assert len(loaded_session.boards) == 1
        assert len(loaded_session.devices) == 2
        assert "arduino_1" in loaded_session.boards
        assert "led_1" in loaded_session.devices
        assert "sensor_1" in loaded_session.devices

    def test_modify_and_track_dirty_state(self):
        """Test that modifications are tracked via dirty state."""
        session = ExperimentSession(name="Dirty Test")

        # Fresh session should be clean (or dirty from name)
        initial_dirty = session.is_dirty

        # Mark clean to establish baseline
        session.mark_clean()
        assert session.is_dirty is False

        # Add board should mark dirty
        session.add_board(BoardConfig(
            id="b1", driver="arduino", name="Board"
        ))
        assert session.is_dirty is True

        # Mark clean
        session.mark_clean()
        assert session.is_dirty is False

        # Add device should mark dirty
        session.add_device(DeviceConfig(
            id="d1", board_id="b1",
            device_type="DigitalOutput", name="Device"
        ))
        assert session.is_dirty is True

        # Mark clean
        session.mark_clean()

        # Remove should mark dirty
        session.remove_device("d1")
        assert session.is_dirty is True

    def test_state_lifecycle(self):
        """Test session state lifecycle."""
        session = ExperimentSession()

        # Initial state
        assert session.state == SessionState.IDLE
        assert session.state.can_start is True
        assert session.state.can_stop is False

        # Transition to running
        session.state = SessionState.RUNNING
        assert session.state.is_active is True
        assert session.state.can_stop is True
        assert session.state.can_start is False

        # Pause
        session.state = SessionState.PAUSED
        assert session.state.is_active is False
        assert session.state.can_stop is True

        # Resume
        session.state = SessionState.RUNNING
        assert session.state.is_active is True

        # Stop
        session.state = SessionState.STOPPING
        session.state = SessionState.IDLE
        assert session.state.can_start is True

    def test_device_board_relationship(self):
        """Test relationship between devices and boards."""
        session = ExperimentSession()

        # Add multiple boards
        session.add_board(BoardConfig(id="b1", driver="arduino", name="Board 1"))
        session.add_board(BoardConfig(id="b2", driver="arduino", name="Board 2"))

        # Add devices to different boards
        session.add_device(DeviceConfig(
            id="d1", board_id="b1", device_type="DigitalOutput", name="D1"
        ))
        session.add_device(DeviceConfig(
            id="d2", board_id="b1", device_type="DigitalInput", name="D2"
        ))
        session.add_device(DeviceConfig(
            id="d3", board_id="b2", device_type="PWMOutput", name="D3"
        ))

        # Verify device-board relationships
        b1_devices = session.get_devices_for_board("b1")
        b2_devices = session.get_devices_for_board("b2")

        assert len(b1_devices) == 2
        assert len(b2_devices) == 1
        assert all(d.board_id == "b1" for d in b1_devices)
        assert all(d.board_id == "b2" for d in b2_devices)

    def test_clear_and_rebuild(self):
        """Test clearing and rebuilding a session."""
        session = ExperimentSession(name="Clear Test")

        # Add some content
        session.add_board(BoardConfig(id="b1", driver="arduino", name="Board"))
        session.add_device(DeviceConfig(
            id="d1", board_id="b1", device_type="DigitalOutput", name="Device"
        ))

        assert len(session.boards) == 1
        assert len(session.devices) == 1

        # Clear
        session.clear()

        assert len(session.boards) == 0
        assert len(session.devices) == 0

        # Rebuild
        session.add_board(BoardConfig(id="b2", driver="raspberry_pi", name="Pi"))
        session.add_device(DeviceConfig(
            id="d2", board_id="b2", device_type="PWMOutput", name="Motor"
        ))

        assert len(session.boards) == 1
        assert "b2" in session.boards
        assert len(session.devices) == 1
        assert "d2" in session.devices


class TestSchemaIntegration:
    """Integration tests for schema serialization."""

    def test_complex_experiment_roundtrip(self, temp_dir):
        """Test roundtrip with a complex experiment configuration."""
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
        )

        # Create complex schema
        schema = ExperimentSchema(
            schema_version=SCHEMA_VERSION,
            metadata=MetadataSchema(
                name="Complex Experiment",
                description="A complex experiment with multiple components",
                author="Integration Test"
            ),
            hardware=HardwareConfigSchema(
                boards=[
                    BoardConfigSchema(
                        id="arduino_1", driver="arduino",
                        name="Main Controller", port="/dev/ttyUSB0"
                    ),
                    BoardConfigSchema(
                        id="pi_1", driver="raspberry_pi",
                        name="Sensor Hub"
                    ),
                ],
                devices=[
                    DeviceConfigSchema(
                        id="led_status", board_id="arduino_1",
                        device_type="DigitalOutput", name="Status LED", pin=13
                    ),
                    DeviceConfigSchema(
                        id="led_error", board_id="arduino_1",
                        device_type="DigitalOutput", name="Error LED", pin=12
                    ),
                    DeviceConfigSchema(
                        id="motor_1", board_id="arduino_1",
                        device_type="PWMOutput", name="Motor", pin=9
                    ),
                    DeviceConfigSchema(
                        id="temp_sensor", board_id="pi_1",
                        device_type="AnalogInput", name="Temperature", pin=0
                    ),
                ]
            ),
            flow=FlowConfigSchema(
                nodes=[
                    NodeSchema(id="start", node_type="StartExperiment",
                               position=(0, 100)),
                    NodeSchema(id="init_led", node_type="Output",
                               position=(150, 100), state={"device_id": "led_status"}),
                    NodeSchema(id="loop", node_type="Loop",
                               position=(300, 100), state={"iterations": 10}),
                    NodeSchema(id="read_temp", node_type="Input",
                               position=(450, 100), state={"device_id": "temp_sensor"}),
                    NodeSchema(id="delay", node_type="Delay",
                               position=(600, 100), state={"duration": 1.0}),
                    NodeSchema(id="end", node_type="EndExperiment",
                               position=(750, 100)),
                ],
                connections=[
                    ConnectionSchema("start", "exec_out", "init_led", "exec_in"),
                    ConnectionSchema("init_led", "exec_out", "loop", "exec_in"),
                    ConnectionSchema("loop", "loop_body", "read_temp", "exec_in"),
                    ConnectionSchema("read_temp", "exec_out", "delay", "exec_in"),
                    ConnectionSchema("delay", "exec_out", "loop", "loop_next"),
                    ConnectionSchema("loop", "exec_out", "end", "exec_in"),
                ]
            ),
            dashboard=DashboardConfigSchema(widgets=[], layout={})
        )

        # Serialize
        data = schema.to_dict()
        file_path = temp_dir / "complex_experiment.json"
        file_path.write_text(json.dumps(data, indent=2))

        # Verify file content
        assert file_path.exists()
        loaded_json = json.loads(file_path.read_text())
        assert loaded_json["schema_version"] == SCHEMA_VERSION
        assert len(loaded_json["hardware"]["boards"]) == 2
        assert len(loaded_json["hardware"]["devices"]) == 4
        assert len(loaded_json["flow"]["nodes"]) == 6
        assert len(loaded_json["flow"]["connections"]) == 6

        # Deserialize
        restored = ExperimentSchema.from_dict(loaded_json)

        # Verify restoration
        assert restored.metadata.name == schema.metadata.name
        assert len(restored.hardware.boards) == 2
        assert len(restored.hardware.devices) == 4
        assert len(restored.flow.nodes) == 6
        assert len(restored.flow.connections) == 6

        # Verify specific values
        arduino_board = next(b for b in restored.hardware.boards if b.id == "arduino_1")
        assert arduino_board.port == "/dev/ttyUSB0"

        delay_node = next(n for n in restored.flow.nodes if n.id == "delay")
        assert delay_node.state["duration"] == 1.0


class TestZoneTrackingIntegration:
    """Integration tests for zone tracking system."""

    def test_multi_object_zone_tracking(self):
        """Test tracking multiple objects across multiple zones."""
        from glider.vision.zones import (
            Zone,
            ZoneConfiguration,
            ZoneEventType,
            ZoneShape,
            ZoneTracker,
        )

        # Create zone configuration
        config = ZoneConfiguration()

        # Add zones
        config.add_zone(Zone(
            id="start_zone", name="Start",
            shape=ZoneShape.RECTANGLE,
            points=[(0.0, 0.0), (0.3, 0.0), (0.3, 1.0), (0.0, 1.0)],
            color=(0, 255, 0)
        ))
        config.add_zone(Zone(
            id="middle_zone", name="Middle",
            shape=ZoneShape.RECTANGLE,
            points=[(0.35, 0.0), (0.65, 0.0), (0.65, 1.0), (0.35, 1.0)],
            color=(255, 255, 0)
        ))
        config.add_zone(Zone(
            id="end_zone", name="End",
            shape=ZoneShape.RECTANGLE,
            points=[(0.7, 0.0), (1.0, 0.0), (1.0, 1.0), (0.7, 1.0)],
            color=(255, 0, 0)
        ))

        tracker = ZoneTracker(config)

        # Simulate object 1 moving through all zones
        events = []

        # Object 1 starts in start zone
        events.extend(tracker.update_object("obj_1", 0.15, 0.5, timestamp=0.0))

        # Object 1 moves to middle
        events.extend(tracker.update_object("obj_1", 0.5, 0.5, timestamp=1.0))

        # Object 2 appears in start zone
        events.extend(tracker.update_object("obj_2", 0.15, 0.5, timestamp=1.5))

        # Object 1 moves to end
        events.extend(tracker.update_object("obj_1", 0.85, 0.5, timestamp=2.0))

        # Object 2 moves to middle
        events.extend(tracker.update_object("obj_2", 0.5, 0.5, timestamp=2.5))

        # Verify events
        obj1_entries = [e for e in events if e.object_id == "obj_1"
                        and e.event_type == ZoneEventType.ENTRY]
        obj1_exits = [e for e in events if e.object_id == "obj_1"
                       and e.event_type == ZoneEventType.EXIT]

        # Object 1 should have entered 3 zones
        assert len(obj1_entries) >= 2  # middle and end (first zone doesn't count as entry)

        # Object 1 should have exited 2 zones
        assert len(obj1_exits) >= 2  # start and middle

        # Verify zone occupancy
        assert tracker.get_zone_occupancy("end_zone") == 1  # obj_1
        assert tracker.get_zone_occupancy("middle_zone") == 1  # obj_2

    def test_zone_dwell_time_calculation(self):
        """Test dwell time calculation in zones."""
        from glider.vision.zones import Zone, ZoneConfiguration, ZoneShape, ZoneTracker

        config = ZoneConfiguration()
        config.add_zone(Zone(
            id="target_zone", name="Target",
            shape=ZoneShape.RECTANGLE,
            points=[(0.25, 0.25), (0.75, 0.25), (0.75, 0.75), (0.25, 0.75)],
            color=(0, 255, 0)
        ))

        tracker = ZoneTracker(config)

        # Object enters zone
        tracker.update_object("obj_1", 0.5, 0.5, timestamp=0.0)

        # Object stays in zone for various time points
        tracker.update_object("obj_1", 0.5, 0.5, timestamp=1.0)
        tracker.update_object("obj_1", 0.5, 0.5, timestamp=2.5)
        tracker.update_object("obj_1", 0.5, 0.5, timestamp=5.0)

        # Check dwell time
        dwell = tracker.get_dwell_time("obj_1", "target_zone")
        assert dwell == 5.0

        # Object leaves zone
        tracker.update_object("obj_1", 0.1, 0.1, timestamp=6.0)

        # Dwell time should now be 0 (or tracked as historical)
        current_dwell = tracker.get_dwell_time("obj_1", "target_zone")
        assert current_dwell == 0.0 or current_dwell is None


class TestCalibrationIntegration:
    """Integration tests for camera calibration."""

    def test_calibration_pixel_conversion_workflow(self):
        """Test complete calibration workflow."""
        from glider.vision.calibration import CalibrationLine, CameraCalibration, LengthUnit

        # Create calibration
        calibration = CameraCalibration()

        # Add calibration lines (simulating user drawing lines on frame)
        # Line 1: 100mm reference at top of frame
        calibration.add_line(CalibrationLine(
            start_x=0.1, start_y=0.2,
            end_x=0.9, end_y=0.2,
            length=100.0, unit=LengthUnit.MM
        ))

        # Calculate pixels per unit for 1920x1080 frame
        frame_width = 1920
        frame_height = 1080
        ppu = calibration.calculate_pixels_per_unit(frame_width, frame_height)

        # Line spans 80% of width = 0.8 * 1920 = 1536 pixels
        # 1536 pixels = 100mm
        # Therefore ~15.36 pixels per mm
        assert abs(ppu - 15.36) < 0.1

        # Test conversions
        # 100 pixels should be ~6.5mm
        distance_mm = calibration.pixels_to_real_world(100)
        assert abs(distance_mm - 6.51) < 0.1

        # 10mm should be ~154 pixels
        pixels = calibration.real_world_to_pixels(10.0)
        assert abs(pixels - 153.6) < 1

    def test_calibration_serialization_workflow(self, temp_dir):
        """Test saving and loading calibration."""
        from glider.vision.calibration import CalibrationLine, CameraCalibration, LengthUnit

        # Create and configure calibration
        original = CameraCalibration()
        original.add_line(CalibrationLine(
            start_x=0.0, start_y=0.5,
            end_x=1.0, end_y=0.5,
            length=200.0, unit=LengthUnit.CM,
            color=(255, 128, 0)
        ))
        original.calculate_pixels_per_unit(1280, 720)

        # Save
        file_path = temp_dir / "calibration.json"
        data = original.to_dict()
        file_path.write_text(json.dumps(data, indent=2))

        # Load
        loaded_data = json.loads(file_path.read_text())
        restored = CameraCalibration.from_dict(loaded_data)

        # Verify
        assert len(restored.lines) == 1
        assert restored.lines[0].length == 200.0
        assert restored.lines[0].unit == LengthUnit.CM
        assert restored.pixels_per_unit == original.pixels_per_unit
