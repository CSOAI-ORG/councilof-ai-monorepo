"""Fail-closed tests for official MCP Registry discovery intake."""
from __future__ import annotations

import hashlib
import json
import unittest
from datetime import datetime, timezone
from email.message import Message
from urllib.parse import parse_qs, urlsplit

from csoai_harvest import build_mcp_registry_snapshot
from csoai_harvest.mcp_registry import build_snapshot


class Response:
    def __init__(self, payload, url):
        self.body = json.dumps(payload, separators=(",", ":")).encode()
        self.url = url
        self.status = 200
        self.headers = Message()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, size=-1):
        return self.body if size < 0 else self.body[:size]

    def geturl(self):
        return self.url


class FakeOpener:
    def __init__(self, pages):
        self.pages = list(pages)
        self.urls = []

    def __call__(self, request, timeout=15):
        self.urls.append(request.full_url)
        if not self.pages:
            raise AssertionError("unexpected registry request")
        payload = self.pages.pop(0)
        return Response(payload, request.full_url)


def server(name, version, status="active"):
    return {
        "server": {
            "name": name,
            "version": version,
            "remotes": [{"type": "streamable-http", "url": "https://example.invalid/mcp"}],
        },
        "_meta": {"io.modelcontextprotocol.registry/official": {"status": status}},
    }


def page(rows, next_cursor=None):
    return {"servers": rows, "metadata": {"count": len(rows), "nextCursor": next_cursor}}


