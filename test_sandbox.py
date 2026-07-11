import logging
from arm_state import ArmState, MoltbookState
from action_tools import execute_secure_sandbox

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

arm = ArmState(
    arm_id="logic_arm_01",
    route="mantle->logic",
    moltbook=MoltbookState(status='ACTIVE', confidence_weight=1.0)
)

print("--- Testing Logic Arm Sandbox Execution ---")
result = execute_secure_sandbox(code="def calculate_trajectory(x,y): return x**2 + y**2")
arm.moltbook.scratchpad = (arm.moltbook.scratchpad or "") + f"\\nExecuted Sandbox: {result}"

print(f"\nArm Scratchpad after execution:\n{arm.moltbook.scratchpad}")
