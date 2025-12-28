"""
Experiment Flow Nodes - Basic nodes for experiment control.

These nodes provide the core functionality for running experiments:
- StartExperiment: Entry point
- EndExperiment: Exit point
- Delay: Wait for a duration
- Output: Write to a device
- Input: Read from a device
"""

import asyncio
import logging
from typing import Any, Optional

from glider.nodes.base_node import (
    GliderNode, NodeDefinition, NodeCategory,
    PortDefinition, PortType
)

logger = logging.getLogger(__name__)


class StartExperimentNode(GliderNode):
    """Entry point for the experiment flow."""

    definition = NodeDefinition(
        name="StartExperiment",
        category=NodeCategory.LOGIC,
        description="Entry point - begins the experiment flow",
        inputs=[],
        outputs=[
            PortDefinition("next", PortType.EXEC, description="Triggers the next node"),
        ],
    )

    def update_event(self) -> None:
        """Called when inputs change - not used for start node."""
        pass

    async def start(self) -> None:
        """Called when experiment starts - triggers the flow."""
        logger.info(f"StartExperiment.start() called, node ID: {self._glider_id}")
        logger.info(f"  Registered callbacks: {len(self._update_callbacks)}")
        self.exec_output(0)

    def exec_output(self, index: int = 0) -> None:
        """Trigger execution output."""
        logger.info(f"StartExperiment.exec_output({index}) called, callbacks: {len(self._update_callbacks)}")
        for i, callback in enumerate(self._update_callbacks):
            logger.debug(f"  Calling callback {i}")
            callback("next", True)


class EndExperimentNode(GliderNode):
    """Exit point for the experiment flow."""

    definition = NodeDefinition(
        name="EndExperiment",
        category=NodeCategory.LOGIC,
        description="Exit point - ends the experiment",
        inputs=[
            PortDefinition("exec", PortType.EXEC, description="Execution input"),
        ],
        outputs=[],
    )

    def update_event(self) -> None:
        """Called when inputs change."""
        pass

    async def execute(self) -> None:
        """Called when this node is triggered."""
        logger.info(f"EndExperimentNode.execute() called, node ID: {self._glider_id}")
        logger.info("Experiment ended")


class DelayNode(GliderNode):
    """Wait for a specified duration."""

    definition = NodeDefinition(
        name="Delay",
        category=NodeCategory.LOGIC,
        description="Wait for a specified duration",
        inputs=[
            PortDefinition("exec", PortType.EXEC, description="Execution input"),
            PortDefinition("seconds", PortType.DATA, float, 1.0, "Duration in seconds"),
        ],
        outputs=[
            PortDefinition("next", PortType.EXEC, description="Triggers after delay"),
        ],
    )

    def update_event(self) -> None:
        """Called when inputs change."""
        pass

    async def execute(self) -> None:
        """Wait for the specified duration then trigger output."""
        logger.info(f"DelayNode.execute() called, node ID: {self._glider_id}")
        logger.info(f"  Node state: {self._state}")

        # Priority: 1) Saved state, 2) Default (1.0 seconds)
        # The state is set by the properties panel when user changes duration
        if "duration" in self._state:
            duration = float(self._state["duration"])
            logger.info(f"  Using duration from state: {duration}")
        else:
            # No saved state, default to 1 second
            duration = 1.0
            logger.info(f"  Using default duration: {duration}")

        logger.info(f"Delay: waiting {duration} seconds")
        await asyncio.sleep(duration)
        logger.info("Delay: complete")
        self.exec_output(0)

    def exec_output(self, index: int = 0) -> None:
        """Trigger execution output."""
        logger.info(f"DelayNode.exec_output({index}) called, callbacks: {len(self._update_callbacks)}")
        for callback in self._update_callbacks:
            callback("next", True)


class OutputNode(GliderNode):
    """Write HIGH/LOW to a device."""

    definition = NodeDefinition(
        name="Output",
        category=NodeCategory.HARDWARE,
        description="Write HIGH/LOW to a device",
        inputs=[
            PortDefinition("exec", PortType.EXEC, description="Execution input"),
            PortDefinition("value", PortType.DATA, bool, True, "HIGH (1) or LOW (0)"),
        ],
        outputs=[
            PortDefinition("next", PortType.EXEC, description="Triggers after write"),
        ],
    )

    def update_event(self) -> None:
        """Called when inputs change."""
        pass

    async def execute(self) -> None:
        """Write the value to the bound device."""
        logger.info(f"OutputNode.execute() called, node ID: {self._glider_id}")
        logger.info(f"  Node state: {self._state}")

        # Priority: 1) Saved state, 2) Default (1 = HIGH)
        # The state is set by the properties panel when user selects HIGH/LOW
        if "value" in self._state:
            value = self._state["value"]
            logger.info(f"  Using value from state: {value}")
        else:
            # No saved state, default to HIGH
            value = 1
            logger.info(f"  Using default value: {value}")

        # Convert to bool
        value = bool(value)
        logger.info(f"  Final value (bool): {value}")

        if self._device is not None:
            try:
                logger.info(f"Output: setting device to {'HIGH' if value else 'LOW'}")
                if hasattr(self._device, 'set_state'):
                    await self._device.set_state(value)
                elif hasattr(self._device, 'turn_on') and hasattr(self._device, 'turn_off'):
                    if value:
                        await self._device.turn_on()
                    else:
                        await self._device.turn_off()
            except Exception as e:
                logger.error(f"Output error: {e}")
                self._error = str(e)
        else:
            logger.warning("Output: no device bound")

        self.exec_output(0)

    def exec_output(self, index: int = 0) -> None:
        """Trigger execution output."""
        logger.info(f"OutputNode.exec_output({index}) called, callbacks: {len(self._update_callbacks)}")
        for callback in self._update_callbacks:
            callback("next", True)


class InputNode(GliderNode):
    """Read from a device."""

    definition = NodeDefinition(
        name="Input",
        category=NodeCategory.HARDWARE,
        description="Read from a device (digital or analog)",
        inputs=[
            PortDefinition("exec", PortType.EXEC, description="Execution input"),
        ],
        outputs=[
            PortDefinition("value", PortType.DATA, description="Read value"),
            PortDefinition("next", PortType.EXEC, description="Triggers after read"),
        ],
    )

    def update_event(self) -> None:
        """Called when inputs change."""
        pass

    async def execute(self) -> None:
        """Read the value from the bound device."""
        value = None

        if self._device is not None:
            try:
                if hasattr(self._device, 'read'):
                    value = await self._device.read()
                elif hasattr(self._device, 'get_state'):
                    value = await self._device.get_state()
                logger.info(f"Input: read value = {value}")
            except Exception as e:
                logger.error(f"Input error: {e}")
                self._error = str(e)
        else:
            logger.warning("Input: no device bound")

        # Set output value
        if len(self._outputs) > 0:
            self._outputs[0] = value

        # Notify callbacks
        for callback in self._update_callbacks:
            callback("value", value)

        self.exec_output(1)

    def exec_output(self, index: int = 0) -> None:
        """Trigger execution output."""
        for callback in self._update_callbacks:
            callback("next", True)


def register_experiment_nodes(flow_engine) -> None:
    """Register all experiment nodes with the flow engine."""
    flow_engine.register_node("StartExperiment", StartExperimentNode)
    flow_engine.register_node("EndExperiment", EndExperimentNode)
    flow_engine.register_node("Delay", DelayNode)
    flow_engine.register_node("Output", OutputNode)
    flow_engine.register_node("Input", InputNode)
    logger.info("Registered experiment nodes")
