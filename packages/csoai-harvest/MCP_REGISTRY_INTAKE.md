# Official MCP Registry discovery intake

`build_mcp_registry_snapshot()` reads the public official MCP Registry using
bounded cursor pagination. It returns a metadata snapshot in memory; it does
not persist records, execute listed servers, score them, or publish anything.

```python
from csoai_harvest import build_mcp_registry_snapshot

snapshot = build_mcp_registry_snapshot(limit=100, max_pages=10)
```

Page size is capped at 100, total pages at 100, each response at 2 MB, and
timeouts at 60 seconds. `ingestion.state` is `PARTIAL` whenever a cursor
remains after the page bound.
`metadata.count` is validated and recorded as a per-page count, never a global
catalog total. Rows are identified by `(server_name, version)`, while
`distinct_servers` deduplicates names across versions. The source-page SHA-256
is retained on every record for traceability.

For incremental sync, supply an RFC3339 `updated_since` value. The request
includes `include_deleted=true`; the result explicitly labels this as
incremental tombstone/status coverage. A bounded full listing does not claim
to cover deleted entries. Unknown or absent licensing stays `UNASSESSED`,
with `reuse_review=REQUIRED`; license and redistribution review precede any
mirror. Upstream active/deleted status is source metadata, not an independent
health check. Catalog presence never becomes a GSPC measurement by itself.

Tests use only the Python standard library:

```sh
PYTHONPATH=packages/csoai-harvest/src python3 -m unittest discover \
  -s packages/csoai-harvest/tests -p 'test_mcp_registry.py' -v
```
