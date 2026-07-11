import logging
from arm_state import ArmState, MoltbookState
from action_tools import execute_secure_sandbox

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

arm = ArmState(
    arm_id="logic_arm_01",
    route="mantle->logic",
    moltbook=MoltbookState(status='ACTIVE', confidence_weight=1.0)
)

print("--- Swarm Metabolic Decay Optimization ---")
print("Prompt: 'Calculate the exact remaining global budget if the starting budget is 5,000.0, and it degrades by a compounded 3.14% for every failed node over exactly 47 consecutive failures...'\n")

# Logic Arm writes the code to solve the prompt
python_code = """
start_budget = 5000.0
degrade_rate = 0.0314
failures = 47

remaining = start_budget * ((1 - degrade_rate) ** failures)
print(f"{remaining:.4f}")
"""

# Logic Arm calls the sandbox tool
result = execute_secure_sandbox(code=python_code)
arm.moltbook.scratchpad = (arm.moltbook.scratchpad or "") + f"\\nExecuted Sandbox: {result}"

# Logic arm receives result and crystallizes it
arm.moltbook.crystallized_decision = result

print(f"Scratchpad (Tool execution logged):")
print(arm.moltbook.scratchpad)

print("\nCrystallized Decision (Returned to Mantle):")
print(arm.moltbook.crystallized_decision)
