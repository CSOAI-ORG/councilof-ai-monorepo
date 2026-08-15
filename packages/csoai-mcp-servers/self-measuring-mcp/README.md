# self-measuring-mcp — the Layer-1 discovery + forcing-function surface

Title: Self-Measuring MCP Server — signed measurement an agent calls on itself.

An orchestrating agent finds us the way it finds any tool in 2026, but THIS
surface is the one that makes it autocatalytic: the agent calls the MCP server
on ITSELF, emits an Ed25519-signed measurement card, and that card feeds the
board + the badge + the training funnel. Discovery (registry, agent-card,
llms.txt, .well-known) makes us findable; the signed-card forcing function
(CI gate / marketplace badge / insurer requirement) makes us USED.

Lane note: this is a NEW surface (agent-facing plumbing that wraps the
canonical measurement), not a third copy of council_signal.py. It imports the
sovos-city CouncilSignal/Chain rather than reimplementing them.
