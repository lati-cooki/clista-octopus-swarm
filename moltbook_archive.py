"""
BLASTEMA PROTOCOL: HIVE MIND ARCHIVE (Firestore layer, collection `clista_hive_mind`)

Stores and looks up decision precedents by exact SHA-256 context hash (see
context_key.py) instead of embedding/cosine-similarity. A decision cache must
never serve a decision that isn't keyed on an exact context match, so all
write and lookup paths are fail-open: any Firestore error, missing key, or
unusable stored record results in a no-op / None rather than a raised
exception or a bad cache hit.

Provenance is never flattened: a fresh consensus is archived as entry_type
CRYSTALLIZATION; recalling a cached precedent logs a distinct entry_type
RECALL that references the original precedent instead of re-archiving as a
new crystallization.
"""

import logging
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Initialize Firestore Client
try:
    from google.cloud import firestore
    db = firestore.Client()
    hive_collection = db.collection('clista_hive_mind')
except Exception as e:
    logger.error(f"Failed to initialize Firestore: {e}")
    db = None
    hive_collection = None

# FieldFilter is the non-deprecated way to build .where() queries on recent
# google-cloud-firestore versions (plain positional .where() emits a
# UserWarning). Guarded separately from client init so an older installed
# version missing this symbol can't break module import.
try:
    from google.cloud.firestore_v1.base_query import FieldFilter
except ImportError:
    FieldFilter = None


def crystallize_to_memory(
    user_prompt: str,
    final_decision: str,
    network_confidence: float,
    context_hash: str | None = None,
    decision_context: dict | None = None,
    execution_id: str | None = None,
) -> None:
    """Archives a fresh consensus into the Hive Mind as entry_type CRYSTALLIZATION.

    Fail-open rule: without an exact context_hash there is no key to look this
    entry back up by, so DO NOT WRITE -- log and return. This also covers the
    case where upstream context extraction failed (context_hash is None).
    """
    if context_hash is None:
        logger.info(
            "crystallize_to_memory: context_hash is None (extraction failed or "
            "not supplied) -- skipping write. A cache entry with no key can "
            "never be looked up, so it must not be written."
        )
        return

    if hive_collection is None:
        logger.warning("Firestore is not initialized. Memory will not persist.")
        return

    logger.info(
        f"Crystallizing to Hive Mind: '{user_prompt}' with confidence {network_confidence:.2f}"
    )
    try:
        doc_id = str(uuid.uuid4())
        payload = {
            'entry_type': 'CRYSTALLIZATION',
            'prompt': user_prompt,
            'decision': final_decision,
            'confidence': network_confidence,
            'context_hash': context_hash,
            'decision_context': decision_context,
            'execution_id': execution_id,
            'timestamp': firestore.SERVER_TIMESTAMP,
        }
        hive_collection.document(doc_id).set(payload)
    except Exception as e:
        logger.error(f"Failed to crystallize to Firestore: {e}")


def query_hive_mind_by_context(context_hash: str) -> dict | None:
    """Exact-match precedent lookup by context_hash. None on no match / any error.

    Only docs with entry_type == "CRYSTALLIZATION" AND an exact context_hash
    match are eligible. Docs missing entry_type are legacy (pre-migration)
    writes -- treated as non-matching (they also lack context_hash, so this
    is belt-and-braces). Any matching doc whose `decision` is None/empty is
    skipped: a decision cache must never serve a null decision, so if that's
    the only match this returns None rather than a match with a null payload.

    Sorting: we fetch all matches for the hash and pick the newest by
    `timestamp` client-side, rather than adding `.order_by('timestamp')` to
    the Firestore query. Combining an equality filter on `context_hash` with
    an order_by on a different field requires a Firestore composite index;
    client-side sorting avoids that infra dependency for what should be a
    small candidate set per hash.
    """
    if hive_collection is None or context_hash is None:
        return None

    # The try covers the ENTIRE lookup -- query, candidate filtering, and
    # newest-first selection -- so "None on any error" is literally true.
    # Example this kills permanently: stored docs with mixed timestamp types
    # (datetime vs string) would make max() raise TypeError; that must
    # degrade to a cache miss, never a raised exception on the serving path.
    try:
        if FieldFilter is not None:
            query = hive_collection.where(filter=FieldFilter('context_hash', '==', context_hash))
        else:
            query = hive_collection.where('context_hash', '==', context_hash)
        docs = list(query.stream())

        candidates = []
        for doc in docs:
            data = doc.to_dict() or {}
            if data.get('entry_type') != 'CRYSTALLIZATION':
                continue
            if not data.get('decision'):
                # Null/empty decision: never serve it, even if it's the only match.
                continue
            candidates.append((doc.id, data))

        if not candidates:
            return None

        def _sort_key(item):
            ts = item[1].get('timestamp')
            # Missing timestamps sort oldest so they lose ties to any real timestamp.
            return ts if ts is not None else datetime.min.replace(tzinfo=timezone.utc)

        doc_id, data = max(candidates, key=_sort_key)

        return {
            'precedent_id': doc_id,
            'decision': data.get('decision'),
            'confidence': data.get('confidence'),
            'timestamp': data.get('timestamp'),
            'execution_id': data.get('execution_id'),
            'context_hash': data.get('context_hash'),
        }
    except Exception as e:
        logger.error(f"query_hive_mind_by_context: lookup failed (fail-open to miss): {e}")
        return None


def record_recall_event(original_precedent_id: str, context_hash: str, current_prompt: str) -> None:
    """Logs a RECALL provenance event referencing the original precedent.

    Recalled results never re-archive as fresh precedents: this writes
    entry_type "RECALL" (never "CRYSTALLIZATION"), so provenance is never
    flattened between an original crystallization and later recalls of it.
    Fail-open: any Firestore error is logged and swallowed.
    """
    if hive_collection is None:
        logger.warning("Firestore is not initialized. Recall event will not persist.")
        return

    try:
        doc_id = str(uuid.uuid4())
        payload = {
            'entry_type': 'RECALL',
            'references': original_precedent_id,
            'context_hash': context_hash,
            'prompt': current_prompt,
            'timestamp': firestore.SERVER_TIMESTAMP,
        }
        hive_collection.document(doc_id).set(payload)
    except Exception as e:
        logger.error(f"Failed to record recall event to Firestore: {e}")
