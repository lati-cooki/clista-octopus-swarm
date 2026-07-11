# DR: Hive Mind Cache Integrity

**Date:** 2026-07-10
**Status:** Accepted

## Context

The Hive Mind is `clista-octopus-swarm`'s decision cache: when a new prompt's embedding is
cosine-similar (≥ 0.88) to a previously archived prompt, the gateway serves the archived
conclusion *and its original rationale* instead of dispatching the multi-arm swarm again,
logging zero compute cost. The design intent is legitimate — genuinely identical decision
contexts should not re-pay for consensus. Whether the design achieves that, for a system
whose outputs are risk-model revalidation recommendations, had never been tested against a
live deployment. On 2026-07-10 it was, and it failed.

## Evidence

A three-phase empirical test was run against the live Cloud Run deployment
(`clista-octopus-swarm`, `us-central1`, GCP project `gen-lang-client-0312043374`) at
approximately 11:29–11:33 PM local time (06:25–06:33 UTC on 2026-07-11 per Firestore
timestamps).

**Phase 1 (seed).** Execution ID `74890807-cccb-4a9f-b4ac-d172b5ff506b`. Prompt (verbatim,
recovered from `clista_audit_logs`):

> A regional bank's PD (probability of default) model for small-business
> lending shows a population stability index (PSI) of 0.08 on all input
> features over the last quarter. Model accuracy (AUC) at last validation
> was 0.82. The model was validated 8 months ago. Should the model risk
> team trigger an out-of-cycle revalidation, or is annual-cycle
> revalidation sufficient? Provide a recommendation with confidence.

The swarm computed fresh (audit write `06:25:57.305Z`, hive-mind archive write
`06:25:58.679Z`, ~1.4s apart — two writes from one execution). Conclusion: annual-cycle
revalidation is sufficient. This is defensible on the stated facts: low PSI, no adverse
signal, mid-cycle. The answer was archived to `clista_hive_mind`.

**Phase 2 (material change).** The identical Phase 1 prompt, plus: *"3 months ago the Fed
cut rates 150bps and the region entered a recession; realized default rates in the
portfolio have doubled while the applicant feature mix is unchanged."* Under the stated
facts, the correct answer flips — this is precisely the population-drift signal that
should trigger immediate out-of-cycle revalidation. The system logged:

```
Hive Mind HIT! Recovered past consensus. 0.0 Compute Cost.
```

It served the Phase 1 answer verbatim, including rationale claiming "no compelling evidence
of performance degradation" — a sentence directly contradicted by the doubled default rate
stated in the Phase 2 prompt itself. Zero arms were spawned; zero budget was consumed.

**Phase 3 (immaterial change).** The Phase 1 prompt with only cosmetic edits: the bank
renamed "webbank," and "8 months ago" changed to "2 months ago" — a change that does not
cross the annual revalidation cycle boundary and should not change the recommendation. This
also produced a `Hive Mind HIT!`, but for the wrong reason: it served rationale asserting
"8 months ago" and "annual revalidation is only 4 months away" — both statements false for
the Phase 3 query, which stated 2 months and would have ~10 months of cycle remaining.

Phase 2 shows a HIT firing when it should have MISSED (a material fact was ignored). Phase 3
shows a HIT firing for approximately the right reason but with the wrong, stale, and
factually false supporting text served to the requester. Together the two phases falsify
the Hive Mind's cache-key and cache-response designs independently: getting a HIT on Phase 2
is a matching-relevance failure; getting a false-fact rationale on Phase 3 (a case where a
HIT was in fact appropriate) is a response-content failure. One test that only checked
"does the cache ever incorrectly recall" would have caught Phase 2 and missed Phase 3, or
vice versa — both defects had to be diagnosed and fixed.

## Diagnosed defects

**1. Relevance-blind matching.** The lookup (`moltbook_archive.py:query_hive_mind`, prior
to this fix) matched purely on prompt-embedding cosine similarity. Similarity is symmetric
and directionless with respect to what actually changed between two prompts: Phase 2 added
a decision-reversing fact and still matched; Phase 3 changed nothing decision-relevant and
also matched. The mechanism cannot tell the two apart in either direction — it is not that
the cache is "mis-keyed" toward one failure mode, it is that similarity carries no signal
about which deltas are material. A key built on semantic proximity of the *prompt text* is
the wrong invariant; the cache needs to key on the *decision-relevant facts*, not on how the
prompt happens to be worded.

