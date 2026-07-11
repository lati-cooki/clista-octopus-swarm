import asyncio
import websockets
import os
import random

# Read port or default to 8000
PORT = os.getenv("PORT", "8000")
URL = f"ws://localhost:{PORT}/ws/octopus"

# Set up valid and invalid tokens for testing
VALID_TOKEN = os.getenv("CLISTA_AUTH_TOKEN", "Bearer SUPER_SECRET_TOKEN").replace("Bearer ", "")
INVALID_TOKEN = "Bearer FAKE_TOKEN_123".replace("Bearer ", "")

async def mock_client(client_id: int, use_valid_token: bool):
    token = VALID_TOKEN if use_valid_token else INVALID_TOKEN
    uri = f"{URL}?token={token}"
    
    try:
        print(f"[Client {client_id}] Connecting with {'VALID' if use_valid_token else 'INVALID'} token...")
        async with websockets.connect(uri) as websocket:
            print(f"[Client {client_id}] Connected successfully!")
            
            # Send a mock payload
            payload = "Initialize Swarm Objective: Test WebSocket stability."
            await websocket.send(payload)
            
            while True:
                response = await websocket.recv()
                print(f"[Client {client_id}] Received: {response[:100]}...")
                
    except websockets.exceptions.InvalidStatusCode as e:
        print(f"[Client {client_id}] Connection rejected with status code: {e.status_code}")
    except websockets.exceptions.ConnectionClosedError as e:
        if e.code == 1008:
            print(f"[Client {client_id}] SUCCESS: Expected 1008 Policy Violation received for unauthorized token.")
        else:
            print(f"[Client {client_id}] Connection closed with code {e.code}: {e.reason}")
    except Exception as e:
        print(f"[Client {client_id}] Unexpected error: {e}")

async def run_chaos_test():
    clients = []
    # Spawn 5 valid clients and 15 invalid clients to simulate an attack
    for i in range(20):
        # 25% chance of valid token, 75% chance of invalid token
        use_valid = random.random() < 0.25
        clients.append(mock_client(i, use_valid))
        
    await asyncio.gather(*clients)

if __name__ == "__main__":
    print("Starting WebSocket Chaos Test...")
    asyncio.run(run_chaos_test())
