"""
BLASTEMA PROTOCOL: ARM STATE (LIVE LLM INTEGRATION)
Manages the state of individual swarm nodes and routes tasks to live LLM providers.
Enforces the MoltbookState Pydantic schema across all models.
"""

import os
from typing import Literal, Optional
from pydantic import BaseModel, Field

# --- 1. THE MOLTBOOK SCHEMA ---
class MoltbookState(BaseModel):
    """The strict schema that all LLMs must return."""
    status: Literal['ACTIVE', 'ABSTAIN', 'SEAL'] = 'ACTIVE'
    confidence_weight: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence in the decision from 0.0 to 1.0")
    scratchpad: Optional[str] = Field(None, description="Internal reasoning and intermediate steps.")
    crystallized_decision: Optional[str] = Field(None, description="The final, pure answer to pass to the Mantle.")

# --- MOCK DEPENDENCIES ---
class RouteRegistry:
    def get_parent_delegation(self, arm_id):
        pass

class ArmState:
    def __init__(self, arm_id: str, route: str = "", provider: str = "openai", model: str = "gpt-4o", moltbook: Optional[MoltbookState] = None):
        self.arm_id = arm_id
        self.route = route
        self.provider = provider.lower()
        self.model = model
        
        self.moltbook = moltbook if moltbook else MoltbookState()
        self.execution_count = 0
        
    def get_route_registry(self):
        return RouteRegistry()

    def force_seal(self, reason: str):
        """Phase 1: The Tourniquet."""
        self.moltbook.status = 'SEAL'
        self.append_to_scratchpad(f"SEAL INITIATED DUE TO FATAL ERROR: {reason}")

    def append_to_scratchpad(self, text: str):
        if self.moltbook.scratchpad:
            self.moltbook.scratchpad += f"\n{text}"
        else:
            self.moltbook.scratchpad = text

    # --- 2. LIVE LLM ROUTING & EXECUTION ---
    def evaluate_payload(self, user_prompt: str, enable_tools: bool = False) -> MoltbookState:
        """
        Routes the prompt to the assigned LLM provider.
        Catches any API failures and forces a SEAL state to protect the orchestrator.
        """
        if os.getenv(f"{self.provider.upper()}_API_KEY"):
            self.append_to_scratchpad(f"Routing to LIVE {self.provider.upper()} ({self.model})...")
        else:
            self.append_to_scratchpad(f"SIMULATED Routing to {self.provider.upper()} ({self.model}) - API Key missing...")
            self.moltbook.status = 'ACTIVE'
            self.moltbook.confidence_weight = 0.85
            self.moltbook.crystallized_decision = "SIMULATED RESPONSE: API Keys not provided. Defaulting to GO."
            return self.moltbook
        
        system_instruction = (
            "You are an active node in the ClisTa Octopus Swarm. "
            "Analyze the prompt, detail your reasoning in the 'scratchpad', "
            "and provide a final answer in 'crystallized_decision' with a 'confidence_weight'."
        )
        
        if enable_tools:
            system_instruction += (
                "\n\nYou have access to external tools via the Action Layer.\n"
                "To invoke a tool, output a specific block in your 'scratchpad':\n"
                "[TOOL_REQUEST: tool_name({\"kwarg1\": \"value\"})]\n"
                "Available tools:\n"
                "1. execute_secure_sandbox(code: str)\n"
                "2. fetch_external_context(url: str, params: dict)\n"
                "3. query_clista_knowledge_graph(cypher_query: str)\n"
                "Make sure you format the JSON arguments correctly inside the TOOL_REQUEST block."
            )

        try:
            if self.provider == "openai":
                self._call_openai(system_instruction, user_prompt)
            elif self.provider == "anthropic":
                self._call_anthropic(system_instruction, user_prompt)
            elif self.provider == "gemini":
                self._call_gemini(system_instruction, user_prompt)
            else:
                raise ValueError(f"Unknown provider: {self.provider}")
                
            self.moltbook.status = 'ACTIVE'
            
        except Exception as e:
            self.force_seal(f"Provider Exception: {str(e)}")
            
        return self.moltbook

    # --- 3. PROVIDER INTEGRATIONS ---
    def _call_openai(self, system_prompt: str, user_prompt: str):
        import openai
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.beta.chat.completions.parse(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format=MoltbookState,
        )
        parsed_result = response.choices[0].message.parsed
        self._sync_state(parsed_result)

    def _call_gemini(self, system_prompt: str, user_prompt: str):
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        instruction = f"{system_prompt}\n\nRespond ONLY with raw, valid JSON matching this schema: {MoltbookState.model_json_schema()}"
        model = genai.GenerativeModel(self.model, system_instruction=instruction)
        response = model.generate_content(
            user_prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json"
            )
        )
        
        text = response.text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        
        parsed_result = MoltbookState.model_validate_json(text)
        self._sync_state(parsed_result)

    def _call_anthropic(self, system_prompt: str, user_prompt: str):
        import anthropic
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        instruction = f"{system_prompt}\n\nRespond ONLY with raw, valid JSON matching this schema: {MoltbookState.model_json_schema()}"
        response = client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=instruction,
            messages=[{"role": "user", "content": user_prompt}]
        )
        
        import re
        text = response.content[0].text
        match = re.search(r'```(?:json)?(.*?)```', text, re.DOTALL | re.IGNORECASE)
        if match:
            text = match.group(1).strip()
        else:
            text = text.strip()
        
        parsed_result = MoltbookState.model_validate_json(text)
        self._sync_state(parsed_result)

    def _sync_state(self, new_state: MoltbookState):
        """Applies the LLM's thought process back to the Arm's state."""
        self.moltbook.confidence_weight = new_state.confidence_weight
        self.moltbook.crystallized_decision = new_state.crystallized_decision
        if new_state.scratchpad:
            self.append_to_scratchpad(f"[LLM Thought Process]:\n{new_state.scratchpad}")


