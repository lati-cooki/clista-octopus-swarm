# TODO

Open issues filed out of scope during the hive-mind cache-integrity work. See
`DR-hive-mind-cache-integrity.md`, section "Open issues (filed, out of scope here)"
for full detail.

1. Apex Arbitrator forces `confidence: 1.0` on every archived entry regardless of
   actual arm-level consensus — needs its own DR. See DR-hive-mind-cache-integrity.md #1.
2. Crystallization drops the numeric confidence value present in the `apex` arm's
   scratchpad reasoning trace. See DR-hive-mind-cache-integrity.md #2.
3. `apex` naming is overloaded — used both for a normal Phase 1 voting arm and for the
   deadlock-only "Apex Arbitrator" tiebreaker role. See DR-hive-mind-cache-integrity.md #3.
4. `creative_arm_02` weight-without-witness: gateway.py's `inject_regrow_state` demo
   scaffolding injects this arm with voting weight but no scratchpad reasoning trace.
   See DR-hive-mind-cache-integrity.md #4.
