import asyncio

from mavsdk import System

async def _wait_until_connected(drone: System,timeout_s: float)->None:
    async def _wait() -> None:
        async for state in drone.core.connection_state():
            if state.is_connected:
                return
    
    await asyncio.wait_for(_wait(), timeout=timeout_s)

async def connect(address: str,timeout_s: float = 30.0) -> System:
    drone = System()
    await drone.connect(system_address=address)
    await _wait_until_connected(drone,timeout_s)
    return drone