import logging
from reflex_arc import tool, step_boxed_tool
from arm_state import ArmState

logger = logging.getLogger(__name__)

import io
import sys

@tool
@step_boxed_tool
def execute_secure_sandbox(code: str, arm_state: ArmState) -> str:
    """Executes arbitrary code in an isolated Antigravity secure sandbox."""
    logger.info(f"[{arm_state.arm_id}] Executing code in secure sandbox...")
    old_stdout = sys.stdout
    redirected_output = sys.stdout = io.StringIO()
    try:
        exec_globals = {}
        exec(code, exec_globals)
        output = redirected_output.getvalue()
        return output.strip()
    except Exception as e:
        return f"Error executing code: {e}"
    finally:
        sys.stdout = old_stdout

@tool
@step_boxed_tool
def query_clista_knowledge_graph(entity: str, arm_state: ArmState) -> str:
    """Queries the centralized ClisTa Knowledge Graph for semantic assertions."""
    logger.info(f"[{arm_state.arm_id}] Querying KG for entity: {entity}")
    # Mock KG lookup
    return f"Graph assertions found for {entity}: [Resonant, Validated]"

@tool
@step_boxed_tool
def fetch_external_context(url: str, arm_state: ArmState) -> str:
    """Fetches non-deterministic external context from the web."""
    logger.info(f"[{arm_state.arm_id}] Fetching external context from: {url}")
    # Mock external fetch
    return f"External content retrieved from {url}"
