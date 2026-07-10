from arm_state import ArmState, MoltbookState
import logging

logger = logging.getLogger(__name__)

def seal_arm(arm_id: str, error: Exception, current_state: ArmState) -> ArmState:
    """
    Phase 1: The Tourniquet.
    Captures state on arm failure. This module MUST NEVER raise an exception to the Mantle.
    It gracefully isolates the dead state.
    """
    try:
        logger.error(f"Arm {arm_id} encountered fatal error: {error}. Initiating SEAL phase.")
        # Trap the state
        sealed_moltbook = MoltbookState(
            status='SEAL',
            confidence_weight=0.0,
            scratchpad=f"SEALED DUE TO ERROR: {str(error)}",
            crystallized_decision=None
        )
        current_state.moltbook = sealed_moltbook
        # We return the sealed state to be handled by blastema/mantle, rather than throwing
        return current_state
    except Exception as tourniquet_error:
        # Ultimate fallback, still never raise
        logger.critical(f"Tourniquet failed for {arm_id}: {tourniquet_error}")
        return ArmState(
            arm_id=arm_id,
            route="UNKNOWN",
            moltbook=MoltbookState(
                status='SEAL',
                confidence_weight=0.0,
                scratchpad="CRITICAL TOURNIQUET FAILURE",
                crystallized_decision=None
            )
        )
