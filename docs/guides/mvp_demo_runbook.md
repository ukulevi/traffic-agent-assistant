# MVP Demo Runbook

## Offline Smoke Evidence

Install the existing orchestrator extra, then run the deterministic offline smoke harness:

```powershell
pip install -e ".[orchestrator]"
python scripts/demo/run_mvp_smoke.py
```

The harness uses in-memory provisional adapters only. It verifies HTTP 202,
terminal status, SSE result delivery, and operator approve/reject audit flow.
It writes aggregate-only evidence to `data/derived/private/demo/mvp_smoke_evidence.json`.

The evidence is private. It is not a production benchmark, live-service result,
raw-video artifact, or authorization to control field equipment. Verify
`automatic_actuation` and `applied_by_system` are `false` for every case.
