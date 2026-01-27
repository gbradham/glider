"""
Tests for glider.vision.zones module.

Tests zone definitions, zone tracking, and zone configuration.
"""


import pytest

from glider.vision.zones import (
    Zone,
    ZoneConfiguration,
    ZoneShape,
    ZoneState,
    ZoneTracker,
)


class TestZoneShape:
    """Tests for ZoneShape enum."""

    def test_shape_values(self):
        """Test ZoneShape enum values."""
        assert ZoneShape.RECTANGLE.value == "rectangle"
        assert ZoneShape.CIRCLE.value == "circle"
        assert ZoneShape.POLYGON.value == "polygon"


class TestZone:
    """Tests for Zone dataclass."""

    def test_rectangle_creation(self):
        """Test creating a rectangular zone."""
        zone = Zone(
            id="zone_1",
            name="Test Zone",
            shape=ZoneShape.RECTANGLE,
            vertices=[(0.1, 0.1), (0.9, 0.9)],
            color=(255, 0, 0)
        )

        assert zone.id == "zone_1"
        assert zone.name == "Test Zone"
        assert zone.shape == ZoneShape.RECTANGLE
        assert len(zone.vertices) == 2

    def test_circle_creation(self):
        """Test creating a circular zone."""
        zone = Zone(
            id="zone_2",
            name="Circle Zone",
            shape=ZoneShape.CIRCLE,
            vertices=[(0.5, 0.5), (0.75, 0.5)],  # center and radius point
            color=(0, 255, 0)
        )

        assert zone.shape == ZoneShape.CIRCLE
        assert zone.vertices[0] == (0.5, 0.5)  # center

    def test_polygon_creation(self):
        """Test creating a polygon zone."""
        zone = Zone(
            id="zone_3",
            name="Polygon Zone",
            shape=ZoneShape.POLYGON,
            vertices=[(0.2, 0.2), (0.8, 0.2), (0.5, 0.8)],  # triangle
            color=(0, 0, 255)
        )

        assert zone.shape == ZoneShape.POLYGON
        assert len(zone.vertices) == 3

    def test_contains_point_rectangle(self):
        """Test point containment for rectangular zone."""
        zone = Zone(
            id="zone_1",
            name="Test Zone",
            shape=ZoneShape.RECTANGLE,
            vertices=[(0.2, 0.2), (0.8, 0.8)],
            color=(255, 0, 0)
        )

        # Point inside
        assert zone.contains_point(0.5, 0.5) is True

        # Point outside
        assert zone.contains_point(0.1, 0.1) is False
        assert zone.contains_point(0.9, 0.9) is False

        # Point on edge (should be inside for rectangles)
        assert zone.contains_point(0.2, 0.5) is True

    def test_contains_point_circle(self):
        """Test point containment for circular zone."""
        zone = Zone(
            id="zone_1",
            name="Circle Zone",
            shape=ZoneShape.CIRCLE,
            vertices=[(0.5, 0.5), (0.7, 0.5)],  # center at 0.5,0.5, radius 0.2
            color=(255, 0, 0)
        )

        # Point inside (center)
        assert zone.contains_point(0.5, 0.5) is True

        # Point inside (near edge)
        assert zone.contains_point(0.6, 0.5) is True

        # Point outside
        assert zone.contains_point(0.1, 0.1) is False
        assert zone.contains_point(0.9, 0.9) is False

    def test_contains_point_polygon(self):
        """Test point containment for polygon zone."""
        # Triangle
        zone = Zone(
            id="zone_1",
            name="Triangle Zone",
            shape=ZoneShape.POLYGON,
            vertices=[(0.5, 0.2), (0.8, 0.8), (0.2, 0.8)],
            color=(255, 0, 0)
        )

        # Point inside (center of triangle)
        assert zone.contains_point(0.5, 0.6) is True

        # Point outside
        assert zone.contains_point(0.1, 0.1) is False
        assert zone.contains_point(0.9, 0.9) is False

    def test_default_color(self):
        """Test Zone default color."""
        zone = Zone(
            id="zone_1",
            name="Test",
            shape=ZoneShape.RECTANGLE,
            vertices=[(0, 0), (1, 1)],
        )

        assert zone.color == (0, 255, 0)  # Default green

    def test_to_dict(self):
        """Test Zone serialization."""
        zone = Zone(
            id="zone_1",
            name="Test Zone",
            shape=ZoneShape.RECTANGLE,
            vertices=[(0.1, 0.1), (0.9, 0.9)],
            color=(128, 128, 128),
        )

        data = zone.to_dict()

        assert data["id"] == "zone_1"
        assert data["name"] == "Test Zone"
        assert data["shape"] == "rectangle"
        assert data["vertices"] == [[0.1, 0.1], [0.9, 0.9]]

    def test_from_dict(self):
        """Test Zone deserialization."""
        data = {
            "id": "zone_2",
            "name": "Loaded Zone",
            "shape": "circle",
            "vertices": [[0.5, 0.5], [0.75, 0.5]],
            "color": [0, 255, 0],
        }

        zone = Zone.from_dict(data)

        assert zone.id == "zone_2"
        assert zone.name == "Loaded Zone"
        assert zone.shape == ZoneShape.CIRCLE

    def test_empty_vertices(self):
        """Test zone with empty vertices."""
        zone = Zone(
            id="empty",
            name="Empty",
            shape=ZoneShape.RECTANGLE,
            vertices=[],
            color=(0, 0, 0)
        )

        # Should return False for any point
        assert zone.contains_point(0.5, 0.5) is False


