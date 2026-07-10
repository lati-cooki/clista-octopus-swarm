from arm_state import ArmState
from budget import MetabolicBudget
import logging

logger = logging.getLogger(__name__)

def regrow_arm(sealed_state: ArmState, budget: MetabolicBudget) -> ArmState:
    """
    Phase 2/3: Regeneration.
    Logic to decay the global budget, inherit the upstream route, and prepare the parameters for a clean container respawn.
    """
    logger.info(f"Initiating BLASTEMA regeneration for arm {sealed_state.arm_id}")
    
    # Decay the global budget
    regrowth_cost = 10.0 # arbitrary cost
    if not budget.consume(regrowth_cost):
        logger.warning(f"Metabolic budget depleted. Cannot regrow arm {sealed_state.arm_id}.")
        return sealed_state # Remains SEALED
        
    # Inherit upstream route and prepare clean respawn
    # (Implementation of container respawn would go here)
    logger.info(f"Respawning arm {sealed_state.arm_id} on route {sealed_state.route}")
    
    # Return a fresh state for the new arm instance, keeping the route
    from arm_state import MoltbookState
    fresh_state = ArmState(
        arm_id=f"{sealed_state.arm_id}_regrown",
        route=sealed_state.route,
        moltbook=MoltbookState(
            status='ACTIVE',
            confidence_weight=1.0,
            scratchpad=None,
            crystallized_decision=None
        )
    )
    return fresh_state
