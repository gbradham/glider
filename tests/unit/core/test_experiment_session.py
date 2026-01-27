import pytest
from glider.core.experiment_session import ExperimentSession, SessionState
from glider.core.flow_engine import FlowEngine

def test_session_init():
    """Test that ExperimentSession initializes correctly."""
    session = ExperimentSession()
    assert session.state == SessionState.IDLE
    assert session.name == "Untitled Experiment"
    assert session.metadata.version == "1.0.0"

def test_session_state_transitions():
    """Test session state transitions."""
    session = ExperimentSession()
    
    session.state = SessionState.RUNNING
    assert session.state == SessionState.RUNNING
    
    session.state = SessionState.PAUSED
    assert session.state == SessionState.PAUSED
    
    session.state = SessionState.IDLE
    assert session.state == SessionState.IDLE
