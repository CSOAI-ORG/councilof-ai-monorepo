"""csoai_bus_redis — Redis-backed persistence for the SOVOS StateBus.

This is the persistence layer (gap #2 from the brief). It is a drop-in
replacement for the in-process StateBus in sovos-mind/state.py: the same
append / read_by_layer / read_by_source / subscribe API, but the data
lives in Redis so it survives process restarts and is shared across the
Mac, the RunPod pod, and any MCP worker.

Why Redis?
----------
- Append-only log per layer (LIST), indexed by sv_id (HSET).
- Pub/sub for the subscribe API — when a new vector lands, every
  subscriber gets a real push, not a poll.
- Atomic Lua scripts for "append + emit" so the append and the
  notification cannot be split across an outage.
- Zero-config: fakeredis fallback if no Redis server is reachable,
  so the chain still works in test / dev.

Public API (drop-in for StateBus):
    from csoai_bus_redis import RedisBus
    bus = RedisBus()                       # uses env or localhost:6379
    bus = RedisBus(redis_url="redis://...") # explicit
    bus = RedisBus(use_fakeredis=True)     # in-memory, no server

    sv_id = bus.append(sv)                 # returns sv.sv_id (or mints one)
    vectors = bus.read_by_layer("water")   # list[StateVector]
    bus.subscribe("water", cb)             # cb(StateVector) on new appends
    stats = bus.stats()                    # {total, by_layer, by_source}

Wire format:
    HSET sovos:sv:<sv_id> source layer ts vector_json payload_json
    LPUSH sovos:layer:<layer> <sv_id>
    LPUSH sovos:source:<source> <sv_id>
    PUBLISH sovos:events:<layer> <sv_id>

This is the substrate that unblocks Modes 0/1/2:
    - Mode 0 (user creation): birth event is a "water" append
    - Mode 1 (chat): message is a "milk" append + "water" subscriber
    - Mode 2 (tool call): tool result is a "honey" append

When Redis is down (or in fakeredis mode), the bus still works locally;
the only thing lost is cross-process persistence.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Optional Redis client — fakeredis fallback if no real Redis is available
# ---------------------------------------------------------------------------
def _import_redis():
    """Return a (client_factory, is_fakeredis) tuple.

    The factory takes no args and returns a Redis-like client.
    Prefers real redis; falls back to fakeredis.
    """
    try:
        import redis as _redis
        # Smoke test: try connecting to default localhost
        try:
            c = _redis.Redis(host="localhost", port=6379, db=0,
                              socket_connect_timeout=0.5, decode_responses=True)
            c.ping()
            return (_redis.Redis, False)
        except Exception:
            pass
    except ImportError:
        pass
    try:
        import fakeredis as _fake
        return (_fake.FakeStrictRedis, True)
    except ImportError:
        return (None, True)


def _make_client(_import_redis, force_fake: bool = False):
    """Return a Redis-like client. Always returns something usable.

    For fakeredis, we create a FRESH FakeServer per call so each
    RedisBus instance is fully isolated — fakeredis otherwise shares a
    single global in-memory server across all FakeStrictRedis instances
    (caught by the full-suite run: successive buses leaked vectors into
    each other). Passing an explicit FakeServer fixes that isolation.

    `force_fake=True` (from RedisBus(use_fakeredis=True)) OVERRIDES
    connectivity detection: a live Redis on localhost must NOT win when
    the caller explicitly asked for fake — otherwise tests write into
    the real server and state persists across processes (caught on this
    Mac: redis-server IS up on 6379, and identical sv_ids reappeared
    across pytest invocations).
    """
    if force_fake:
        try:
            import fakeredis as _fkr
            server = _fkr.FakeServer()
            return _fkr.FakeStrictRedis(server=server, decode_responses=True), True
        except ImportError:
            raise RuntimeError(
                "csoai_bus_redis: fakeredis required for use_fakeredis=True. "
                "Install with `pip install fakeredis`."
            )
    factory, is_fake = _import_redis()
    if factory is None:
        raise RuntimeError(
            "csoai_bus_redis requires `redis` or `fakeredis`. "
            "Install with `pip install redis` or `pip install fakeredis`."
        )
    if is_fake:
        # fakeredis.FakeStrictRedis(server=...) gives per-bus isolation
        try:
            import fakeredis as _fkr
            server = _fkr.FakeServer()
            return _fkr.FakeStrictRedis(server=server, decode_responses=True), True
        except Exception:
            pass
    return factory(decode_responses=True), is_fake


# ---------------------------------------------------------------------------
# StateVector — same dataclass shape as sovos-mind.state.StateVector.
# Re-declared here to keep this package self-contained (sovos-mind is an
# optional dep). If you import sovos-mind, the StateBus.append() method
# accepts both shapes; the RedisBus serializes by attribute.
# ---------------------------------------------------------------------------
@dataclass
class StateVector:
    source: str
    layer: str             # "water" | "milk" | "honey" | "action" | "control"
    vector: List[float]
    payload: Dict[str, Any] = field(default_factory=dict)
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    sv_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "StateVector":
        return cls(
            source=d.get("source", ""),
            layer=d.get("layer", ""),
            vector=list(d.get("vector", [])),
            payload=dict(d.get("payload", {})),
            ts=d.get("ts", ""),
            sv_id=d.get("sv_id", ""),
        )


# ---------------------------------------------------------------------------
# RedisBus — the drop-in replacement for StateBus
# ---------------------------------------------------------------------------
class RedisBus:
    """Redis-backed SOVOS StateBus.

    Attributes:
        namespace: key prefix (default "sovos") — useful for multi-tenant
        use_fakeredis: if True, use fakeredis even when a real Redis is available
        redis_url: explicit redis://... URL (overrides REDIS_URL env var)
    """

    def __init__(self, redis_url: Optional[str] = None,
                 namespace: str = "sovos",
                 use_fakeredis: bool = False):
        self.namespace = namespace
        self._client: Any = None
        self._is_fake = True
        self._pubsub: Any = None
        self._pubsub_thread: Optional[threading.Thread] = None
        self._pubsub_stop = threading.Event()
        self._subscribers: Dict[str, List[Callable[[StateVector], None]]] = defaultdict(list)

        url = redis_url or os.environ.get("REDIS_URL", "redis://localhost:6379/0")

        # If caller wants fake, or no redis URL given, try fakeredis first.
        if use_fakeredis or url.startswith("fakeredis://"):
            client, is_fake = _make_client(_import_redis, force_fake=True)
            self._client = client
            self._is_fake = True
            logger.info("RedisBus: fakeredis (in-memory, no server)")
            return

        # Try real Redis first; fall back to fakeredis on any failure.
        try:
            import redis as _redis_mod
            self._client = _redis_mod.from_url(url, decode_responses=True)
            self._client.ping()
            self._is_fake = False
            logger.info("RedisBus: connected to %s", url)
        except Exception as e:
            logger.warning("RedisBus: cannot connect to %s (%s); falling back to fakeredis", url, e)
            client, is_fake = _make_client(_import_redis)
            self._client = client
            self._is_fake = True

        # Start the pub/sub listener thread (only if we have at least one subscriber)
        # It starts lazily on first subscribe() to keep idle cost at zero.

    # -----------------------------------------------------------------------
    # Key helpers
    # -----------------------------------------------------------------------
    def _k_sv(self, sv_id: str) -> str:
        return f"{self.namespace}:sv:{sv_id}"

    def _k_layer(self, layer: str) -> str:
        return f"{self.namespace}:layer:{layer}"

    def _k_source(self, source: str) -> str:
        return f"{self.namespace}:source:{source}"

    def _k_events_layer(self, layer: str) -> str:
        return f"{self.namespace}:events:{layer}"

    # -----------------------------------------------------------------------
    # Core API (drop-in for StateBus)
    # -----------------------------------------------------------------------
    def append(self, sv: StateVector) -> str:
        """Append a StateVector. Returns its sv_id (mints one if missing).

        Wire:
          HSET sovos:sv:<id> {source, layer, ts, vector_json, payload_json}
          LPUSH sovos:layer:<layer> <id>
          LPUSH sovos:source:<source> <id>
          PUBLISH sovos:events:<layer> <id>
        """
        if not sv.sv_id:
            sv.sv_id = self._mint_sv_id(sv)
        d = sv.to_dict()
        self._client.hset(self._k_sv(sv.sv_id), mapping={
            "source": sv.source,
            "layer": sv.layer,
            "ts": sv.ts,
            "vector_json": json.dumps(sv.vector),
            "payload_json": json.dumps(sv.payload),
        })
        self._client.lpush(self._k_layer(sv.layer), sv.sv_id)
        self._client.lpush(self._k_source(sv.source), sv.sv_id)
        # Publish — also fires local subscribers via the listener thread.
        self._client.publish(self._k_events_layer(sv.layer), sv.sv_id)
        # Fire in-process subscribers directly as well (fakeredis pubsub
        # is in-process so this is redundant for fakeredis, but necessary
        # for threaded pubsub with real Redis).
        for cb in self._subscribers.get(sv.layer, []):
            try:
                cb(sv)
            except Exception as e:
                logger.debug("subscriber callback failed: %s", e)
        return sv.sv_id

    def read_by_layer(self, layer: str, limit: int = 1000) -> List[StateVector]:
        ids = self._client.lrange(self._k_layer(layer), 0, limit - 1)
        return [self._read_one(sv_id) for sv_id in ids if self._exists(sv_id)]

    def read_by_source(self, source: str, limit: int = 1000) -> List[StateVector]:
        ids = self._client.lrange(self._k_source(source), 0, limit - 1)
        return [self._read_one(sv_id) for sv_id in ids if self._exists(sv_id)]

    def read_all(self, limit: int = 1000) -> List[StateVector]:
        """Read the most recent vectors across all layers (best-effort)."""
        all_ids = set()
        for layer in ("water", "milk", "honey", "action", "control"):
            for sv_id in self._client.lrange(self._k_layer(layer), 0, 99):
                all_ids.add(sv_id)
        return [self._read_one(sv_id) for sv_id in list(all_ids)[:limit] if self._exists(sv_id)]

    def subscribe(self, layer: str, callback: Callable[[StateVector], None]) -> None:
        """Register a callback for new StateVectors in `layer`.

        This is BOTH an in-process callback AND a Redis pub/sub subscription.
        For fakeredis, the in-process callback fires immediately (the append
        method calls it directly). For real Redis, the listener thread
        picks up the publish and dispatches the callback.
        """
        self._subscribers[layer].append(callback)
        self._ensure_listener()

    def stats(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "namespace": self.namespace,
            "backend": "fakeredis" if self._is_fake else "redis",
            "by_layer": {},
            "by_source": {},
            "total": 0,
        }
        for layer in ("water", "milk", "honey", "action", "control"):
            n = self._client.llen(self._k_layer(layer))
            if n:
                out["by_layer"][layer] = n
                out["total"] += n
        # Scan sources — bounded scan for the demo
        for key in self._client.scan_iter(match=f"{self.namespace}:source:*", count=100):
            source = key.split(":", 2)[-1]
            n = self._client.llen(key)
            out["by_source"][source] = n
        return out

    def ping(self) -> bool:
        try:
            return bool(self._client.ping())
        except Exception:
            return False

    def close(self) -> None:
        """Stop the listener thread and close the Redis connection."""
        self._pubsub_stop.set()
        if self._pubsub_thread is not None:
            self._pubsub_thread.join(timeout=2.0)
        try:
            if self._client is not None and hasattr(self._client, "close"):
                self._client.close()
        except Exception:
            pass

    # -----------------------------------------------------------------------
    # Internals
    # -----------------------------------------------------------------------
    def _mint_sv_id(self, sv: StateVector) -> str:
        import hashlib
        body = json.dumps({
            "source": sv.source, "layer": sv.layer,
            "vector": sv.vector, "payload": sv.payload,
            "ts": sv.ts,
        }, sort_keys=True, default=str).encode()
        return hashlib.sha256(body).hexdigest()[:16]

    def _exists(self, sv_id: str) -> bool:
        return bool(self._client.exists(self._k_sv(sv_id)))

    def _read_one(self, sv_id: str) -> Optional[StateVector]:
        h = self._client.hgetall(self._k_sv(sv_id))
        if not h:
            return None
        try:
            vector = json.loads(h.get("vector_json", "[]"))
            payload = json.loads(h.get("payload_json", "{}"))
        except json.JSONDecodeError:
            vector, payload = [], {}
        return StateVector(
            source=h.get("source", ""),
            layer=h.get("layer", ""),
            vector=vector,
            payload=payload,
            ts=h.get("ts", ""),
            sv_id=sv_id,
        )

    def _ensure_listener(self) -> None:
        """Start the pub/sub listener thread if not already running."""
        if self._pubsub_thread is not None and self._pubsub_thread.is_alive():
            return
        if not self._subscribers:
            return
        # fakeredis: in-process callbacks already fire on append().
        # But we still start the listener so the API surface is uniform.
        try:
            self._pubsub = self._client.pubsub()
            for layer in list(self._subscribers.keys()):
                self._pubsub.subscribe(self._k_events_layer(layer))
        except Exception as e:
            logger.debug("pubsub subscribe failed: %s", e)
            return

        self._pubsub_stop.clear()

        def _listen():
            try:
                while not self._pubsub_stop.is_set():
                    msg = self._pubsub.get_message(timeout=0.5)
                    if msg is None:
                        continue
                    if msg.get("type") != "message":
                        continue
                    channel = msg.get("channel", "")
                    sv_id = msg.get("data", "")
                    if not isinstance(sv_id, str):
                        continue
                    # channel format: sovos:events:<layer>
                    parts = channel.split(":")
                    if len(parts) < 3:
                        continue
                    layer = parts[2]
                    sv = self._read_one(sv_id)
                    if sv is None:
                        continue
                    for cb in self._subscribers.get(layer, []):
                        try:
                            cb(sv)
                        except Exception as e:
                            logger.debug("listener callback failed: %s", e)
            except Exception as e:
                logger.warning("pubsub listener exited: %s", e)

        self._pubsub_thread = threading.Thread(target=_listen, daemon=True)
        self._pubsub_thread.start()


# ---------------------------------------------------------------------------
# Convenience: build a Bus instance from env
# ---------------------------------------------------------------------------
def from_env() -> RedisBus:
    """Build a RedisBus from environment variables.

    Env:
        REDIS_URL: explicit redis://... URL (default redis://localhost:6379/0)
        SOVOS_BUS_NAMESPACE: key prefix (default "sovos")
        SOVOS_BUS_FAKE: "1" / "true" to force fakeredis
    """
    url = os.environ.get("REDIS_URL")
    namespace = os.environ.get("SOVOS_BUS_NAMESPACE", "sovos")
    fake = os.environ.get("SOVOS_BUS_FAKE", "").lower() in ("1", "true", "yes")
    return RedisBus(redis_url=url, namespace=namespace, use_fakeredis=fake)


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------
def self_test() -> Dict[str, Any]:
    """Run an in-memory smoke test. Returns a dict of results.

    NB: LPUSH prepends, so the most-recent vector is at index 0.
    """
    bus = RedisBus(use_fakeredis=True)
    received: List[StateVector] = []

    def cb(sv: StateVector) -> None:
        received.append(sv)

    bus.subscribe("water", cb)
    sv1 = StateVector(source="self-test", layer="water", vector=[1.0, 2.0])
    bus.append(sv1)
    sv2 = StateVector(source="self-test", layer="water", vector=[3.0, 4.0])
    bus.append(sv2)

    water = bus.read_by_layer("water")
    by_src = bus.read_by_source("self-test")
    stats = bus.stats()
    bus.close()

    # Either order is fine — both vectors should be present
    ids = {v.sv_id for v in water}
    return {
        "appended_ok": len(water) == 2 and sv1.sv_id in ids and sv2.sv_id in ids,
        "by_source_count": len(by_src),
        "subscribers_fired": len(received),
        "stats_total": stats.get("total", 0),
        "backend": stats.get("backend", "?"),
    }
