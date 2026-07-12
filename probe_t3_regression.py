"""
T3 REGRESSION PROBE — the three-phase Hive Mind cache-integrity gate, re-runnable.

Re-runs the DR-hive-mind-cache-integrity verification matrix against a live
deployment (mutual-reliance-proposal.md §6 T3; original gate passed 2026-07-11
against revision 00038 — this script exists so the matrix can be re-checked
after ANY later deploy). Each regression run uses its own scenario values so
prior runs' archived precedents cannot satisfy Phase 1: the phase-1 prompt must
FRESH-compute and archive, or the whole matrix is measuring the wrong thing.

Pass matrix (from the DR / proposal):
  Phase 1 (seed)            fresh compute (SPAWN..FINAL_OUTPUT), archived precedent
  Phase 2 (material change) cache MISS -> fresh compute, recommendation FLIPS
  Phase 3 (cosmetic change) RECALL hit: cited conclusion, precedent metadata,
                            re-grounded rationale, zero swarm spend
  All phases                every run (recalls included) leaves an audit record —
                            silence is the defect class this gate exists to catch.

Usage:
  python3 probe_t3_regression.py --url wss://<service>/ws/octopus --token <token> \
      [--out docs/verification/t3-regression-<date>]

The script only drives the public gateway websocket and writes local JSON
capture files; Firestore end-state checks are a separate read-only step.
"""

import argparse
import asyncio
import json
import pathlib
import sys
from datetime import datetime, timezone

import websockets

# Scenario values for THIS regression run — deliberately distinct from the
# 2026-07-11 gate (PSI 0.08 / AUC 0.82 / 8 months) so phase 1 cannot recall
# that run's precedent. PSI 0.06 is clearly benign (no drift signal), so the
# expected phase-1 answer is "annual cycle sufficient" and phase 2's recession
# variant has a real recommendation to flip.
BASE = dict(psi="0.06", auc="0.84", months="7", bank="A regional bank's", entity_note="")

PHASE1 = (
    f"{BASE['bank']} PD (probability of default) model for small-business\n"
    f"lending shows a population stability index (PSI) of {BASE['psi']} on all input\n"
    f"features over the last quarter. Model accuracy (AUC) at last validation\n"
    f"was {BASE['auc']}. The model was validated {BASE['months']} months ago. Should the model risk\n"
    "team trigger an out-of-cycle revalidation, or is annual-cycle\n"
    "revalidation sufficient? Provide a recommendation with confidence."
)

PHASE2 = (
    PHASE1
    + "\nNote: 3 months ago the Fed cut rates 150bps and the region entered a"
    "\nrecession; realized default rates in the portfolio have doubled while the"
    "\napplicant feature mix is unchanged."
)

# Cosmetic only: entity renamed, elapsed months moved WITHIN the same annual
# cycle bucket (7 -> 4 months, both "within_cycle"), everything decision-
# relevant unchanged -> same context hash as phase 1.
PHASE3 = PHASE1.replace("A regional bank's", "Nordbank's").replace(
    f"validated {BASE['months']} months ago", "validated 4 months ago"
)


async def run_phase(url: str, token: str, name: str, prompt: str, timeout: float):
    events = []
    uri = f"{url}?token={token}"
    async with websockets.connect(uri, max_size=None, open_timeout=90) as ws:
        await ws.send(json.dumps({"prompt": prompt}))
        while True:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
            except asyncio.TimeoutError:
                print(f"  ! {name}: timed out waiting for events", file=sys.stderr)
                break
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                event = {"type": "RAW", "message": raw}
            events.append(event)
            etype = event.get("type")
            print(f"  [{name}] {etype}: {str(event.get('message', ''))[:100]}")
            if etype == "FINAL_OUTPUT":
                break
    return events


def summarize(name: str, events: list) -> dict:
    types = [e.get("type") for e in events]
    final = next((e for e in events if e.get("type") == "FINAL_OUTPUT"), {})
    return {
        "phase": name,
        "event_types": types,
        "spawned_arms": types.count("SPAWN"),
        "recall": "RECALL" in types,
        "final_budget": final.get("budget"),
        "final_message_head": str(final.get("message", ""))[:300],
    }


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True, help="wss://<service>/ws/octopus")
    parser.add_argument("--token", required=True)
    parser.add_argument("--out", default=None)
    parser.add_argument("--timeout", type=float, default=300.0, help="per-event timeout (s)")
    args = parser.parse_args()

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_dir = pathlib.Path(args.out or f"docs/verification/t3-regression-{stamp}")
    out_dir.mkdir(parents=True, exist_ok=True)

    phases = [("phase1", PHASE1), ("phase2", PHASE2), ("phase3", PHASE3)]
    summaries = []
    for name, prompt in phases:
        print(f"\n=== {name} ===")
        events = await run_phase(args.url, args.token, name, prompt, args.timeout)
        (out_dir / f"{name}-events.json").write_text(
            json.dumps({"phase": name, "prompt": prompt, "events": events}, indent=2) + "\n"
        )
        summaries.append(summarize(name, events))

    (out_dir / "summary.json").write_text(json.dumps(summaries, indent=2) + "\n")
    print("\n=== matrix ===")
    for s in summaries:
        print(json.dumps(s, indent=1))
    print(f"\ncaptures: {out_dir}/")


if __name__ == "__main__":
    asyncio.run(main())
