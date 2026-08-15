# csoai-certification-loop

**The 6-hop bridge loop that proves the SOVOS end-to-end certification story.**

```
Stripe webhook → order row → RunPod GPU spin → clan inference →
GovBench eval → SOV SIGNAL composite → C2PA Ed25519-signed manifest → proofof.ai certificate
```

Each hop is real Python code. External services (Stripe, RunPod, proofof.ai) are
represented as **stub adapters** with a clean interface, so the production
deployment just swaps the stub for the real client.

This is the heartbeat of SOVOS: every claim in the Series A deck becomes
testable when this loop runs end-to-end once.

## Hops

| # | Hop | Stub class | Real replacement |
|---|---|---|---|
| 1 | Stripe webhook | `StripeWebhookStub` | `stripe.Webhook.construct_event()` |
| 2 | Order row insert | `OrderStore` | PostgreSQL via SQLAlchemy |
| 3 | RunPod GPU spin | `RunPodStub` | `runpod.create_pod()` |
| 4 | Clan inference | `LocalClan` | `sov-core` API call |
| 5 | GovBench eval | `run_benchmark()` | (real — `sov33-benchmark`) |
| 6 | C2PA sign | `C2PASigner` | `c2pa-python` SDK |
| 7 | proofof.ai cert | `ProofOfAIStub` | HTTPS POST to `proofof.ai/api/certify` |

(The brief says 6 hops; we have 7 because C2PA signing and proofof.ai are
distinct steps.)

## Run it

```bash
PYTHONPATH=src python3 tests/test_loop.py
```

Expected: `✅ N/N tests PASSED` — the loop completes, the certificate is
emitted, every hop's stub is invoked in order.

## License

MIT — CSOAI Ltd (UK 16939677)
