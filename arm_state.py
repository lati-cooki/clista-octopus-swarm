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
    def __init__(self, arm_id: str, route: str = "", provider: str = "openai", model: str = "gpt-4o"):
        self.arm_id = arm_id
        self.route = route
        self.provider = provider.lower()
        self.model = model
        
        self.moltbook = MoltbookState()
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
    def evaluate_payload(self, user_prompt: str) -> MoltbookState:
        """
        Routes the prompt to the assigned LLM provider.
        Catches any API failures and forces a SEAL state to protect the orchestrator.
        """
        self.append_to_scratchpad(f"Routing to {self.provider.upper()} ({self.model})...")
        
        system_instruction = (
            "You are an active node in the ClisTa Octopus Swarm. "
            "Analyze the prompt, detail your reasoning in the 'scratchpad', "
            "and provide a final answer in 'crystallized_decision' with a 'confidence_weight'."
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
            # If the API times out, throws a 500, or hallucinations break the JSON parser:
            # Swallow the error into the scratchpad and quarantine the arm!
            self.force_seal(f"Provider Exception: {str(e)}")
            
        return self.moltbook

    # --- 3. PROVIDER INTEGRATIONS ---
    def _call_openai(self, system_prompt: str, user_prompt: str):
        import openai # Requires: pip install openai
        
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # We use .parse() to guarantee the Moltbook schema is returned
        response = client.beta.chat.completions.parse(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format=MoltbookState,
        )
        
        # Update our internal state with the LLM's structured output
        parsed_result = response.choices[0].message.parsed
        self._sync_state(parsed_result)

    def _call_gemini(self, system_prompt: str, user_prompt: str):
        import google.generativeai as genai # Requires: pip install google-generativeai
        
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model = genai.GenerativeModel(self.model, system_instruction=system_prompt)
        
        # Enforce the Pydantic schema natively in the Gemini generation config
        response = model.generate_content(
            user_prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=MoltbookState.model_json_schema()
            )
        )
        
        parsed_result = MoltbookState.model_validate_json(response.text)
        self._sync_state(parsed_result)

    def _call_anthropic(self, system_prompt: str, user_prompt: str):
        import anthropic # Requires: pip install anthropic
        
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        
        # Anthropic prefers prompt-level guidance for JSON structure in conjunction with tool use
        instruction = f"{system_prompt}\n\nRespond ONLY with raw, valid JSON matching this schema: {MoltbookState.model_json_schema()}"
        
        response = client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=instruction,
            messages=[{"role": "user", "content": user_prompt}]
        )
        
        parsed_result = MoltbookState.model_validate_json(response.content[0].text)
        self._sync_state(parsed_result)

    def _sync_state(self, new_state: MoltbookState):
        """Applies the LLM's thought process back to the Arm's state."""
        self.moltbook.confidence_weight = new_state.confidence_weight
        self.moltbook.crystallized_decision = new_state.crystallized_decision
        if new_state.scratchpad:
            self.append_to_scratchpad(f"[LLM Thought Process]:\n{new_state.scratchpad}")
