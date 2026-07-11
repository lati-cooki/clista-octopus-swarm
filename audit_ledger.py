"""
BLASTEMA PROTOCOL v3: AUDIT LEDGER
Captures the full execution history (scratchpads, tool outputs, deadlocks)
into an immutable Firestore collection for Model Risk Management (MRM) and compliance.
"""
from google.cloud import firestore
import uuid

class FirestoreAuditLedger:
    def __init__(self, collection_name="clista_audit_logs"):
        # Automatically inherits the Cloud Run service account credentials
        try:
            self.db = firestore.Client()
            self.collection = self.db.collection(collection_name)
        except Exception as e:
            print(f"Failed to initialize Firestore: {e}")
            self.db = None
            self.collection = None

    def record_execution(self, prompt: str, final_decision: str, arms_data: list, metadata: dict):
        """
        Commits the complete, unmolted execution record to the audit trail.
        """
        record_id = str(uuid.uuid4())
        
        payload = {
            "record_id": record_id,
            "timestamp": firestore.SERVER_TIMESTAMP if self.db else "MOCKED_TIMESTAMP",
            "prompt": prompt,
            "final_decision": final_decision,
            "arms_execution_history": arms_data, # Contains raw scratchpads and tool outputs
            "metadata": metadata
        }
        
        if self.collection:
            doc_ref = self.collection.document(record_id)
            doc_ref.set(payload)
            print(f"[AUDIT LEDGER] Full execution history permanently recorded. (ID: {record_id})")
        else:
            print(f"[AUDIT LEDGER] MOCKED execution history recorded. (ID: {record_id})")

        return record_id

# Global persistent instance for the ledger
global_audit_ledger = FirestoreAuditLedger()

def commit_audit_record(prompt: str, final_decision: str, arms_data: list, metadata: dict = None):
    """
    Helper function to be called by the Mantle Orchestrator just before molting.
    """
    if metadata is None:
        metadata = {}
    return global_audit_ledger.record_execution(prompt, final_decision, arms_data, metadata)
