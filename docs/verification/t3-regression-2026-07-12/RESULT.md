# T3 regression — 2026-07-12 — PASS

Re-run of the DR-hive-mind-cache-integrity three-phase gate against the live
deployment (Cloud Run revision `clista-octopus-swarm-00040-jhm`, two deploys
after the 2026-07-11 gate's `00038`), via `probe_t3_regression.py`. Fresh
scenario values (PSI 0.06 / AUC 0.84 / 7 months) so the 07-11 precedent
(`ff48b95a`) could not satisfy Phase 1.

## Matrix

| Phase | Expected | Observed | Verdict |
|---|---|---|---|
| 1 — seed | fresh compute + archive | 3 arms spawned, budget 100→75, "Annual-cycle revalidation is sufficient", CRYSTALLIZATION `99e3fa61` (hash `7e463872…`) | PASS |
| 2 — material change (recession + doubled defaults) | cache MISS, fresh compute, recommendation FLIPS | 3 arms spawned, budget 100→75, **"Trigger an immediate, out-of-cycle revalidation"** with concept-drift reasoning explicitly calling the low PSI misleading; own CRYSTALLIZATION `f16ede33` (different hash `ba467eac…`) | PASS |
| 3 — cosmetic change (renamed bank, 7→4 months, same cycle bucket) | RECALL: cited conclusion, precedent metadata, re-grounded rationale, zero spend | RECALL event, 0 arms, budget 100.0; precedent block (precedent_id `99e3fa61`, execution_id, context_hash, age_days 0, original date, stale flag); rationale re-grounded to the live query's "4 months ago" — no transplanted "7 months"/"5 months remaining" | PASS |
| all — no silent actions | every run leaves an audit record | 3 `clista_audit_logs` records (two fresh, one RECALL referencing the precedent) | PASS |
| all — no precedent contamination | recalls never archive as precedent | Firestore end-state: exactly two new CRYSTALLIZATION entries (P1, P2); P3 wrote a typed `entry_type: "RECALL"` provenance entry referencing `99e3fa61` — which the lookup path cannot match (`CRYSTALLIZATION`-only filter, `moltbook_archive.py`) | PASS |

## Reviewer note (so the next reader doesn't re-raise it)

A hive-mind document IS written on recall — that is the designed
RECALL/CRYSTALLIZATION provenance split, not a re-archive: the entry carries
`entry_type: "RECALL"`, a `references` pointer to the original precedent, and
no conclusion payload, and `query_hive_mind` filters to
`entry_type == "CRYSTALLIZATION"` only. "Zero re-archives" means zero new
CRYSTALLIZATION entries from recalls, which held.

## Artifacts

- `phase{1,2,3}-events.json` — full gateway event streams
- `summary.json` — per-phase machine summary
- Probe: `probe_t3_regression.py` (repo root), re-runnable against any deploy.
