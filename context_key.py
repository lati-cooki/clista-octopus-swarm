"""
BLASTEMA PROTOCOL: DECISION CONTEXT KEY

Extracts the decision-relevant facts from a raw prompt via an LLM structured-output
call, canonicalizes them, and produces a deterministic SHA-256 cache key.

Design intent (see docs/plans/hive-mind-cache-integrity-plan.md, "Architecture
decisions (binding)"): the Hive Mind cache must key on decision-relevant substance,
not prompt-embedding similarity. Cosmetic fields (entity name) and raw elapsed
months are deliberately excluded from the hash — elapsed time only enters the hash
as a coarse cycle-position bucket ("within_cycle" / "overdue" / "unknown").

This module has NO Firestore or FastAPI imports. It is pure extraction + hashing.
Extraction failure (any exception, missing API key, unparseable/refused response)
returns None so callers can fail open to a fresh compute rather than serve (or
poison) a cache entry keyed on a bad extraction.
"""

import hashlib
import json
import logging
import os
from typing import Literal, Optional

import openai
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class DecisionContext(BaseModel):
    """Decision-relevant facts extracted from a prompt for a given schema.

    `entity` is cosmetic (excluded from the hash). `months_since_validation` is
    kept for audit/display but is canonicalized to a cycle-position bucket before
    hashing — see `context_hash`.
    """

    schema_id: Literal["mrm_revalidation_v1"]
    entity: Optional[str] = Field(
        default=None,
        description="Cosmetic identifier (e.g. bank/model name). Excluded from the hash.",
    )
    metrics: dict[str, float] = Field(
        default_factory=dict,
        description="Normalized lowercase metric names to values (e.g. {'psi': 0.08, 'auc': 0.82}).",
    )
    months_since_validation: Optional[float] = Field(
        default=None,
        description="Raw elapsed months since last validation, kept for audit only.",
    )
    validation_cycle_months: float = Field(
        default=12.0,
        description="Length of the validation cycle in months.",
    )
    exogenous_events: list[str] = Field(
        default_factory=list,
        description=(
            "Canonicalized lowercase slugs of stated exogenous events / outcome "
            "facts (rate changes, recessions, realized default-rate changes, etc.)."
        ),
    )


class ExtractedMetric(BaseModel):
    """One metric name/value pair on the extraction wire model."""

    name: str
    value: float


class DecisionContextExtraction(BaseModel):
    """WIRE model for the OpenAI strict structured-output call ONLY.

    Identical to DecisionContext except `metrics` is a list of name/value pairs:
    OpenAI's strict structured-output mode rejects free-form objects
    (`dict[str, float]` compiles to typed additionalProperties, which the API
    refuses with a 400 "'required' is required to be supplied ..."). Converted
    to DecisionContext immediately after parsing — never used downstream.
    """

    schema_id: Literal["mrm_revalidation_v1"]
    entity: Optional[str] = None
    metrics: list[ExtractedMetric] = Field(default_factory=list)
    months_since_validation: Optional[float] = None
    validation_cycle_months: float = 12.0
    exogenous_events: list[str] = Field(default_factory=list)

    def to_decision_context(self) -> DecisionContext:
        return DecisionContext(
            schema_id=self.schema_id,
            entity=self.entity,
            # Normalize metric names here for cleanliness (context_hash also
            # normalizes defensively). On duplicates after normalization, last wins.
            metrics={" ".join(m.name.lower().split()): m.value for m in self.metrics},
            months_since_validation=self.months_since_validation,
            validation_cycle_months=self.validation_cycle_months,
            exogenous_events=self.exogenous_events,
        )


_EXTRACTION_SYSTEM_PROMPT = """
You extract decision-relevant facts from a model-risk-management (MRM) revalidation
prompt into a strict schema. Follow these rules exactly:

- `schema_id` is always "mrm_revalidation_v1" for this extraction task.
- `entity` (e.g. bank or model name) is COSMETIC — extract it if present, but it has
  no bearing on the decision.
- `metrics`: extract every named model-performance metric and its numeric value
  (e.g. PSI, AUC, KS, Gini) as name/value pairs, with lowercase metric names.
- `months_since_validation`: the elapsed time in months since the model was last
  validated, if stated.
- `validation_cycle_months`: the length of the required validation cycle in months,
  if stated; otherwise leave it at the default of 12.0.
- `exogenous_events`: capture EVERY stated exogenous event or outcome fact that
  could be decision-relevant — rate changes, recessions, realized default-rate
  changes, macro shocks, portfolio composition shifts, etc. Represent each as a
  short canonical lowercase slug (e.g. "fed rate cut 150bps", "regional
  recession", "default rates doubled"). If none are stated, return an empty list.

Do not include any commentary — only the structured fields.
"""

_MODEL = "gpt-4o"


def extract_decision_context(prompt: str) -> Optional[DecisionContext]:
    """Extract a DecisionContext from a raw prompt via one OpenAI structured-output call.

    Returns None on ANY failure: OpenAI client construction, network/API exception,
    missing/invalid API key, empty response, or an unparseable/refused completion.
    Never raises.
    """
    try:
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.beta.chat.completions.parse(
            model=_MODEL,
            messages=[
                {"role": "system", "content": _EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            response_format=DecisionContextExtraction,
        )
        choices = response.choices
        if not choices:
            return None
        parsed = choices[0].message.parsed
        if parsed is None:
            return None
        return parsed.to_decision_context()
    except Exception as e:
        logger.warning(
            "Context extraction failed (fail-open to fresh compute): %s: %s",
            type(e).__name__,
            e,
        )
        return None


def _cycle_position(months_since_validation: Optional[float], validation_cycle_months: float) -> str:
    if months_since_validation is None:
        return "unknown"
    if months_since_validation >= validation_cycle_months:
        return "overdue"
    return "within_cycle"


def _canonicalize_events(events: list[str]) -> list[str]:
    normalized = {" ".join(event.lower().split()) for event in events}
    return sorted(normalized)


def context_hash(ctx: DecisionContext) -> str:
    """SHA-256 hex digest of the canonical JSON of the decision-relevant fields.

    Included: schema_id, metrics (keys defensively normalized — lowercased,
    whitespace-stripped/collapsed — even though extraction requests lowercase keys;
    values rounded to 6 decimal places), cycle_position (derived from
    months_since_validation vs validation_cycle_months), exogenous_events
    (sorted, lowercased, whitespace-collapsed).

    Excluded: entity (cosmetic), raw months_since_validation, validation_cycle_months.
    """
    payload = {
        "schema_id": ctx.schema_id,
        "metrics": {
            " ".join(k.lower().split()): round(float(v), 6) for k, v in ctx.metrics.items()
        },
        "cycle_position": _cycle_position(ctx.months_since_validation, ctx.validation_cycle_months),
        "exogenous_events": _canonicalize_events(ctx.exogenous_events),
    }
    canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
