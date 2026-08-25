#!/usr/bin/env python3
"""FRAMEWORKS DRUM — MCP server (stdlib-only, JSON-RPC 2.0 over stdio).

Serves the living catalog (catalog.json) to any MCP client. Reads the catalog on
every call so a fresh `build_catalog.py` run is visible immediately.

Run:  python3 frameworks_drum_server.py          (MCP JSON-RPC over stdio)
      python3 frameworks_drum_server.py --selftest  (prints tool results, exits 0)
"""
import json
import os
import re
import sys

PACK = os.path.dirname(os.path.abspath(__file__))
CATALOG = os.path.join(PACK, "..", "catalog.json")

INITIALIZE_OK = {
    "protocolVersion": "2024-11-05",
    "capabilities": {"tools": {"listChanged": False}},
    "serverInfo": {"name": "frameworks-drum", "version": "1.0.0"},
}


def load_catalog():
    try:
        with open(CATALOG, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {"items": [], "generated": None, "error": "catalog.json missing — run build_catalog.py"}


def _match(item, q):
    q = q.lower()
    hay = " ".join(
        str(item.get(k, "")) for k in ("name", "kind", "issuer", "region", "status", "effective", "description")
    ).lower()
    return q in hay


def _public(items, include_internal=False):
    if include_internal:
        return items
    return [it for it in items if not it.get("internal")]


def drum_catalog(args):
    cat = load_catalog()
    items = _public(cat.get("items", []), (args or {}).get("include_internal"))
    kinds = {}
    for it in items:
        kinds[it.get("kind", "?")] = kinds.get(it.get("kind", "?"), 0) + 1
    return {"total": len(items), "internal_hidden": len(cat.get("items", [])) - len(items),
            "kinds": kinds, "generated": cat.get("generated")}


def drum_search(args):
    q = (args or {}).get("query", "")
    kind = (args or {}).get("kind")
    limit = int((args or {}).get("limit", 20))
    offset = int((args or {}).get("offset", 0))
    items = _public(load_catalog().get("items", []), (args or {}).get("include_internal"))
    out = [it for it in items if _match(it, q) and (not kind or it.get("kind") == kind)]
    return {"query": q, "count": len(out), "offset": offset, "items": out[offset:offset + limit]}


def drum_get(args):
    iid = (args or {}).get("id", "")
    items = _public(load_catalog().get("items", []), (args or {}).get("include_internal"))
    for it in items:
        if it.get("id") == iid:
            return it
    return {"error": f"no public item with id '{iid}' (internal items are hidden unless include_internal=true)"}


def drum_crosswalk(args):
    """Find items that connect a source and a target (e.g. charter to framework).

    Returns source-side hits, target-side hits, and any direct overlap. Clause-level
    cross-walk mappings live in the estate's crosswalk pages — this tool surfaces the
    drum items on each side plus overlap, and points at the estate crosswalk source.
    """
    src = (args or {}).get("source", "")
    tgt = (args or {}).get("target", "")
    limit = int((args or {}).get("limit", 10))
    items = _public(load_catalog().get("items", []), (args or {}).get("include_internal"))

    def words(term):
        return [w for w in re.split(r"[^a-z0-9]+", term.lower()) if len(w) >= 3]

    sw, tw = words(src), words(tgt)

    def hay(it):
        return " ".join(str(it.get(k, "")) for k in ("name", "kind", "issuer", "region", "status", "description")).lower()

    s_items = [it for it in items if any(w in hay(it) for w in sw)]
    t_items = [it for it in items if any(w in hay(it) for w in tw)]
    s_ids, t_ids = {it["id"] for it in s_items}, {it["id"] for it in t_items}
    overlap = [it for it in s_items if it["id"] in t_ids]

    def brief(it):
        return {"id": it.get("id"), "name": it.get("name"), "kind": it.get("kind")}

    return {
        "source": src, "target": tgt,
        "source_hits": {"count": len(s_items), "items": [brief(i) for i in s_items[:limit]]},
        "target_hits": {"count": len(t_items), "items": [brief(i) for i in t_items[:limit]]},
        "direct_overlap": [brief(i) for i in overlap[:limit]],
        "note": "Clause-level cross-walk mappings live in the estate crosswalk pages (e.g. csoai.org/frameworks, the 12-framework crosswalk, the 236-framework universal list — see item sources); this tool surfaces the drum items on each side + any overlap.",
    }


def drum_watch(args):
    """Reg-event delta watcher (move 17): diff current reg_events.json vs the previous
    snapshot. New/changed regulation events are the DORADO reg_events + SOV SIGNAL input."""
    feed = os.path.join(PACK, "..", "feeds", "reg_events.json")
    prev_feed = os.path.join(PACK, "..", "feeds", "reg_events.prev.json")
    try:
        cur = json.load(open(feed, encoding="utf-8")).get("events", [])
    except Exception:
        return {"error": "current reg_events.json missing — run build_catalog.py"}
    prev = []
    if os.path.exists(prev_feed):
        try:
            prev = json.load(open(prev_feed, encoding="utf-8")).get("events", [])
        except Exception:
            prev = []
    cur_ids = {e.get("id") for e in cur}
    prev_ids = {e.get("id") for e in prev}
    added = [e for e in cur if e.get("id") not in prev_ids]
    changed = []
    prev_by_id = {e.get("id"): e for e in prev}
    for e in cur:
        p = prev_by_id.get(e.get("id"))
        if p and (p.get("binding") != e.get("binding") or p.get("status") != e.get("status") or p.get("effective") != e.get("effective")):
            changed.append({"id": e.get("id"), "regulation": e.get("regulation"), "field_delta": "binding/status/effective"})
    removed = [i for i in prev_ids - cur_ids]
    return {"added": len(added), "changed": len(changed), "removed": len(removed),
            "added_events": added[:10], "changed_events": changed[:10],
            "note": "delta feed for DORADO reg_events + SOV SIGNAL regulatory-pressure features"}


def drum_freshness(args):
    """Catalog freshness (move 18, P15-48): generation date + age + per-item last-verified coverage."""
    cat = load_catalog()
    gen = cat.get("generated")
    age = None
    if gen:
        from datetime import date
        try:
            age = (date.today() - date.fromisoformat(gen)).days
        except ValueError:
            age = None
    items = cat.get("items", [])
    verified = sum(1 for i in items if i.get("last_verified"))
    stale = sum(1 for i in items if i.get("last_verified") and i["last_verified"] != gen)
    return {"generated": gen, "age_days": age,
            "last_verified": {"coverage": f"{verified}/{len(items)}", "stale_vs_fold": stale},
            "note": "last_verified set at fold time (P15-48); per-item re-verification cadence is future work",
            "counts": cat.get("counts")}


def _trust_marker():
    """The trust marker written by the realized-coverage check (move 27) — the ONLY
    authority for trusted. Absent or trusted=false => NOT trusted, with the reason."""
    p = os.path.join(PACK, "..", "feeds", "router_trust.json")
    if not os.path.exists(p):
        return {"trusted": False, "reason": "no trust marker — coverage check not run"}
    try:
        m = json.load(open(p, encoding="utf-8"))
        if m.get("trusted") is True:
            return {"trusted": True, "alpha": m.get("alpha"), "n_cal": m.get("n_cal"),
                    "n_val": m.get("n_val"), "realized_error": m.get("realized_error"), "ts": m.get("ts")}
        return {"trusted": False, "reason": f"coverage check failed: realized_error={m.get('realized_error')} alpha={m.get('alpha')}"}
    except Exception as exc:  # noqa: BLE001
        return {"trusted": False, "reason": f"trust marker unreadable: {exc}"}


def drum_route(args):
    """Route a finding through the frozen conformal predicate (move 26 integration).

    Honest register: trusted ONLY when the realized-coverage check (move 27) has run and
    written feeds/router_trust.json with trusted:true. The tool never infers trust.
    """
    score = args.get("score")
    if score is None:
        return {"error": "score required"}
    try:
        score = float(score)
    except (TypeError, ValueError):
        return {"error": "score must be a number"}
    try:
        import sys as _sys
        _sys.path.insert(0, os.path.join(PACK, "..", "router"))
        import calibration_set
        import conformal_router
        rows = calibration_set.load()
        if not rows:
            return {"error": "calibration set empty — run router/calibration_set.py --seed"}
        measured = [r for r in rows if not r.get("simulated")]
        used = measured if measured else rows
        cal = [r["score"] for r in used]
        qhat, n = conformal_router.calibrate(cal)
        decision = conformal_router.route(score, qhat)
        proxy = bool(measured) and all(r.get("score_proxy") for r in used)
        marker = _trust_marker()
        return {"score": score, "qhat": round(qhat, 6), "n": n,
                "measured_labels": len(measured),
                "calibration": "measured" if measured else "SIMULATED (not trusted)",
                "score_proxy": bool(proxy),
                "decision": decision,
                "trusted": bool(marker.get("trusted")) and bool(measured) and not proxy,
                "trust_marker": marker,
                "note": "trusted ONLY when the realized-coverage check wrote trusted:true (feeds/router_trust.json)",
                "contamination_note": "benchmark leakage register: feeds/benchmark_contamination.json — "
                                      "never route a model to a probe it has seen (anti-Goodhart; NEXT-100 P3)"}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"router unavailable: {exc}"}


