import pytest
from arm_state import ArmState, MoltbookState
from action_tools import execute_secure_sandbox

def test_metabolic_decay_optimization():
    arm = ArmState(
        arm_id="logic_arm_01",
        route="mantle->logic",
        moltbook=MoltbookState(status='ACTIVE', confidence_weight=1.0)
    )
    
    python_code = """
start_budget = 5000.0
degrade_rate = 0.0314
failures = 47

remaining = start_budget * ((1 - degrade_rate) ** failures)
print(f"{remaining:.4f}")
"""
    result = execute_secure_sandbox(code=python_code)
    
    assert "[SANDBOX EXECUTION SUCCESS]" in result
    
    arm.moltbook.scratchpad = (arm.moltbook.scratchpad or "") + f"\nExecuted Sandbox: {result}"
    arm.moltbook.crystallized_decision = result
    
    assert "Executed Sandbox:" in arm.moltbook.scratchpad
    assert arm.moltbook.crystallized_decision == result
