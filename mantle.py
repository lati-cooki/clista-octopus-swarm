from typing import List, Tuple, Literal
from arm_state import ArmState, MoltbookState
from seal import seal_arm
from blastema import regrow_arm
from budget import MetabolicBudget
from moltbook_archive import crystallize_to_memory
import logging

logger = logging.getLogger(__name__)

class MantleOrchestrator:
    """
    Phase 4/5: Orchestrator, Consensus Aggregation and Molting Engine.
    The core ADK GraphWorkflow/Supervisor. Drives the seal->blastema->resume loop, 
    evaluates consensus, manages negotiations, and molts ephemeral data.
    """
    def __init__(self, budget: MetabolicBudget):
        self.budget = budget
        self.arms: List[ArmState] = []
        self.negotiation_passes: int = 0
        self.max_negotiations: int = 2
        
    def delegate_task(self, prompt: str) -> None:
        """Decompose prompt and spawn arms."""
        pass
        
    def evaluate_resonant_coherence(self, threshold: float = 0.85) -> Literal['CONSENSUS', 'FRACTURED']:
        """
        Check if active network confidence >= threshold.
        Filters out SEALed arms (which regenerate in background).
        """
        active_arms = [a for a in self.arms if a.moltbook.status == 'ACTIVE']
        if not active_arms:
            logger.warning("No ACTIVE arms available for coherence evaluation.")
            return 'FRACTURED'
            
        avg_confidence = sum(a.moltbook.confidence_weight for a in active_arms) / len(active_arms)
        logger.info(f"Current resonant coherence (average confidence): {avg_confidence:.2f}")
        
        if avg_confidence >= threshold:
            return 'CONSENSUS'
        else:
            return 'FRACTURED'

    def molt_state(self):
        """
        The Molting Process (Context Shedding).
        Explicitly deletes scratchpad data from the ArmState, 
        leaving ONLY the crystallized_decision to avoid polluting global context.
        """
        logger.info("Initiating Molt Process: Shedding ephemeral scratchpads.")
        for arm in self.arms:
            if arm.moltbook.status == 'ACTIVE':
                arm.moltbook.scratchpad = None

    def broadcast_negotiation(self):
        """
        Bundles conflicting crystallized_decision outputs and broadcasts 
        them back to active arms for negotiation.
        """
        active_arms = [a for a in self.arms if a.moltbook.status == 'ACTIVE']
        conflicting_decisions = [a.moltbook.crystallized_decision for a in active_arms if a.moltbook.crystallized_decision]
        
        logger.info(f"Broadcasting {len(conflicting_decisions)} decisions for negotiation pass {self.negotiation_passes + 1}")
        # In a real ADK, we would send these decisions back to the LLMs for re-evaluation.
        # We mock this by incrementing pass and slightly bumping confidence for simulation purposes.
        for arm in active_arms:
            # Mock LLM negotiation resulting in higher confidence
            arm.moltbook.confidence_weight = min(1.0, arm.moltbook.confidence_weight + 0.15)
        
        self.negotiation_passes += 1

    def run_cycle(self, prompt: str = "default prompt") -> str:
        """
        Main Supervisor Execution Loop.
        Drives the seal->blastema->resume loop, consensus evaluation, and molting.
        """
        # Step 1: Manage Regenerations
        for i, arm in enumerate(self.arms):
            if arm.moltbook.status == 'SEAL':
                new_arm = regrow_arm(arm, self.budget)
                self.arms[i] = new_arm
                
        # Step 2: Evaluate Consensus
        status = self.evaluate_resonant_coherence()
        
        if status == 'CONSENSUS':
            logger.info("Resonant Coherence Achieved: CONSENSUS reached.")
            self.molt_state()
            # Return the unified consensus decision
            active_arms = [a for a in self.arms if a.moltbook.status == 'ACTIVE']
            if active_arms:
                final_decision = active_arms[0].moltbook.crystallized_decision or "Consensus reached without specific output."
                avg_confidence = sum(a.moltbook.confidence_weight for a in active_arms) / len(active_arms)
                
                # Archiving to Hive Mind
                crystallize_to_memory(prompt, final_decision, avg_confidence)
                
                return final_decision
            return "Consensus reached but no active arms available."
            
        # Step 3: The Negotiation Loop
        if status == 'FRACTURED':
            if self.negotiation_passes < self.max_negotiations:
                logger.info(f"Coherence FRACTURED. Initiating negotiation pass {self.negotiation_passes + 1}/{self.max_negotiations}...")
                self.broadcast_negotiation()
                return self.run_cycle(prompt) # Recurse for the next cycle
            else:
                logger.warning("Max negotiations reached. Escalating to Apex Arbitrator.")
                
                active_arms = [a for a in self.arms if a.moltbook.status == 'ACTIVE']
                deadlocked_decisions = [a.moltbook.crystallized_decision for a in active_arms]
                
                logger.info("Spawning arbitration_arm...")
                arbitration_arm = ArmState(
                    arm_id="apex_arbitrator",
                    route="mantle->arbitration",
                    moltbook=MoltbookState(
                        status='ACTIVE',
                        confidence_weight=1.0,
                        crystallized_decision=f"APEX ARBITRATION OVERRIDE: Resolving {len(deadlocked_decisions)} deadlocked options into logically superior path."
                    )
                )
                
                self.arms = [arbitration_arm]
                logger.info("Apex Arbitrator has resolved the deadlock. Forcing consensus.")
                
                self.molt_state()
                final_decision = arbitration_arm.moltbook.crystallized_decision
                crystallize_to_memory(prompt, final_decision, 1.0)
                
                return final_decision
