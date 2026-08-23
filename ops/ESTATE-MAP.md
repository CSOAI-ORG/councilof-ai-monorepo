# CSOAI estate map

Measurement packages live here. The public site does **not**.

Do not copy the `councilof-ai` SPA into this monorepo. Deploy source of truth
for the stranger surface is `CSOAI-ORG/councilof-ai` → Cloudflare Pages project
`councilof-ai` (apex `councilof.ai`).

| Piece | Repo / host | Role |
|---|---|---|
| Public site + Council OS + DSH | `CSOAI-ORG/councilof-ai` → Pages `councilof-ai` | Stranger doors, `?lobby=`, `/dashboard` |
| Apex DID / static keys | `CSOAI-ORG/csoai-static-deploy2` → Pages `csoai-site` | `did:web:csoai.org` at `csoai.org`. Do not redeploy the SPA here. |
| Signed measurement packages | this repo `packages/csoai-*` | Axis engine, fleet, core, benches |
| Eunomia / bond-router | this repo `packages/eunomia-*` | In-flight: PR #2. Do not merge blindly. |
| Ops cron + mirror | this repo `ops/cron`, `ops/mirror` | Scheduled jobs, dataset mirrors |
| Org profile + defaults | `CSOAI-ORG/.github` | Profile README, community-health files only |
| ClaimGuard | `CSOAI-ORG/claimguard` | Claim track (sibling inventory on `.github` PR #3) |
| Attestation verify (live) | `https://meok-attestation-api.vercel.app/verify` | Host still named meok-*; renamed host 404s. Do not "fix" the name without a live host. |

## Front end publishing (do not vendor)

- Official deploy: `councilof-ai` `.github/workflows/deploy.yml` — prerender, aliases, brand-gate, wrangler to `--branch=master`, `main`, `production`.
- Owner blocker: disable Pages **Git auto-deploy** on project `councilof-ai` (see `DEPLOY-LOCK.md` in that repo). Auto-build clobbers the gated tree.
- AG UI **is** Council OS. Door is `https://councilof.ai/?lobby=home`. Do not iframe `/os` as Home. Do not remount a second console.
- Counts live in `GET https://councilof.ai/api/gspc`. Do not hardcode axis totals.

## GPU / RunPods / mining

- No RunPod integration exists in CSOAI-ORG code (searched 2026-08-23).
- Fleet packages here: `packages/csoai-fleet`, `packages/csoai-fleet-manifest`. Start there if a GPU fleet is commissioned.
- `CSOAI-ORG/mining-ai` is a stale MEOK MCP (last update 2026-06-27). Not a public product. Do not revive as crypto mining.
- Hugging Face (Nick): public datasets `govbench`, `govbench-items`, archival `csai-govbench-2026`. Most `sov33*` models are private and still use retracted BFT/Sovereign labels — do not publish them as the product without an owner de-brand decision.

## Open work left to their authors

- `.github` draft PR #3 — axis canon + ClaimGuard gap + HF patches (sibling agent).
- `councilof-ai` PR #324 — Dorado Bench + evidence pack (`mergeable_state: unstable`). Review doctrine before squash.
- This monorepo PR #2 — eunomia financial axes + bond-router.
