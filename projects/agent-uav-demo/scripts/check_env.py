import asyncio

from uav_agent.config import DEFAULT_CONFIG
from uav_agent.connection import connect

async def main() -> None:
    drone = await connect(DEFAULT_CONFIG.system_address,DEFAULT_CONFIG.connection_timeout_s)
    print("Connected to SITL")

    async for battery in drone.telemetry.battery():
        print(f"battery={battery.remaining_percent:.0f}%")
        break

    async for position in drone.telemetry.position():
        print(f"lat={position.latitude_deg:.6f} "
         f"lon={position.longitude_deg:.6f} "
         f"rel_alt={position.relative_altitude_m:.1f}m")
        break

    async for mode in drone.telemetry.flight_mode():
        print(f"mode={mode}")
        break

if __name__ == "__main__":
    asyncio.run(main())