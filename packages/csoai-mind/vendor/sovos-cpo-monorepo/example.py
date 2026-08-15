"""
example.py — Run this to see SOVOS in action.
Full pipeline: Water → Milk → Honey → Layer 0.
"""
import asyncio
import numpy as np

from sovos.core.mind import SovosMind
from sovos.core.layer0 import CPOLink, MCPTool, A2AAgent


async def main():
    print("╔══════════════════════════════════════════════════╗")
    print("║     SOVOS CPO — One Mind Initialization         ║")
    print("╚══════════════════════════════════════════════════╝\n")

    mind = SovosMind()

    # --- Layer 0: Wire the photonic fabric ---
    print("[Layer 0] Wiring photonic fabric...")
    mind.fabric.register_link(CPOLink("sov1→gpu", "sov1.edge", "gpu.cluster", photonic_mode="hybrid"))
    mind.fabric.register_link(CPOLink("gpu→quantum", "gpu.cluster", "quantum.coprocessor", photonic_mode="quantum"))
    mind.fabric.register_link(CPOLink("sov1→inet", "sov1.edge", "internet", photonic_mode="classical"))

    # Register MCP tools with capability vectors
    print("[Layer 0] Registering MCP tools...")
    mind.fabric.register_tool(MCPTool(
        "fishkeeper",
        "https://fishkeeper.ai/mcp",
        capability_embedding=np.random.randn(512).astype(np.float32)
    ))
    mind.fabric.register_tool(MCPTool(
        "councilof",
        "https://councilof.ai/mcp",
        capability_embedding=np.random.randn(512).astype(np.float32)
    ))

    # Register A2A agents
    print("[Layer 0] Registering A2A agents...")
    mind.fabric.register_agent(A2AAgent("sov1_edge", "gateway"))
    mind.fabric.register_agent(A2AAgent("gpu_cluster", "compute"))
    mind.fabric.register_agent(A2AAgent("watchdog", "safety"))

    # --- Ingest Water ---
    print("\n[Water] Ingesting raw data from farm sensors...")
    vid = await mind.ingest("iokfarm.sensors", {
        "pond_temp": 18.5,
        "koi_count": 42,
        "oxygen_level": 7.2,
        "alert": False,
    })
    print(f"  → Water vector: {vid}")

    # --- Process to Milk ---
    print("\n[Milk] Processing to task vectors...")
    milk_vid = await mind.process(vid)
    print(f"  → Milk vector: {milk_vid}")

    # OWEM hive transform
    milk_vec = await mind.bus.read(milk_vid)
    await mind.milk.hive_transform(milk_vec, mode="frozen")
    print("  → OWEM hive transform: frozen (stable)")

    # --- Distill to Honey ---
    print("\n[Honey] Distilling intent...")
    intent = await mind.distill(milk_vid, use_quantum=False)
    print(f"  → Intent: {intent.action}")
    print(f"  → Confidence: {intent.confidence:.4f}")

    # --- Execute through Layer 0 ---
    print("\n[Action] Executing through Layer 0 fabric...")
    result = await mind.execute(intent)
    print(f"  → Result: {result}")

    # --- Status ---
    print("\n══════════════════════════════════════════════════")
    print("SOVOS MIND STATUS")
    print("══════════════════════════════════════════════════")
    status = mind.status()
    print(f"Pipeline: {status['pipeline']}")
    print(f"Fabric links: {list(status['fabric']['links'].keys())}")
    print(f"Fabric tools: {status['fabric']['tools']}")
    print(f"Bus vectors: {status['fabric']['bus_vectors']}")
    print(f"Quantum backend: {status['quantum']['backend']}")
    print("══════════════════════════════════════════════════")

    # --- CPO Power Savings ---
    from sovos.quantum.photonic import CPOFabric
    cpo = CPOFabric()
    cpo.add_channel(mind.fabric.links["sov1→gpu"].__class__("ch1", "sov1", "gpu"))
    cpo.add_channel(mind.fabric.links["gpu→quantum"].__class__("ch2", "gpu", "quantum"))
    cpo.add_channel(mind.fabric.links["sov1→inet"].__class__("ch3", "sov1", "inet"))
    savings = cpo.savings_vs_pluggable()
    print(f"\n[CPO] Power savings vs pluggable optics:")
    print(f"  CPO: {savings['cpo_power_w']:.0f}W")
    print(f"  Pluggable: {savings['pluggable_power_w']:.0f}W")
    print(f"  Saved: {savings['savings_w']:.0f}W ({savings['savings_percent']:.0f}%)")

    print("\n✅ SOVOS CPO Monorepo operational. One mind. Layer 0. Light.")


if __name__ == "__main__":
    asyncio.run(main())
