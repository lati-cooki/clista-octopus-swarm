import logging
from arm_state import ArmState, MoltbookState
from budget import MetabolicBudget
from mantle import MantleOrchestrator
from reflex_arc import probe_context, reflect_schema

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

print("=== Starting Local ADK Simulation ===")
budget = MetabolicBudget(initial_capacity=100.0)
mantle = MantleOrchestrator(budget=budget)

print("\n--- Injecting Prompt: 'Process the payload using the missing upstream variable.' ---")
# 1. Initialize Arm State
arm = ArmState(
    arm_id="arm_test_001",
    route="root->data_pipeline",
    moltbook=MoltbookState(
        status='ACTIVE',
        confidence_weight=1.0
    )
)
mantle.arms.append(arm)

print(f"Initial State: execution_count={arm.execution_count}, status={arm.moltbook.status}")

# 2. Arm attempts to recover missing context (1st tool call - allowed)
print("\n[Arm Action] Calling probe_context('upstream variable') to find missing context...")
probe_context(query='upstream variable', arm_state=arm)

print(f"\nAfter Step 1: execution_count={arm.execution_count}, status={arm.moltbook.status}")
print(f"Scratchpad Content:{arm.moltbook.scratchpad}")

# 3. Arm hallucinates/loops and attempts a 2nd tool call (blocked by circuit breaker)
print("\n[Arm Action] Calling reflect_schema() because it got confused...")
reflect_schema(arm_state=arm)

print(f"\nAfter Step 2: execution_count={arm.execution_count}, status={arm.moltbook.status}")
print(f"Scratchpad Content:{arm.moltbook.scratchpad}")

# 4. Mantle runs a cycle to evaluate the sealed arm
print("\n--- Mantle Evaluating Swarm State ---")
mantle.run_cycle()

print(f"\nFinal Arms in Mantle:")
for a in mantle.arms:
    print(f" - ID: {a.arm_id} | Status: {a.moltbook.status} | Route: {a.route}")
