from typing import Optional, Literal, Dict, Any
from pydantic import BaseModel, Field

class MoltbookState(BaseModel):
    status: Literal['ACTIVE', 'ABSTAIN', 'SEAL']
    confidence_weight: float = Field(ge=0.0, le=1.0)
    scratchpad: Optional[str] = None
    crystallized_decision: Optional[str] = None

class ArmState(BaseModel):
    arm_id: str
    route: str
    moltbook: MoltbookState
    execution_count: int = 0
    # other fields...

class ArmStateDB:
    # mock DB for arm states
    def __init__(self):
        self._states: Dict[str, ArmState] = {}
        
    def save(self, state: ArmState):
        self._states[state.arm_id] = state
        
    def get(self, arm_id: str) -> Optional[ArmState]:
        return self._states.get(arm_id)

class RouteRegistry:
    # tracks parent delegation routes
    pass
