"""
Tests for moltbook_archive.py: context-hash cache lookup, entry-type provenance
(CRYSTALLIZATION vs RECALL), and fail-open behavior on Firestore errors.

Firestore is mocked entirely (module's `hive_collection` is patched) -- no
google.cloud calls, no network.
"""

from unittest.mock import MagicMock, patch

import moltbook_archive


def _make_doc(doc_id: str, data: dict):
    doc = MagicMock()
    doc.id = doc_id
    doc.to_dict.return_value = data
    return doc


class TestCrystallizeToMemory:
    def test_refuses_to_write_when_context_hash_is_none(self):
        mock_collection = MagicMock()
        with patch.object(moltbook_archive, "hive_collection", mock_collection):
            moltbook_archive.crystallize_to_memory(
                user_prompt="some prompt",
                final_decision="some decision",
                network_confidence=0.9,
                context_hash=None,
            )

        mock_collection.document.assert_not_called()

    def test_writes_all_fields_with_entry_type_crystallization(self):
        mock_doc_ref = MagicMock()
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref

        with patch.object(moltbook_archive, "hive_collection", mock_collection):
            moltbook_archive.crystallize_to_memory(
                user_prompt="What is the routing path?",
                final_decision="Path B provides 0% drop rate.",
                network_confidence=0.95,
                context_hash="abc123hash",
                decision_context={"schema_id": "mrm_revalidation_v1"},
                execution_id="exec-42",
            )

        mock_collection.document.assert_called_once()
        mock_doc_ref.set.assert_called_once()
        payload = mock_doc_ref.set.call_args[0][0]

        assert payload["entry_type"] == "CRYSTALLIZATION"
        assert payload["prompt"] == "What is the routing path?"
        assert payload["decision"] == "Path B provides 0% drop rate."
        assert payload["confidence"] == 0.95
        assert payload["context_hash"] == "abc123hash"
        assert payload["decision_context"] == {"schema_id": "mrm_revalidation_v1"}
        assert payload["execution_id"] == "exec-42"
        assert "timestamp" in payload

    def test_fails_open_on_firestore_error_no_raise(self):
        mock_collection = MagicMock()
        mock_collection.document.side_effect = Exception("firestore is down")

        with patch.object(moltbook_archive, "hive_collection", mock_collection):
            # Must not raise.
            moltbook_archive.crystallize_to_memory(
                user_prompt="p",
                final_decision="d",
                network_confidence=0.5,
                context_hash="h",
            )

    def test_noop_when_hive_collection_unavailable(self):
        with patch.object(moltbook_archive, "hive_collection", None):
            # Must not raise even though there's nothing to write to.
            moltbook_archive.crystallize_to_memory(
                user_prompt="p",
                final_decision="d",
                network_confidence=0.5,
                context_hash="h",
            )


