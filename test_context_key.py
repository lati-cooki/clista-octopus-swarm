"""
Tests for context_key.py — decision-context extraction, canonicalization, and
SHA-256 hashing.

All OpenAI calls are mocked. No network I/O occurs in this test file.
"""

import re
from unittest.mock import Mock, patch

from context_key import (
    DecisionContext,
    DecisionContextExtraction,
    ExtractedMetric,
    context_hash,
    extract_decision_context,
)


def make_ctx(**overrides) -> DecisionContext:
    defaults = dict(
        schema_id="mrm_revalidation_v1",
        entity="Regional Bank Co",
        metrics={"psi": 0.08, "auc": 0.82},
        months_since_validation=8.0,
        validation_cycle_months=12.0,
        exogenous_events=[],
    )
    defaults.update(overrides)
    return DecisionContext(**defaults)


def make_wire_ctx(**overrides) -> DecisionContextExtraction:
    """Build the wire-model object the OpenAI parse call actually returns."""
    defaults = dict(
        schema_id="mrm_revalidation_v1",
        entity="Regional Bank Co",
        metrics=[
            ExtractedMetric(name="psi", value=0.08),
            ExtractedMetric(name="auc", value=0.82),
        ],
        months_since_validation=8.0,
        validation_cycle_months=12.0,
        exogenous_events=[],
    )
    defaults.update(overrides)
    return DecisionContextExtraction(**defaults)


def mock_parse_client(parsed) -> Mock:
    """Mock OpenAI client whose parse call returns a response with one parsed message."""
    mock_message = Mock()
    mock_message.parsed = parsed
    mock_choice = Mock()
    mock_choice.message = mock_message
    mock_response = Mock()
    mock_response.choices = [mock_choice]
    mock_client = Mock()
    mock_client.beta.chat.completions.parse.return_value = mock_response
    return mock_client


class TestContextHashCanonicalization:
    def test_different_entity_names_same_hash(self):
        ctx_a = make_ctx(entity="Regional Bank Co")
        ctx_b = make_ctx(entity="Webbank")
        assert context_hash(ctx_a) == context_hash(ctx_b)

    def test_within_cycle_months_2_and_8_same_hash(self):
        ctx_a = make_ctx(months_since_validation=2.0, validation_cycle_months=12.0)
        ctx_b = make_ctx(months_since_validation=8.0, validation_cycle_months=12.0)
        assert context_hash(ctx_a) == context_hash(ctx_b)

    def test_overdue_13_months_differs_from_within_cycle_8_months(self):
        ctx_within = make_ctx(months_since_validation=8.0, validation_cycle_months=12.0)
        ctx_overdue = make_ctx(months_since_validation=13.0, validation_cycle_months=12.0)
        assert context_hash(ctx_within) != context_hash(ctx_overdue)

    def test_nonempty_exogenous_events_differs_from_empty(self):
        ctx_empty = make_ctx(exogenous_events=[])
        ctx_events = make_ctx(
            exogenous_events=[
                "fed rate cut 150bps",
                "regional recession",
                "default rates doubled",
            ]
        )
        assert context_hash(ctx_empty) != context_hash(ctx_events)

    def test_exogenous_events_order_independent(self):
        ctx_a = make_ctx(
            exogenous_events=[
                "fed rate cut 150bps",
                "regional recession",
                "default rates doubled",
            ]
        )
        ctx_b = make_ctx(
            exogenous_events=[
                "default rates doubled",
                "fed rate cut 150bps",
                "regional recession",
            ]
        )
        assert context_hash(ctx_a) == context_hash(ctx_b)

    def test_exogenous_events_casing_and_whitespace_normalized(self):
        # Casing, leading/trailing whitespace, AND internal whitespace collapse
        # must all normalize to the same hash across multi-event lists.
        ctx_a = make_ctx(exogenous_events=["Fed Rate Cut 150bps", "Regional Recession"])
        ctx_b = make_ctx(exogenous_events=["  fed rate cut 150bps  ", "regional   recession"])
        ctx_canonical = make_ctx(exogenous_events=["fed rate cut 150bps", "regional recession"])
        assert context_hash(ctx_a) == context_hash(ctx_canonical)
        assert context_hash(ctx_b) == context_hash(ctx_canonical)
        assert context_hash(ctx_a) == context_hash(ctx_b)

    def test_different_metric_values_differ(self):
        ctx_a = make_ctx(metrics={"psi": 0.08, "auc": 0.82})
        ctx_b = make_ctx(metrics={"psi": 0.09, "auc": 0.82})
        assert context_hash(ctx_a) != context_hash(ctx_b)

    def test_metric_key_casing_normalized(self):
        # Defensive: even though extraction requests lowercase metric names, an
        # LLM emitting "PSI" must not produce a different hash than "psi".
        ctx_upper = make_ctx(metrics={"PSI": 0.08, "AUC": 0.82})
        ctx_lower = make_ctx(metrics={"psi": 0.08, "auc": 0.82})
        assert context_hash(ctx_upper) == context_hash(ctx_lower)

    def test_metric_key_whitespace_normalized(self):
        ctx_padded = make_ctx(metrics={" psi ": 0.08, "auc": 0.82})
        ctx_clean = make_ctx(metrics={"psi": 0.08, "auc": 0.82})
        assert context_hash(ctx_padded) == context_hash(ctx_clean)

    def test_months_equal_to_cycle_buckets_as_overdue(self):
        # Boundary: elapsed == cycle length is "overdue" (>=), not within_cycle.
        ctx_boundary = make_ctx(months_since_validation=12.0, validation_cycle_months=12.0)
        ctx_within = make_ctx(months_since_validation=8.0, validation_cycle_months=12.0)
        ctx_overdue = make_ctx(months_since_validation=13.0, validation_cycle_months=12.0)
        assert context_hash(ctx_boundary) != context_hash(ctx_within)
        assert context_hash(ctx_boundary) == context_hash(ctx_overdue)

    def test_hash_is_64_char_lowercase_hex(self):
        h = context_hash(make_ctx())
        assert len(h) == 64
        assert re.fullmatch(r"[0-9a-f]{64}", h)

    def test_hash_is_deterministic_across_calls(self):
        ctx = make_ctx()
        h1 = context_hash(ctx)
        h2 = context_hash(ctx)
        assert h1 == h2

    def test_unknown_cycle_position_when_months_since_validation_none(self):
        ctx_unknown = make_ctx(months_since_validation=None)
        ctx_within = make_ctx(months_since_validation=8.0, validation_cycle_months=12.0)
        assert context_hash(ctx_unknown) != context_hash(ctx_within)


