from reflex_arc import tool
import requests
import json
import urllib.parse

# --- THE ACTION LAYER (EXECUTION TOOLS) ---
# These tools allow the arms to mutate external state and gather live data.
# They are not bound by the 1-step reflex limit, but should handle their own timeouts gracefully.

@tool
def execute_secure_sandbox(code: str) -> str:
    """
    Executes Python code in an isolated, secure sandbox.
    Use this strictly for deterministic math, data formatting, or complex logic calculations.
    DO NOT use this to attempt network requests.
    """
    try:
        # In the Antigravity ADK, this would route to a secure gVisor container
        # For local execution, we mock the output structure.
        # WARNING: Never run raw eval() in production without a true sandbox.
        
        # Mocking sandbox execution for the framework setup
        return f"[SANDBOX EXECUTION SUCCESS] Evaluated logic block. (Length: {len(code)} chars)"
    except Exception as e:
        return f"[SANDBOX ERROR] Execution failed: {str(e)}. Review your logic and try again."

@tool
def fetch_external_context(url: str, params: dict = None) -> str:
    """
    Fetches raw text data from an external REST API or URL.
    Use this when your internal session context lacks real-world or real-time facts.
    """
    try:
        # Apply strict timeouts to prevent the arm from hanging and draining the budget
        query_string = f"?{urllib.parse.urlencode(params)}" if params else ""
        full_url = f"{url}{query_string}"
        
        response = requests.get(full_url, timeout=5.0)
        response.raise_for_status()
        
        # Truncate massive payloads to prevent context window explosion
        content = response.text[:2000] 
        return f"[FETCH SUCCESS] Payload snippet: {content}..."
    
    except requests.exceptions.Timeout:
        return "[FETCH ERROR] The external service timed out. Do not retry more than once."
    except requests.exceptions.RequestException as e:
        return f"[FETCH ERROR] Network error occurred: {str(e)}"

@tool
def query_clista_knowledge_graph(cypher_query: str) -> str:
    """
    Executes a Cypher query against the internal ClisTa knowledge graph.
    Use this to find relationships between users, datasets, or historical consensus records.
    """
    # Mocking a graph database connection
    # If a query is malformed, it should return an explicit error so the arm can self-correct.
    if "MATCH" not in cypher_query.upper():
        return "[GRAPH ERROR] Malformed Cypher query. 'MATCH' clause required."
    
    return "[GRAPH SUCCESS] Found 3 related nodes in the Lati ecosystem."