**2. Rationale transplant.** Even where the cached *conclusion* would have been the right
answer (Phase 3), serving the cached *rationale* verbatim is never safe, because a
rationale's sentences are indexed to the facts of the query that produced them ("8 months
ago," "4 months away") — not to the query that recalls it. This is the same distinction case
law draws between a holding and an opinion's recitation of facts: a later court may cite a
prior case's *holding* as binding precedent without importing the *facts of that case* as if
they were facts of the new one. Doing the latter — reading the prior opinion's facts into
the current record — is exactly what a Hive Mind HIT does today when it copies the cached
rationale text. A cached conclusion may be defensible on the current facts; a cached
justification, quoted verbatim, asserts facts about the current case that were never
established for it.

## Slice 1 forensics finding

A read-only forensic pass (Task 1; see `.superpowers/sdd/slice1-forensics.md`) inspected
live Firestore state directly, using scripts that made no `.set()`, `.update()`, `.delete()`,
or `.add()` calls, to answer the follow-on question: did the Phase 2/3 recalls make the
contamination worse by re-archiving the recalled (and in Phase 2's case, wrong) answer as a
fresh precedent, compounding the error for future recalls?

**Verdict: CLEAN.** `clista_hive_mind` contains exactly one document matching the Phase 1
prompt (`000ea11a-69fe-46a5-84df-858d6cad1883`, written `06:25:58.679Z`). No document with a
matching or near-identical prompt exists in the minutes following the seed write. Phases 2
and 3 created zero new hive-mind entries. Precedent contamination — recalls compounding
into new bad precedents — did not occur.

**But: Phases 2 and 3 left no audit trail at all.** `clista_audit_logs` contains the Phase 1
record (`74890807-cccb-4a9f-b4ac-d172b5ff506b`) and no other document in the post-seed
window. This is not merely "the recalls didn't write an audit entry with reduced detail" —
there is **no server-side record whatsoever** that Phases 2 and 3 executed. The recall path
returns before `commit_audit_record` is reached. Their existence, their prompts, and their
outcomes can only be reconstructed from the human-authored test plan, not from anything
Firestore holds. For a system whose sales pitch rests on auditability of AI decisions, a
code path that serves a decision to a requester while leaving zero trace that the decision
was served is itself a defect independent of the caching-correctness defects above — the
remedy below closes this gap by giving every recall its own logged event.

## Decision

**Context-hash cache keys.** Replace prompt-embedding similarity with an exact-match key
derived from the decision's *content*, not its phrasing. A single LLM call
(`extract_decision_context`, `context_key.py`) parses the prompt into a declared
`DecisionContext`: cosmetic fields (`entity`) are captured but excluded from the key;
decision-relevant fields (`metrics`, elapsed-time-as-cycle-position, `exogenous_events`) are
retained. The decision-relevant subset is serialized as canonical JSON
(`json.dumps(..., sort_keys=True, separators=(",", ":"))`) and hashed with SHA-256. Lookups
become an exact-equality Firestore filter on `context_hash`, not a similarity threshold.
Extraction failure (any exception, unparseable response, prompt that fits no known schema)
returns `None`, and `None` propagates to a full cache bypass: no read, no write, straight to
fresh compute. The cache can be wrong by being silent; it must never be wrong by being
confidently stale.

**Precedent-as-citation.** On a genuine hit, the cached *conclusion* is served, explicitly
tagged as precedent with metadata (`precedent_id`, `execution_id`, `context_hash`,
`age_days`, `original_decision_date`, a `stale` flag past a 90-day TTL). The rationale is
never transplanted: a single cheap re-grounding LLM call (`reground_rationale`) is given
only the precedent's conclusion and the *current* query, and asked to justify the conclusion
against the current facts. On re-grounding failure, a neutral fallback template is used
(`"Consistent with precedent {id} ({age} old) on materially identical decision context."`)
rather than any cached sentence. This is the case-law fix made mechanical: cite the holding,
regenerate the reasoning against the case in front of you.

*Known limitation (no-holding fallback).* When the cached decision is a JSON object with no
recognized conclusion field (`recommendation`/`decision`/`conclusion`), no citable holding
can be isolated, and the re-grounder is given the *full* cached decision as context —
deviating from the "conclusion only" input above — so the precedent's answer survives
re-grounding instead of being lost. Nothing from the cached blob is ever served verbatim
(the served body is the re-grounded text plus the neutral citation template), but on this
branch the anti-transplant guarantee rests on the re-grounding prompt's instructions rather
than on construction. Additionally, the served text carries a `"PRECEDENT RECALL: "` label
prefix beyond the plan's wording, so a citation is visually unmistakable in the output.

**RECALL/CRYSTALLIZATION provenance separation.** `crystallize_to_memory` writes
`entry_type: "CRYSTALLIZATION"` and refuses to write at all when `context_hash` is `None`.
A hit never re-crystallizes — it calls `record_recall_event`, which writes a distinct
`entry_type: "RECALL"` document referencing the original `precedent_id`. Provenance is never
flattened: a reader of the archive can always tell a document that represents original
compute from one that represents a citation of prior compute.

**RECALL event in the event stream.** The gateway emits event type `RECALL` (never
`CONSENSUS`) when serving a hit, with message `"Hive Mind RECALL — precedent matched on
decision context. Serving cited conclusion."`. This closes the audit-trail gap the
forensics pass found: every recall now produces both a distinct Mantle stream event and a
Firestore `RECALL` document, where before it produced neither.

## Elapsed-time canonicalization ruling

Elapsed time since validation is decision-relevant — it cannot simply be dropped from the
key, or Phase-2-style staleness would go undetected in the other direction (an old model
recalling a fresh one's answer). But raw elapsed time is exactly the kind of continuous
field where two nearly-identical values (2 months vs. 8 months) should not force a cache
miss when both fall on the same side of the decision boundary. The ruling: elapsed time
since validation IS decision-relevant but is canonicalized to cycle position —
`within_cycle` (elapsed < validation cycle length, default 12 months) vs. `overdue` (elapsed
≥ cycle length) — rather than hashed as a raw number. So 2 and 8 months hash identically
(Phase 3 hits), while 13 months would miss (crossing into `overdue`). Raw months are stored
in the extracted `DecisionContext` for audit visibility but are excluded from the hash
input itself.

## Consequences

- Extraction adds one LLM call per run (`extract_decision_context`) on top of the existing
  swarm-arm calls. This is accepted: it is far cheaper than serving a wrong recommendation
  with a false rationale, which is what the prior design did on both Phase 2 and Phase 3.
- Legacy `clista_hive_mind` documents (all 13 pre-fix documents, including the Phase 1 seed
  entry itself) have no `context_hash` field, so they can never match the new exact-key
  lookup. They are naturally quarantined from the new lookup path — no data migration is
  required or attempted; they simply age out of relevance.
- Embedding generation (`get_embedding`) and cosine-similarity matching are removed
  entirely. The semantic-similarity lookup path no longer exists in this system; it is
  replaced, not supplemented, by exact context-hash matching.
- Phrasing variance in how exogenous events get slugged (e.g. "fed rate cut 150bps" worded
  slightly differently across two otherwise-identical prompts) can only produce a hash
  mismatch, and a hash mismatch can only produce a false MISS (extra, wasted compute on a
  case that could have been recalled) — never a false HIT. The design fails open by
  construction: every failure mode identified above (extraction failure, hash mismatch,
  Firestore unavailability) routes to fresh compute, never to a stale or mismatched recall.

## Open issues (filed, out of scope here)

1. **Apex Arbitrator forced-1.0-confidence.** Every one of the 13 inspected
   `clista_hive_mind` entries stores top-level `confidence: 1.0`, regardless of the
   underlying per-arm confidence spread (Phase 1's arms showed 0.4, 0.95, 0.95). Forensics
   confirmed this is not incidental — the gateway passes a hardcoded literal into the
   archive write rather than a value derived from arm consensus, so stored confidence does
   not reflect arm-level confidence at all. Arbitrated resolutions should be labeled as
   arbitrated, with dissent preserved rather than collapsed to a fixed 1.0. This gets its
   own DR.
2. **Crystallization drops a requested numeric confidence field.** The `apex` arm's
   scratchpad explicitly states "Assign Confidence: Confidence is high (0.95)," but the
   final crystallized JSON omits this numeric field — the value is present in the reasoning
   trace and lost on the way to storage.
3. **`apex` naming is overloaded.** The `apex` arm participated in Phase 1 as a normal
   0.95-weight voter alongside `creative` and `creative_arm_02`, while the README describes
   the "Apex Arbitrator" as a deadlock-only tiebreaker role. The same name is used for two
   different behaviors in the codebase and in documentation.
4. **`creative_arm_02` weight-without-witness.** Task 1 forensics confirmed
   `creative_arm_02` carries `confidence_weight: 0.4` with an empty (`""`), not missing,
   scratchpad — it contributes voting weight with no recorded reasoning trace at all. This
   arm is injected by `gateway.py`'s `inject_regrow_state` demo scaffolding with a
   hardcoded decision and no scratchpad, unlike the other two arms in the same execution,
   which both show substantial, distinct chain-of-thought traces.

## Post-verification addendum (2026-07-11)

The verification gate was re-run against the deployed service (Cloud Run revision
`clista-octopus-swarm-00038`, 2026-07-11 ~08:09–08:17 UTC) with the remedy in place. The
matrix from the plan's Global Constraints **passed**:

- **Phase 1** fresh-computed and archived a keyed precedent
  (`ff48b95a-2be9-466d-bc95-fe25b71860bf`).
- **Phase 2** (recession variant) was a cache **MISS**: fresh compute with nonzero budget
  spend (75.0 remaining of 100), and the recommendation flipped to "Trigger an immediate,
  out-of-cycle model revalidation" — the answer the prior design failed to produce.
- **Phase 3** (webbank / 2-months variant) was a **RECALL** hit: it served the cited
  conclusion with rationale re-grounded in the current query's facts ("validated 2 months
  ago"), full precedent metadata (precedent id, execution id, context hash, age, original
  decision date, stale flag), zero swarm spend (budget 100.0), and no false claims — no
  "8 months," no "4 months."

Full event streams are committed as `docs/verification/phase{1,2,3}-events-2026-07-11.json`.

Firestore end-state confirms provenance separation live: two `CRYSTALLIZATION` entries
(Phase 1 hash `40a19680…`, Phase 2 hash `56d04763…`), two `RECALL` entries referencing
`ff48b95a`, and zero re-archives.

The gate itself surfaced four additional live defects, each fixed with a regression test
before the matrix passed:

1. OpenAI strict structured-output rejected the extraction schema's dict-typed `metrics`
   field, so extraction always failed open in production (every run bypassed the cache) —
   fixed with a strict-compatible wire model (`814d0e8`).
2. Default-temperature extraction was nondeterministic: one trial dropped the AUC metric,
   producing a false miss — fixed with temperature 0 and a fixed seed (`74ca1b5`).
3. The gateway archived its own no-output fallback sentinel ("Apex Arbitration reached
   without specific output.") as a keyed precedent when the arbitration arm transiently
   failed — fixed so non-decisions are never archived (`0a6601b`). The legacy store already
   contained the same class of garbage ("Consensus reached without specific output.", doc
   `3250d5d6`) from before this work.
4. The first-paragraph conclusion heuristic served entire JSON-blob decisions verbatim on
   recall — including the original justification's "8 months"/"4 months" facts, i.e. the
   rationale-transplant defect resurfacing through a different seam — fixed with JSON-aware
   holding extraction (`85c9350`).

One quarantine action: hive-mind doc `9097a9a4` (the sentinel precedent written by defect 3
during the gate run itself) was verified and deleted.

Throughout the gate, fail-open behaved as designed: every extraction failure produced a
fresh compute, never a stale recall.
