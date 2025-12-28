"""
GLIDER Node System

Provides the node types for flow-based visual programming:
- Hardware Nodes: Interface with physical devices
- Logic Nodes: Mathematical operations, comparisons, timers
- Interface Nodes: Dashboard widgets for user interaction
- Script Nodes: Custom Python code execution
"""

from glider.nodes.base_node import GliderNode, NodeCategory, PortType

__all__ = [
    "GliderNode",
    "NodeCategory",
    "PortType",
]