class TestQueryHiveMindByContext:
    def test_returns_none_on_no_match(self):
        mock_collection = MagicMock()
        mock_collection.where.return_value.stream.return_value = []

        with patch.object(moltbook_archive, "hive_collection", mock_collection):
            result = moltbook_archive.query_hive_mind_by_context("no-such-hash")

        assert result is None

    def test_returns_none_on_firestore_error(self):
        mock_collection = MagicMock()
        mock_collection.where.side_effect = Exception("firestore unavailable")

        with patch.object(moltbook_archive, "hive_collection", mock_collection):
            result = moltbook_archive.query_hive_mind_by_context("h")

        assert result is None

    def test_returns_none_when_hive_collection_unavailable(self):
        with patch.object(moltbook_archive, "hive_collection", None):
            result = moltbook_archive.query_hive_mind_by_context("h")

        assert result is None

    def test_returns_precedent_dict_on_match(self):
        doc = _make_doc(
            "doc-1",
            {
                "entry_type": "CRYSTALLIZATION",
                "prompt": "original prompt",
                "decision": "Path B is optimal.",
                "confidence": 0.9,
                "context_hash": "matching-hash",
                "execution_id": "exec-1",
                "timestamp": "2026-01-01T00:00:00Z",
            },
        )
        mock_collection = MagicMock()
        mock_collection.where.return_value.stream.return_value = [doc]

        with patch.object(moltbook_archive, "hive_collection", mock_collection):
            result = moltbook_archive.query_hive_mind_by_context("matching-hash")

        assert result is not None
        assert result["precedent_id"] == "doc-1"
        assert result["decision"] == "Path B is optimal."
        assert result["confidence"] == 0.9
        assert result["execution_id"] == "exec-1"
        assert result["context_hash"] == "matching-hash"
        assert "timestamp" in result

    def test_ignores_docs_missing_entry_type_legacy(self):
        legacy_doc = _make_doc(
            "legacy-1",
            {
                # No entry_type, no context_hash -- pre-migration legacy doc.
                "prompt": "legacy prompt",
                "decision": None,
            },
        )
        mock_collection = MagicMock()
        mock_collection.where.return_value.stream.return_value = [legacy_doc]

        with patch.object(moltbook_archive, "hive_collection", mock_collection):
            result = moltbook_archive.query_hive_mind_by_context("some-hash")

        assert result is None

    def test_skips_match_with_null_decision(self):
        null_decision_doc = _make_doc(
            "doc-null",
            {
                "entry_type": "CRYSTALLIZATION",
                "decision": None,
                "context_hash": "h",
                "timestamp": "2026-01-01T00:00:00Z",
            },
        )
        mock_collection = MagicMock()
        mock_collection.where.return_value.stream.return_value = [null_decision_doc]

        with patch.object(moltbook_archive, "hive_collection", mock_collection):
            result = moltbook_archive.query_hive_mind_by_context("h")

        assert result is None

    def test_skips_match_with_empty_string_decision(self):
        empty_decision_doc = _make_doc(
            "doc-empty",
            {
                "entry_type": "CRYSTALLIZATION",
                "decision": "",
                "context_hash": "h",
                "timestamp": "2026-01-01T00:00:00Z",
            },
        )
        mock_collection = MagicMock()
        mock_collection.where.return_value.stream.return_value = [empty_decision_doc]

        with patch.object(moltbook_archive, "hive_collection", mock_collection):
            result = moltbook_archive.query_hive_mind_by_context("h")

        assert result is None

    def test_ignores_recall_entries_only_crystallization_matches(self):
        recall_doc = _make_doc(
            "recall-1",
            {
                "entry_type": "RECALL",
                "decision": "should not be served",
                "context_hash": "h",
                "timestamp": "2026-01-01T00:00:00Z",
            },
        )
        mock_collection = MagicMock()
        mock_collection.where.return_value.stream.return_value = [recall_doc]

        with patch.object(moltbook_archive, "hive_collection", mock_collection):
            result = moltbook_archive.query_hive_mind_by_context("h")

        assert result is None

    def test_picks_newest_match_by_timestamp(self):
        older = _make_doc(
            "older",
            {
                "entry_type": "CRYSTALLIZATION",
                "decision": "old decision",
                "context_hash": "h",
                "timestamp": "2020-01-01T00:00:00Z",
            },
        )
        newer = _make_doc(
            "newer",
            {
                "entry_type": "CRYSTALLIZATION",
                "decision": "new decision",
                "context_hash": "h",
                "timestamp": "2026-01-01T00:00:00Z",
            },
        )
        mock_collection = MagicMock()
        mock_collection.where.return_value.stream.return_value = [older, newer]

        with patch.object(moltbook_archive, "hive_collection", mock_collection):
            result = moltbook_archive.query_hive_mind_by_context("h")

        assert result["precedent_id"] == "newer"
        assert result["decision"] == "new decision"


class TestRecordRecallEvent:
    def test_writes_entry_type_recall_with_references(self):
        mock_doc_ref = MagicMock()
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref

        with patch.object(moltbook_archive, "hive_collection", mock_collection):
            moltbook_archive.record_recall_event(
                original_precedent_id="precedent-123",
                context_hash="h",
                current_prompt="current prompt text",
            )

        mock_doc_ref.set.assert_called_once()
        payload = mock_doc_ref.set.call_args[0][0]

        assert payload["entry_type"] == "RECALL"
        assert payload["references"] == "precedent-123"
        assert payload["context_hash"] == "h"
        assert payload["prompt"] == "current prompt text"
        assert "timestamp" in payload
        assert payload["entry_type"] != "CRYSTALLIZATION"

    def test_never_writes_entry_type_crystallization(self):
        mock_doc_ref = MagicMock()
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref

        with patch.object(moltbook_archive, "hive_collection", mock_collection):
            moltbook_archive.record_recall_event(
                original_precedent_id="p-1",
                context_hash="h",
                current_prompt="prompt",
            )

        payload = mock_doc_ref.set.call_args[0][0]
        assert payload["entry_type"] == "RECALL"

    def test_fails_open_on_firestore_error_no_raise(self):
        mock_collection = MagicMock()
        mock_collection.document.side_effect = Exception("firestore is down")

        with patch.object(moltbook_archive, "hive_collection", mock_collection):
            # Must not raise.
            moltbook_archive.record_recall_event(
                original_precedent_id="p-1",
                context_hash="h",
                current_prompt="prompt",
            )

    def test_noop_when_hive_collection_unavailable(self):
        with patch.object(moltbook_archive, "hive_collection", None):
            # Must not raise even though there's nothing to write to.
            moltbook_archive.record_recall_event(
                original_precedent_id="p-1",
                context_hash="h",
                current_prompt="prompt",
            )
