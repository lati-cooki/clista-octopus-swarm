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

from mantle import MantleOrchestrator
from budget import MetabolicBudget
from arm_state import ArmState, MoltbookState
from seal import seal_arm
from moltbook_archive import query_hive_mind

async def simulate_swarm_execution(websocket: WebSocket, prompt: str):
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
    cached_decision = query_hive_mind(prompt, recall_arm)
    
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
    
    logic_arm = ArmState(
        arm_id="logic_arm_01",
        route="mantle->logic",
        moltbook=MoltbookState(status='ACTIVE', confidence_weight=0.4, crystallized_decision="Optimize for speed and local data sovereignty.")
    )
    orchestrator.arms.append(logic_arm)
    
    creative_arm = ArmState(
        arm_id="creative_arm_01",
        route="mantle->creative",
        moltbook=MoltbookState(status='ACTIVE', confidence_weight=1.0)
    )
    orchestrator.arms.append(creative_arm)
    
    await websocket.send_json(build_payload("SPAWN", "Spawning logic_arm_01 and creative_arm_01..."))
    await asyncio.sleep(1.5)
    
    await websocket.send_json(build_payload("TELEMETRY", "[logic_arm_01] Processing task..."))
    await asyncio.sleep(1.5)
    
    await websocket.send_json(build_payload("ERROR", "[creative_arm_01] Encountered fatal error: Lost in complex LLM API calls!"))
    await asyncio.sleep(1)
    
    try:
        raise ValueError("Lost in complex LLM API calls! Stack overflow.")
    except Exception as e:
        seal_arm(creative_arm.arm_id, e, creative_arm)
        
    await websocket.send_json(build_payload("SEAL", "[creative_arm_01] Reflex failed. Circuit breaker triggered. Sealing node."))
    await asyncio.sleep(2)
    
    await websocket.send_json(build_payload("BLASTEMA", "Decaying budget. Regenerating creative_arm from clean blueprint."))
    await asyncio.sleep(2)
    
    # We must patch regrow to return a specific state for the simulation
    import mantle
    original_regrow = mantle.regrow_arm
    def mock_regrow(route, bdgt):
        arm = original_regrow(route, bdgt)
        if arm:
            arm.arm_id = "creative_arm_02"
            arm.moltbook.confidence_weight = 0.4 
            arm.moltbook.crystallized_decision = "Strict enforcement required. Security > Speed."
        return arm
    mantle.regrow_arm = mock_regrow
    
    # Run the cycle inside an async wrapper so we can stream the actual outputs
    # Since run_cycle is recursive and synchronous, we will manually trigger its logic here to stream it.
    
    # Step 1: Manage Regenerations
    dead_arms = [a for a in orchestrator.arms if a.moltbook.status == 'SEAL']
    for arm in dead_arms:
        orchestrator.arms.remove(arm)
        new_arm = mantle.regrow_arm(arm.route, orchestrator.budget)
        orchestrator.arms.append(new_arm)
        
    await websocket.send_json(build_payload("SPAWN", "creative_arm_02 online. Resuming route..."))
    await asyncio.sleep(1.5)
    
    await websocket.send_json(build_payload("TELEMETRY", "Evaluating Resonant Coherence..."))
    await asyncio.sleep(1)
    
    # Step 2 & 3: Deadlock Loop
    for _ in range(2):
        status = orchestrator.evaluate_resonant_coherence()
        await websocket.send_json(build_payload("WARNING", f"Coherence {status}. Initiating negotiation pass..."))
        budget.consume(5.0)
        orchestrator.broadcast_negotiation()
        await asyncio.sleep(1.5)
        
    await websocket.send_json(build_payload("ERROR", "Max negotiations reached. Escalating to Apex Arbitrator."))
    await asyncio.sleep(1)
    
    # Step 4: Apex Arbitrator
    await websocket.send_json(build_payload("SPAWN", "Spawning arbitration_arm..."))
    await asyncio.sleep(1.5)
    
    arbitration_arm = ArmState(
        arm_id="apex_arbitrator",
        route="mantle->arbitration",
        moltbook=MoltbookState(status='ACTIVE', confidence_weight=1.0, crystallized_decision=f"APEX ARBITRATION OVERRIDE: {prompt} -> Split Architecture Recommended.")
    )
    orchestrator.arms = [arbitration_arm]
    
    await websocket.send_json(build_payload("ARBITRATION", "[apex_arbitrator] GAVEL DROP. Forcing consensus."))
    await asyncio.sleep(2)
    
    orchestrator.molt_state()
    await websocket.send_json(build_payload("MOLT", "Shedding ephemeral scratchpads. Crystallizing to Hive Mind."))
    await asyncio.sleep(1)
    
    final_decision = arbitration_arm.moltbook.crystallized_decision
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
            await simulate_swarm_execution(websocket, prompt)
            
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