def drum_history(args):
    """Knowledge archive query (move 40): list entries + lineage for a content_id."""
    try:
        import sys as _sys
        _sys.path.insert(0, os.path.join(PACK, "..", "archive"))
        import knowledge_archive as ka
        cid = (args or {}).get("content_id")
        if cid:
            lin = ka.lineage(cid)
            return {"content_id": cid, "lineage": [
                {"name": e.get("name"), "kind": e.get("kind"), "outcome": e.get("outcome"),
                 "signed": e.get("signed"), "ts": e.get("ts")} for e in lin]}
        return {"entries": ka.count(), "note": "append-only; supersedes, never deletes; unsigned until #dsh rail"}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"archive unavailable: {exc}"}


def drum_compliance(args):
    """Measured-compliance evidence surface + EU AI Act GPAI map (the ecosystem's compliance layer)."""
    out = {}
    feed_dir = os.path.join(PACK, "..", "feeds")
    for name in ("measured_compliance", "gpai_compliance_map"):
        p = os.path.join(feed_dir, f"{name}.json")
        if os.path.exists(p):
            try:
                out[name] = json.load(open(p, encoding="utf-8"))
            except Exception:
                out[name] = {"error": "unreadable"}
    if not out:
        return {"error": "compliance feeds not built — run ops/build_measured_compliance.py + ops/build_gpai_map.py"}
    out["note"] = "measurement, not certification; unmeasured stays UNMEASURED"
    return out


