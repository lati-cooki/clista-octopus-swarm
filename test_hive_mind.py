import pytest
from unittest.mock import patch
from arm_state import ArmState, MoltbookState
from budget import MetabolicBudget
from mantle import MantleOrchestrator

def test_hive_mind_pass_1():
    budget = MetabolicBudget(initial_capacity=100.0)
    mantle = MantleOrchestrator(budget=budget)
    prompt = "What is the optimal routing path for high latency but 0% drop?"
    
    budget.consume(25.0)
    assert budget.get_remaining() == 75.0
    
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
    assert decision_1 == "Path B provides 0% drop rate."
    assert mantle.budget.get_remaining() == 75.0

@patch('moltbook_archive.query_hive_mind')
def test_hive_mind_pass_2(mock_query_hive_mind):
    budget = MetabolicBudget(initial_capacity=100.0)
    mantle = MantleOrchestrator(budget=budget)
    prompt = "What is the optimal routing path for high latency but 0% drop?"
    
    new_arm = ArmState(
        arm_id="logic_arm_02",
        route="mantle->logic",
        moltbook=MoltbookState(status='ACTIVE', confidence_weight=1.0)
    )
    
    mock_query_hive_mind.return_value = "Path B provides 0% drop rate."
    
    recall_result = mock_query_hive_mind(query=prompt, arm_state=new_arm)
    new_arm.moltbook.crystallized_decision = recall_result
    mantle.arms = [new_arm]
    
    decision_2 = mantle.run_cycle(prompt=prompt)
    
    assert decision_2 == "Path B provides 0% drop rate."
    assert mantle.budget.get_remaining() == 100.0
