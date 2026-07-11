from typing import List, Tuple, Literal
from arm_state import ArmState, MoltbookState
from seal import seal_arm
from blastema import regrow_arm
from budget import MetabolicBudget
from moltbook_archive import crystallize_to_memory
from audit_ledger import commit_audit_record
from ci_cd_webhook import trigger_deployment_webhook
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
            
            # Pre-molt processing
            active_arms = [a for a in self.arms if a.moltbook.status == 'ACTIVE']
            if active_arms:
                final_decision = active_arms[0].moltbook.crystallized_decision or "Consensus reached without specific output."
                avg_confidence = sum(a.moltbook.confidence_weight for a in active_arms) / len(active_arms)
                
                # V3 DUAL-TRACK MEMORY: Compile pre-molt audit record
                arms_data = [{
                    "arm_id": arm.arm_id,
                    "status": arm.moltbook.status,
                    "confidence_weight": arm.moltbook.confidence_weight,
                    "scratchpad": arm.moltbook.scratchpad
                } for arm in self.arms]
                
                commit_audit_record(
                    prompt=prompt, 
                    final_decision=final_decision, 
                    arms_data=arms_data, 
                    metadata={"budget_remaining": self.budget.get_remaining(), "coherence": avg_confidence}
                )
                
                self.molt_state()
                
                # Archiving to Hive Mind
                crystallize_to_memory(prompt, final_decision, avg_confidence)
                
                # MANUAL APPROVAL REQUIRED for CI/CD webhook. Autonomous deploy is disabled.
                # trigger_deployment_webhook(prompt, final_decision, avg_confidence)
                
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
                
                logger.info("Spawning apex_arbitrator (gemini-2.5-pro)...")
                arbitration_arm = ArmState(
                    arm_id="apex_arbitrator",
                    route="mantle->arbitration",
                    provider="gemini",
                    model="gemini-2.5-pro"
                )
                arbitration_prompt = f"{prompt}\n\nOVERRIDE PREVIOUS DEADLOCK. Conflicting options: {deadlocked_decisions}"
                arbitration_arm.evaluate_payload(arbitration_prompt, enable_tools=False)
                
                # Dynamic Fallback Mechanism
                if arbitration_arm.moltbook.status == 'SEAL':
                    logger.warning(f"Apex Arbitrator (Gemini) failed. Falling back to Anthropic...")
                    arbitration_arm = ArmState(
                        arm_id="apex_arbitrator_fallback",
                        route="mantle->arbitration",
                        provider="anthropic",
                        model="claude-3-5-sonnet-20241022"
                    )
                    arbitration_arm.evaluate_payload(arbitration_prompt, enable_tools=False)
                    
                    if arbitration_arm.moltbook.status == 'SEAL':
                        logger.warning(f"Fallback Arbitrator (Anthropic) failed. Falling back to OpenAI...")
                        arbitration_arm = ArmState(
                            arm_id="apex_arbitrator_final_fallback",
                            route="mantle->arbitration",
                            provider="openai",
                            model="o3-mini"
                        )
                        arbitration_arm.evaluate_payload(arbitration_prompt, enable_tools=False)
                
                # V3 DUAL-TRACK MEMORY: Compile pre-molt audit record including the deadlock override
                arms_data = [{
                    "arm_id": arm.arm_id,
                    "status": arm.moltbook.status,
                    "confidence_weight": arm.moltbook.confidence_weight,
                    "scratchpad": arm.moltbook.scratchpad
                } for arm in self.arms]
                
                arms_data.append({
                    "arm_id": arbitration_arm.arm_id,
                    "status": arbitration_arm.moltbook.status,
                    "confidence_weight": arbitration_arm.moltbook.confidence_weight,
                    "scratchpad": arbitration_arm.moltbook.scratchpad
                })
                
                final_decision = arbitration_arm.moltbook.crystallized_decision
                
                commit_audit_record(
                    prompt=prompt, 
                    final_decision=final_decision, 
                    arms_data=arms_data, 
                    metadata={"budget_remaining": self.budget.get_remaining(), "coherence": 1.0}
                )
                
                self.arms = [arbitration_arm]
                logger.info("Apex Arbitrator has resolved the deadlock. Forcing consensus.")
                
                self.molt_state()
                crystallize_to_memory(prompt, final_decision, 1.0)
                
                # MANUAL APPROVAL REQUIRED for CI/CD webhook. Autonomous deploy is disabled.
                # trigger_deployment_webhook(prompt, final_decision, 1.0)
                
                return final_decision
