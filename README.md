# 🐙 ClisTa Octopus Swarm

The ClisTa Octopus Swarm is a fully autonomous, self-healing, multi-agent AI orchestration engine. Built on the Blastema Protocol, this framework maps biological fault-tolerance into a deterministic neural architecture.

Unlike traditional multi-agent systems that crash or hallucinate in infinite loops, the Octopus Swarm is strictly bound by metabolic compute limits, circuit breakers, and an autonomous deadlock resolution system.

## 🧠 Core Architecture
The architecture consists of a central orchestrator (The Mantle) and distributed worker nodes (The Arms).

- **The Mantle Orchestrator (`mantle.py`)**: Manages the global `MetabolicBudget`, routes payloads, and enforces network coherence (consensus).
- **Multi-Brain Arms (`arm_state.py`)**: Model-agnostic nodes capable of running OpenAI, Anthropic, or Gemini interchangeably. Arms evaluate payloads and return structured Pydantic schemas (`MoltbookState`).
- **The Tourniquet (`reflex_arc.py`)**: A strict circuit breaker. If an Arm hits an API rate limit, API timeout, or a recursive hallucination loop, the Tourniquet instantly forces a `SEAL` state. The exception is swallowed, the node is quarantined, and the Mantle regenerates a clean replacement.
- **Apex Arbitrator Override**: If the Swarm exhausts its negotiation passes without reaching a mathematically sound consensus (a deadlock), an Apex Arbitrator is dynamically spawned to force a 1.0 confidence resolution.

## 💾 The Hive Mind (Zero-Compute Caching)
Every successfully crystallized consensus is permanently archived to Google Cloud Firestore via `moltbook_archive.py`.

When the Swarm encounters a prompt, the arms first query the Hive Mind. If a past precedent exists (like a previously resolved deadlock), the Swarm instantly recalls the decision. This allows the network to bypass massive compute costs and solve complex, repetitive tasks for 0.0 budget expenditure.

## 📊 Glassmorphic Telemetry Dashboard
The Swarm is visually accessible via a React/Vite dashboard (`App.jsx`) connected to a live FastAPI WebSocket Gateway (`gateway.py`).

Watch the architecture heal itself in real-time:
- 🔴 **SEAL Events**: Visual tourniquet alarms when nodes crash.
- 📉 **Budget Decay**: Physical tracking of compute expenditure.
- ⚖️ **Arbitration Overrides**: Amber pulses when the Apex Arbitrator forces a deadlock resolution.
- 🟢 **Crystallization**: The final, pristine output stripped of its messy reasoning scratchpads.

## 🚀 Deployment (Google Cloud Run)
The ClisTa Octopus Swarm is designed to be deployed as a unified, serverless container on GCP.

### Prerequisites
- Google Cloud CLI (`gcloud`) installed and authenticated.
- A GCP Project with Cloud Run and Firestore APIs enabled.

### 1. Deploy the Swarm
Navigate to the root directory and execute the following command to package the React UI and Python backend into a single container:

```bash
gcloud run deploy clista-octopus-swarm \
  --source . \
  --region us-central1 \
  --allow-unauthenticated
```

### 2. Configure Environment Variables
Once deployed, navigate to your Cloud Run service in the GCP Console and inject your preferred model API keys as Environment Variables:
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `GEMINI_API_KEY`

## 🛡️ Example Use Case: Model Risk Management (MRM)
The strict Maker-Checker nature of the Swarm makes it ideal for enterprise compliance tasks.
- Assign `logic_arm` (Claude 3.5 Sonnet) as the Model Validator.
- Assign `creative_arm` (GPT-4o) as the Model Developer.
- Allow them to friction-test quantitative code via the `execute_secure_sandbox` tool.
- Rely on the Moltbook Archive to generate an immutable, bloat-free audit trail in Firestore for compliance review.
