"""
Tests for moltbook_archive.py: context-hash cache lookup, entry-type provenance
(CRYSTALLIZATION vs RECALL), and fail-open behavior on Firestore errors.

Also covers gateway.py's Hive Mind recall path (TestGatewayRecallPath below):
precedent-as-citation, the RECALL event type, and extraction-failure cache
bypass. All LLM/Firestore calls are mocked -- no network.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

import gateway
import moltbook_archive
from arm_state import ArmState


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


# ---------------------------------------------------------------------------
# gateway.py: execute_swarm recall path (precedent-as-citation, RECALL event,
# extraction-failure cache bypass). No network: extract_decision_context,
# context_hash, query_hive_mind_by_context, record_recall_event,
# crystallize_to_memory, reground_rationale, commit_audit_record, and
# ArmState.evaluate_payload are all mocked at the gateway module level.
# ---------------------------------------------------------------------------


class FakeWebSocket:
    """Records every payload sent via send_json for later assertion."""

    def __init__(self):
        self.sent = []

    async def send_json(self, payload):
        self.sent.append(payload)


def _fresh_arm_eval(self, user_prompt, enable_tools=False):
    """Stand-in for ArmState.evaluate_payload on the fresh-compute path.

    Always resolves ACTIVE with confidence >= 0.85 so natural consensus is
    reached without exercising the Apex Arbitrator, and without any real
    LLM call.
    """
    self.moltbook.status = "ACTIVE"
    self.moltbook.confidence_weight = 0.9
    self.moltbook.crystallized_decision = f"Fresh decision from {self.arm_id}."
    return self.moltbook


@pytest.fixture(autouse=True)
def _no_real_sleep():
    """Patches gateway's asyncio.sleep with an async no-op for every test in
    this module, so the gateway recall-path tests don't burn 10+ real
    seconds walking the theater-event delays. Harmless for the
    moltbook_archive tests above, which never touch gateway.asyncio.sleep.
    """
    with patch("gateway.asyncio.sleep", new=AsyncMock()):
        yield


class TestGatewayRecallPath:
    def test_material_context_change_misses_cache(self):
        """Two prompts whose extracted contexts differ in exogenous_events
        hash differently. Simulating no match for the second (material
        change) prompt must take the fresh-compute path: SPAWN events
        present and budget consumed.
        """
        ws = FakeWebSocket()
        ctx_seed = MagicMock(name="ctx_seed")
        ctx_material = MagicMock(name="ctx_material")

        with patch.object(ArmState, "evaluate_payload", _fresh_arm_eval), \
             patch("gateway.extract_decision_context", side_effect=[ctx_seed, ctx_material]), \
             patch("gateway.context_hash", side_effect=["hash-seed", "hash-material-change"]) as mock_hash, \
             patch("gateway.query_hive_mind_by_context", return_value=None) as mock_query, \
             patch("gateway.crystallize_to_memory") as mock_crystallize, \
             patch("gateway.commit_audit_record", return_value="exec-id-1") as mock_audit, \
             patch("gateway.reground_rationale") as mock_reground, \
             patch("gateway.record_recall_event") as mock_recall:
            asyncio.run(gateway.execute_swarm(ws, "seed prompt, PSI 0.08, validated 8 months ago"))
            asyncio.run(gateway.execute_swarm(
                ws,
                "seed prompt, PSI 0.08, validated 8 months ago; Fed cut rates 150bps and "
                "the region entered a recession; realized default rates have doubled",
            ))

        # Different decision contexts hashed to different keys, and each was
        # looked up individually (a material change must not reuse a cache key).
        assert mock_hash.call_count == 2
        assert mock_query.call_args_list == [call("hash-seed"), call("hash-material-change")]

        # Both invocations missed (query returns None every time) -> fresh
        # compute happened both times: SPAWN events present, budget consumed,
        # no RECALL event, no recall bookkeeping calls.
        types = [e["type"] for e in ws.sent]
        assert "SPAWN" in types
        assert "RECALL" not in types
        mock_recall.assert_not_called()
        final_outputs = [e for e in ws.sent if e["type"] == "FINAL_OUTPUT"]
        assert len(final_outputs) == 2
        for fo in final_outputs:
            assert fo["budget"] < 100.0  # metabolic budget was actually consumed

    def test_cosmetic_change_hits_cache(self):
        """Contexts differing only in cosmetic entity name hash identically.
        A precedent match must fire a RECALL and must NOT spawn the
        logic/creative compute arms.
        """
        ws = FakeWebSocket()
        ctx = MagicMock(name="ctx_cosmetic")
        precedent = {
            "precedent_id": "precedent-abc",
            "decision": "Annual-cycle revalidation is sufficient.\n\nOriginal rationale paragraph, not to be repeated.",
            "confidence": 0.92,
            "timestamp": datetime.now(timezone.utc) - timedelta(days=3),
            "execution_id": "orig-exec-1",
            "context_hash": "same-hash",
        }

        with patch.object(ArmState, "evaluate_payload", _fresh_arm_eval), \
             patch("gateway.extract_decision_context", return_value=ctx), \
             patch("gateway.context_hash", return_value="same-hash"), \
             patch("gateway.query_hive_mind_by_context", return_value=precedent), \
             patch("gateway.reground_rationale", return_value="Re-grounded justification text.") as mock_reground, \
             patch("gateway.record_recall_event") as mock_recall, \
             patch("gateway.commit_audit_record", return_value="audit-1") as mock_audit, \
             patch("gateway.crystallize_to_memory") as mock_crystallize:
            asyncio.run(gateway.execute_swarm(ws, "webbank prompt, validated 2 months ago"))

        types = [e["type"] for e in ws.sent]
        assert "RECALL" in types
        assert "SPAWN" not in types
        mock_crystallize.assert_not_called()
        mock_reground.assert_called_once()

    def test_recall_never_serves_stale_rationale(self):
        """The recall FINAL_OUTPUT must not contain any sentence from the
        original cached RATIONALE portion, must contain the re-grounded
        text, and must carry the full precedent metadata object.
        """
        ws = FakeWebSocket()
        ctx = MagicMock(name="ctx")
        marker_sentence = "the last validation was 8 months ago"
        precedent = {
            "precedent_id": "precedent-xyz",
            "decision": (
                "Annual-cycle revalidation is sufficient.\n\n"
                f"{marker_sentence.capitalize()} and there is no compelling evidence of "
                "performance degradation."
            ),
            "confidence": 0.95,
            "timestamp": datetime.now(timezone.utc) - timedelta(days=10),
            "execution_id": "orig-exec-2",
            "context_hash": "same-hash-2",
        }
        regrounded_text = "Given the current query's stated facts, revalidation remains within the normal cycle."

        with patch.object(ArmState, "evaluate_payload", _fresh_arm_eval), \
             patch("gateway.extract_decision_context", return_value=ctx), \
             patch("gateway.context_hash", return_value="same-hash-2"), \
             patch("gateway.query_hive_mind_by_context", return_value=precedent), \
             patch("gateway.reground_rationale", return_value=regrounded_text), \
             patch("gateway.record_recall_event"), \
             patch("gateway.commit_audit_record", return_value="audit-2"), \
             patch("gateway.crystallize_to_memory") as mock_crystallize:
            asyncio.run(gateway.execute_swarm(ws, "webbank prompt, validated 2 months ago"))

        final_outputs = [e for e in ws.sent if e["type"] == "FINAL_OUTPUT"]
        assert len(final_outputs) == 1
        decision_text = final_outputs[0]["decision"]

        assert marker_sentence not in decision_text.lower()
        assert regrounded_text in decision_text
        assert "Annual-cycle revalidation is sufficient." in decision_text  # cited conclusion

        precedent_meta = final_outputs[0].get("precedent")
        assert precedent_meta is not None
        assert precedent_meta["precedent_id"] == "precedent-xyz"
        assert precedent_meta["execution_id"] == "orig-exec-2"
        assert precedent_meta["context_hash"] == "same-hash-2"
        assert precedent_meta["age_days"] == 10
        assert precedent_meta["stale"] is False
        assert precedent_meta["original_decision_date"] is not None

        mock_crystallize.assert_not_called()

    def test_recall_does_not_archive_as_fresh_precedent(self):
        """After a recall, crystallize_to_memory is never called, and
        record_recall_event is called exactly once with the original
        precedent_id.
        """
        ws = FakeWebSocket()
        ctx = MagicMock(name="ctx")
        precedent = {
            "precedent_id": "precedent-999",
            "decision": "Conclusion only, no rationale paragraph.",
            "confidence": 0.9,
            "timestamp": datetime.now(timezone.utc) - timedelta(days=1),
            "execution_id": "orig-exec-3",
            "context_hash": "hash-999",
        }

        with patch.object(ArmState, "evaluate_payload", _fresh_arm_eval), \
             patch("gateway.extract_decision_context", return_value=ctx), \
             patch("gateway.context_hash", return_value="hash-999"), \
             patch("gateway.query_hive_mind_by_context", return_value=precedent), \
             patch("gateway.reground_rationale", return_value="Re-grounded."), \
             patch("gateway.record_recall_event") as mock_recall, \
             patch("gateway.commit_audit_record", return_value="audit-3") as mock_audit, \
             patch("gateway.crystallize_to_memory") as mock_crystallize:
            asyncio.run(gateway.execute_swarm(ws, "some prompt"))

        mock_crystallize.assert_not_called()
        mock_recall.assert_called_once_with("precedent-999", "hash-999", "some prompt")

        # A recall must still leave an audit trail (forensics found zero
        # audit records on the old hit path).
        mock_audit.assert_called_once()
        audit_kwargs = mock_audit.call_args.kwargs
        assert audit_kwargs["metadata"]["event"] == "RECALL"
        assert audit_kwargs["metadata"]["precedent_id"] == "precedent-999"

    def test_recall_emits_recall_event_not_consensus(self):
        """The recall path's event stream contains a RECALL-type event and
        never a CONSENSUS-type event.
        """
        ws = FakeWebSocket()
        ctx = MagicMock(name="ctx")
        precedent = {
            "precedent_id": "precedent-abc123",
            "decision": "Conclusion text.",
            "confidence": 0.9,
            "timestamp": datetime.now(timezone.utc) - timedelta(days=1),
            "execution_id": "orig-exec-4",
            "context_hash": "hash-abc123",
        }

        with patch.object(ArmState, "evaluate_payload", _fresh_arm_eval), \
             patch("gateway.extract_decision_context", return_value=ctx), \
             patch("gateway.context_hash", return_value="hash-abc123"), \
             patch("gateway.query_hive_mind_by_context", return_value=precedent), \
             patch("gateway.reground_rationale", return_value="Re-grounded."), \
             patch("gateway.record_recall_event"), \
             patch("gateway.commit_audit_record", return_value="audit-4"), \
             patch("gateway.crystallize_to_memory") as mock_crystallize:
            asyncio.run(gateway.execute_swarm(ws, "some prompt"))

        types = [e["type"] for e in ws.sent]
        assert "RECALL" in types
        assert "CONSENSUS" not in types
        mock_crystallize.assert_not_called()

    def test_fallback_sentinel_decision_is_not_archived(self):
        """When no arm produces a crystallized_decision, the fresh path
        serves a fallback sentinel ("Consensus reached without specific
        output.") -- that sentinel must NEVER be crystallized to the Hive
        Mind as a keyed precedent (a no-decision must never become citable
        precedent). The audit record must still be written: audit is
        history, cache is precedent.
        """
        ws = FakeWebSocket()
        ctx = MagicMock(name="ctx")
        ctx.model_dump.return_value = {"schema_id": "mrm_revalidation_v1"}

        def no_decision_eval(self, user_prompt, enable_tools=False):
            # ACTIVE with high confidence so natural consensus resolves
            # without the arbitrator, but NO crystallized decision produced
            # (e.g. transient LLM failure returning an empty payload).
            self.moltbook.status = "ACTIVE"
            self.moltbook.confidence_weight = 0.9
            self.moltbook.crystallized_decision = None
            return self.moltbook

        with patch.object(ArmState, "evaluate_payload", no_decision_eval), \
             patch("gateway.extract_decision_context", return_value=ctx), \
             patch("gateway.context_hash", return_value="hash-no-decision"), \
             patch("gateway.query_hive_mind_by_context", return_value=None), \
             patch("gateway.crystallize_to_memory") as mock_crystallize, \
             patch("gateway.commit_audit_record", return_value="exec-no-decision") as mock_audit, \
             patch("gateway.reground_rationale"), \
             patch("gateway.record_recall_event"):
            asyncio.run(gateway.execute_swarm(ws, "a prompt whose arms all fail to decide"))

        final_outputs = [e for e in ws.sent if e["type"] == "FINAL_OUTPUT"]
        assert len(final_outputs) == 1
        assert "Consensus reached without specific output." in final_outputs[0]["decision"]

        # The sentinel is served but never archived as citable precedent.
        mock_crystallize.assert_not_called()
        # Audit still records the run (history != precedent).
        mock_audit.assert_called_once()

        info_messages = [e["message"] for e in ws.sent if e["type"] == "INFO"]
        assert any("not archiving as precedent" in m for m in info_messages)

    def test_recall_reground_runs_off_event_loop(self):
        """reground_rationale is a blocking OpenAI network call; the recall
        path must run it via asyncio.to_thread, never directly on the event
        loop. Inside a to_thread worker, asyncio.get_running_loop() raises
        RuntimeError -- so a probe that records whether a running loop is
        visible distinguishes on-loop execution from thread offload.
        """
        ws = FakeWebSocket()
        ctx = MagicMock(name="ctx")
        precedent = {
            "precedent_id": "precedent-thread",
            "decision": "Conclusion text.",
            "confidence": 0.9,
            "timestamp": datetime.now(timezone.utc) - timedelta(days=1),
            "execution_id": "orig-exec-5",
            "context_hash": "hash-thread",
        }
        observed = {}

        def probe_reground(*args, **kwargs):
            try:
                asyncio.get_running_loop()
                observed["on_event_loop"] = True
            except RuntimeError:
                observed["on_event_loop"] = False
            return "Re-grounded."

        with patch.object(ArmState, "evaluate_payload", _fresh_arm_eval), \
             patch("gateway.extract_decision_context", return_value=ctx), \
             patch("gateway.context_hash", return_value="hash-thread"), \
             patch("gateway.query_hive_mind_by_context", return_value=precedent), \
             patch("gateway.reground_rationale", side_effect=probe_reground), \
             patch("gateway.record_recall_event"), \
             patch("gateway.commit_audit_record", return_value="audit-5"), \
             patch("gateway.crystallize_to_memory"):
            asyncio.run(gateway.execute_swarm(ws, "some prompt"))

        assert observed, "reground_rationale was never called on the recall path"
        assert observed["on_event_loop"] is False, (
            "reground_rationale executed on the event loop thread's running "
            "loop -- it must be offloaded via asyncio.to_thread"
        )

    def test_extraction_failure_bypasses_cache(self):
        """extract_decision_context returning None must skip the cache
        lookup entirely, skip the crystallize write (context_hash=None
        forces the moltbook layer to also refuse), and proceed to fresh
        compute.
        """
        ws = FakeWebSocket()

        with patch.object(ArmState, "evaluate_payload", _fresh_arm_eval), \
             patch("gateway.extract_decision_context", return_value=None), \
             patch("gateway.context_hash") as mock_hash, \
             patch("gateway.query_hive_mind_by_context") as mock_query, \
             patch("gateway.crystallize_to_memory") as mock_crystallize, \
             patch("gateway.commit_audit_record", return_value="exec-id-bypass") as mock_audit, \
             patch("gateway.reground_rationale") as mock_reground, \
             patch("gateway.record_recall_event") as mock_recall:
            asyncio.run(gateway.execute_swarm(ws, "a prompt that doesn't fit the schema"))

        mock_hash.assert_not_called()
        mock_query.assert_not_called()
        mock_recall.assert_not_called()

        info_messages = [e["message"] for e in ws.sent if e["type"] == "INFO"]
        assert any("Context extraction failed" in m and "bypassing Hive Mind" in m for m in info_messages)

        types = [e["type"] for e in ws.sent]
        assert "SPAWN" in types  # fresh compute proceeded
        assert "RECALL" not in types

        mock_crystallize.assert_called_once()
        crystallize_kwargs = mock_crystallize.call_args.kwargs
        assert crystallize_kwargs["context_hash"] is None
