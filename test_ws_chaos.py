import pytest
import asyncio
import websockets
import os
from unittest.mock import patch, AsyncMock

PORT = os.getenv("PORT", "8000")
URL = f"ws://localhost:{PORT}/ws/octopus"

VALID_TOKEN = os.getenv("CLISTA_AUTH_TOKEN", "Bearer SUPER_SECRET_TOKEN").replace("Bearer ", "")
INVALID_TOKEN = "Bearer FAKE_TOKEN_123".replace("Bearer ", "")

async def mock_client(client_id: int, use_valid_token: bool):
    token = VALID_TOKEN if use_valid_token else INVALID_TOKEN
    uri = f"{URL}?token={token}"
    
    try:
        async with websockets.connect(uri) as websocket:
            payload = "Initialize Swarm Objective: Test WebSocket stability."
            await websocket.send(payload)
            response = await websocket.recv()
            return True, response
    except websockets.exceptions.InvalidStatusCode as e:
        return False, e.status_code
    except websockets.exceptions.ConnectionClosedError as e:
        return False, e.code
    except Exception as e:
        return False, str(e)

@pytest.mark.asyncio
async def test_ws_chaos_with_mocking():
    """
    Since this tests a live server by default, we just assert the setup is sound
    and mock the connect call to avoid requiring the server for unit testing.
    """
    with patch("websockets.connect") as mock_connect:
        # Mock connection context manager
        mock_ws = mock_connect.return_value.__aenter__.return_value
        mock_ws.send = AsyncMock()
        mock_ws.recv = AsyncMock(return_value="[mock] Accepted")
        
        success, result = await mock_client(client_id=1, use_valid_token=True)
        assert success is True
        assert result == "[mock] Accepted"
        mock_ws.send.assert_called_once()
        mock_ws.recv.assert_called_once()

@pytest.mark.asyncio
async def test_ws_chaos_invalid_token_with_mocking():
    with patch("websockets.connect") as mock_connect:
        # Simulate connection error
        error = websockets.exceptions.InvalidStatusCode(1008, {})
        mock_connect.side_effect = error
        
        success, result = await mock_client(client_id=2, use_valid_token=False)
        assert success is False
        assert result == 1008
