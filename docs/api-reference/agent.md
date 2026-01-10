# Agent API Reference

The agent module provides AI-powered experiment orchestration through natural language conversations.

## Module: `glider.agent`

```python
from glider.agent import (
    AgentController,
    AgentConfig,
    AgentResponse,
    AgentAction,
    ActionBatch,
    ActionStatus,
    LLMBackend,
    AgentToolkit,
)
```

---

## AgentController

Main orchestrator for AI agent interactions.

### Class: `AgentController`

```python
class AgentController:
    """Manages AI agent interactions."""
```

#### Constructor

```python
AgentController(core: GliderCore, config: Optional[AgentConfig] = None)
```

**Parameters:**
- `core`: GliderCore instance for accessing session and hardware
- `config`: Agent configuration (loads from default file if not provided)

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| `config` | `AgentConfig` | Current configuration |
| `is_processing` | `bool` | Whether currently processing a message |
| `pending_batch` | `Optional[ActionBatch]` | Pending actions awaiting confirmation |
| `conversation` | `List[Message]` | Conversation history (copy) |

#### Methods

##### `async process_message`

```python
async def process_message(user_message: str) -> AsyncIterator[AgentResponse]
```

Process a user message and yield streaming responses.

**Parameters:**
- `user_message`: The user's natural language message

**Yields:** `AgentResponse` objects as content streams in

**Example:**
```python
async for response in controller.process_message("Add an LED on pin 13"):
    print(response.content)
    if response.is_complete:
        if response.has_actions:
            print(f"Proposed actions: {len(response.actions)}")
```

##### `async confirm_actions`

```python
async def confirm_actions(action_ids: Optional[List[str]] = None) -> AgentResponse
```

Confirm and execute pending actions.

**Parameters:**
- `action_ids`: Specific action IDs to confirm, or None for all

**Returns:** `AgentResponse` with execution results

**Example:**
```python
# Confirm all pending actions
result = await controller.confirm_actions()

# Confirm specific actions
result = await controller.confirm_actions(["action_1", "action_2"])
```

##### `async reject_actions`

```python
async def reject_actions(action_ids: Optional[List[str]] = None) -> AgentResponse
```

Reject pending actions.

**Parameters:**
- `action_ids`: Specific action IDs to reject, or None for all

**Returns:** `AgentResponse` confirming rejection

##### `clear_conversation`

```python
def clear_conversation() -> None
```

Clear conversation history and reset state.

##### `async check_connection`

```python
async def check_connection() -> bool
```

Check if LLM backend is reachable.

**Returns:** True if connection successful

##### `async list_models`

```python
async def list_models() -> List[str]
```

List available models from the LLM backend.

**Returns:** List of model names

##### `add_error`

```python
def add_error(error: str) -> None
```

Add an error to recent errors list (used for context).

#### Callbacks

##### `on_response`

```python
def on_response(callback: Callable[[AgentResponse], None]) -> None
```

Register callback for agent responses.

##### `on_action`

```python
def on_action(callback: Callable[[AgentAction], None]) -> None
```

Register callback for proposed actions.

---

## AgentConfig

Configuration for the agent system.

### Dataclass: `AgentConfig`

```python
@dataclass
class AgentConfig:
    # LLM Backend Settings
    backend: str = "ollama"              # "ollama" or "openai"
    model: str = "llama3.2"              # Model name
    api_url: str = "http://localhost:11434"  # API endpoint
    api_key: Optional[str] = None        # API key (for OpenAI)

    # Context Settings
    include_flow_state: bool = True      # Include nodes/connections in prompt
    include_hardware_state: bool = True  # Include boards/devices in prompt
    include_recent_errors: bool = True   # Include recent errors in prompt

    # Behavior Settings
    auto_execute_safe: bool = True       # Auto-execute non-destructive actions
    require_confirmation: bool = True    # Require confirmation for changes
    max_conversation_length: int = 50    # Max messages before truncation

    # Custom Instructions
    custom_instructions: str = ""        # Additional system prompt text
```

#### Methods

##### `load`

```python
@classmethod
def load(cls, path: Optional[Path] = None) -> AgentConfig
```

Load configuration from file.

**Parameters:**
- `path`: Config file path, or None for default (`~/.glider/agent_config.json`)

**Returns:** Loaded `AgentConfig`

##### `save`

