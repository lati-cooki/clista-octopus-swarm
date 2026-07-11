import logging
import math
import openai
from reflex_arc import tool, step_boxed_tool
from arm_state import ArmState
import hashlib
import uuid

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
    # Fallback/Legacy ID generation
    return hashlib.sha256(query.encode('utf-8')).hexdigest()

def get_embedding(text: str) -> list[float]:
    try:
        client = openai.OpenAI()
        response = client.embeddings.create(input=[text], model="text-embedding-3-small")
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Embedding generation failed: {e}")
        return []

def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    if not v1 or not v2: return 0.0
    dot_product = sum(a * b for a, b in zip(v1, v2))
    norm_v1 = math.sqrt(sum(a * a for a in v1))
    norm_v2 = math.sqrt(sum(b * b for b in v2))
    if norm_v1 == 0 or norm_v2 == 0: return 0.0
    return dot_product / (norm_v1 * norm_v2)

def crystallize_to_memory(user_prompt: str, final_decision: str, network_confidence: float):
    """Archives a successful consensus into the long-term Vector Memory."""
    logger.info(f"Crystallizing to Hive Mind: '{user_prompt}' with confidence {network_confidence:.2f}")
    if hive_collection is not None:
        try:
            # Generate embedding for semantic search
            embedding = get_embedding(user_prompt)
            doc_id = str(uuid.uuid4())
            
            payload = {
                'prompt': user_prompt,
                'decision': final_decision,
                'confidence': network_confidence,
                'timestamp': firestore.SERVER_TIMESTAMP
            }
            if embedding:
                payload['embedding'] = embedding
                
            hive_collection.document(doc_id).set(payload)
        except Exception as e:
            logger.error(f"Failed to crystallize to Firestore: {e}")
    else:
        logger.warning("Firestore is not initialized. Memory will not persist.")

@tool
@step_boxed_tool
def query_hive_mind(query: str, arm_state: ArmState) -> str:
    """Queries the long-term vector memory for past solutions using Semantic Similarity."""
    logger.info(f"[{arm_state.arm_id}] Querying Semantic Hive Mind for: '{query}'")
    
    if hive_collection is not None:
        try:
            query_emb = get_embedding(query)
            if not query_emb:
                return "[HIVE MIND ERROR] Could not generate embeddings for semantic search."
                
            # Scan recent memories and calculate cosine similarity locally 
            # (Allows zero-config vector search without GCP Vector Indexes)
            docs = hive_collection.order_by('timestamp', direction=firestore.Query.DESCENDING).limit(100).stream()
            
            best_match = None
            highest_sim = 0.0
            
            for doc in docs:
                data = doc.to_dict()
                doc_emb = data.get('embedding')
                if doc_emb:
                    sim = cosine_similarity(query_emb, doc_emb)
                    if sim > highest_sim:
                        highest_sim = sim
                        best_match = data
                        
            if best_match and highest_sim >= 0.88:
                decision = best_match.get('decision')
                logger.info(f"[{arm_state.arm_id}] Semantic Hive Mind HIT! (Similarity: {highest_sim:.4f})")
                return f"{decision}"
            else:
                logger.info(f"[{arm_state.arm_id}] No close semantic match found (Highest: {highest_sim:.4f}).")
                
        except Exception as e:
            logger.error(f"[{arm_state.arm_id}] Firestore vector query failed: {e}")
            
    logger.info(f"[{arm_state.arm_id}] Hive Mind MISS. Calculation required.")
    return ""
