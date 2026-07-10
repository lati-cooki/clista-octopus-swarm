import logging
from reflex_arc import tool, step_boxed_tool
from arm_state import ArmState
import hashlib

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

def get_doc_id(query: str) -> str:
    # Use SHA-256 hash of the query as the document ID
    return hashlib.sha256(query.encode('utf-8')).hexdigest()

def crystallize_to_memory(user_prompt: str, final_decision: str, network_confidence: float):
    """Archives a successful consensus into the long-term Vector Memory."""
    logger.info(f"Crystallizing to Hive Mind: '{user_prompt}' with confidence {network_confidence:.2f}")
    if hive_collection is not None:
        try:
            doc_id = get_doc_id(user_prompt)
            hive_collection.document(doc_id).set({
                'prompt': user_prompt,
                'decision': final_decision,
                'confidence': network_confidence,
                'timestamp': firestore.SERVER_TIMESTAMP
            })
        except Exception as e:
            logger.error(f"Failed to crystallize to Firestore: {e}")
    else:
        logger.warning("Firestore is not initialized. Memory will not persist.")

@tool
@step_boxed_tool
def query_hive_mind(query: str, arm_state: ArmState) -> str:
    """Queries the long-term vector memory for past solutions before calculating."""
    logger.info(f"[{arm_state.arm_id}] Querying Hive Mind for: '{query}'")
    
    if hive_collection is not None:
        try:
            doc_id = get_doc_id(query)
            doc = hive_collection.document(doc_id).get()
            if doc.exists:
                decision = doc.to_dict().get('decision')
                logger.info(f"[{arm_state.arm_id}] Hive Mind HIT! Recovered past consensus.")
                return f"{decision}"
        except Exception as e:
            logger.error(f"[{arm_state.arm_id}] Firestore query failed: {e}")
            
    logger.info(f"[{arm_state.arm_id}] Hive Mind MISS. Calculation required.")
    return ""
