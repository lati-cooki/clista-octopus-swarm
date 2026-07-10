import logging
from reflex_arc import tool, step_boxed_tool
from arm_state import ArmState

logger = logging.getLogger(__name__)

# Mock vector DB in memory for testing
_hive_mind_db = {}

def crystallize_to_memory(user_prompt: str, final_decision: str, network_confidence: float):
    """Archives a successful consensus into the long-term Vector Memory."""
    logger.info(f"Crystallizing to Hive Mind: '{user_prompt}' with confidence {network_confidence:.2f}")
    _hive_mind_db[user_prompt] = final_decision

@tool
@step_boxed_tool
def query_hive_mind(query: str, arm_state: ArmState) -> str:
    """Queries the long-term vector memory for past solutions before calculating."""
    logger.info(f"[{arm_state.arm_id}] Querying Hive Mind for: '{query}'")
    
    # Exact match for mock simplicity
    if query in _hive_mind_db:
        logger.info(f"[{arm_state.arm_id}] Hive Mind HIT! Recovered past consensus.")
        return f"HIVE MIND RECALL: {_hive_mind_db[query]}"
    
    logger.info(f"[{arm_state.arm_id}] Hive Mind MISS. Calculation required.")
    return "No historical consensus found. Calculation required."
