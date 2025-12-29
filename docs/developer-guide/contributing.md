# Contributing to GLIDER

Thank you for your interest in contributing to GLIDER! This guide will help you get started with development.

## Getting Started

### Development Environment

1. **Clone the Repository**

```bash
git clone https://github.com/LaingLab/glider.git
cd glider
```

2. **Create a Virtual Environment**

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

3. **Install Development Dependencies**

```bash
pip install -e ".[dev]"
```

This installs GLIDER in editable mode with development tools.

4. **Verify Installation**

```bash
# Run tests
pytest

# Run type checker
mypy src/glider

# Run linter
ruff check src/glider

# Launch GLIDER
python -m glider
```

### IDE Setup

#### VS Code

Recommended extensions:
- Python (Microsoft)
- Pylance
- Ruff
- GitLens

Settings (`.vscode/settings.json`):
```json
{
    "python.defaultInterpreterPath": "${workspaceFolder}/venv/Scripts/python",
    "python.analysis.typeCheckingMode": "basic",
    "editor.formatOnSave": true,
    "[python]": {
        "editor.defaultFormatter": "charliermarsh.ruff"
    }
}
```

#### PyCharm

1. Open the project folder
2. Configure interpreter: File → Settings → Project → Python Interpreter
3. Select the virtual environment
4. Enable pytest: File → Settings → Tools → Python Integrated Tools

## Code Style

### Python Style Guide

GLIDER follows PEP 8 with some modifications:

- **Line length**: 100 characters maximum
- **Imports**: Sorted with `isort` (grouped: stdlib, third-party, local)
- **Docstrings**: Google style
- **Type hints**: Required for public APIs

```python
"""Module docstring describing purpose."""

import asyncio
from typing import Dict, List, Optional

from glider.hal.base_board import BaseBoard


class ExampleClass:
    """One-line summary.

    Longer description if needed. Can span
    multiple lines.

    Attributes:
        name: Human-readable name.
        value: Current value.
    """

    def __init__(self, name: str, value: int = 0) -> None:
        """Initialize the example.

        Args:
            name: Human-readable name.
            value: Initial value. Defaults to 0.
        """
        self.name = name
        self.value = value

    async def process(self, data: List[int]) -> Dict[str, int]:
        """Process the data asynchronously.

        Args:
            data: List of integers to process.

        Returns:
            Dictionary mapping names to processed values.

        Raises:
            ValueError: If data is empty.
        """
        if not data:
            raise ValueError("Data cannot be empty")

        return {"sum": sum(data), "count": len(data)}
```

### Async Guidelines

- Use `async/await` for all I/O operations
- Never block the event loop
- Track async tasks for cleanup
- Use `asyncio.sleep()` instead of `time.sleep()`

```python
# Good
async def read_sensor(self) -> float:
    value = await self.board.read_analog(self.pin)
    return value

# Bad - blocks event loop
def read_sensor(self) -> float:
    import time
    time.sleep(0.1)  # Blocks!
    return self._value
```

### Qt Guidelines

- Use signals/slots for cross-component communication
- Run async code with `qasync`
- Keep UI updates on the main thread

```python
from PyQt6.QtCore import pyqtSignal, QObject

class Controller(QObject):
    """Controller with Qt signals."""

    value_changed = pyqtSignal(float)

    def update_value(self, value: float) -> None:
        """Update and emit signal."""
        self._value = value
        self.value_changed.emit(value)
```

## Project Structure

```
glider/
├── src/glider/           # Main source code
│   ├── core/             # Core orchestration
│   ├── gui/              # PyQt6 interface
│   ├── hal/              # Hardware abstraction
│   ├── nodes/            # Flow graph nodes
│   ├── plugins/          # Plugin system
│   └── serialization/    # Save/load
├── tests/                # Test suite
│   ├── unit/             # Unit tests
│   ├── integration/      # Integration tests
│   └── fixtures/         # Test data
├── docs/                 # Documentation
├── examples/             # Example experiments
└── pyproject.toml        # Package configuration
```

## Making Changes

### Workflow

1. **Create a Branch**

```bash
git checkout -b feature/my-feature
# or
git checkout -b fix/bug-description
```

Branch naming:
- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation updates
- `refactor/` - Code refactoring
- `test/` - Test additions/fixes

2. **Make Changes**

- Write clean, documented code
- Add tests for new functionality
- Update documentation if needed

3. **Run Quality Checks**

```bash
# Format code
ruff format src/glider tests

# Check linting
ruff check src/glider tests

# Type check
mypy src/glider

# Run tests
pytest
```

4. **Commit Changes**

Write clear commit messages:

```
Short summary (50 chars or less)

More detailed explanation if needed. Wrap at 72 characters.
Explain what and why, not how.

- Bullet points are fine
- Use present tense ("Add feature" not "Added feature")
```

5. **Push and Create PR**

```bash
git push origin feature/my-feature
```

Then create a pull request on GitHub.

### Pull Request Guidelines

**Title**: Clear, concise description of the change

**Description**:
- What does this PR do?
- Why is this change needed?
- How was it tested?
- Any breaking changes?

**Checklist**:
- [ ] Tests pass
- [ ] Code is formatted
- [ ] Type hints added
- [ ] Documentation updated
- [ ] No breaking changes (or documented)

## Testing

### Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=glider --cov-report=html

# Specific test file
pytest tests/unit/test_flow_engine.py

