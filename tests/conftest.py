import pytest
import asyncio
from unittest.mock import MagicMock

@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def mock_hardware_manager():
    """Provide a mock hardware manager."""
    manager = MagicMock()
    manager.boards = {}
    manager.devices = {}
    return manager

@pytest.fixture
def mock_core(mock_hardware_manager):
    """Provide a mock GliderCore."""
    core = MagicMock()
    core.hardware_manager = mock_hardware_manager
    return core
