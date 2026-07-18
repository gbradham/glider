"""Regression tests for GLIDER's experiment lifecycle safety contract.

These tests intentionally use mocked devices and recorders: the state changes
and safe-state behaviour must be reliable without requiring lab hardware.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from glider.core.experiment_session import ExperimentSession, SessionState
from glider.core.glider_core import GliderCore


@pytest.fixture
def core_with_session():
    """Return a core whose hardware-facing collaborators are inert mocks."""
    core = GliderCore()
    core._session = ExperimentSession()
    core._flow_engine.stop = AsyncMock()
    core._flow_engine.pause = AsyncMock()
    core._flow_engine.resume = AsyncMock()
    core._data_recorder = MagicMock(is_recording=False)
    core._video_recorder = MagicMock(is_recording=False)
    core._multi_video_recorder = MagicMock(is_recording=False)
    core._tracking_logger = MagicMock(is_recording=False)
    core._hardware_manager = MagicMock(devices={})
    return core


@pytest.mark.asyncio
async def test_pause_then_resume_preserves_lifecycle_state(core_with_session):
    """A paused experiment resumes without rebuilding or stopping its flow."""
    core = core_with_session
    core.session.state = SessionState.RUNNING

    await core.pause_experiment()

    core._flow_engine.pause.assert_awaited_once()
    assert core.session.state is SessionState.PAUSED

    await core.resume_experiment()

    core._flow_engine.resume.assert_awaited_once()
    assert core.session.state is SessionState.RUNNING
    core._flow_engine.stop.assert_not_awaited()


@pytest.mark.asyncio
async def test_stop_reaches_ready_only_after_every_device_is_safe(core_with_session):
    """Stopping a successful run shuts down outputs before declaring READY."""
    core = core_with_session
    core.session.state = SessionState.RUNNING
    valve = MagicMock()
    valve.shutdown = AsyncMock()
    core._hardware_manager.devices = {"reward_valve": valve}

    await core.stop_experiment()

    core._flow_engine.stop.assert_awaited_once()
    valve.shutdown.assert_awaited_once()
    assert core.session.state is SessionState.READY


@pytest.mark.asyncio
async def test_stop_enters_error_when_a_device_cannot_reach_safe_state(core_with_session):
    """A shutdown failure must remain visible to the operator as ERROR."""
    core = core_with_session
    core.session.state = SessionState.RUNNING
    stuck_valve = MagicMock()
    stuck_valve.shutdown = AsyncMock(side_effect=RuntimeError("relay unresponsive"))
    core._hardware_manager.devices = {"reward_valve": stuck_valve}

    await core.stop_experiment()

    stuck_valve.shutdown.assert_awaited_once()
    assert core.session.state is SessionState.ERROR


@pytest.mark.asyncio
async def test_pause_and_resume_ignore_invalid_states(core_with_session):
    """Lifecycle buttons cannot alter an experiment that is not running/paused."""
    core = core_with_session
    core.session.state = SessionState.READY

    await core.pause_experiment()
    await core.resume_experiment()

    core._flow_engine.pause.assert_not_awaited()
    core._flow_engine.resume.assert_not_awaited()
    assert core.session.state is SessionState.READY
