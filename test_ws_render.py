import asyncio
import websockets

async def test():
    try:
        print("Connecting...")
        async with websockets.connect('wss://smartlib-be.onrender.com/ws/admin-notifications') as ws:
            print("Connected!")
    except Exception as e:
        print("Error:", e)

asyncio.run(test())
