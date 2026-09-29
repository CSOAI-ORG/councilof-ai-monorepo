"""Read-only discovery intake for the official MCP Registry.

Registry entries are versioned discovery metadata. They are not evidence of
availability, safety, endorsement, permission to execute, or a GSPC result.
This module performs no server execution and persists nothing by default.
"""
from __future__ import annotations

import hashlib
import json
import math
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Callable


BASE_URL = "https://registry.modelcontextprotocol.io"
SERVERS_PATH = "/v0.1/servers"
MAX_PAGE_BYTES = 2_000_000
MAX_LIMIT = 100
MAX_PAGES = 100
MAX_TIMEOUT_SECONDS = 60.0


def _safe_registry_url(url: str) -> bool:
    parsed = urllib.parse.urlsplit(url)
    return (
        parsed.scheme == "https"
        and parsed.hostname == "registry.modelcontextprotocol.io"
        and parsed.port in (None, 443)
        and not parsed.username
        and not parsed.password
        and parsed.path == SERVERS_PATH
        and not parsed.fragment
    )


def _checked_updated_since(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError("updated_since must be an RFC3339 timestamp")
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)
    except ValueError as exc:
        raise ValueError("updated_since must be an RFC3339 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("updated_since must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _request_page(
    url: str,
    opener: Callable[..., Any],
    timeout: float,
) -> tuple[dict[str, Any], bytes]:
    if not _safe_registry_url(url):
        raise ValueError("refusing non-allowlisted MCP Registry URL")
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "CSOAI-MCP-Registry-Discovery/0.1 (+https://councilof.ai)",
        },
    )
    with opener(req, timeout=timeout) as response:
        final_url = response.geturl() if hasattr(response, "geturl") else url
        if not _safe_registry_url(final_url):
            raise ValueError("registry response redirected outside the allowlisted endpoint")
        body = response.read(MAX_PAGE_BYTES + 1)
        if len(body) > MAX_PAGE_BYTES:
            raise ValueError("registry page exceeds the 2 MB safety limit")
        if getattr(response, "status", None) != 200:
            raise ValueError(f"registry returned HTTP {getattr(response, 'status', 'unknown')}")
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("registry page is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("registry page must be a JSON object")
    return payload, body


def _normalize_row(row: Any, page_number: int, page_sha256: str) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise ValueError("registry returned a non-object row")
    server = row.get("server")
    if not isinstance(server, dict):
        raise ValueError("registry row has no server object")
    name = server.get("name")
    version = server.get("version")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("registry server name is missing")
    if not isinstance(version, str) or not version.strip():
        raise ValueError("registry server version is missing")

    meta = row.get("_meta", {})
    if not isinstance(meta, dict):
        raise ValueError("registry row _meta must be an object")
    official = meta.get("io.modelcontextprotocol.registry/official", {})
    if not isinstance(official, dict):
        raise ValueError("official registry metadata must be an object")
    status = official.get("status")
    if status is not None and not isinstance(status, str):
        raise ValueError("registry status must be a string when present")

    remotes = server.get("remotes", [])
    packages = server.get("packages", [])
    if not isinstance(remotes, list) or not isinstance(packages, list):
        raise ValueError("registry remotes and packages must be arrays when present")

    return {
        "server_name": name.strip(),
        "version": version.strip(),
        "upstream_status": status,
        "remote_count": len(remotes),
        "package_count": len(packages),
        "license_state": "UNASSESSED",
        "reuse_review": "REQUIRED",
        "source": "official-mcp-registry",
        "source_url": BASE_URL + SERVERS_PATH,
        "page_number": page_number,
        "page_sha256": page_sha256,
        "claim_boundary": "DISCOVERY_METADATA_ONLY",
    }


def build_snapshot(
    *,
    limit: int = 100,
    max_pages: int = 10,
    updated_since: str | None = None,
    timeout: float = 15,
    opener: Callable[..., Any] = urllib.request.urlopen,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Fetch a bounded registry snapshot; incomplete pagination stays PARTIAL.

    `metadata.count` is recorded only as per-page metadata; it is never
    treated as a global catalog total. Incremental sync explicitly asks for
    deleted records, matching the registry's documented tombstone semantics.
    """
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_LIMIT:
        raise ValueError(f"limit must be an integer from 1 through {MAX_LIMIT}")
    if (
        isinstance(max_pages, bool)
        or not isinstance(max_pages, int)
        or not 1 <= max_pages <= MAX_PAGES
    ):
        raise ValueError(f"max_pages must be an integer from 1 through {MAX_PAGES}")
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not math.isfinite(timeout)
        or not 0 < timeout <= MAX_TIMEOUT_SECONDS
    ):
        raise ValueError(f"timeout must be greater than 0 and at most {MAX_TIMEOUT_SECONDS}")
    since = _checked_updated_since(updated_since)

    records: dict[tuple[str, str], dict[str, Any]] = {}
    pages: list[dict[str, Any]] = []
    cursor: str | None = None
    seen_cursors: set[str] = set()
    complete = False

    for page_number in range(1, max_pages + 1):
        query: dict[str, str] = {"limit": str(limit)}
        if cursor is not None:
            query["cursor"] = cursor
        if since is not None:
            query["updated_since"] = since
            query["include_deleted"] = "true"
        url = BASE_URL + SERVERS_PATH + "?" + urllib.parse.urlencode(query)
        payload, body = _request_page(url, opener, timeout)
        page_hash = hashlib.sha256(body).hexdigest()
        servers = payload.get("servers")
        metadata = payload.get("metadata")
        if not isinstance(servers, list) or not isinstance(metadata, dict):
            raise ValueError("registry response requires servers[] and metadata{}")
        page_count = metadata.get("count")
        if (
            isinstance(page_count, bool)
            or not isinstance(page_count, int)
            or page_count != len(servers)
        ):
            raise ValueError("registry metadata.count does not match this page")
        if len(servers) > limit:
            raise ValueError("registry returned more rows than the requested page limit")
        for row in servers:
            record = _normalize_row(row, page_number, page_hash)
            key = (record["server_name"], record["version"])
            if key in records:
                raise ValueError("duplicate server name/version across registry pages")
            records[key] = record
        next_cursor = metadata.get("nextCursor")
        if next_cursor is not None and not isinstance(next_cursor, str):
            raise ValueError("registry nextCursor must be a string or null")
        pages.append({
            "page_number": page_number,
            "response_sha256": page_hash,
            "response_bytes": len(body),
            "rows": len(servers),
            "reported_page_count": page_count,
            "request_cursor_sha256": (
                hashlib.sha256(cursor.encode("utf-8")).hexdigest()
                if cursor is not None
                else None
            ),
            "next_cursor_sha256": (
                hashlib.sha256(next_cursor.encode("utf-8")).hexdigest()
                if isinstance(next_cursor, str) and next_cursor
                else None
            ),
        })
        if not next_cursor:
            complete = True
            cursor = None
            break
        cursor_hash = hashlib.sha256(next_cursor.encode("utf-8")).hexdigest()
        if cursor_hash in seen_cursors:
            raise ValueError("registry repeated a pagination cursor")
        seen_cursors.add(cursor_hash)
        cursor = next_cursor

    observed = now or datetime.now(timezone.utc)
    if observed.tzinfo is None:
        raise ValueError("observation time must include a timezone")
    return {
        "schema": "csoai.mcp-registry-discovery/0.1",
        "source": {
            "name": "Official Model Context Protocol Registry",
            "api_url": BASE_URL + SERVERS_PATH,
            "observed_at": observed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            "sync_mode": "INCREMENTAL" if since else "BOUNDED_FULL_SCAN",
            "updated_since": since,
            "deleted_record_coverage": (
                "INCREMENTAL_STATUS_ONLY"
                if since
                else "NOT_COVERED_BY_DEFAULT_LISTING"
            ),
        },
        "ingestion": {
            "state": "COMPLETE" if complete else "PARTIAL",
            "complete": complete,
            "pages_read": len(pages),
            "rows_observed": len(records),
            "distinct_servers": len({name for name, _ in records}),
            "distinct_server_versions": len(records),
            "next_page_available": cursor is not None,
            "page_count_semantics": "PER_PAGE_NOT_GLOBAL_TOTAL",
            "pages": pages,
        },
        "records": [records[key] for key in sorted(records)],
        "limitations": [
            "Registry presence and upstream status are not independent endpoint health checks.",
            "Catalog entries are not tested or admitted GSPC measurements.",
            "No listed server is executed by this importer.",
            "License and redistribution terms are unassessed; review is required before mirroring.",
        ],
    }


__all__ = ["BASE_URL", "MAX_LIMIT", "SERVERS_PATH", "build_snapshot"]
