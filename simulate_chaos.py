import logging
from arm_state import ArmState, MoltbookState
from budget import MetabolicBudget
from mantle import MantleOrchestrator
from seal import seal_arm

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

print("==================================================")
print("   BLASTEMA PROTOCOL: CATASTROPHIC FAILURE SIM    ")
print("==================================================\n")

print("--- [1] Environment Setup ---")
# Budget is 25.0. Regrowth costs 10.0. 
# We expect 2 arms to regrow successfully, and the 3rd to remain SEALED.
budget = MetabolicBudget(initial_capacity=25.0) 
mantle = MantleOrchestrator(budget=budget)
print(f"Initial Budget: {budget.get_remaining()}")

print("\n--- [2] Spawning Arms ---")
arms = []
for i in range(3):
    arm = ArmState(
        arm_id=f"worker_arm_{i}",
        route=f"mantle->worker_{i}",
        moltbook=MoltbookState(status='ACTIVE', confidence_weight=1.0)
    )
    arms.append(arm)
mantle.arms.extend(arms)

print(f"Spawned {len(arms)} active arms.")

print("\n--- [3] The Disaster Event ---")
print("Simulating a severe hallucination leading to a fatal Exception in all arms...")

for arm in mantle.arms:
    try:
        # Simulating a massive crash during arm processing
        raise ValueError(f"CRITICAL COGNITIVE COLLAPSE in {arm.arm_id}")
    except Exception as e:
        # The tourniquet intercepts the exception, ensuring the process never crashes
        seal_arm(arm.arm_id, e, arm)

print("\nState after Tourniquet (Before Mantle Cycle):")
for arm in mantle.arms:
    print(f" - {arm.arm_id}: Status={arm.moltbook.status}")
    print(f"   Scratchpad Trapped: {arm.moltbook.scratchpad}")

print("\n--- [4] Mantle Regeneration Cycle ---")
# The Mantle will attempt to regrow all 3 SEALED arms
mantle.run_cycle()

print("\n--- [5] Final System State ---")
print(f"Remaining Metabolic Budget: {mantle.budget.get_remaining()}")
for arm in mantle.arms:
    print(f" - {arm.arm_id}: Status={arm.moltbook.status}")

print("==================================================")