```python
def save(self, path: Optional[Path] = None) -> None
```

Save configuration to file.

---

## AgentResponse

A response from the agent.

### Dataclass: `AgentResponse`

```python
@dataclass
class AgentResponse:
    content: str = ""                    # Response text
    actions: List[AgentAction] = []      # Proposed actions
    is_complete: bool = False            # Whether response is complete
    error: Optional[str] = None          # Error message if failed
```

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| `has_actions` | `bool` | True if response includes actions |
| `pending_actions` | `List[AgentAction]` | Actions requiring confirmation |

---

## AgentAction

Represents an action proposed by the agent.

### Dataclass: `AgentAction`

```python
@dataclass
class AgentAction:
    id: str                              # Unique action ID
    tool_name: str                       # Tool to execute
    description: str                     # Human-readable description
    parameters: Dict[str, Any]           # Tool parameters
    requires_confirmation: bool          # Whether user must confirm
    status: ActionStatus                 # Current status
    result: Optional[Any] = None         # Execution result
    error: Optional[str] = None          # Error if failed
```

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| `is_pending` | `bool` | True if status is PENDING |
| `is_complete` | `bool` | True if status is COMPLETE |
| `is_failed` | `bool` | True if status is FAILED |

#### Methods

##### `confirm`

```python
def confirm() -> None
```

Mark action as confirmed (ready to execute).

##### `reject`

```python
def reject() -> None
```

Mark action as rejected.

##### `start_execution`

```python
def start_execution() -> None
```

Mark action as executing.

##### `complete`

```python
def complete(result: Any) -> None
```

Mark action as completed with result.

##### `fail`

```python
def fail(error: str) -> None
```

Mark action as failed with error.

---

## ActionStatus

Status of an agent action.

### Enum: `ActionStatus`

```python
class ActionStatus(Enum):
    PENDING = auto()      # Awaiting confirmation
    CONFIRMED = auto()    # Confirmed, ready to execute
    EXECUTING = auto()    # Currently executing
    COMPLETE = auto()     # Successfully completed
    FAILED = auto()       # Execution failed
    REJECTED = auto()     # Rejected by user
```

---

## ActionBatch

A batch of related actions.

### Dataclass: `ActionBatch`

```python
@dataclass
class ActionBatch:
    message: str = ""                    # Associated message
    actions: List[AgentAction] = []      # Actions in batch
```

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| `pending_actions` | `List[AgentAction]` | Actions still pending |
| `confirmed_actions` | `List[AgentAction]` | Confirmed actions |
| `completed_actions` | `List[AgentAction]` | Completed actions |

#### Methods

##### `add_action`

```python
def add_action(action: AgentAction) -> None
```

Add an action to the batch.

---

## LLMBackend

Abstracts communication with LLM providers.

### Class: `LLMBackend`

```python
class LLMBackend:
    """Handles LLM API communication."""
```

#### Constructor

```python
LLMBackend(config: AgentConfig)
```

#### Methods

##### `async chat`

```python
async def chat(
    messages: List[Message],
    tools: Optional[List[Dict]] = None,
    stream: bool = True
) -> AsyncIterator[ChatChunk]
```

Send messages to LLM and stream response.

**Parameters:**
- `messages`: Conversation messages
- `tools`: Tool definitions for function calling
- `stream`: Whether to stream response

**Yields:** `ChatChunk` objects with content and tool calls

##### `async check_connection`

```python
async def check_connection() -> bool
```

Test connection to LLM backend.

##### `async list_models`

```python
async def list_models() -> List[str]
```

List available models.

##### `async close`

```python
async def close() -> None
```

Close connections and clean up.

---

## Message

A conversation message.

### Dataclass: `Message`

```python
@dataclass
class Message:
    role: str                # "system", "user", or "assistant"
    content: str             # Message content
    tool_calls: Optional[List[Dict]] = None  # Tool calls (for assistant)
    tool_call_id: Optional[str] = None       # Tool result ID
```

---

## ChatChunk

A streaming response chunk.

### Dataclass: `ChatChunk`

```python
@dataclass
class ChatChunk:
    content: str = ""                    # Text content
    tool_calls: Optional[List[Dict]] = None  # Tool calls
    is_final: bool = False               # Whether this is the final chunk
```

---

## AgentToolkit

Defines and executes tools available to the agent.

### Class: `AgentToolkit`

