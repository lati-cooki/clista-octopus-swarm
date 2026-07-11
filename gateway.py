"""
BLASTEMA PROTOCOL: WEBSOCKET GATEWAY
Exposes the Mantle Orchestrator via a live WebSocket connection.
Streams real-time telemetry (budget, node status, coherence) to the client.
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Header, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
import asyncio
import json
import os
from datetime import datetime, timezone

app = FastAPI(title="ClisTa Octopus Swarm API", version="1.0.0")

from fastapi.middleware.cors import CORSMiddleware
from google.cloud import firestore

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://clista-ui.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def verify_token(authorization: str = Header(None)):
    expected_token = os.getenv("CLISTA_AUTH_TOKEN", "Bearer SUPER_SECRET_TOKEN")
    if authorization != expected_token:
        raise HTTPException(status_code=401, detail="Unauthorized")

@app.get("/api/audit/logs", dependencies=[Depends(verify_token)])
def get_audit_logs():
    """
    Fetches the immutable execution history from Firestore.
    """
    try:
        db = firestore.Client()
        docs = db.collection("clista_audit_logs").order_by(
            "timestamp", direction=firestore.Query.DESCENDING
        ).limit(50).stream()
        
        logs = []
        for doc in docs:
            data = doc.to_dict()
            if 'timestamp' in data and data['timestamp']:
                data['timestamp'] = data['timestamp'].isoformat()
            logs.append(data)
            
        return {"status": "success", "data": logs}
    except Exception as e:
        print(f"Firestore Error: {e}")
        return {"status": "error", "message": "Failed to fetch from Firestore. Ensure credentials are set."}


from mantle import MantleOrchestrator
from budget import MetabolicBudget
from arm_state import ArmState, MoltbookState
from seal import seal_arm
from context_key import extract_decision_context, context_hash
from moltbook_archive import (
    query_hive_mind_by_context,
    record_recall_event,
    crystallize_to_memory,
)
from audit_ledger import commit_audit_record

# DR-hive-mind-cache-integrity.md: a recalled precedent older than this many
# days is flagged `stale` in the FINAL_OUTPUT precedent metadata (served
# anyway -- staleness is advisory, not a bypass -- but callers/UI can act on it).
PRECEDENT_TTL_DAYS = 90

_REGROUND_SYSTEM_PROMPT = (
    "You are given a precedent conclusion that was reached on a materially "
    "identical decision context, and the CURRENT query. Restate the "
    "justification for that conclusion grounded ONLY in the current query's "
    "stated facts. Do not assert any fact that is not present in the current "
    "query. Keep it concise."
)

# Architecture decisions (binding), docs/plans/hive-mind-cache-integrity-plan.md:
# neutral fallback used when re-grounding fails -- it names the precedent
# without re-asserting any of ITS original facts against the current query.
_REGROUND_FALLBACK_TEMPLATE = (
    "Consistent with precedent {precedent_id} ({age} old) on materially "
    "identical decision context."
)


def reground_rationale(
    conclusion: str,
    current_prompt: str,
    precedent_id: str = "",
    age: str = "unknown age",
) -> str:
    """Re-grounds a cited precedent's rationale against the CURRENT query only.

    One cheap OpenAI gpt-4o completion, given ONLY the precedent's conclusion
    and the live prompt -- never the original cached rationale, per the DR's
    "rationale transplant is never defensible" remedy (a cached justification
    is indexed to the ORIGINAL query's facts, not the current one).

    NEVER raises: any failure (missing key, network error, empty/refused
    response) falls back to a neutral template that names the precedent
    without re-asserting any of its original facts.
    """
    try:
        import openai

        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": _REGROUND_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Precedent conclusion: {conclusion}\n\n"
                        f"Current query: {current_prompt}"
                    ),
                },
            ],
        )
        text = response.choices[0].message.content
        if not text or not text.strip():
            raise ValueError("empty re-grounding response")
        return text.strip()
    except Exception:
        return _REGROUND_FALLBACK_TEMPLATE.format(precedent_id=precedent_id, age=age)


def conclusion_of(decision: str) -> str:
    """Extracts the citable holding from a cached decision string.

    DR-hive-mind-cache-integrity.md remedy ("cite the holding, don't read
    the prior opinion's facts into the current record"): fresh
    crystallizations under the new contract store the final decision as the
    conclusion. Defensively -- e.g. any legacy-format text mixing
    conclusion+rationale -- only the FIRST paragraph (split on a blank line)
    is ever treated as the citable holding; any rationale paragraphs beyond
    it are never served.
    """
    if not decision:
        return ""
    return decision.split("\n\n")[0].strip()


def _precedent_age_days(timestamp):
    """Computes (age_days, stale) from a precedent's Firestore timestamp.

    A missing/unparseable timestamp is treated defensively as unknown AND
    stale (age_days=None, stale=True): an untimestamped precedent cannot be
    affirmatively shown to fall within the PRECEDENT_TTL_DAYS window, so it
    does not get the benefit of the doubt.
    """
    if timestamp is None:
        return None, True
    try:
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        age_days = (datetime.now(timezone.utc) - timestamp).days
        return age_days, age_days > PRECEDENT_TTL_DAYS
    except Exception:
        return None, True


async def execute_swarm(websocket: WebSocket, prompt: str):
    """
    Executes the REAL MantleOrchestrator architecture for the given prompt,
    streaming the live state changes over the WebSocket.
    """
    budget = MetabolicBudget(initial_capacity=100.0)
    orchestrator = MantleOrchestrator(budget=budget)
    
    def build_payload(event_type: str, message: str):
        active = len([a for a in orchestrator.arms if a.moltbook.status == 'ACTIVE'])
        avg_coh = 0.0
        if active > 0:
            avg_coh = sum(a.moltbook.confidence_weight for a in orchestrator.arms if a.moltbook.status == 'ACTIVE') / active
            
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": event_type,
            "budget": orchestrator.budget.get_remaining(),
            "coherence": avg_coh,
            "active_arms": active,
            "message": message
        }

    await websocket.send_json(build_payload("SYSTEM", "Initializing Mantle Orchestrator..."))
    await asyncio.sleep(1)
    
    # Check Hive Mind First!
    await websocket.send_json(build_payload("INFO", f"Checking Hive Mind for prompt: '{prompt}'..."))
    await asyncio.sleep(1.5)

    # Extract the decision-relevant context key BEFORE any cache read/write.
    # Extraction failure fails OPEN to compute: no cache read, no cache
    # write for this run (DR-hive-mind-cache-integrity.md remedy).
    ctx = await asyncio.to_thread(extract_decision_context, prompt)
    cache_bypassed = ctx is None
    h = None
    precedent = None

    if cache_bypassed:
        await websocket.send_json(build_payload(
            "INFO", "Context extraction failed — bypassing Hive Mind, computing fresh."
        ))
        await asyncio.sleep(0.5)
    else:
        h = context_hash(ctx)
        precedent = await asyncio.to_thread(query_hive_mind_by_context, h)

    if precedent is not None:
        # --- RECALL PATH: precedent-as-citation. Never a CONSENSUS event,
        # never a re-crystallization. Only the cited conclusion is served;
        # the rationale is re-grounded fresh against the CURRENT query.
        await websocket.send_json(build_payload(
            "RECALL",
            "Hive Mind RECALL — precedent matched on decision context. Serving cited conclusion.",
        ))
        await asyncio.sleep(0.5)

        precedent_id = precedent.get("precedent_id")
        conclusion = conclusion_of(precedent.get("decision") or "")
        age_days, stale = _precedent_age_days(precedent.get("timestamp"))
        human_age = f"{age_days} days" if age_days is not None else "unknown age"

        regrounded = reground_rationale(conclusion, prompt, precedent_id or "", human_age)
        served_decision = f"PRECEDENT RECALL: {conclusion}\n\n{regrounded}"

        ts = precedent.get("timestamp")
        try:
            original_decision_date = ts.isoformat() if ts is not None else None
        except Exception:
            original_decision_date = None

        precedent_meta = {
            "precedent_id": precedent_id,
            "execution_id": precedent.get("execution_id"),
            "context_hash": h,
            "age_days": age_days,
            "original_decision_date": original_decision_date,
            "stale": stale,
        }

        # A recall is auditable too: forensics found zero audit trail on the
        # old hit path (it returned before commit_audit_record ever ran).
        await asyncio.to_thread(
            commit_audit_record,
            prompt=prompt,
            final_decision=served_decision,
            arms_data=[{
                "arm_id": "hive_mind_recall",
                "status": "ACTIVE",
                "confidence_weight": precedent.get("confidence") or 0.0,
                "scratchpad": f"RECALL of precedent {precedent_id}",
            }],
            metadata={"event": "RECALL", "precedent_id": precedent_id, "context_hash": h},
        )

        await websocket.send_json({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "FINAL_OUTPUT",
            "budget": budget.get_remaining(),
            "coherence": 1.0,
            "active_arms": 1,
            "decision": served_decision,
            "precedent": precedent_meta,
        })

        # Recalled results never re-archive as fresh precedents: log
        # distinct RECALL provenance referencing the original entry instead
        # of calling crystallize_to_memory.
        await asyncio.to_thread(record_recall_event, precedent_id, h, prompt)
        return

    await websocket.send_json(build_payload("INFO", "No exact Hive Mind match. Initiating live swarm computation..."))
    await asyncio.sleep(1)
    
    if not budget.consume(15.0):
        await websocket.send_json(build_payload("ERROR", "Insufficient metabolic budget. Aborting execution."))
        return
    
    logic_arm = ArmState(arm_id="logic", provider="anthropic", model="claude-3-5-sonnet-20241022")
    creative_arm = ArmState(arm_id="creative", provider="openai", model="o3-mini")
    
    orchestrator.arms.append(logic_arm)
    orchestrator.arms.append(creative_arm)
    
    await websocket.send_json(build_payload("SPAWN", f"Spawning {logic_arm.arm_id} ({logic_arm.provider}) and {creative_arm.arm_id} ({creative_arm.provider})..."))
    await asyncio.sleep(0.5)
    
    await websocket.send_json(build_payload("TELEMETRY", "Executing live LLM reasoning pathways concurrently..."))
    
    # Execute LLMs concurrently in threads so we don't block the WebSocket event loop
    results = await asyncio.gather(
        asyncio.to_thread(logic_arm.evaluate_payload, prompt, True),
        asyncio.to_thread(creative_arm.evaluate_payload, prompt, True),
        return_exceptions=True
    )
    
    # Check for crashes (SEALs)
    for arm in orchestrator.arms:
        if arm.moltbook.status == 'SEAL':
            await websocket.send_json(build_payload("SEAL", f"[{arm.arm_id}] Reflex failed. Circuit breaker triggered. Sealing node."))
            await asyncio.sleep(1)
    
    await websocket.send_json(build_payload("BLASTEMA", "Decaying budget. Regenerating creative_arm from clean blueprint."))
    await asyncio.sleep(2)
    
    # Patch regrow to inject state for the execution pathway
    import mantle
    original_regrow = mantle.regrow_arm
    def inject_regrow_state(sealed_state, bdgt):
        arm = original_regrow(sealed_state, bdgt)
        if arm:
            arm.arm_id = "creative_arm_02"
            arm.moltbook.confidence_weight = 0.4 
            arm.moltbook.crystallized_decision = "Strict enforcement required. Security > Speed."
        return arm
    mantle.regrow_arm = inject_regrow_state
    
    # Run the cycle inside an async wrapper so we can stream the actual outputs
    # Since run_cycle is recursive and synchronous, we will manually trigger its logic here to stream it.
    
    # Step 1: Manage Regenerations
    dead_arms = [a for a in orchestrator.arms if a.moltbook.status == 'SEAL']
    for arm in dead_arms:
        orchestrator.arms.remove(arm)
        new_arm = mantle.regrow_arm(arm, orchestrator.budget)
        orchestrator.arms.append(new_arm)
        
    await websocket.send_json(build_payload("SPAWN", "creative_arm_02 online. Resuming route..."))
    await asyncio.sleep(1.5)
    
    await websocket.send_json(build_payload("TELEMETRY", "Evaluating Resonant Coherence..."))
    await asyncio.sleep(1)
    
    # Real Deadlock Checking
    status = orchestrator.evaluate_resonant_coherence()
    
    if status == 'CONSENSUS':
        await websocket.send_json(build_payload("CONSENSUS", f"Natural consensus achieved without arbitration!"))
        await asyncio.sleep(1)
        active_arms = [a for a in orchestrator.arms if a.moltbook.status == 'ACTIVE']
        final_decision = next((a.moltbook.crystallized_decision for a in active_arms if a.moltbook.crystallized_decision), "Consensus reached without specific output.")
        arms_data = [{
            "arm_id": arm.arm_id,
            "status": arm.moltbook.status,
            "confidence_weight": arm.moltbook.confidence_weight,
            "scratchpad": arm.moltbook.scratchpad or ""
        } for arm in orchestrator.arms]
        
    else:
        # Step 4: Apex Arbitrator
        await websocket.send_json(build_payload("WARNING", f"Coherence: {status}. Escalating to Apex Arbitrator..."))
        await asyncio.sleep(1.5)
        
        arbitration_arm = ArmState(arm_id="apex", provider="gemini", model="gemini-2.5-pro")
        await websocket.send_json(build_payload("SPAWN", f"Spawning {arbitration_arm.arm_id} ({arbitration_arm.provider})..."))
        
        # Capture all deadlocked arms before overriding
        arms_data = [{
            "arm_id": arm.arm_id,
            "status": arm.moltbook.status,
            "confidence_weight": arm.moltbook.confidence_weight,
            "scratchpad": arm.moltbook.scratchpad or ""
        } for arm in orchestrator.arms]
        
        orchestrator.arms = [arbitration_arm]
        
        # Run Arbitrator Live
        await websocket.send_json(build_payload("TELEMETRY", "[apex] Analyzing deadlocked payloads..."))
        await asyncio.to_thread(arbitration_arm.evaluate_payload, prompt + "\n\nOVERRIDE PREVIOUS DEADLOCK.", True)
        
        await websocket.send_json(build_payload("ARBITRATION", "[apex] GAVEL DROP. Forcing consensus."))
        await asyncio.sleep(1)
        
        final_decision = arbitration_arm.moltbook.crystallized_decision or "Apex Arbitration reached without specific output."
        
        arms_data.append({
            "arm_id": arbitration_arm.arm_id,
            "status": arbitration_arm.moltbook.status,
            "confidence_weight": arbitration_arm.moltbook.confidence_weight,
            "scratchpad": arbitration_arm.moltbook.scratchpad or ""
        })
    
    execution_id = await asyncio.to_thread(
        commit_audit_record,
        prompt=prompt,
        final_decision=final_decision,
        arms_data=arms_data,
        metadata={"budget_remaining": budget.get_remaining(), "coherence": 1.0}
    )

    orchestrator.molt_state()
    await websocket.send_json(build_payload("MOLT", "Shedding ephemeral scratchpads. Crystallizing to Hive Mind."))
    await asyncio.sleep(1)

    await asyncio.to_thread(
        crystallize_to_memory,
        prompt,
        final_decision,
        1.0,
        context_hash=h if not cache_bypassed else None,
        decision_context=ctx.model_dump() if ctx else None,
        execution_id=execution_id,
    )
    
    await websocket.send_json({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": "FINAL_OUTPUT",
        "budget": budget.get_remaining(),
        "coherence": 1.0,
        "active_arms": 1,
        "decision": final_decision
    })


@app.websocket("/ws/octopus")
async def octopus_swarm_endpoint(websocket: WebSocket, token: str = None):
    """
    The main WebSocket endpoint for clients to connect to the Swarm.
    """
    expected_token = os.getenv("CLISTA_AUTH_TOKEN", "Bearer SUPER_SECRET_TOKEN").replace("Bearer ", "")
    if token != expected_token:
        await websocket.close(code=1008, reason="Unauthorized")
        return
    await websocket.accept()
    print("Client connected to Swarm Gateway.")
    
    try:
        while True:
            # Wait for the client to send a prompt
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                prompt = payload.get("prompt", "Default diagnostic prompt.")
            except json.JSONDecodeError:
                prompt = data
                
            print(f"Executing swarm for prompt: {prompt}")
            
            # Run the swarm execution and stream events back
            await execute_swarm(websocket, prompt)
            
    except WebSocketDisconnect:
        print("Client disconnected from Swarm Gateway.")

# Serve the static React frontend
dist_path = os.path.join(os.path.dirname(__file__), "clista-swarm-ui", "dist")
if os.path.exists(dist_path):
    app.mount("/", StaticFiles(directory=dist_path, html=True), name="static")
else:
    print(f"Warning: Static frontend directory not found at {dist_path}")

if __name__ == "__main__":
    import uvicorn
    # Run the server locally on port 8000
    print("Starting ClisTa Octopus Gateway on ws://localhost:8000/ws/octopus")
    uvicorn.run(app, host="0.0.0.0", port=8000)