from dataclasses import dataclass

@dataclass(frozen=True)
class Config:
    system_address: str = "udp://:14540"
    takeoff_altitude_m:float = 5.0
    max_altitude_m: float = 30.0
    min_battery_percent: float = 30.0
    max_distance_from_home_m: float = 200.0
    connection_timeout_s: float = 30.0
    mission_timeout_s: float = 300.0


DEFAULT_CONFIG = Config()
