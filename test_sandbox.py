import pytest
from arm_state import ArmState, MoltbookState
from action_tools import execute_secure_sandbox

def test_execute_secure_sandbox():
    arm = ArmState(
        arm_id="logic_arm_01",
        route="mantle->logic",
        moltbook=MoltbookState(status='ACTIVE', confidence_weight=1.0)
    )
    
    code = "def calculate_trajectory(x,y): return x**2 + y**2"
    result = execute_secure_sandbox(code=code)
    
    assert "[SANDBOX EXECUTION SUCCESS]" in result
    
    arm.moltbook.scratchpad = (arm.moltbook.scratchpad or "") + f"\nExecuted Sandbox: {result}"
    
    assert "Executed Sandbox:" in arm.moltbook.scratchpad
    assert "[SANDBOX EXECUTION SUCCESS]" in arm.moltbook.scratchpad
