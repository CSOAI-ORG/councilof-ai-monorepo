"""
tests/test_mind.py
Integration test: full Water → Milk → Honey pipeline.
"""
import asyncio
import pytest
import numpy as np

from sovos.core.mind import SovosMind
from sovos.core.state import StateBus


@pytest.mark.asyncio
async def test_full_pipeline():
    mind = SovosMind()

    # Register Layer 0 fabric
    from sovos.core.layer0 import CPOLink, MCPTool, A2AAgent
    mind.fabric.register_link(CPOLink("link1", "sov1", "gpu", photonic_mode="hybrid"))
    mind.fabric.register_tool(MCPTool("test_tool", "http://localhost:9999"))
    mind.fabric.register_agent(A2AAgent("agent1", "compute"))

    # Ingest water
    vid = await mind.ingest("test_source", {"message": "hello sovos"})
    assert vid.startswith("water.")

    # Process to milk
    milk_vid = await mind.process(vid)
    assert milk_vid.startswith("milk.")

    # Distill to honey
    intent = await mind.distill(milk_vid)
    assert intent.confidence > 0.0
    assert intent.intent_id.startswith("honey.")

    # Check state bus
    bus = StateBus()
    assert len(bus._vectors) >= 3  # water + milk + honey

    print("\n=== SOVOS Mind Status ===")
    print(mind.status())


if __name__ == "__main__":
    asyncio.run(test_full_pipeline())
