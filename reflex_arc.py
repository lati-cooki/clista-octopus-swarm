import functools
import json
from typing import Callable, Any
from arm_state import ArmState, MoltbookState, RouteRegistry

# Mock ADK tool decorator
def tool(func):
    """Antigravity ADK tool decorator."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper

def step_boxed_tool(func: Callable) -> Callable:
    """
    The Circuit Breaker (1-Step Limit).
    Interceptor/decorator that enforces a strict 1-step limit on tool execution.
    Requires an 'arm_state' kwarg to be passed to track execution count.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        arm_state: ArmState = kwargs.get('arm_state')
        if not arm_state:
            raise ValueError("arm_state must be provided to a step-boxed tool.")
            
        if arm_state.execution_count >= 1:
            # Forcefully inject SEAL status
            arm_state.moltbook.status = 'SEAL'
            arm_state.moltbook.confidence_weight = 0.0
            error_msg = f"CIRCUIT BREAKER TRIGGERED: Tool {func.__name__} blocked. Limit of 1 step exceeded."
            
            # Append to scratchpad
            current_scratchpad = arm_state.moltbook.scratchpad or ""
            arm_state.moltbook.scratchpad = current_scratchpad + f"\n[ERROR] {error_msg}"
            
            return error_msg
            
        # First call, increment and execute
        arm_state.execution_count += 1
        result = func(*args, **kwargs)
        
        # Append result to scratchpad exclusively
        current_scratchpad = arm_state.moltbook.scratchpad or ""
        arm_state.moltbook.scratchpad = current_scratchpad + f"\n[{func.__name__} Result]: {result}"
        
        return result
    return wrapper

@tool
@step_boxed_tool
def probe_context(query: str, arm_state: ArmState) -> str:
    """
    Performs a semantic search against the Antigravity Session history. 
    This helps the arm recover missing context without asking the user.
    """
    # Mock semantic search against session history
    return f"Context matching '{query}' from session history."

@tool
@step_boxed_tool
def reflect_schema(arm_state: ArmState) -> str:
    """
    Returns a stringified JSON schema of the MoltbookState Pydantic model. 
    This allows the arm to self-correct formatting errors mid-generation.
    """
    return json.dumps(MoltbookState.model_json_schema(), indent=2)

@tool
@step_boxed_tool
def verify_lineage(arm_state: ArmState) -> str:
    """
    Retrieves the parent delegation route from the RouteRegistry so the arm 
    can verify if the upstream assumptions were flawed.
    """
    # Mock route registry lookup
    # In a real scenario, this would look up arm_state.route in the RouteRegistry
    return f"Verified Lineage for route {arm_state.route}. Upstream is valid."