# Specific test
pytest tests/unit/test_flow_engine.py::test_execute_node

# Verbose output
pytest -v

# Stop on first failure
pytest -x
```

### Writing Tests

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from glider.core.flow_engine import FlowEngine
from glider.nodes.base_node import GliderNode


class TestFlowEngine:
    """Tests for FlowEngine class."""

    @pytest.fixture
    def engine(self):
        """Create a FlowEngine instance."""
        return FlowEngine()

    def test_add_node(self, engine):
        """Test adding a node to the engine."""
        node = MagicMock(spec=GliderNode)
        node.id = "node_1"

        engine.add_node(node)

        assert "node_1" in engine.nodes

    @pytest.mark.asyncio
    async def test_execute_flow(self, engine):
        """Test flow execution."""
        node = AsyncMock(spec=GliderNode)
        node.id = "node_1"
        node.execute = AsyncMock()

        engine.add_node(node)
        await engine.execute()

        node.execute.assert_called_once()


@pytest.fixture
def mock_board():
    """Create a mock board for hardware tests."""
    board = MagicMock()
    board.connect = AsyncMock(return_value=True)
    board.disconnect = AsyncMock()
    board.write_digital = AsyncMock()
    board.read_analog = AsyncMock(return_value=512)
    return board
```

### Test Categories

Use markers for test categories:

```python
@pytest.mark.unit
def test_simple_logic():
    """Fast unit test."""
    pass

@pytest.mark.integration
async def test_full_workflow():
    """Integration test with multiple components."""
    pass

@pytest.mark.hardware
async def test_real_device():
    """Requires physical hardware."""
    pass

@pytest.mark.slow
async def test_long_running():
    """Takes more than 1 second."""
    pass
```

Run by category:

```bash
pytest -m unit           # Only unit tests
pytest -m "not hardware" # Skip hardware tests
pytest -m "not slow"     # Skip slow tests
```

## Documentation

### Building Documentation

```bash
# Install docs dependencies
pip install mkdocs mkdocs-material

# Serve locally
mkdocs serve

# Build static site
mkdocs build
```

### Documentation Style

- Use clear, concise language
- Include code examples
- Add Mermaid diagrams for complex concepts
- Cross-reference related pages
- Keep paragraphs short

```markdown
## Feature Name

Brief description of the feature.

### Usage

How to use this feature:

```python
# Example code
result = do_something()
```

### Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `name` | `"default"` | The name to use |

> **Note:** Important information for the user.

### See Also

- [Related Topic](related.md) - Description
```

## Adding Features

### New Node Type

1. Create node class in `src/glider/nodes/`:

```python
# src/glider/nodes/logic/my_node.py
from glider.nodes.base_node import GliderNode, NodeCategory

class MyNode(GliderNode):
    """Description of the node."""

    title = "My Node"
    category = NodeCategory.LOGIC

    def __init__(self):
        super().__init__()
        self.add_input("value", data_type="float")
        self.add_output("result", data_type="float")

    def update_event(self):
        value = self.get_input(0)
        self.set_output(0, value * 2)
```

2. Register in `__init__.py`:

```python
from .my_node import MyNode

__all__ = ["MyNode"]
```

3. Add tests in `tests/unit/nodes/`:

```python
def test_my_node():
    node = MyNode()
    node._inputs[0].value = 5.0
    node.update_event()
    assert node._outputs[0].value == 10.0
```

4. Document in `docs/api-reference/nodes.md`

### New Device Type

1. Create device class in `src/glider/hal/devices/`
2. Register in device registry
3. Add corresponding node if needed
4. Write tests
5. Document usage

### New Board Driver

1. Create driver class in `src/glider/hal/boards/`
2. Implement `BaseBoard` interface
3. Register with `HardwareManager`
4. Add platform-specific tests
5. Document setup requirements

## Release Process

### Version Numbering

GLIDER uses semantic versioning: `MAJOR.MINOR.PATCH`

- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

### Release Checklist

1. Update version in `pyproject.toml`
2. Update `CHANGELOG.md`
3. Run full test suite
4. Create git tag
5. Build and publish to PyPI

```bash
# Update version
# Edit pyproject.toml

# Commit and tag
git add pyproject.toml CHANGELOG.md
git commit -m "Release v1.2.0"
git tag v1.2.0

# Push
git push origin main --tags

# Build
python -m build

# Publish (maintainers only)
twine upload dist/*
```

## Getting Help

### Questions

- Check existing [documentation](../../README.md)
- Search [GitHub issues](https://github.com/LaingLab/glider/issues)
- Ask in [Discussions](https://github.com/LaingLab/glider/discussions)

### Reporting Bugs

Create an issue with:
- GLIDER version
- Python version
- Operating system
- Steps to reproduce
- Expected vs actual behavior
- Error messages/logs

### Feature Requests

Create an issue with:
- Use case description
- Proposed solution
- Alternatives considered

## Code of Conduct

- Be respectful and inclusive
- Welcome newcomers
- Provide constructive feedback
- Focus on the code, not the person
- Report unacceptable behavior to maintainers

## License

By contributing to GLIDER, you agree that your contributions will be licensed under the same license as the project (MIT License).

## See Also

- [Architecture](architecture.md) - System design
- [Plugin Development](plugin-development.md) - Extension guide
- [API Reference](../api-reference/core.md) - Complete API