class TestZoneConfiguration:
    """Tests for ZoneConfiguration class."""

    def test_creation(self):
        """Test ZoneConfiguration creation."""
        config = ZoneConfiguration()

        assert config.zones == []
        assert config.enabled is True

    def test_add_zone(self):
        """Test adding a zone."""
        config = ZoneConfiguration()
        zone = Zone(
            id="zone_1",
            name="Test",
            shape=ZoneShape.RECTANGLE,
            vertices=[(0, 0), (1, 1)],
            color=(255, 0, 0)
        )

        config.add_zone(zone)

        assert len(config.zones) == 1
        assert config.zones[0] == zone

    def test_remove_zone(self):
        """Test removing a zone by ID."""
        config = ZoneConfiguration()
        zone = Zone(
            id="zone_1",
            name="Test",
            shape=ZoneShape.RECTANGLE,
            vertices=[(0, 0), (1, 1)],
            color=(255, 0, 0)
        )
        config.add_zone(zone)

        config.remove_zone("zone_1")

        assert len(config.zones) == 0

    def test_get_zone(self):
        """Test getting a zone by ID."""
        config = ZoneConfiguration()
        zone1 = Zone(id="z1", name="Zone 1", shape=ZoneShape.RECTANGLE,
                     vertices=[(0, 0), (0.5, 0.5)], color=(255, 0, 0))
        zone2 = Zone(id="z2", name="Zone 2", shape=ZoneShape.RECTANGLE,
                     vertices=[(0.5, 0.5), (1, 1)], color=(0, 255, 0))

        config.add_zone(zone1)
        config.add_zone(zone2)

        assert config.get_zone("z1") == zone1
        assert config.get_zone("z2") == zone2
        assert config.get_zone("z3") is None

    def test_get_zones_at_point(self):
        """Test getting all zones containing a point."""
        config = ZoneConfiguration()

        # Overlapping zones
        zone1 = Zone(id="z1", name="Zone 1", shape=ZoneShape.RECTANGLE,
                     vertices=[(0.0, 0.0), (0.6, 0.6)],
                     color=(255, 0, 0))
        zone2 = Zone(id="z2", name="Zone 2", shape=ZoneShape.RECTANGLE,
                     vertices=[(0.4, 0.4), (1.0, 1.0)],
                     color=(0, 255, 0))

        config.add_zone(zone1)
        config.add_zone(zone2)

        # Point in zone1 only
        zones = config.get_zones_at_point(0.2, 0.2)
        assert len(zones) == 1
        assert zones[0].id == "z1"

        # Point in overlap
        zones = config.get_zones_at_point(0.5, 0.5)
        assert len(zones) == 2

        # Point in zone2 only
        zones = config.get_zones_at_point(0.8, 0.8)
        assert len(zones) == 1
        assert zones[0].id == "z2"

        # Point outside all zones
        zones = config.get_zones_at_point(0.0, 0.9)
        assert len(zones) == 0

    def test_to_dict(self):
        """Test ZoneConfiguration serialization."""
        config = ZoneConfiguration()
        config.add_zone(Zone(id="z1", name="Zone 1", shape=ZoneShape.RECTANGLE,
                             vertices=[(0, 0), (1, 1)], color=(255, 0, 0)))
        config.enabled = False

        data = config.to_dict()

        assert "zones" in data
        assert len(data["zones"]) == 1
        assert data["enabled"] is False

    def test_from_dict(self):
        """Test ZoneConfiguration deserialization."""
        data = {
            "zones": [
                {
                    "id": "z1",
                    "name": "Test Zone",
                    "shape": "rectangle",
                    "vertices": [[0.1, 0.1], [0.9, 0.9]],
                    "color": [255, 0, 0],
                }
            ],
            "enabled": True
        }

        config = ZoneConfiguration.from_dict(data)

        assert len(config.zones) == 1
        assert config.zones[0].id == "z1"
        assert config.enabled is True

    def test_clear(self):
        """Test clearing all zones."""
        config = ZoneConfiguration()
        config.add_zone(Zone(id="z1", name="Z1", shape=ZoneShape.RECTANGLE,
                             vertices=[(0, 0), (1, 1)], color=(255, 0, 0)))
        config.add_zone(Zone(id="z2", name="Z2", shape=ZoneShape.CIRCLE,
                             vertices=[(0.5, 0.5), (0.7, 0.5)], color=(0, 255, 0)))

        config.clear()

        assert len(config.zones) == 0


