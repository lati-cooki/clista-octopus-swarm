import logging
from arm_state import ArmState, MoltbookState
from budget import MetabolicBudget
from mantle import MantleOrchestrator
from moltbook_archive import query_hive_mind

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

print("==================================================")
print("       HIVE MIND: VECTOR MEMORY SIMULATION        ")
print("==================================================\n")

budget = MetabolicBudget(initial_capacity=100.0)
mantle = MantleOrchestrator(budget=budget)

prompt = "What is the optimal routing path for high latency but 0% drop?"

# --- PASS 1: Computation & Arguing (Budget Drops) ---
print(">>> PASS 1: Injecting complex prompt. No prior memory exists.")
budget.consume(25.0) # Simulate massive compute drain due to negotiation
arm_1 = ArmState(
    arm_id="logic_arm_01",
    route="mantle->logic",
    moltbook=MoltbookState(
        status='ACTIVE',
        confidence_weight=0.9,
        crystallized_decision="Path B provides 0% drop rate."
    )
)
mantle.arms.append(arm_1)
decision_1 = mantle.run_cycle(prompt=prompt)
print(f"Pass 1 Decision: {decision_1}")
print(f"Pass 1 Remaining Budget: {mantle.budget.get_remaining()} (Cost: 25.0)\n")

# --- PASS 2: Hive Mind Recall (Zero Compute) ---
print(">>> PASS 2: Injecting the exact same prompt...")
new_arm = ArmState(
    arm_id="logic_arm_02",
    route="mantle->logic",
    moltbook=MoltbookState(status='ACTIVE', confidence_weight=1.0)
)
# Arm queries the hive mind instead of doing math
recall_result = query_hive_mind(query=prompt, arm_state=new_arm)
new_arm.moltbook.crystallized_decision = recall_result
mantle.arms = [new_arm]

decision_2 = mantle.run_cycle(prompt=prompt)
print(f"Pass 2 Decision: {decision_2}")
print(f"Pass 2 Remaining Budget: {mantle.budget.get_remaining()} (Cost: 0.0)")
print("==================================================")
