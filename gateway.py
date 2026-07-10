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

async def simulate_swarm_execution(websocket: WebSocket, prompt: str):
    """
    Simulates the asynchronous execution of the Swarm.
    In production, this would hook directly into `mantle.py` and yield actual ADK events.
    """
    budget = 100.0
    
    def build_payload(event_type: str, message: str, coherence: float = 0.0, active_arms: int = 0):
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "type": event_type,
            "budget": budget,
            "coherence": coherence,
            "active_arms": active_arms,
            "message": message
        }

    # Phase 1: Setup & Injection
    await websocket.send_json(build_payload("SYSTEM", "Initializing Mantle Orchestrator..."))
    await asyncio.sleep(1)
    await websocket.send_json(build_payload("INFO", f"Received Prompt: '{prompt}'"))
    await asyncio.sleep(1)
    
    # Phase 2: Spawning Arms
    await websocket.send_json(build_payload("SPAWN", "Spawning logic_arm_01 and creative_arm_01...", 0.0, 2))
    await asyncio.sleep(1.5)
    
    # Phase 3: The Dispute
    await websocket.send_json(build_payload("TELEMETRY", "[logic_arm_01] Calculating precision routing (Path A)...", 0.45, 2))
    await asyncio.sleep(1)
    await websocket.send_json(build_payload("TELEMETRY", "[creative_arm_01] Exploring lateral options (Path B)...", 0.45, 2))
    await asyncio.sleep(1.5)
    
    # Phase 4: Deadlocked Negotiations
    budget -= 5.0
    await websocket.send_json(build_payload("WARNING", "Coherence FRACTURED (0.45). Initiating negotiation pass 1/2...", 0.45, 2))
    await asyncio.sleep(1.5)
    
    budget -= 5.0
    await websocket.send_json(build_payload("WARNING", "Coherence FRACTURED (0.45). Initiating negotiation pass 2/2...", 0.45, 2))
    await asyncio.sleep(1.5)
    
    await websocket.send_json(build_payload("ERROR", "Max negotiations reached. Deadlock detected.", 0.45, 2))
    await asyncio.sleep(1)
    
    # Phase 5: Apex Arbitrator Override
    await websocket.send_json(build_payload("SPAWN", "Spawning apex_arbitrator arm...", 0.45, 3))
    await asyncio.sleep(1.5)
    
    await websocket.send_json(build_payload("ARBITRATION", "[apex_arbitrator] GAVEL DROP. Resolving deadlocked options into logically superior path.", 1.0, 1))
    await asyncio.sleep(2)
    
    # Phase 6: Forced Consensus & Molt
    await websocket.send_json(build_payload("CONSENSUS", "Apex Arbitrator has resolved the deadlock. Forcing consensus.", 1.0, 1))
    await asyncio.sleep(1)
    
    await websocket.send_json(build_payload("MOLT", "Shedding ephemeral scratchpads. Crystallizing to Hive Mind.", 1.0, 1))
    await asyncio.sleep(1)
    
    # Final Output
    final_decision = "APEX ARBITRATION OVERRIDE: Path B provides mathematically superior latency/drop equilibrium."
    await websocket.send_json({
        "timestamp": datetime.utcnow().isoformat(),
        "type": "FINAL_OUTPUT",
        "budget": budget,
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