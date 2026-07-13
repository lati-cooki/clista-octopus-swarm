# ISSUE: Swarm → ThreadHub delta (filed, not built)

**Filed:** 2026-07-12 (Phase 5, Wave 4 / Slice 8)
**Status:** OPEN — Phase 6 work
**Inherits from:** `DR-phase5-topology` (ADOPTED 2026-07-12, sealed on
ThreadHub thread `dr-phase5-topology`, head
`sha256:a406d40ae108df11160bbee04c9e927432761c90245da74bf7ae9e2c9060706a`),
in the `lati-cooki/clista` repo at
`docs/decision-records/DR-phase5-topology.md`; and this repo's
`DR-hive-mind-cache-integrity.md` (Accepted 2026-07-10), whose Open Issues
#1–#4 this issue cross-references rather than duplicates.
**Code citations:** every `gateway.py` line number below was verified against
this repo's HEAD (`0ee49f0`) at filing time. Where the Phase 5 plan's
original numbers still hold, they are cited as-is; any drift from the plan's
verified state is disclosed inline.

---

## 1. Why filed, not built

Phase 5 deliberately fenced the swarm to documentation: DR-phase5-topology
rule 3.4 says the swarm rows of the event ontology are *mapping-only* — the
seal committed the vocabulary, not the implementation — and the DR's
"Applies to" line binds `clista-octopus-swarm` "mapping only until Phase 6."
That fence is why this document exists as an issue and not a diff. It is the
complete statement of what the swarm owes ThreadHub, so that Phase 6 starts
from a citable list instead of a re-derivation, and so that nothing in it
can later be discovered as an unfiled obligation. Nothing in this file
changes swarm behavior; nothing in it may be read as a promise that any
specific slice of Phase 6 is already underway.

## 2. Event mapping owed

The binding mapping is DR-phase5-topology Decision 3. The swarm-relevant
rows, reproduced exactly:

| Emitter event (family-qualified) | Protocol vocabulary | Notes |
|---|---|---|
| swarm `firestore:CRYSTALLIZATION` | `ClaimCreated` + `CrossThreadEvidence` | Original compute archived as precedent: the conclusion as a claim, its cross-thread reach as evidence import. Mapping only; build in Phase 6. |
| swarm `firestore:RECALL` | `PrecedentReference` | Citation of prior compute — the archived witness of a reuse. Mapping only; build in Phase 6. |
| swarm `stream:RECALL` | `PrecedentReference` | The gateway's Mantle stream event (emitted on a hit, never `CONSENSUS`) is the at-action-time witness of the same reuse the `firestore:RECALL` document archives — one recall act, two swarm-side traces, exactly one `PrecedentReference` emission (rule 3.5). Mapping only; build in Phase 6. |
| swarm arbitration | labeled arbitrated: `ClaimCreated` carrying the arbitrated outcome + `PositionTaken` per arm + `MinorityReportFiled` for preserved dissent | Arbitrated resolutions are labeled arbitrated with dissent preserved, never laundered as confidence 1.0 (silent-action DR rule 2). The outcome itself travels as a `ClaimCreated` labeled arbitrated. Today's Arbitrator does the opposite (`gateway.py:477`); its own DR is still owed — this row records the mapping, not a fix. Build in Phase 6. |

(Rows reproduced verbatim from Decision 3, except that the DR's pre-seal
amendment provenance parentheticals — notes on that record's own editing
history, e.g. "*Note tightened by pre-seal amendment...*" on the
`stream:RECALL` row and "*Outcome carrier added by pre-seal amendment...*"
on the arbitration row — are omitted here; the sealed DR is the authority
for its own amendment history.)

What binds, restated so Phase 6 cannot miss it:

- **The table is BINDING** (rule 3.2): an emitter event family not in the
  table does not flow into the hub until a mapping row is added *by
  amendment to DR-phase5-topology*. Vocabulary changes go through that DR;
  this issue cannot grow the mapping.
- **Names are family-qualified** (rule 3.3): `RECALL` exists in two swarm
  families — the Mantle event *stream* and the Firestore *entry_type*. In
  every cross-system reference the name is `stream:RECALL` or
  `firestore:RECALL`; an unqualified `RECALL` in a cross-system context is
  malformed. This resolves the name collision once, at the sealed DR, not
  per-adapter.