class TestExtractDecisionContext:
    def test_returns_parsed_context_on_success(self):
        # The mock returns the WIRE model (matching real API behavior);
        # extract_decision_context must convert it to a DecisionContext.
        mock_client = mock_parse_client(make_wire_ctx())

        with patch("context_key.openai.OpenAI", return_value=mock_client):
            result = extract_decision_context("Some MRM prompt about revalidation.")

        assert result == make_ctx()
        # The strict-compatible wire model — not DecisionContext — must be sent
        # as response_format (DecisionContext's dict field is rejected by the API).
        call_kwargs = mock_client.beta.chat.completions.parse.call_args.kwargs
        assert call_kwargs["response_format"] is DecisionContextExtraction

    def test_extraction_wire_model_is_strict_schema_compatible(self):
        # Encodes the exact OpenAI strict structured-output constraint that bit
        # us in production: every object node must have additionalProperties
        # False and a required array covering every property. A free-form
        # dict[str, float] field violates this — the API rejects it with a 400
        # (to_strict_json_schema itself does NOT raise; the rejection is
        # server-side, hence asserting the schema SHAPE here).
        from openai.lib._pydantic import to_strict_json_schema

        schema = to_strict_json_schema(DecisionContextExtraction)

        def walk(node):
            if isinstance(node, dict):
                if node.get("type") == "object":
                    assert node.get("additionalProperties") is False, node
                    props = node.get("properties", {})
                    assert sorted(node.get("required", [])) == sorted(props.keys()), node
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)

        walk(schema)

    def test_extraction_converts_wire_metrics_to_dict(self):
        wire = make_wire_ctx(
            metrics=[
                ExtractedMetric(name="PSI", value=0.08),
                ExtractedMetric(name="auc", value=0.82),
            ]
        )
        mock_client = mock_parse_client(wire)

        with patch("context_key.openai.OpenAI", return_value=mock_client):
            result = extract_decision_context("Some MRM prompt about revalidation.")

        assert result is not None
        assert result.metrics == {"psi": 0.08, "auc": 0.82}

    def test_returns_none_when_openai_call_raises(self):
        mock_client = Mock()
        mock_client.beta.chat.completions.parse.side_effect = RuntimeError("network down")

        with patch("context_key.openai.OpenAI", return_value=mock_client):
            result = extract_decision_context("Some MRM prompt about revalidation.")

        assert result is None

    def test_returns_none_when_response_unparseable(self):
        mock_message = Mock()
        mock_message.parsed = None
        mock_choice = Mock()
        mock_choice.message = mock_message
        mock_response = Mock()
        mock_response.choices = [mock_choice]

        mock_client = Mock()
        mock_client.beta.chat.completions.parse.return_value = mock_response

        with patch("context_key.openai.OpenAI", return_value=mock_client):
            result = extract_decision_context("Some MRM prompt about revalidation.")

        assert result is None

    def test_returns_none_on_empty_choices(self):
        mock_response = Mock()
        mock_response.choices = []

        mock_client = Mock()
        mock_client.beta.chat.completions.parse.return_value = mock_response

        with patch("context_key.openai.OpenAI", return_value=mock_client):
            result = extract_decision_context("Some MRM prompt about revalidation.")

        assert result is None

    def test_returns_none_when_openai_client_init_raises(self):
        # e.g. missing API key configured to raise on client construction
        with patch("context_key.openai.OpenAI", side_effect=RuntimeError("no api key")):
            result = extract_decision_context("Some MRM prompt about revalidation.")

        assert result is None
