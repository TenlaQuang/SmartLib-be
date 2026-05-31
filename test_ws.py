import asyncio
import websockets
import json

async def test_ws():
    async with websockets.connect("ws://127.0.0.1:8000/ws/admin-notifications") as websocket:
        print("Connected")
        while True:
            message = await websocket.recv()
            print(f"Received: {message}")

asyncio.run(test_ws())