- **One recall act, one emission** (rule 3.5): `stream:RECALL` and
  `firestore:RECALL` are two swarm-side traces of the *same act* and MUST
  dedupe to exactly ONE `PrecedentReference`. Emitting two for one recall is
  malformed. The Phase 6 emission code owes this dedup by construction, not
  by convention.
- The `RECALL`/`CRYSTALLIZATION` provenance separation the mapping rides on
  is this repo's own work — see `DR-hive-mind-cache-integrity.md`,
  "RECALL/CRYSTALLIZATION provenance separation" and "RECALL event in the
  event stream." The mapping does not re-decide that separation; it gives it
  a protocol-vocabulary landing.

## 3. Arm custody

Arm identity today is asserted strings. Verified at HEAD:

- `gateway.py:335-336` — `logic_arm = ArmState(arm_id="logic", ...)` and
  `creative_arm = ArmState(arm_id="creative", ...)`: the arm ids are string
  literals in constructor calls, bound to nothing.
- `gateway.py:416` — `arbitration_arm = ArmState(arm_id="apex", ...)`: same
  pattern for the Arbitrator.

Nothing signs as these arms; nothing prevents any code path from wearing any
arm's name. This is exactly the T1 run's first `knownGaps` entry ("writers
as gate-registered strings") reproduced in the swarm, and DR-phase5-topology
Decision 5 is the doctrine that closes it. The Phase 6 options, per that
decision:

- **Non-custodial keys per arm** (the T1 harness pattern, rule 5.1):
  per-run ed25519 keys signing each event at reasoning time, submitted as
  `threadhub.record.v0` envelopes — reference client
  `packages/threadhub/adapters/octopus.js` in the clista repo. Arms are
  processes that can sign at reasoning time, so this is the natural fit.
- **Custodial identities per arm** (the studio pattern, rule 5.2): the hub
  mints and holds a distinct identity per arm. Permitted, but rule 5.3
  applies — custody is disclosed and downgrades the independence claim —
  and rule 5.4's append-only upgrade path is the exit.

Either way, rule 5.5 holds absolutely: no key material in this repo or any
doc, ever. Choosing between the options is Phase 6 work; what is *owed* is
that arm_id stops being an asserted string before any swarm event flows
into the hub.

**The `creative_arm_02` smell.** Verified at HEAD, `gateway.py:365-373`
(`inject_regrow_state`, demo scaffolding): line 368 hardcodes
`arm.arm_id = "creative_arm_02"`, line 369 hardcodes
`arm.moltbook.confidence_weight = 0.4`, line 370 hardcodes its decision
("Strict enforcement required. Security > Speed."), and line 371 injects a
boilerplate scratchpad sentence. Disclosure of drift from the forensic
record: `DR-hive-mind-cache-integrity.md` Open Issue #4 found this arm with
an *empty* (`""`) scratchpad in live Firestore; at current HEAD the
scratchpad is a fixed template string rather than empty. The smell is
unchanged in substance: the arm contributes voting weight with no reasoning
trace behind it — a templated sentence is not a witness. Voting weight with
no witnessed reasoning is unwitnessed influence on an output, the exact
class the silent-action DR (clista repo,
`docs/decision-records/DR-2026-07-12-silent-action-prohibition.md`) exists
to prohibit. Phase 6 either gives this arm a real reasoning path that can be
witnessed, or removes its weight; carrying scaffolding weight into a
hub-connected swarm is not an option.

## 4. CrossThreadEvidence linkage

When swarm consensus feeds a parent thread (a decision thread that consumed
the swarm's recommendation), it crosses via `CrossThreadEvidence` like any
other decision output. The pattern is fixed by the claim-citation DR
(clista repo,
`docs/decision-records/DR-2026-07-12-claim-citation-events.md`), rule 4: a
report or output consumed by *another* thread crosses via
`CrossThreadEvidence`; it never registers into its own thread's evidence —
self-feeding is the circular self-witnessing pattern that DR's Option A
rejection names as laundering. For the swarm this means: the consensus
thread's output enters the parent thread as imported evidence with declared
derivation, and the `firestore:CRYSTALLIZATION` mapping row already carries
the `CrossThreadEvidence` half for exactly this reach. Phase 6 owes the
emission; the shape is already decided.

## 5. The Arbitrator DR still owed

Verified at HEAD:

- `gateway.py:477` — the literal `1.0` passed as `network_confidence` into
  `crystallize_to_memory` (signature at `moltbook_archive.py:43-50`). The
  archived confidence is a hardcoded constant, not a value derived from arm
  consensus. (Supporting: `gateway.py:455` and `gateway.py:497` also
  hardcode `"coherence": 1.0` into the audit metadata and the final
  websocket payload.)
- `gateway.py:412-448` — the Apex Arbitrator branch. On deadlock it spawns
  `apex` (line 416), snapshots the deadlocked arms into `arms_data` (lines
  420-425, so the dissenting scratchpads do reach the audit record), then
  replaces the entire live arm set with the arbitrator alone (line 427:
  `orchestrator.arms = [arbitration_arm]`) and forces consensus (line 433:
  "GAVEL DROP. Forcing consensus."). The arbitrated outcome then flows to
  the archive carrying the hardcoded `1.0` — dissent is preserved in the
  audit snapshot but collapsed everywhere the decision travels as
  precedent.

The silent-action DR, rule 2, names arbitration a covered action class:
"Arbitrated resolutions are labeled arbitrated, with dissent preserved —
never laundered as unanimous or confidence 1.0." Today's gateway does the
opposite on the confidence axis. This repo's own
`DR-hive-mind-cache-integrity.md` Open Issue #1 already files the defect
(all 13 inspected hive-mind entries stored `confidence: 1.0` regardless of
per-arm spread) and states "This gets its own DR." DR-phase5-topology rule
3.4 fences the same residual out of the topology seal as "a disclosed
nonconformance owed its own DR."

This issue restates the obligation with its ordering constraint: **the
Arbitrator labeling fix gets its own decision record, in this repo, before
any hub wiring of the arbitration mapping row.** The Decision 3 arbitration
row is a vocabulary commitment only; wiring it while the gateway still
launders arbitrated outcomes as 1.0 would hub-accumulate exactly the
laundered records the row exists to prevent.

## 6. Phase 6 scope statement

**In scope for Phase 6:**

1. **Emission code for the four mapping rows** in section 2 — including the
   rule 3.5 dedup (one recall act → one `PrecedentReference`) and the
   family-qualified naming of rule 3.3 at every cross-system boundary.
2. **Arm identity** — replace asserted arm_id strings
   (`gateway.py:335-336,416`) with one of the Decision 5 regimes
   (non-custodial per-arm keys, or custodial identities with disclosed
   downgrade); resolve the `creative_arm_02` weight-without-witness
   scaffolding (section 3; swarm DR Open Issue #4).
3. **CrossThreadEvidence linkage** — swarm consensus into parent threads
   per section 4.
4. **The Arbitrator DR and fix** — its own decision record in this repo,
   then the labeling fix (`ClaimCreated` labeled arbitrated +
   `PositionTaken` + `MinorityReportFiled`; no hardcoded `1.0`), *before*
   the arbitration row is wired to the hub (section 5; swarm DR Open Issue
   #1).
5. **Moltbook migration** — the Moltbook archive layer
   (`moltbook_archive.py`, Firestore `clista_hive_mind` and
   `clista_audit_logs`) currently lives entirely outside ThreadHub. Under
   topology rules 1.2 and 2.2 it becomes a declared projection with the hub
   as the accumulation layer; Phase 6 owes that migration, including the
   declared-provenance fields on every projected document.

**Out of scope — for Phase 6 and for this issue:**

- Anything that touches Phase 5's sealed definitions — the Decision 3
  mapping table, the citation shape (rule 1.3), the custody doctrine, the
  anchors doctrine — except by amendment to `DR-phase5-topology`. This
  issue can be superseded; the sealed DR can only be amended.
- Re-deciding anything `DR-hive-mind-cache-integrity.md` already decided
  (context-hash keys, precedent-as-citation, provenance separation). Its
  Open Issues #2 (crystallization drops the requested numeric confidence)
  and #3 (`apex` naming overload) remain filed there; the Arbitrator DR of
  section 5 is the natural place to sweep both in, but that is a note, not
  a commitment.

Nothing here is built. This file is the delta, stated once, so Phase 6 can
be checked against it line by line.
