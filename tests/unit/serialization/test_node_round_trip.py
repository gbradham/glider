"""
Round-trip regression test for node state serialization.

Catches the class of bug where node state is silently dropped on save
because the serializer reads a property name that no node class defines
(prior bug: ``getattr(node, "property_names", [])`` always returned ``[]``).

Every save of an experiment should round-trip every node-local property
(camera index, GPIO pin, threshold, ITI duration, etc.) through
``dump → load → dump`` without loss.
"""

from __future__ import annotations

from typing import Any

import pytest

from glider.serialization.serializer import ExperimentSerializer


class _FakeNodeWithState:
    """Stand-in for a real node that has ``get_state`` / ``set_state``."""

    name = "FakeNode"

    def __init__(self, initial: dict[str, Any] | None = None):
        self._state: dict[str, Any] = dict(initial or {})
        self._glider_id = "fake-1"
        self._enabled = True
        self._visible_in_runner = False

    def get_state(self) -> dict[str, Any]:
        return self._state.copy()

    def set_state(self, state: dict[str, Any]) -> None:
        self._state = state.copy()


def test_extract_node_properties_uses_get_state():
    """Saved properties include the per-node state dict (not just metadata)."""
    serializer = ExperimentSerializer()

    state = {"pin": 13, "duration_ms": 250, "threshold": 1.5, "label": "valve_A"}
    node = _FakeNodeWithState(initial=state)

    props = serializer._extract_node_properties(node)

    assert "state" in props, (
        "Node state was not extracted — every node parameter (pin, duration, "
        "threshold, etc.) silently drops on save. Check that "
        "_extract_node_properties calls node.get_state()."
    )
    assert props["state"] == state, (
        f"State payload doesn't match: got {props['state']!r}, expected {state!r}"
    )


def test_extract_node_properties_round_trip():
    """get_state → _extract_node_properties → set_state preserves every key."""
    serializer = ExperimentSerializer()

    original = {
        "pin": 17,
        "duration_ms": 1000,
        "threshold": 2.5,
        "enabled_features": ["zone_a", "zone_b"],
        "metadata": {"label": "left_lever", "trial_id": 42},
        "polarity": True,
    }
    node1 = _FakeNodeWithState(initial=original)
    props = serializer._extract_node_properties(node1)

    node2 = _FakeNodeWithState()
    node2.set_state(props["state"])

    assert node2.get_state() == original


def test_extract_node_properties_handles_missing_get_state():
    """Nodes without get_state still produce a valid (empty-state) payload."""
    serializer = ExperimentSerializer()

    class BareNode:
        name = "BareNode"
        _glider_id = "bare-1"

    props = serializer._extract_node_properties(BareNode())
    # No state key when get_state isn't available; should not raise.
    assert "state" not in props


def test_extract_node_properties_handles_empty_state():
    """A node with an empty state dict shouldn't add a meaningless empty key."""
    serializer = ExperimentSerializer()
    node = _FakeNodeWithState(initial={})

    props = serializer._extract_node_properties(node)
    assert "state" not in props


def test_extract_node_properties_includes_common_attrs():
    """visible_in_runner and enabled persist outside the state dict."""
    serializer = ExperimentSerializer()
    node = _FakeNodeWithState(initial={"pin": 1})
    node._visible_in_runner = True
    node._enabled = False

    props = serializer._extract_node_properties(node)
    assert props["visible_in_runner"] is True
    assert props["enabled"] is False


def test_extract_node_properties_survives_get_state_exception():
    """A buggy get_state shouldn't break the entire save — log + skip state."""
    serializer = ExperimentSerializer()

    class BrokenNode:
        name = "BrokenNode"
        _glider_id = "broken-1"
        _enabled = True
        _visible_in_runner = False

        def get_state(self):
            raise RuntimeError("oops")

    # Should not raise; should produce a properties dict (just without state)
    props = serializer._extract_node_properties(BrokenNode())
    assert "state" not in props
    assert props.get("enabled") is True
