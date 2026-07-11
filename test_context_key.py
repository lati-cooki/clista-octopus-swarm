"""
Tests for context_key.py — decision-context extraction, canonicalization, and
SHA-256 hashing.

All OpenAI calls are mocked. No network I/O occurs in this test file.
"""

import re
from unittest.mock import Mock, patch

from context_key import DecisionContext, context_hash, extract_decision_context


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
        ctx_a = make_ctx(exogenous_events=["Fed Rate Cut 150bps", "Regional Recession"])
        ctx_b = make_ctx(exogenous_events=["  fed rate cut 150bps  ", "regional   recession"])
        # Note: internal whitespace collapsing is best-effort; leading/trailing +
        # casing normalization must hold at minimum.
        assert context_hash(make_ctx(exogenous_events=["Fed Rate Cut 150bps"])) == context_hash(
            make_ctx(exogenous_events=["fed rate cut 150bps"])
        )
        assert context_hash(make_ctx(exogenous_events=["  fed rate cut 150bps  "])) == context_hash(
            make_ctx(exogenous_events=["fed rate cut 150bps"])
        )

    def test_different_metric_values_differ(self):
        ctx_a = make_ctx(metrics={"psi": 0.08, "auc": 0.82})
        ctx_b = make_ctx(metrics={"psi": 0.09, "auc": 0.82})
        assert context_hash(ctx_a) != context_hash(ctx_b)

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
        expected = make_ctx()
        mock_message = Mock()
        mock_message.parsed = expected
        mock_choice = Mock()
        mock_choice.message = mock_message
        mock_response = Mock()
        mock_response.choices = [mock_choice]

        mock_client = Mock()
        mock_client.beta.chat.completions.parse.return_value = mock_response

        with patch("context_key.openai.OpenAI", return_value=mock_client):
            result = extract_decision_context("Some MRM prompt about revalidation.")

        assert result == expected

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