```python
class AgentToolkit:
    """Provides tools for agent to manipulate experiments."""
```

#### Constructor

```python
AgentToolkit(core: GliderCore)
```

#### Methods

##### `get_tool_definitions`

```python
def get_tool_definitions() -> List[Dict]
```

Get OpenAI-format tool definitions.

**Returns:** List of tool schemas

##### `create_action`

```python
def create_action(tool_name: str, arguments: Dict) -> Optional[AgentAction]
```

Create an action from a tool call.

**Parameters:**
- `tool_name`: Name of the tool
- `arguments`: Tool arguments

**Returns:** `AgentAction` or None if tool not found

##### `async execute`

```python
async def execute(tool_name: str, params: Dict) -> ToolResult
```

Execute a tool.

**Parameters:**
- `tool_name`: Name of the tool
- `params`: Tool parameters

**Returns:** `ToolResult` with success/failure status

##### `reset_state`

```python
def reset_state() -> None
```

Reset toolkit state.

---

## ToolResult

Result of a tool execution.

### Dataclass: `ToolResult`

```python
@dataclass
class ToolResult:
    success: bool                        # Whether execution succeeded
    result: Optional[Any] = None         # Result data
    error: Optional[str] = None          # Error message if failed
```

#### Methods

##### `to_message`

```python
def to_message() -> str
```

Convert result to human-readable message.

---

## Available Tools

The agent has access to these tools:

### Experiment Tools

| Tool | Description | Confirmation |
|------|-------------|--------------|
| `start_experiment` | Start running the experiment | Yes |
| `stop_experiment` | Stop the running experiment | Yes |
| `pause_experiment` | Pause the experiment | Yes |
| `resume_experiment` | Resume paused experiment | Yes |
| `get_session_info` | Get current session state | No |

### Hardware Tools

| Tool | Description | Confirmation |
|------|-------------|--------------|
| `add_board` | Add a new hardware board | Yes |
| `remove_board` | Remove a board | Yes |
| `add_device` | Add a device to a board | Yes |
| `remove_device` | Remove a device | Yes |
| `list_boards` | List configured boards | No |
| `list_devices` | List configured devices | No |

### Flow Tools

| Tool | Description | Confirmation |
|------|-------------|--------------|
| `add_node` | Add a node to the flow | Yes |
| `remove_node` | Remove a node | Yes |
| `connect_nodes` | Connect two nodes | Yes |
| `disconnect_nodes` | Remove a connection | Yes |
| `list_nodes` | List flow nodes | No |

### Knowledge Tools

| Tool | Description | Confirmation |
|------|-------------|--------------|
| `get_available_boards` | List available board types | No |
| `get_available_devices` | List available device types | No |
| `get_available_nodes` | List available node types | No |

---

## Usage Example

```python
import asyncio
from glider.core.glider_core import GliderCore, create_core
from glider.agent import AgentController, AgentConfig

async def main():
    # Create core
    core = await create_core()

    # Configure agent
    config = AgentConfig(
        backend="ollama",
        model="llama3.2",
        auto_execute_safe=True,
    )

    # Create controller
    agent = AgentController(core, config)

    # Check connection
    if not await agent.check_connection():
        print("LLM backend not available")
        return

    # Process a message
    async for response in agent.process_message(
        "Add an Arduino board on COM3 with an LED on pin 13"
    ):
        print(response.content)

        if response.is_complete and response.has_actions:
            # Show pending actions
            for action in response.pending_actions:
                print(f"  - {action.description}")

            # Confirm all actions
            result = await agent.confirm_actions()
            print(result.content)

    # Cleanup
    await agent.shutdown()
    await core.shutdown()

asyncio.run(main())
```

---

## Configuration File

The agent configuration is stored in `~/.glider/agent_config.json`:

```json
{
  "backend": "ollama",
  "model": "llama3.2",
  "api_url": "http://localhost:11434",
  "api_key": null,
  "include_flow_state": true,
  "include_hardware_state": true,
  "include_recent_errors": true,
  "auto_execute_safe": true,
  "require_confirmation": true,
  "max_conversation_length": 50,
  "custom_instructions": ""
}
```

---

## See Also

- [Architecture](../developer-guide/architecture.md) - Agent layer architecture
- [Core API](core.md) - GliderCore integration
- [Builder Mode](../user-guide/builder-mode.md) - Agent panel usage
