# CSOAI durable-receipt runtime — design (READ-ONLY, no deploy)

**Status:** design only. Do NOT deploy or wire until Nick approves the architectural decision. Owner-gated.
**Why it exists:** `gaps-2026-09.md` P0 #1 + `functions/api/receipts/index.ts` say it plainly — LEADS KV has
no compare-and-swap, so `/api/action-jobs` is SINGLE_WRITER_STAGING and there are **no durable settlement
receipts** (`/api/receipts/latest` = UNPUBLISHED). This is the ONE real "full stack" gap.

## The problem (measured, not assumed)
- `/api/action-jobs` = 200, bounded action-intent ledger on KV, write-once keys for immutable events/receipts,
  BUT the **head + idempotency indexes cannot be safe under concurrent writers**.
- `/api/agentic-fix` = 503 `@openapi-unavailable` (honesty-gated; the fix→retest→receipt step is not live).
- `/api/receipts/latest` = UNPUBLISHED — a buyer who HAS paid must be told "receipts are not recorded at all",
  and today that is the true answer.

## The design (Cloudflare-native, matches the product map)
| Concern | Product | Why |
|---|---|---|
| Per-actor strongly-consistent ledger state | **Durable Object** `ActionJobLedger` | transactional, single-threaded per key → safe head/idempotency under concurrent writers |
| Queryable SQL (receipts, jobs, by payer/axis) | **D1** | relational queries, joins, per-payer history |
| Immutable signed artifacts (cards, receipts) | **R2** | content-addressed object store, S3-compatible |
| Async fan-out (notify, re-sign) | **Queues** | decouple the ledger from side effects |
| Embedding search over cards | **Vectorize** | semantic lookup over the measurement corpus |
| Model inference (re-measure/fresh sweeps) | **Workers AI** | edge inference for new-axis grading |
| Signed-card attestation at rest | **Secrets Store** | estate signer key, never in code |

## D1 schema (SQL) — `receipts` + `action_jobs`
```sql
CREATE TABLE IF NOT EXISTS action_jobs (
  id TEXT PRIMARY KEY,              -- content-id / write-once
  payer TEXT NOT NULL,
  axis TEXT NOT NULL,
  kind TEXT NOT NULL,               -- 'submit' | 'approve' | 'fix' | 'retest' | 'receipt'
  status TEXT NOT NULL,             -- 'staged' | 'pending-verify' | 'measured' | 'unmeasured' | 'receipted'
  accuracy REAL,                    -- NEVER emitted unless status='measured' (trap #1: signed != verdict)
  payload TEXT NOT NULL,            -- canonical JCS-ish JSON
  signature TEXT,                   -- Ed25519 over canonical payload (estate signer)
  canon TEXT,                       -- 'jcs-rfc8785' for new cards; absent = legacy v1
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_action_jobs_payer ON action_jobs(payer, status);
CREATE INDEX IF NOT EXISTS idx_action_jobs_axis ON action_jobs(axis, status);
```
- **Honesty rules baked in:** `status` is authoritative; `accuracy` is write-once and only ever published next to
  `status='measured'`. A signed card that says `unmeasured` stays `unmeasured` (hub-cards already honours
  `signed-pending-verify`). Never a bare zero; a null is an unread value, never a measured zero.
- **Idempotency:** primary key = content-id; `INSERT ... ON CONFLICT(id) DO NOTHING` makes submission/approval
  write-once. The DO serialises the head + idempotency index so the SQL stays append-only.

## Durable Object sketch (`ActionJobLedger`)
```
class ActionJobLedger {
  // single-threaded per key (payer or axis) -> head + idempotency index are atomic
  async submit(cid, row)      { const r = await this.state.storage.get(cid); if (r) return {dup:true}; await set(cid,row); updateHead; return row }
  async transition(cid, to)   { read current; assert valid transition; write receipt; updateHead; return {ok, receipt} }
  async head(payer)           { return this.state.storage.get(`head:${payer}`) }
}
```
- One DO per payer (or shard by `payer % N`) → strong consistency + hot-key isolation.
- Receipts R2-put as `signed/receipts/{cid}.json`; the D1 row is the queryable projection.

## Migration / rollout
1. Land the D1 migration + DO class behind a flag; keep the current honest `/api/receipts` response until storage wired.
2. Enable `/api/agentic-fix` (drop the 503) ONLY after multi-writer + receipts are proven.
3. Prove it: a test that **fails without the DO** (concurrent `submit` of two transitions → one winning, no
   double-receipt), write it first, watch it red, then green.

## Learn-from-integrations → improve everything
| Estate surface | Current | Upgrade (Cloudflare/HF) | Wins |
|---|---|---|---|
| Measurement freshness (board 3 wks old) | RunPod sweep | **Workers AI** edge inference for quick re-grades + **Queues** for re-sign fan-out | fresher figures without a big fleet run |
| Card search/lookup | linear scan | **Vectorize** embeddings over cards | semantic find a card by meaning |
| Signed artifact durability | sink volume | **R2** third copy (s3-compatible, reachable from anywhere) | durable + accessible |
| HF population | 699 cells Hub mirror | **HF datasets + Spaces + inference** — re-publish the 17 XRPL + 13 EUNOMIA measured sets as fresh datasets; add a Space running `verify-card.mjs` (the brief's three-state VALID/INVALID/UNCHECKABLE demo) | public, verifiable, fresh |
| A2A/discovery | agent-card.json | keep pinned-DID Ed25519 (never Sigstore/Fulcio — identity is the asset) | stable trust |

## What I deliberately did NOT do
No D1/DO was created, no deploy, no signing, no receipt written, no HF publish. This is a design + schema for
Nick to approve. The moment storage is unblocked, the schema + DO sketch drop straight in.

_Design 2026-09-05, grounded in Cloudflare DO/D1/R2/Queues/Vectorize/Workers AI + HF datasets/Spaces/inference._