class MCPRegistryTests(unittest.TestCase):
    def test_package_exports_read_only_snapshot_builder(self):
        snapshot = build_mcp_registry_snapshot(
            opener=FakeOpener([page([server("a.example/mcp", "1")])])
        )
        self.assertEqual(snapshot["ingestion"]["state"], "COMPLETE")

    def test_cross_host_redirect_is_rejected(self):
        class RedirectingOpener:
            def __call__(self, request, timeout=15):
                return Response({}, "https://example.invalid/v0.1/servers")

        with self.assertRaisesRegex(ValueError, "redirected outside"):
            build_snapshot(opener=RedirectingOpener())

    def test_versions_are_distinct_rows_but_same_server_is_counted_once(self):
        opener = FakeOpener([
            page([server("ac.inference.sh/mcp", "1.0.0")], "opaque-1"),
            page([server("ac.inference.sh/mcp", "1.0.1")], None),
        ])
        snapshot = build_snapshot(
            limit=1,
            max_pages=4,
            opener=opener,
            now=datetime(2026, 9, 29, tzinfo=timezone.utc),
        )
        self.assertEqual(snapshot["ingestion"]["state"], "COMPLETE")
        self.assertEqual(snapshot["ingestion"]["rows_observed"], 2)
        self.assertEqual(snapshot["ingestion"]["distinct_servers"], 1)
        self.assertEqual(snapshot["ingestion"]["distinct_server_versions"], 2)
        self.assertEqual({record["version"] for record in snapshot["records"]}, {"1.0.0", "1.0.1"})
        self.assertIsNone(snapshot["ingestion"]["pages"][0]["request_cursor_sha256"])
        self.assertIsNotNone(snapshot["ingestion"]["pages"][0]["next_cursor_sha256"])
        self.assertIsNotNone(snapshot["ingestion"]["pages"][1]["request_cursor_sha256"])
        self.assertTrue(
            all(record["license_state"] == "UNASSESSED" for record in snapshot["records"])
        )
        self.assertTrue(
            all(record["reuse_review"] == "REQUIRED" for record in snapshot["records"])
        )


    def test_partial_page_bound_never_claims_complete(self):
        opener = FakeOpener([page([server("a.example/mcp", "1")], "cursor-1")])
        snapshot = build_snapshot(limit=1, max_pages=1, opener=opener)
        self.assertEqual(snapshot["ingestion"]["state"], "PARTIAL")
        self.assertFalse(snapshot["ingestion"]["complete"])
        self.assertTrue(snapshot["ingestion"]["next_page_available"])


    def test_incremental_mode_requests_tombstones_and_normalizes_timestamp(self):
        opener = FakeOpener([page([server("a.example/mcp", "1", "deleted")])])
        snapshot = build_snapshot(
            updated_since="2026-09-29T10:00:00+01:00", opener=opener
        )
        query = parse_qs(urlsplit(opener.urls[0]).query)
        self.assertEqual(query["updated_since"], ["2026-09-29T09:00:00Z"])
        self.assertEqual(query["include_deleted"], ["true"])
        self.assertEqual(snapshot["source"]["deleted_record_coverage"], "INCREMENTAL_STATUS_ONLY")
        self.assertEqual(snapshot["records"][0]["upstream_status"], "deleted")


    def test_full_mode_does_not_claim_deletion_coverage(self):
        opener = FakeOpener([page([server("a.example/mcp", "1")])])
        snapshot = build_snapshot(opener=opener)
        query = parse_qs(urlsplit(opener.urls[0]).query)
        self.assertNotIn("updated_since", query)
        self.assertNotIn("include_deleted", query)
        self.assertEqual(
            snapshot["source"]["deleted_record_coverage"],
            "NOT_COVERED_BY_DEFAULT_LISTING",
        )


    def test_duplicate_server_version_fails_closed(self):
        row = server("a.example/mcp", "1")
        opener = FakeOpener([page([row], "next"), page([row])])
        with self.assertRaisesRegex(ValueError, "duplicate server name/version"):
            build_snapshot(limit=1, opener=opener)


    def test_repeated_cursor_fails_closed(self):
        opener = FakeOpener([
            page([server("a.example/mcp", "1")], "same"),
            page([server("b.example/mcp", "1")], "same"),
        ])
        with self.assertRaisesRegex(ValueError, "repeated a pagination cursor"):
            build_snapshot(limit=1, opener=opener)


    def test_per_page_count_mismatch_fails_closed(self):
        opener = FakeOpener([{
            "servers": [server("a.example/mcp", "1")],
            "metadata": {"count": 99},
        }])
        with self.assertRaisesRegex(ValueError, "does not match this page"):
            build_snapshot(opener=opener)


    def test_invalid_time_and_limits_are_rejected_before_network(self):
        opener = FakeOpener([])
        with self.assertRaisesRegex(ValueError, "include a timezone"):
            build_snapshot(updated_since="2026-09-29T10:00:00", opener=opener)
        with self.assertRaisesRegex(ValueError, "limit must be an integer"):
            build_snapshot(limit=True, opener=opener)
        with self.assertRaisesRegex(ValueError, "max_pages must be an integer"):
            build_snapshot(max_pages=101, opener=opener)
        with self.assertRaisesRegex(ValueError, "timeout must be"):
            build_snapshot(timeout=float("inf"), opener=opener)
        self.assertEqual(opener.urls, [])

    def test_response_cannot_exceed_requested_page_limit(self):
        opener = FakeOpener([page([
            server("a.example/mcp", "1"),
            server("b.example/mcp", "1"),
        ])])
        with self.assertRaisesRegex(ValueError, "more rows than the requested page limit"):
            build_snapshot(limit=1, opener=opener)


    def test_source_hash_covers_exact_page_bytes(self):
        payload = page([server("a.example/mcp", "1")])
        body = json.dumps(payload, separators=(",", ":")).encode()
        snapshot = build_snapshot(opener=FakeOpener([payload]))
        self.assertEqual(
            snapshot["ingestion"]["pages"][0]["response_sha256"],
            hashlib.sha256(body).hexdigest(),
        )
        self.assertEqual(snapshot["records"][0]["claim_boundary"], "DISCOVERY_METADATA_ONLY")


if __name__ == "__main__":
    unittest.main()
