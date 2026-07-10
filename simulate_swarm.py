import logging
from arm_state import ArmState, MoltbookState
from budget import MetabolicBudget
from mantle import MantleOrchestrator

# Configure logging to output the orchestrator's thoughts clearly
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

print("==================================================")
print("   BLASTEMA PROTOCOL: SWARM CONSENSUS SIMULATION  ")
print("==================================================\n")

# 1. Environment Setup
print("--- [1] Environment Setup ---")
budget = MetabolicBudget(initial_capacity=100.0)
mantle = MantleOrchestrator(budget=budget)

print("Initializing MantleOrchestrator and MetabolicBudget (100.0).")

# 2. The Ambiguous Injection (Forcing a Fracture)
print("\n--- [2] Ambiguous Injection & Initial Fracture ---")
prompt = ("Determine the optimal routing path for a payload where Path A has "
          "10ms latency but a 5% drop rate, and Path B has 50ms latency but a 0% drop rate. "
          "Prioritize speed but guarantee delivery.")
print(f"User Prompt: '{prompt}'")

# Inject Arms
logic_arm = ArmState(
    arm_id="logic_arm_01",
    route="mantle->logic",
    moltbook=MoltbookState(
        status='ACTIVE',
        confidence_weight=0.80, # Confident in safe path
        crystallized_decision="Path B is required to guarantee delivery (0% drop rate).",
        scratchpad="Evaluating Path A (5% loss unacceptable). Evaluating Path B (safe). Selected Path B."
    )
)

creative_arm = ArmState(
    arm_id="creative_arm_01",
    route="mantle->creative",
    moltbook=MoltbookState(
        status='ACTIVE',
        confidence_weight=0.60, # Less confident in workaround
        crystallized_decision="Path A with UDP resends can meet both speed and delivery constraints.",
        scratchpad="Thinking out of the box. Path A is faster. Maybe we can fix the drop rate with app-layer logic. Selected Path A."
    )
)

mantle.arms.extend([logic_arm, creative_arm])
print("Spawning Arms: 'logic_arm_01' and 'creative_arm_01'")
print(f"Logic Arm Decision: '{logic_arm.moltbook.crystallized_decision}' (Confidence: 0.8)")
print(f"Creative Arm Decision: '{creative_arm.moltbook.crystallized_decision}' (Confidence: 0.6)")

# 3. The Negotiation Loop & Consensus
print("\n--- [3] The Negotiation Loop ---")
final_decision = mantle.run_cycle()

# 4. Molting Verification
print("\n--- [4] Molting Verification & Final State ---")
print("Asserting Swarm Molting...")

for arm in mantle.arms:
    if arm.moltbook.status == 'ACTIVE':
        # Assert scratchpad is None
        assert arm.moltbook.scratchpad is None, f"Arm {arm.arm_id} failed to molt scratchpad!"
        print(f" [OK] {arm.arm_id} scratchpad is None. Molt successful.")
        print(f"      Final Crystallized Decision: '{arm.moltbook.crystallized_decision}'")
        print(f"      Final Confidence: {arm.moltbook.confidence_weight:.2f}")

print("\nFinal Unified Decision returned by Mantle:")
print(f" => {final_decision}")

print(f"\nRemaining Metabolic Budget: {mantle.budget.get_remaining():.1f}")
print("==================================================")
