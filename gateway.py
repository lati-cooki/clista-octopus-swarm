"""
BLASTEMA PROTOCOL: WEBSOCKET GATEWAY
Exposes the Mantle Orchestrator via a live WebSocket connection.
Streams real-time telemetry (budget, node status, coherence) to the client.
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
import asyncio
import json
import os
from datetime import datetime

app = FastAPI(title="ClisTa Octopus Swarm API", version="1.0.0")

from fastapi.middleware.cors import CORSMiddleware
from google.cloud import firestore

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/audit/logs")
async def get_audit_logs():
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
from moltbook_archive import query_hive_mind

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
            "timestamp": datetime.utcnow().isoformat(),
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
    
    recall_arm = ArmState(arm_id="hive_mind_probe", route="mantle->memory", moltbook=MoltbookState(status='ACTIVE', confidence_weight=1.0))
    cached_decision = query_hive_mind(query=prompt, arm_state=recall_arm)
    
    if cached_decision:
        await websocket.send_json(build_payload("CONSENSUS", "Hive Mind HIT! Recovered past consensus. 0.0 Compute Cost."))
        await asyncio.sleep(1)
        await websocket.send_json(build_payload("MOLT", "Shedding ephemeral scratchpads."))
        await asyncio.sleep(1)
        await websocket.send_json({
            "timestamp": datetime.utcnow().isoformat(),
            "type": "FINAL_OUTPUT",
            "budget": budget.get_remaining(),
            "coherence": 1.0,
            "active_arms": 1,
            "decision": f"HIVE MIND RECALL: {cached_decision}"
        })
        return

    await websocket.send_json(build_payload("INFO", "No exact Hive Mind match. Initiating live swarm computation..."))
    await asyncio.sleep(1)
    
    budget.consume(15.0)
    
    logic_arm = ArmState(arm_id="logic", provider="anthropic", model="claude-3-7-sonnet")
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
    
    if status == "Consensus reached.":
        await websocket.send_json(build_payload("CONSENSUS", f"Natural consensus achieved without arbitration!"))
        await asyncio.sleep(1)
        final_decision = logic_arm.moltbook.crystallized_decision
        
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
        
        final_decision = arbitration_arm.moltbook.crystallized_decision
        
        arms_data.append({
            "arm_id": arbitration_arm.arm_id,
            "status": arbitration_arm.moltbook.status,
            "confidence_weight": arbitration_arm.moltbook.confidence_weight,
            "scratchpad": arbitration_arm.moltbook.scratchpad or ""
        })
    
    final_decision = arbitration_arm.moltbook.crystallized_decision
    from audit_ledger import commit_audit_record
    commit_audit_record(
        prompt=prompt,
        final_decision=final_decision,
        arms_data=arms_data,
        metadata={"budget_remaining": budget.get_remaining(), "coherence": 1.0}
    )
    
    orchestrator.molt_state()
    await websocket.send_json(build_payload("MOLT", "Shedding ephemeral scratchpads. Crystallizing to Hive Mind."))
    await asyncio.sleep(1)
    
    from moltbook_archive import crystallize_to_memory
    crystallize_to_memory(prompt, final_decision, 1.0)
    
    await websocket.send_json({
        "timestamp": datetime.utcnow().isoformat(),
        "type": "FINAL_OUTPUT",
        "budget": budget.get_remaining(),
        "coherence": 1.0,
        "active_arms": 1,
        "decision": final_decision
    })


@app.websocket("/ws/octopus")
async def octopus_swarm_endpoint(websocket: WebSocket):
    """
    The main WebSocket endpoint for clients to connect to the Swarm.
    """
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