class TestZoneState:
    """Tests for ZoneState dataclass."""

    def test_creation(self):
        """Test ZoneState creation."""
        state = ZoneState(
            zone_id="z1",
            zone_name="Zone 1"
        )

        assert state.zone_id == "z1"
        assert state.zone_name == "Zone 1"
        assert state.object_count == 0
        assert state.occupied is False

    def test_occupied_property(self):
        """Test occupied property."""
        state = ZoneState(zone_id="z1", zone_name="Zone 1")

        assert state.occupied is False

        state.object_count = 1
        assert state.occupied is True

        state.object_count = 5
        assert state.occupied is True


class TestZoneTracker:
    """Tests for ZoneTracker class."""

    @pytest.fixture
    def tracker_with_zones(self):
        """Create a ZoneTracker with test zones."""
        config = ZoneConfiguration()
        config.add_zone(Zone(
            id="z1", name="Zone 1",
            shape=ZoneShape.RECTANGLE,
            vertices=[(0.0, 0.0), (0.5, 0.5)],
            color=(255, 0, 0)
        ))
        config.add_zone(Zone(
            id="z2", name="Zone 2",
            shape=ZoneShape.RECTANGLE,
            vertices=[(0.5, 0.5), (1.0, 1.0)],
            color=(0, 255, 0)
        ))

        tracker = ZoneTracker()
        tracker.set_zone_configuration(config)
        return tracker

    def test_creation(self):
        """Test ZoneTracker creation."""
        tracker = ZoneTracker()

        assert tracker._zone_config is None

    def test_set_zone_configuration(self, tracker_with_zones):
        """Test setting zone configuration."""
        tracker = tracker_with_zones

        assert tracker._zone_config is not None
        assert len(tracker._zone_config.zones) == 2

    def test_update_with_no_objects(self, tracker_with_zones):
        """Test update with no tracked objects."""
        tracker = tracker_with_zones

        states = tracker.update([], frame_width=640, frame_height=480)

        assert "z1" in states
        assert "z2" in states
        assert states["z1"].object_count == 0
        assert states["z2"].object_count == 0

    def test_get_zone_state(self, tracker_with_zones):
        """Test getting zone state."""
        tracker = tracker_with_zones

        # Initialize with empty update
        tracker.update([], frame_width=640, frame_height=480)

        state = tracker.get_zone_state("z1")
        assert state is not None
        assert state.zone_id == "z1"

        # Non-existent zone
        state = tracker.get_zone_state("z999")
        assert state is None

    def test_clear(self, tracker_with_zones):
        """Test clearing tracker state."""
        tracker = tracker_with_zones

        # Initialize
        tracker.update([], frame_width=640, frame_height=480)

        tracker.clear()

        assert tracker._zone_config is not None  # Config remains
        assert len(tracker._zone_states) == 0  # State cleared


class TestZoneRoundtrip:
    """Tests for zone serialization roundtrip."""

    def test_zone_roundtrip(self):
        """Test Zone serialization roundtrip."""
        original = Zone(
            id="test_zone",
            name="Test Zone",
            shape=ZoneShape.POLYGON,
            vertices=[(0.1, 0.1), (0.9, 0.1), (0.5, 0.9)],
            color=(100, 150, 200)
        )

        restored = Zone.from_dict(original.to_dict())

        assert restored.id == original.id
        assert restored.name == original.name
        assert restored.shape == original.shape
        assert restored.vertices == original.vertices
        assert restored.color == original.color

    def test_configuration_roundtrip(self):
        """Test ZoneConfiguration serialization roundtrip."""
        original = ZoneConfiguration()
        original.add_zone(Zone(
            id="z1", name="Zone 1",
            shape=ZoneShape.RECTANGLE,
            vertices=[(0, 0), (0.5, 0.5)],
            color=(255, 0, 0)
        ))
        original.add_zone(Zone(
            id="z2", name="Zone 2",
            shape=ZoneShape.CIRCLE,
            vertices=[(0.75, 0.75), (0.9, 0.75)],
            color=(0, 255, 0)
        ))
        original.enabled = False

        restored = ZoneConfiguration.from_dict(original.to_dict())

        assert len(restored.zones) == len(original.zones)
        assert restored.enabled == original.enabled
        assert restored.zones[0].id == original.zones[0].id
        assert restored.zones[1].shape == original.zones[1].shape
