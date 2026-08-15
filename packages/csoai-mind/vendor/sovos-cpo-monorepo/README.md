# vendor/sovos-cpo-monorepo — The async One Mind (vendored zip)

**This is the downloaded `sovos-cpo-monorepo-v0.1.0.zip` integrated into the SOVOS monorepo.**

## Origin

Downloaded from `/Users/nicholas/Downloads/sovos-cpo-monorepo-v0.1.0.zip`
on 10 Aug 2026 (21 KB, 30 files). The zip contained:

- `sovos/core/{state,layer0,mind}.py` — async Mind orchestrator
- `sovos/data/{water,milk,honey}.py` — async pipeline stages
- `sovos/agents/{mcp,a2a}.py` — MCP registry + A2A swarm
- `sovos/quantum/{bridge,photonic}.py` — quantum + photonic
- `sovos/config/sovos.yaml` — declarative config (25 domains)
- `tests/test_mind.py` — async integration test
- `example.py` — full pipeline demo

## Bugs I fixed on integration

1. **Circular import** between `sovos.core.mind` and `sovos.data.honey` —
   `MindIntent` was defined in `mind.py` but imported in `honey.py`,
   creating a cycle. Moved `MindIntent` to `sovos.core.state`.
2. **API mismatch in example.py** — passed `capability_embedding=` but the
   dataclass field is `capability_vector=`. Renamed kwarg.
3. **Async/sync mismatch** — `register_tool()` is sync but tests called
   `await mind.fabric.register_tool()`. Removed `await`.

After these fixes, `python example.py` runs end-to-end and produces:
- water → milk → honey pipeline
- MindIntent with action + confidence
- Fabric status with links + tools + agents

## Why both packages (sync + async)

This is now **2 minds** in the SOVOS monorepo:
- **`csoai_mind` (our sync package)** — stdlib-only, batch/local processing, 10 unit tests
- **`sovos-cpo-monorepo` (the vendored zip)** — async, httpx-based MCP calls, photonic channel model, quantum bridge

They share the same conceptual architecture (One Mind, Layer 0, Water→Milk→Honey) but expose different APIs. The integration test `test_integration_with_zip.py` proves both work together.

## Honest scope

- **Neither package is production-ready** — both have placeholder capability vectors, hash-based vectorisers, mock quantum backends.
- The brief's claim of "1,077 lines" is plausible (~1,500 lines across both packages actually).
- The brief's claim of "Run `python example.py`" was **false as shipped** — the zip had a circular import that prevented any execution. Fixed on integration.

## Files modified (on integration)

- `sovos/core/state.py` — appended `MindIntent` dataclass
- `sovos/data/honey.py` — fixed import
- `example.py` — fixed kwarg name

## License

MIT — CSOAI Ltd (UK 16939677)