TOOLS = {
    "drum_catalog": {"handler": drum_catalog, "schema": {"type": "object", "properties": {}}},
    "drum_search": {"handler": drum_search, "schema": {"type": "object", "properties": {
        "query": {"type": "string", "description": "free-text query"},
        "kind": {"type": "string", "description": "framework | charter | regulation | article | sector | benchmark"},
        "limit": {"type": "integer", "description": "max results (default 20)"},
        "offset": {"type": "integer", "description": "pagination offset (default 0)"},
    }, "required": ["query"]}},
    "drum_get": {"handler": drum_get, "schema": {"type": "object", "properties": {
        "id": {"type": "string", "description": "item id (slug)"},
    }, "required": ["id"]}},
    "drum_crosswalk": {"handler": drum_crosswalk, "schema": {"type": "object", "properties": {
        "source": {"type": "string", "description": "source term"},
        "target": {"type": "string", "description": "target term"},
        "limit": {"type": "integer", "description": "max results (default 10)"},
    }, "required": ["source", "target"]}},
    "drum_watch": {"handler": drum_watch, "schema": {"type": "object", "properties": {}}},
    "drum_freshness": {"handler": drum_freshness, "schema": {"type": "object", "properties": {}}},
    "drum_route": {"handler": drum_route, "schema": {"type": "object", "properties": {
        "score": {"type": "number", "description": "nonconformity score for the finding"},
    }, "required": ["score"]}},
    "drum_history": {"handler": drum_history, "schema": {"type": "object", "properties": {
        "content_id": {"type": "string", "description": "optional archive entry id for lineage"},
    }}},
    "drum_compliance": {"handler": drum_compliance, "schema": {"type": "object", "properties": {}}},
}


def handle(msg):
    method = msg.get("method")
    mid = msg.get("id")
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": mid, "result": INITIALIZE_OK}
    if method == "notifications/initialized":
        return None
    if method == "tools/list":
        tools = [{"name": n, "description": t["handler"].__doc__ or n, "inputSchema": t["schema"]}
                 for n, t in TOOLS.items()]
        return {"jsonrpc": "2.0", "id": mid, "result": {"tools": tools}}
    if method == "tools/call":
        name = (msg.get("params") or {}).get("name")
        args = (msg.get("params") or {}).get("arguments") or {}
        t = TOOLS.get(name)
        if not t:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"tool not found: {name}"}}
        try:
            result = t["handler"](args)
            return {"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}}
        except Exception as exc:  # noqa: BLE001 — MCP boundary
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32603, "message": str(exc)}}
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"method not found: {method}"}}


def serve():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = handle(msg)
        if resp is not None:
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()


def selftest():
    ok = 0
    edge_cases = {
        "drum_search": [{"query": "eu ai act"}, {"query": ""}, {"query": "zzz-no-such-term"}, {"query": "x", "limit": 5000}, {"query": "gdpr", "offset": 1}],
        "drum_get": [{"id": "eu-ai-act"}, {"id": "no-such-id"}, {}, {"id": ""}],
        "drum_crosswalk": [{"source": "charter", "target": "gdpr"}, {"source": "x", "target": "y"}, {}],
        "drum_catalog": [{}],
        "drum_watch": [{}],
        "drum_freshness": [{}],
        "drum_route": [{"score": 0.5}, {"score": 99.9}, {}, {"score": "nan"}],
        "drum_history": [{}, {"content_id": "nonexistent"}],
        "drum_compliance": [{}],
    }
    for name, t in TOOLS.items():
        cases = edge_cases.get(name, [{}])
        for args in cases:
            try:
                r = t["handler"](args)
                assert isinstance(r, dict)
                ok += 1
            except Exception as exc:  # noqa: BLE001
                print(f"FAIL {name}{args}: {exc}")
    print(f"selftest {ok}/{sum(len(v) for v in edge_cases.values())} passed")
    sys.exit(0 if ok == sum(len(v) for v in edge_cases.values()) else 1)


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        serve()
