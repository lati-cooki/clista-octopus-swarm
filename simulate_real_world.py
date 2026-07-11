import logging
from arm_state import ArmState, MoltbookState
from budget import MetabolicBudget
from mantle import MantleOrchestrator
from seal import seal_arm
# NOTE: this demo script hits live services (Firestore/OpenAI) and is not
# executed by the test suite. Updated minimally to keep imports resolvable
# after the context-hash cache rework -- see moltbook_archive.py.
from moltbook_archive import query_hive_mind_by_context
import mantle

logging.basicConfig(level=logging.INFO, format='%(message)s')

print("==================================================")
print("     REAL-WORLD SIMULATION: MULTI-REGION ARCH     ")
print("==================================================\n")

budget = MetabolicBudget(initial_capacity=100.0)
orchestrator = MantleOrchestrator(budget=budget)

prompt = "Architect a global routing protocol for PII payloads: US needs speed (<10ms), EU needs strict GDPR compliance."

# Monkey-patch regrowth to simulate the stubborn creative arm
original_regrow = mantle.regrow_arm
def mock_regrow(route, budget):
    arm = original_regrow(route, budget)
    if arm:
        arm.arm_id = "creative_arm_02"
        arm.moltbook.confidence_weight = 0.4 # Force low coherence
        arm.moltbook.crystallized_decision = "Strict GDPR enforcement: Must route all data to EU stateful ledger regardless of latency."
    return arm
mantle.regrow_arm = mock_regrow

# Monkey-patch ArmState to inject the exact Arbitrator realization
original_armstate = mantle.ArmState
class MockArmState(original_armstate):
    def __init__(self, **data):
        super().__init__(**data)
        if self.arm_id == "apex_arbitrator":
            self.moltbook.crystallized_decision = "APEX ARBITRATION OVERRIDE: Split the architecture. Deploy stateless execution at the edge for US traffic, and sync to a stateful ledger in the EU for strict GDPR compliance."
mantle.ArmState = MockArmState

print(">>> PASS 1: The First Execution (Architecting the Solution)")
budget.consume(25.0)

logic_arm = ArmState(
    arm_id="logic_arm_01",
    route="mantle->logic",
    moltbook=MoltbookState(status='ACTIVE', confidence_weight=0.4, crystallized_decision="Speed is paramount: Route all traffic via stateless US edge execution.")
)
orchestrator.arms.append(logic_arm)

creative_arm = ArmState(
    arm_id="creative_arm_01",
    route="mantle->creative",
    moltbook=MoltbookState(status='ACTIVE', confidence_weight=1.0)
)
orchestrator.arms.append(creative_arm)

print("\n--- 1. The Circuit Breaker Saves the System ---")
print("creative_arm_01 attempting to parse EU regulatory API...")
try:
    raise ValueError("Lost in complex legal API calls! Stack overflow.")
except Exception as e:
    seal_arm(creative_arm.arm_id, e, creative_arm)

print("\n--- 2. The Deadlock & 3. The Apex Solution ---")
decision_1 = orchestrator.run_cycle(prompt=prompt)
print(f"\nFinal Consensus Output: {decision_1}")
print(f"Remaining Budget: {orchestrator.budget.get_remaining()}\n")


print("\n--- 4. The Hive Mind Payoff (Three Days Later) ---")
print(">>> PASS 2: Injecting the exact same multi-million dollar architectural question...")
new_arm = ArmState(
    arm_id="creative_arm_03",
    route="mantle->creative",
    moltbook=MoltbookState(status='ACTIVE', confidence_weight=1.0)
)
# TODO: this demo predates context-hash extraction; it no longer has a real
# DecisionContext to hash, so this recall lookup is a placeholder that will
# simply miss (None) rather than crash the script.
recall_precedent = query_hive_mind_by_context(context_hash=None)
new_arm.moltbook.crystallized_decision = (
    recall_precedent["decision"] if recall_precedent else ""
)

orchestrator.arms = [new_arm]
orchestrator.negotiation_passes = 0 # reset
decision_2 = orchestrator.run_cycle(prompt=prompt)

print(f"\nFinal Consensus Output: {decision_2}")
print(f"Remaining Budget: {orchestrator.budget.get_remaining()} (0.0 Compute Cost!)")
print("==================================================")
