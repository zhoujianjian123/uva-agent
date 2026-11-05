# 阶段 1：应用层闭环实施计划（2026-11 ~ 2026-12）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **本计划的实际执行者是用户本人（教练模式）。** Claude 负责讲解、出题、review 和排障；代码由用户动手写。参考实现只用于卡住时对照，不要先抄。

**Goal:** 用 8 周产出可公开演示的「自然语言 → Agent 任务规划 → MAVSDK → PX4 SITL 执行」项目，并通过安全校验与完整任务链路验收。

**Architecture:** 一个 Python 包 `uav_agent`，分层为连接、飞行控制、安全校验、任务生成、Agent 编排和 CLI。LLM 只输出高层任务参数（结构化 JSON），由确定性安全层校验后才允许执行；所有飞行都在 SITL 内完成。

**Tech Stack:** Python 3.10+、MAVSDK-Python、Pydantic v2、LangChain + LangGraph（OpenAI 兼容接口）、pytest。

## Global Constraints

- **时间**：每周 15 小时以上；论文优先，任何一周可整体暂停，不补课，恢复后从当前任务继续。
- **环境**：Windows 11 + WSL2 Ubuntu 24.04；PX4 v1.16.2 SITL + Gazebo（`gz_x500`）在 WSL2 内运行；QGroundControl 在 Windows 运行。WSL2 未安装 Java，jMAVSim 不可用，本计划统一使用 Gazebo。WSL2 使用 mirrored 网络模式，QGC 通过 localhost/UDP 14550 连接正常。MAVSDK 连接地址 `udp://:14540`；本阶段不改网络配置。
- **安全**：LLM 绝不直接输出姿态、速度、位置控制量；只允许输出 `MissionRequest` 高层任务参数，必须经过 `safety.py` 校验；所有飞行先在 SITL 完成。
- **版本**：阶段 1 固定 `mavsdk>=2.8,<4`，使用 gRPC API（`from mavsdk import System` 等）。MAVSDK 4.x 是原生绑定，API 不兼容，暂不使用。实际安装为 `mavsdk 3.17.4`；该版本没有 `mavsdk.__version__`，记录版本用 `python -c "from importlib.metadata import version; print(version('mavsdk'))"`。若 API 名称不同，以实际版本为准并在 `notes/` 记录差异。连接地址暂用 `udp://:14540`；3.x 提示未来迁移到 `udpin://`/`udpout://`，阶段 2 再处理。
- **工作方式**：教练模式。每个实验先自己实现，卡住 20 分钟后再看参考实现；完成后由教练 review 并追问原理。
- **版本控制**：本阶段不初始化 git（用户决定）。每个任务完成后保存代码并更新 `notes/weekXX.md`；若后续改变主意，可在阶段结束后统一补仓库。
- **连接边界**：阶段 1 的 `connect()` 只负责启动握手与首次连接超时；断链监控、自动重连、命令闸门属于阶段 2，不在本阶段实现。
- **范围**：只做多旋翼 SITL；不做真机、不做控制算法、不做 SLAM/强化学习。

## File Structure

```
d:\Code\UAV\
  docs/superpowers/specs/2026-10-20-uav-deep-learning-design.md
  docs/superpowers/plans/2026-10-20-stage1-application-layer.md
  labs/stage1/week01/README.md ... week08/README.md   # 每周任务书与实验记录
  notes/week01.md ... week08.md                       # 每周复盘
  projects/agent-uav-demo/
    pyproject.toml
    README.md
    README.en.md
    .env.example
    src/uav_agent/
      __init__.py
      config.py          # 配置常量
      connection.py      # 连接与超时
      flight.py          # 解锁/起飞/降落
      safety.py          # 安全判断与任务校验
      mission.py         # 坐标换算、航线生成、任务执行
      schema.py          # MissionRequest 结构
      tools.py           # MAVSDK 工具封装
      agent.py           # LangGraph 编排
      cli.py             # 命令行入口
    scripts/
      check_env.py       # 第 1 周
      telemetry_logger.py# 第 2 周
      basic_flight.py    # 第 3 周
      safe_flight.py     # 第 4 周
      mission_flight.py  # 第 5 周
      offboard_demo.py   # 第 6 周
    tests/
      test_offsets.py
      test_safety.py
      test_schema.py
      test_agent.py
```

代码直接长成作品，`labs/` 只放任务书和实验记录，避免后期二次搬运。

## Key Interfaces

| 文件 | 接口 | 说明 |
|---|---|---|
| `config.py` | `Config`、`DEFAULT_CONFIG` | 地址、高度、电量、距离阈值 |
| `connection.py` | `async connect(address, timeout_s) -> System` | 连接并等待心跳 |
| `flight.py` | `async arm_and_takeoff(drone, altitude_m, timeout_s=60)` | 解锁、起飞、等待高度 |
| `flight.py` | `async land_and_wait(drone, timeout_s=60)` | 降落并等待落地 |
| `safety.py` | `should_abort(battery_pct, alt_m, max_alt, min_battery) -> bool` | 低电量/超高度判断 |
| `safety.py` | `distance_m(lat1, lon1, lat2, lon2) -> float` | Haversine 距离 |
| `safety.py` | `validate_request(req, home_lat, home_lon, battery_pct, config) -> list[str]` | 任务级安全校验 |
| `mission.py` | `offset_lat_lon(lat, lon, north_m, east_m) -> (lat, lon)` | 局部偏移换算 |
| `mission.py` | `build_square_mission(home_lat, home_lon, alt, leg_m, speed=5) -> MissionPlan` | 方形航线 |
| `mission.py` | `build_goto_mission(lat, lon, alt, speed=5) -> MissionPlan` | 单点航线 |
| `mission.py` | `async execute_mission(drone, plan, timeout_s=300)` | 上传并执行 |
| `schema.py` | `MissionRequest` | `action/altitude_m/leg_m/repetitions/target_lat/target_lon` |
| `tools.py` | `UavTools.execute(req) -> str` | 真实执行入口（含二次校验） |
| `agent.py` | `parse_offline(prompt) -> MissionRequest` | 无 LLM 的确定性解析 |
| `agent.py` | `build_graph(executor=None, offline=None) -> CompiledGraph` | LangGraph 编排 |
| `cli.py` | `main()` | `uav-agent "<prompt>" --offline --dry-run` |

## Weekly Schedule

| 周 | 任务 | 产出 | 预计时长 |
|---|---|---|---|
| 1 | 环境复核 + 项目骨架 + 系统链路图 | 可运行的 `check_env.py`、`system_map.md` | 15h |
| 2 | 遥测记录与飞行概念 | 60 秒遥测 CSV、概念笔记 | 15h |
| 3 | MAVSDK 基础飞控 | 一键起降脚本 | 15h |
| 4 | 安全监控 + TDD | `safety.py` + 监控脚本 + 测试 | 15h |
| 5 | 航线任务 | 方形航线执行脚本 + 测试 | 15h |
| 6 | Offboard + 围栏/失效保护实验 | Offboard Demo + 实验记录 | 15h |
| 7 | 任务 Schema + LangGraph Agent | 离线 Agent + 安全拒绝测试 | 15h |
| 7-8 | 端到端联调 | 正例/反例演示 | 6h |
| 8 | 打包、文档、视频、验收 | 开源项目 + 5 分钟讲解 | 12h |

---

### Task 1: 环境复核与系统链路图（第 1 周）

**Files:**
- Create: `projects/agent-uav-demo/pyproject.toml`
- Create: `projects/agent-uav-demo/src/uav_agent/__init__.py`
- Create: `projects/agent-uav-demo/src/uav_agent/config.py`
- Create: `projects/agent-uav-demo/src/uav_agent/connection.py`
- Create: `projects/agent-uav-demo/scripts/check_env.py`
- Create: `labs/stage1/week01/README.md`
- Create: `notes/week01.md`

**Interfaces:**
- Produces: `connect(address: str, timeout_s: float = 30.0) -> System`
- Produces: `Config`、`DEFAULT_CONFIG`
- Produces: 环境版本记录、系统链路图

- [ ] **Step 1: 记录环境版本（10 分钟）**

在 PowerShell 运行：

```powershell
wsl -l -v
```

预期：Ubuntu 发行版状态为 Running。

在 WSL2 终端运行：

```bash
uname -a
python3 --version
gz --version
cd ~/PX4-Autopilot && git describe --tags --always
find ~ -maxdepth 4 -type d -name "PX4-Autopilot"
```

预期：Linux 内核、Python 3.12、Gazebo 可用、PX4 版本 v1.16.2。把版本与路径写入 `notes/week01.md`。Java 未安装不影响 Gazebo。

- [ ] **Step 2: 启动 PX4 SITL（5 分钟）**

另开一个 WSL2 终端：

```bash
cd ~/PX4-Autopilot
make px4_sitl gz_x500
```

预期：出现 Gazebo 窗口和 PX4 shell，日志出现 `Ready for takeoff`。保持这个终端运行。

启动阶段可能先出现 `ekf2 missing data` 或 `Accel #0 fail: TIMEOUT!`，这是 Gazebo 初始化时的瞬态告警；只要随后出现 `Ready for takeoff!`、能够解锁，就不影响实验。若告警持续且无法解锁，重启 SITL。

若路径不同，用 Step 1 找到的路径；若 Gazebo 窗口打不开，记录报错并先排查 WSLg。若构建时间较长，先等待编译完成。

- [ ] **Step 3: 启动 QGC 并观察 MAVLink（15 分钟）**

在 Windows 启动 QGroundControl，确认已连接虚拟飞机并显示姿态/位置/电量。

打开 QGC 的 **MAVLink Inspector**，找到这些消息并记录 ID：

| 消息 | ID | 用途 |
|---|---|---|
| HEARTBEAT | 0 | 心跳 |
| SYS_STATUS | 1 | 系统状态 |
| ATTITUDE | 30 | 姿态 |
| LOCAL_POSITION_NED | 32 | 局部位置 |
| GLOBAL_POSITION_INT | 33 | 经纬度/高度 |
| BATTERY_STATUS | 147 | 电量 |
| COMMAND_LONG | 76 | 长命令 |
| COMMAND_ACK | 77 | 命令确认 |

把观察结果写入 `notes/week01.md`：QGC 当前用什么方式连接（UDP 端口/IP）、消息刷新频率。

- [ ] **Step 4: 创建项目骨架（20 分钟）**

在 WSL2 中：

```bash
mkdir -p /mnt/d/Code/UAV/projects/agent-uav-demo/src/uav_agent
mkdir -p /mnt/d/Code/UAV/projects/agent-uav-demo/scripts
mkdir -p /mnt/d/Code/UAV/projects/agent-uav-demo/tests
mkdir -p /mnt/d/Code/UAV/labs/stage1/week01
mkdir -p /mnt/d/Code/UAV/notes
```

创建 `pyproject.toml`：

```toml
[build-system]
requires = ["setuptools>=69", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "uav-agent-demo"
version = "0.1.0"
description = "Natural-language UAV mission demo with MAVSDK and LangGraph (SITL only)"
requires-python = ">=3.10"
dependencies = [
  "mavsdk>=2.8,<4",
  "pydantic>=2.7",
  "python-dotenv>=1.0",
  "langchain-openai>=0.2",
  "langgraph>=0.2",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-asyncio>=0.24"]

[project.scripts]
uav-agent = "uav_agent.cli:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

创建 `config.py`：

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    system_address: str = "udp://:14540"
    takeoff_altitude_m: float = 5.0
    max_altitude_m: float = 30.0
    min_battery_percent: float = 30.0
    max_distance_from_home_m: float = 200.0
    connection_timeout_s: float = 30.0
    mission_timeout_s: float = 300.0


DEFAULT_CONFIG = Config()
```

创建 `connection.py`：

```python
import asyncio

from mavsdk import System


async def _wait_until_connected(drone: System, timeout_s: float) -> None:
    async def _wait() -> None:
        async for state in drone.core.connection_state():
            if state.is_connected:
                return

    await asyncio.wait_for(_wait(), timeout=timeout_s)


async def connect(address: str, timeout_s: float = 30.0) -> System:
    drone = System()
    await drone.connect(system_address=address)
    await _wait_until_connected(drone, timeout_s)
    return drone
```

`__init__.py` 暂时留空。

- [ ] **Step 5: 创建虚拟环境并安装（15 分钟）**

在 WSL2 中：

```bash
python3 -m venv ~/.venvs/uav
source ~/.venvs/uav/bin/activate
pip install --upgrade pip
cd /mnt/d/Code/UAV/projects/agent-uav-demo
pip install -e ".[dev]"
```

预期：`Successfully installed ... mavsdk ...`。验证：

```bash
python -c "from importlib.metadata import version; print(version('mavsdk'))"
```

把版本写入 `notes/week01.md`。

- [ ] **Step 6: 编写并运行连接检查（30 分钟）**

创建 `scripts/check_env.py`：

```python
import asyncio

from uav_agent.config import DEFAULT_CONFIG
from uav_agent.connection import connect


async def main() -> None:
    drone = await connect(DEFAULT_CONFIG.system_address, DEFAULT_CONFIG.connection_timeout_s)
    print("Connected to SITL")

    async for battery in drone.telemetry.battery():
        print(f"battery={battery.remaining_percent:.0f}%")
        break

    async for position in drone.telemetry.position():
        print(
            f"lat={position.latitude_deg:.6f} "
            f"lon={position.longitude_deg:.6f} "
            f"rel_alt={position.relative_altitude_m:.1f}m"
        )
        break

    async for mode in drone.telemetry.flight_mode():
        print(f"mode={mode}")
        break


if __name__ == "__main__":
    asyncio.run(main())
```

运行：

```bash
python scripts/check_env.py
```

预期输出示例（模式名称可能因 PX4 版本不同）：

```
Connected to SITL
battery=100%
lat=47.397742 lon=8.545594 rel_alt=0.0m
mode=HOLD
```

如果连不上，先检查 PX4 是否仍在运行、端口是否 14540、WSL2 内是否用同一网络命名空间。

- [ ] **Step 7: 画系统链路图（40 分钟）**

创建 `labs/stage1/week01/README.md`，写清：

1. 五个组成部分：飞控（PX4）、机载计算机、数据链、地面站（QGC）、云端/任务系统。
2. 三条消息流：
   - 遥控/MAVSDK → PX4（命令）
   - PX4 → QGC/MAVSDK（遥测）
   - PX4 → 执行器（电机/舵机）
3. 标注 14540（MAVSDK）与 14550（QGC）的角色差异。

- [ ] **Step 8: 自测并写复盘（20 分钟）**

在 `notes/week01.md` 回答：

1. `sysid` 和 `compid` 分别标识什么？PX4 默认是多少？
2. QGC 从 14550 收遥测，MAVSDK 从 14540 控制，这两个端口在 PX4 SITL 里分别是什么角色？
3. 心跳丢失后，QGC 和飞控各自会发生什么？
4. 画出「你的 Agent → MAVSDK → PX4 → 仿真器」的数据流。

**验收标准：**
- `check_env.py` 能稳定输出连接、电量、位置、模式。
- 系统链路图能讲清五个组成部分和三条消息流。
- 四个自测问题回答正确；教练追问时能解释，而不是背答案。

---

### Task 2: 遥测记录与飞行概念（第 2 周）

**Files:**
- Create: `projects/agent-uav-demo/scripts/telemetry_logger.py`
- Create: `labs/stage1/week02/README.md`
- Modify: `notes/week02.md`

**Interfaces:**
- Consumes: `connect()`、`DEFAULT_CONFIG`
- Produces: `telemetry.csv`（13 列，1Hz）

**阅读（2 小时）：**
- PX4 飞行模式：https://docs.px4.io/main/en/flight_modes/
- PX4 坐标系与消息：https://docs.px4.io/main/en/msg_docs/
- MAVLink 公共消息：https://mavlink.io/en/messages/common.html

- [ ] **Step 1: 写遥测记录脚本（60 分钟）**

创建 `scripts/telemetry_logger.py`：

```python
import asyncio
import csv
from datetime import datetime, timezone

from uav_agent.connection import connect

FIELDS = [
    "ts", "mode", "roll_deg", "pitch_deg", "yaw_deg",
    "north_m", "east_m", "down_m",
    "lat_deg", "lon_deg", "abs_alt_m", "rel_alt_m", "battery_pct",
]


async def main(duration_s: int = 60, out_path: str = "telemetry.csv") -> None:
    drone = await connect("udp://:14540")
    latest = {key: None for key in FIELDS[1:]}

    async def read_modes() -> None:
        async for mode in drone.telemetry.flight_mode():
            latest["mode"] = str(mode)

    async def read_attitude() -> None:
        async for attitude in drone.telemetry.attitude_euler():
            latest["roll_deg"] = attitude.roll_deg
            latest["pitch_deg"] = attitude.pitch_deg
            latest["yaw_deg"] = attitude.yaw_deg

    async def read_ned() -> None:
        async for pv in drone.telemetry.position_velocity_ned():
            latest["north_m"] = pv.position.north_m
            latest["east_m"] = pv.position.east_m
            latest["down_m"] = pv.position.down_m

    async def read_global() -> None:
        async for position in drone.telemetry.position():
            latest["lat_deg"] = position.latitude_deg
            latest["lon_deg"] = position.longitude_deg
            latest["abs_alt_m"] = position.absolute_altitude_m
            latest["rel_alt_m"] = position.relative_altitude_m

    async def read_battery() -> None:
        async for battery in drone.telemetry.battery():
            latest["battery_pct"] = battery.remaining_percent

    tasks = [
        asyncio.create_task(read_modes()),
        asyncio.create_task(read_attitude()),
        asyncio.create_task(read_ned()),
        asyncio.create_task(read_global()),
        asyncio.create_task(read_battery()),
    ]

    rows = []
    try:
        loop = asyncio.get_running_loop()
        end = loop.time() + duration_s
        while loop.time() < end:
            rows.append({"ts": datetime.now(timezone.utc).isoformat(), **latest})
            await asyncio.sleep(1)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    with open(out_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"wrote {len(rows)} rows to {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: 在 QGC 中飞一次并记录（30 分钟）**

终端运行：

```bash
python scripts/telemetry_logger.py
```

同时在 QGC 中完成：解锁 → 起飞 → 悬停 → 切换模式（Position/Altitude）→ RTL → 降落。

预期：生成 `telemetry.csv`，约 60 行，字段有值。

- [ ] **Step 3: 分析日志（60 分钟）**

用 Python 或表格软件分析：
- 起飞时 `rel_alt_m` 如何变化，`abs_alt_m` 与 `rel_alt_m` 差值是否等于 home 海拔。
- RTL 时 `mode` 字段变化，`north_m/east_m` 是否回到原点附近。
- 姿态角在悬停时的范围。

把 3 条结论写入 `notes/week02.md`。

- [ ] **Step 4: 概念笔记（60 分钟）**

在 `labs/stage1/week02/README.md` 写清：
1. NED 与 ENU 的区别，PX4 用哪个。
2. `relative_altitude_m`、`absolute_altitude_m`、气压高度、GPS 高度的基准。
3. 空速与地速的区别；多旋翼和固定翼分别更关注哪个。
4. Position 模式丢失 GPS 会发生什么；Altitude 模式呢。
5. 为什么多旋翼悬停时姿态角接近 0，而前飞时需要抬头/低头。

- [ ] **Step 5: 自测（20 分钟）**

回答：
1. `down_m` 为正代表飞机在地面以上还是以下？
2. 为什么 RTL 的高度逻辑在山区需要特别配置？
3. 如果 Agent 只拿到 GPS 坐标，没有 home 海拔，能安全生成航线吗？为什么？

**验收标准：**
- CSV 至少 60 行，关键字段无全空。
- 能解释 NED、两种高度、空速/地速、模式失效行为。
- 自测回答正确，能结合 CSV 数据说明。

---

### Task 3: MAVSDK 基础飞控（第 3 周）

**Files:**
- Create: `projects/agent-uav-demo/src/uav_agent/flight.py`
- Create: `projects/agent-uav-demo/scripts/basic_flight.py`
- Create: `labs/stage1/week03/README.md`
- Modify: `notes/week03.md`

**Interfaces:**
- Consumes: `System`、`connect()`
- Produces: `async arm_and_takeoff(drone, altitude_m, timeout_s=60)`
- Produces: `async wait_for_landed(drone, timeout_s=60)`
- Produces: `async land_and_wait(drone, timeout_s=60)`

**阅读（2 小时）：**
- MAVSDK-Python 教程：https://mavsdk.mavlink.io/main/en/python/
- PX4 解锁检查：https://docs.px4.io/main/en/preflight/preflight_checks.html

- [ ] **Step 1: 实现飞行控制函数（60 分钟）**

创建 `flight.py`：

```python
import asyncio

from mavsdk import System


async def arm_and_takeoff(drone: System, altitude_m: float, timeout_s: float = 60.0) -> None:
    await drone.action.set_takeoff_altitude(altitude_m)
    await drone.action.arm()
    await drone.action.takeoff()

    async def _wait_altitude() -> None:
        async for position in drone.telemetry.position():
            if position.relative_altitude_m >= altitude_m * 0.8:
                return

    await asyncio.wait_for(_wait_altitude(), timeout=timeout_s)
    await asyncio.sleep(1)


async def wait_for_landed(drone: System, timeout_s: float = 60.0) -> None:
    async def _wait() -> None:
        async for in_air in drone.telemetry.in_air():
            if not in_air:
                return

    await asyncio.wait_for(_wait(), timeout=timeout_s)


async def land_and_wait(drone: System, timeout_s: float = 60.0) -> None:
    await drone.action.land()
    await wait_for_landed(drone, timeout_s)
```

- [ ] **Step 2: 写一键起降脚本（30 分钟）**

创建 `scripts/basic_flight.py`：

```python
import asyncio

from uav_agent.config import DEFAULT_CONFIG
from uav_agent.connection import connect
from uav_agent.flight import arm_and_takeoff, land_and_wait


async def main() -> None:
    drone = await connect(DEFAULT_CONFIG.system_address, DEFAULT_CONFIG.connection_timeout_s)
    try:
        await arm_and_takeoff(drone, DEFAULT_CONFIG.takeoff_altitude_m)
        print(f"Hovering at {DEFAULT_CONFIG.takeoff_altitude_m}m for 5s")
        await asyncio.sleep(5)
    finally:
        await land_and_wait(drone)
        print("Landed")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 3: 在 SITL 验证（30 分钟）**

```bash
python scripts/basic_flight.py
```

预期：飞机解锁、起飞到约 5 米、悬停 5 秒、降落。观察 QGC 的模式与高度变化。

- [ ] **Step 4: 异常测试（30 分钟）**

飞机悬停时，在 PX4 终端按 Ctrl+C 停止 SITL。预期：脚本抛出连接/等待异常并退出，不出现无限挂起。

在 `notes/week03.md` 记录异常类型和脚本退出行为。

- [ ] **Step 5: 阅读与回答（50 分钟）**

回答：
1. `set_takeoff_altitude` 设置的高度是相对什么基准？
2. PX4 解锁前会做哪些检查？哪些检查失败会导致拒绝解锁？
3. 为什么 `takeoff()` 返回后还要等待 `relative_altitude_m >= 80%`？
4. UDP 地址 `udp://:14540` 中冒号前后的含义是什么？

**验收标准：**
- 脚本可稳定完成起飞—悬停—降落。
- 中断 SITL 时脚本干净退出。
- 能解释起飞高度基准、解锁检查和等待逻辑。

---

### Task 4: 安全监控与 TDD（第 4 周）

**Files:**
- Create: `projects/agent-uav-demo/tests/test_safety.py`
- Create: `projects/agent-uav-demo/src/uav_agent/safety.py`
- Create: `projects/agent-uav-demo/scripts/safe_flight.py`
- Create: `labs/stage1/week04/README.md`
- Modify: `notes/week04.md`

**Interfaces:**
- Produces: `should_abort(battery_percent, relative_altitude_m, max_altitude_m, min_battery_percent) -> bool`
- Produces: `distance_m(lat1, lon1, lat2, lon2) -> float`
- Consumes: `arm_and_takeoff()`、`wait_for_landed()`、`land_and_wait()`

**先写测试，再写实现（TDD）。**

- [ ] **Step 1: 写失败测试（30 分钟）**

创建 `tests/test_safety.py`：

```python
import math

import pytest

from uav_agent.safety import distance_m, should_abort


def test_should_abort_on_low_battery() -> None:
    assert should_abort(20.0, 10.0, 30.0, 30.0) is True


def test_should_not_abort_when_normal() -> None:
    assert should_abort(80.0, 10.0, 30.0, 30.0) is False


def test_should_abort_on_altitude() -> None:
    assert should_abort(80.0, 50.0, 30.0, 30.0) is True


def test_should_ignore_nan_battery() -> None:
    assert should_abort(math.nan, 10.0, 30.0, 30.0) is False


def test_distance_same_point_is_zero() -> None:
    assert distance_m(47.397742, 8.545594, 47.397742, 8.545594) == pytest.approx(0.0, abs=0.01)


def test_distance_one_degree_latitude_is_about_111km() -> None:
    assert distance_m(0.0, 0.0, 1.0, 0.0) == pytest.approx(111_195.0, rel=0.01)
```

运行：

```bash
pytest tests/test_safety.py -v
```

预期：失败，`ModuleNotFoundError: No module named 'uav_agent.safety'`。

- [ ] **Step 2: 实现最小代码（30 分钟）**

创建 `safety.py`：

```python
import math


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_378_137.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def should_abort(
    battery_percent: float,
    relative_altitude_m: float,
    max_altitude_m: float,
    min_battery_percent: float,
) -> bool:
    battery_low = not math.isnan(battery_percent) and battery_percent < min_battery_percent
    return battery_low or relative_altitude_m > max_altitude_m
```

运行测试：

```bash
pytest tests/test_safety.py -v
```

预期：6 passed。

- [ ] **Step 3: 写安全飞行脚本（45 分钟）**

创建 `scripts/safe_flight.py`：

```python
import asyncio

from uav_agent.config import DEFAULT_CONFIG
from uav_agent.connection import connect
from uav_agent.flight import arm_and_takeoff, land_and_wait, wait_for_landed
from uav_agent.safety import should_abort


async def main() -> None:
    drone = await connect(DEFAULT_CONFIG.system_address, DEFAULT_CONFIG.connection_timeout_s)
    latest = {"battery": float("nan"), "alt": 0.0}

    async def read_battery() -> None:
        async for battery in drone.telemetry.battery():
            latest["battery"] = battery.remaining_percent

    async def read_position() -> None:
        async for position in drone.telemetry.position():
            latest["alt"] = position.relative_altitude_m

    tasks = [
        asyncio.create_task(read_battery()),
        asyncio.create_task(read_position()),
    ]

    aborted = False
    try:
        await arm_and_takeoff(drone, 5.0)
        print("Takeoff complete; monitoring for 20s")
        for _ in range(40):
            if should_abort(
                latest["battery"],
                latest["alt"],
                DEFAULT_CONFIG.max_altitude_m,
                DEFAULT_CONFIG.min_battery_percent,
            ):
                print("Abort condition met -> RTL")
                await drone.action.return_to_launch()
                aborted = True
                break
            await asyncio.sleep(0.5)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if aborted:
            await wait_for_landed(drone, timeout_s=90)
        else:
            await land_and_wait(drone, timeout_s=60)
        print("Landed")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: 集成验证（30 分钟）**

运行：

```bash
python scripts/safe_flight.py
```

预期：起飞、监控 20 秒、正常降落。

再验证 RTL 路径：临时把 `config.py` 中的 `max_altitude_m` 改为 3.0（低于起飞高度 5 米），重新运行，预期触发 RTL 并降落。测试后恢复配置。

- [ ] **Step 5: 自测（20 分钟）**

回答：
1. 为什么安全监控要独立于任务逻辑？
2. 电池百分比为 NaN 时为什么不能当作低电量处理？如果当作低电量，会导致什么？
3. RTL 的触发条件有哪些？RTL 高度如何配置？
4. 如果安全监控脚本本身崩溃，飞机由谁保护？

**验收标准：**
- 测试先失败后通过，体现 TDD 流程。
- 正常路径和 RTL 路径都能在 SITL 中跑到落地。
- 能解释安全层的地位和失效保护责任边界。

---

### Task 5: 航线任务（第 5 周）

**Files:**
- Create: `projects/agent-uav-demo/tests/test_offsets.py`
- Create: `projects/agent-uav-demo/src/uav_agent/mission.py`
- Create: `projects/agent-uav-demo/scripts/mission_flight.py`
- Create: `labs/stage1/week05/README.md`
- Modify: `notes/week05.md`

**Interfaces:**
- Produces: `offset_lat_lon(lat_deg, lon_deg, north_m, east_m) -> tuple[float, float]`
- Produces: `build_square_mission(home_lat, home_lon, altitude_m, leg_m, speed_m_s=5.0) -> MissionPlan`
- Produces: `build_goto_mission(target_lat, target_lon, altitude_m, speed_m_s=5.0) -> MissionPlan`
- Produces: `async execute_mission(drone, plan, timeout_s=300.0) -> None`

**阅读（2 小时）：**
- MAVSDK Mission：https://mavsdk.mavlink.io/main/en/python/plugins/mission.html
- PX4 任务模式：https://docs.px4.io/main/en/flight_modes/mission.html

- [ ] **Step 1: 先写坐标与航线测试（30 分钟）**

创建 `tests/test_offsets.py`：

```python
import pytest

from uav_agent.mission import build_square_mission, offset_lat_lon
from uav_agent.safety import distance_m

HOME_LAT = 47.397742
HOME_LON = 8.545594


def test_offset_north_20m() -> None:
    lat, lon = offset_lat_lon(HOME_LAT, HOME_LON, 20.0, 0.0)
    assert distance_m(HOME_LAT, HOME_LON, lat, lon) == pytest.approx(20.0, rel=0.01)


def test_offset_east_20m() -> None:
    lat, lon = offset_lat_lon(HOME_LAT, HOME_LON, 0.0, 20.0)
    assert distance_m(HOME_LAT, HOME_LON, lat, lon) == pytest.approx(20.0, rel=0.01)


def test_square_mission_has_five_items() -> None:
    plan = build_square_mission(HOME_LAT, HOME_LON, 10.0, 20.0)
    assert len(plan.mission_items) == 5


def test_square_mission_return_to_home() -> None:
    plan = build_square_mission(HOME_LAT, HOME_LON, 10.0, 20.0)
    first = plan.mission_items[0]
    last = plan.mission_items[-1]
    assert distance_m(first.latitude_deg, first.longitude_deg, last.latitude_deg, last.longitude_deg) < 1.0
```

运行：

```bash
pytest tests/test_offsets.py -v
```

预期：失败（模块不存在或函数未定义）。

- [ ] **Step 2: 实现航线生成与执行（90 分钟）**

创建 `mission.py`：

```python
import asyncio
import math

from mavsdk import System
from mavsdk.mission import MissionItem, MissionPlan

EARTH_RADIUS_M = 6_378_137.0


def offset_lat_lon(
    lat_deg: float,
    lon_deg: float,
    north_m: float,
    east_m: float,
) -> tuple[float, float]:
    dlat = north_m / EARTH_RADIUS_M * (180.0 / math.pi)
    dlon = east_m / (EARTH_RADIUS_M * math.cos(math.radians(lat_deg))) * (180.0 / math.pi)
    return lat_deg + dlat, lon_deg + dlon


def _item(lat: float, lon: float, altitude_m: float, speed_m_s: float) -> MissionItem:
    return MissionItem(
        latitude_deg=lat,
        longitude_deg=lon,
        relative_altitude_m=altitude_m,
        speed_m_s=speed_m_s,
        is_fly_through=True,
        gimbal_pitch_deg=float("nan"),
        gimbal_yaw_deg=float("nan"),
        camera_action=MissionItem.CameraAction.NONE,
        loiter_time_s=float("nan"),
        camera_photo_interval_s=float("nan"),
        acceptance_radius_m=float("nan"),
        yaw_deg=float("nan"),
        camera_photo_distance_m=float("nan"),
        vehicle_action=MissionItem.VehicleAction.NONE,
    )


def build_square_mission(
    home_lat: float,
    home_lon: float,
    altitude_m: float,
    leg_m: float,
    speed_m_s: float = 5.0,
) -> MissionPlan:
    corners = [(0.0, 0.0), (leg_m, 0.0), (leg_m, leg_m), (0.0, leg_m), (0.0, 0.0)]
    items = [
        _item(*offset_lat_lon(home_lat, home_lon, north, east), altitude_m, speed_m_s)
        for north, east in corners
    ]
    return MissionPlan(items)


def build_goto_mission(
    target_lat: float,
    target_lon: float,
    altitude_m: float,
    speed_m_s: float = 5.0,
) -> MissionPlan:
    return MissionPlan([_item(target_lat, target_lon, altitude_m, speed_m_s)])


async def execute_mission(drone: System, plan: MissionPlan, timeout_s: float = 300.0) -> None:
    await drone.mission.upload_mission(plan)
    await drone.mission.start_mission()

    async def _wait_for_completion() -> None:
        async for progress in drone.mission.mission_progress():
            if progress.total > 0 and progress.current == progress.total:
                return

    await asyncio.wait_for(_wait_for_completion(), timeout=timeout_s)
```

运行测试：

```bash
pytest tests/test_offsets.py -v
```

预期：4 passed。

- [ ] **Step 3: 写任务执行脚本（30 分钟）**

创建 `scripts/mission_flight.py`：

```python
import asyncio

from uav_agent.config import DEFAULT_CONFIG
from uav_agent.connection import connect
from uav_agent.flight import arm_and_takeoff, land_and_wait
from uav_agent.mission import build_square_mission, execute_mission


async def main() -> None:
    drone = await connect(DEFAULT_CONFIG.system_address, DEFAULT_CONFIG.connection_timeout_s)
    home = await anext(drone.telemetry.home())
    plan = build_square_mission(
        home.latitude_deg,
        home.longitude_deg,
        altitude_m=10.0,
        leg_m=20.0,
    )

    await arm_and_takeoff(drone, 10.0)
    try:
        await execute_mission(drone, plan, timeout_s=300.0)
        print("Mission complete")
    finally:
        await land_and_wait(drone, timeout_s=60.0)
        print("Landed")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: 在 SITL 执行方形航线（30 分钟）**

```bash
python scripts/mission_flight.py
```

预期：起飞到 10 米 → 依次飞 4 个角点 → 返回起点 → 降落。在 QGC 中观察航点与进度。

如果任务在第一个点就结束：检查 home 是否获取成功、任务是否上传成功、`mission_progress` 的 `total` 是否为 0。

- [ ] **Step 5: 自测（20 分钟）**

回答：
1. 任务上传的完整消息序列是什么（MISSION_COUNT、MISSION_REQUEST_INT、MISSION_ITEM_INT、MISSION_ACK）？
2. 为什么最后要回到起点？
3. 相对高度航线在 home 位置变化后会发生什么？
4. 如果任务执行中途切换模式为 Position，任务会怎样？

**验收标准：**
- 4 个测试通过。
- 方形航线在 SITL 完整执行并降落。
- 能讲清任务上传序列（能对着 QGC 的 MAVLink Inspector 指出消息）。

---

### Task 6: Offboard 与围栏/失效保护实验（第 6 周）

**Files:**
- Create: `projects/agent-uav-demo/scripts/offboard_demo.py`
- Create: `labs/stage1/week06/README.md`
- Modify: `notes/week06.md`

**Interfaces:**
- Consumes: `arm_and_takeoff()`、`land_and_wait()`
- Produces: Offboard 速度控制 Demo
- Produces: Mission vs Offboard 对比笔记、围栏实验结果

**阅读（2 小时）：**
- PX4 Offboard 模式：https://docs.px4.io/main/en/flight_modes/offboard.html
- PX4 地理围栏：https://docs.px4.io/main/en/config/geofence.html

- [ ] **Step 1: 写 Offboard Demo（60 分钟）**

创建 `scripts/offboard_demo.py`：

```python
import asyncio

from mavsdk.offboard import OffboardError, VelocityNedYaw
from uav_agent.config import DEFAULT_CONFIG
from uav_agent.connection import connect
from uav_agent.flight import arm_and_takeoff, land_and_wait


async def main() -> None:
    drone = await connect(DEFAULT_CONFIG.system_address, DEFAULT_CONFIG.connection_timeout_s)
    await arm_and_takeoff(drone, 5.0)

    await drone.offboard.set_velocity_ned(VelocityNedYaw(0.0, 0.0, 0.0, 0.0))
    try:
        await drone.offboard.start()
        print("Offboard started; moving north at 1 m/s for 5s")
        for _ in range(20):
            await drone.offboard.set_velocity_ned(VelocityNedYaw(1.0, 0.0, 0.0, 0.0))
            await asyncio.sleep(0.25)
        await drone.offboard.set_velocity_ned(VelocityNedYaw(0.0, 0.0, 0.0, 0.0))
        await asyncio.sleep(1.0)
    except OffboardError as error:
        print(f"Offboard failed: {error}")
    finally:
        try:
            await drone.offboard.stop()
        except OffboardError:
            pass
        await land_and_wait(drone, timeout_s=60.0)
        print("Landed")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: 运行并观察（30 分钟）**

```bash
python scripts/offboard_demo.py
```

预期：飞机起飞后向北移动约 5 秒，然后悬停、退出 Offboard、降落。QGC 中模式应显示 OFFBOARD。

如果 `offboard.start()` 失败：确认在 start 前已经发送过 setpoint，且发送频率高于 2Hz。

- [ ] **Step 3: 围栏/失效保护实验（45 分钟）**

在 QGC 中设置一个 100 米半径的地理围栏和 30 米最大高度。然后临时把 `mission_flight.py` 的 `leg_m` 改为 150 米，运行任务。

预期：飞机在接近围栏时触发保护动作（默认可能是 RTL/降落/悬停，取决于 QGC 与 PX4 参数）。记录实际行为、QGC 告警和飞行模式变化。

如果围栏配置不生效，检查 PX4 参数 `GF_*` 并记录你使用的参数值。实验后恢复围栏和代码。

- [ ] **Step 4: 写对比笔记（40 分钟）**

在 `labs/stage1/week06/README.md` 写清：
1. Mission 模式与 Offboard 模式的本质区别（谁在生成 setpoint）。
2. Offboard 为什么必须持续发送 setpoint；停止发送会发生什么。
3. 围栏触发后 PX4 可执行哪些动作。
4. 在 Agent 场景中，哪种任务适合 Mission，哪种适合 Offboard。

- [ ] **Step 5: 自测（20 分钟）**

回答：
1. 如果 Agent 发送了 Offboard 流速指令后网络中断，飞机会怎样？
2. 为什么本项目的 Agent Demo 选择 Mission 而不是 Offboard？
3. 围栏和 RTL 分别保护什么风险？

**验收标准：**
- Offboard Demo 能运行并正常退出。
- 围栏实验有实际观察记录，哪怕结果与预期不同。
- 能讲清 Mission/Offboard 的分工和风险。

---

### Task 7: 任务 Schema 与安全校验（第 7 周）

**Files:**
- Create: `projects/agent-uav-demo/src/uav_agent/schema.py`
- Modify: `projects/agent-uav-demo/src/uav_agent/safety.py`
- Modify: `projects/agent-uav-demo/tests/test_safety.py`
- Create: `projects/agent-uav-demo/tests/test_schema.py`
- Modify: `notes/week07.md`

**Interfaces:**
- Produces: `MissionRequest`（Pydantic v2 模型）
- Produces: `validate_request(req, home_lat, home_lon, battery_percent, config=DEFAULT_CONFIG) -> list[str]`

- [ ] **Step 1: 写 Schema 与校验测试（45 分钟）**

创建 `tests/test_schema.py`：

```python
import pytest
from pydantic import ValidationError

from uav_agent.schema import MissionRequest


def test_square_request_defaults() -> None:
    request = MissionRequest(action="square")
    assert request.altitude_m == 10.0
    assert request.leg_m == 20.0


def test_altitude_has_structural_bounds() -> None:
    with pytest.raises(ValidationError):
        MissionRequest(action="square", altitude_m=1000.0)


def test_invalid_action_is_rejected() -> None:
    with pytest.raises(ValidationError):
        MissionRequest(action="fly_to_moon")
```

在 `tests/test_safety.py` 追加：

```python
from uav_agent.schema import MissionRequest
from uav_agent.safety import validate_request


def test_validate_rejects_high_altitude() -> None:
    request = MissionRequest(action="square", altitude_m=100.0)
    errors = validate_request(request, 47.397742, 8.545594, battery_percent=80.0)
    assert any("outside allowed" in error for error in errors)


def test_validate_rejects_goto_without_target() -> None:
    request = MissionRequest(action="goto", altitude_m=10.0)
    errors = validate_request(request, 47.397742, 8.545594, battery_percent=80.0)
    assert any("target_lat" in error for error in errors)


def test_validate_rejects_far_goto() -> None:
    request = MissionRequest(
        action="goto",
        altitude_m=10.0,
        target_lat=47.397742,
        target_lon=8.545594 + 0.01,
    )
    errors = validate_request(request, 47.397742, 8.545594, battery_percent=80.0)
    assert any("exceeds max" in error for error in errors)


def test_validate_rejects_low_battery() -> None:
    request = MissionRequest(action="square", altitude_m=10.0)
    errors = validate_request(request, 47.397742, 8.545594, battery_percent=20.0)
    assert any("battery" in error for error in errors)


def test_validate_accepts_valid_square() -> None:
    request = MissionRequest(action="square", altitude_m=10.0, leg_m=20.0)
    assert validate_request(request, 47.397742, 8.545594, battery_percent=80.0) == []
```

运行：

```bash
pytest tests/test_schema.py tests/test_safety.py -v
```

预期：失败（`schema` 模块或 `validate_request` 不存在）。

- [ ] **Step 2: 实现 Schema（20 分钟）**

创建 `schema.py`：

```python
from typing import Literal, Optional

from pydantic import BaseModel, Field


class MissionRequest(BaseModel):
    action: Literal["square", "goto", "takeoff_land"]
    altitude_m: float = Field(default=10.0, ge=1.0, le=500.0)
    leg_m: float = Field(default=20.0, ge=5.0, le=200.0)
    repetitions: int = Field(default=1, ge=1, le=3)
    target_lat: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    target_lon: Optional[float] = Field(default=None, ge=-180.0, le=180.0)
```

- [ ] **Step 3: 扩展安全校验（30 分钟）**

在 `safety.py` 追加：

```python
from uav_agent.config import DEFAULT_CONFIG, Config
from uav_agent.schema import MissionRequest


def validate_request(
    request: MissionRequest,
    home_lat: float,
    home_lon: float,
    battery_percent: float,
    config: Config = DEFAULT_CONFIG,
) -> list[str]:
    errors: list[str] = []

    if request.altitude_m < 2.0 or request.altitude_m > config.max_altitude_m:
        errors.append(
            f"altitude {request.altitude_m:.1f}m outside allowed "
            f"2.0-{config.max_altitude_m:.1f}m"
        )

    if request.action == "goto":
        if request.target_lat is None or request.target_lon is None:
            errors.append("goto requires target_lat and target_lon")
        else:
            distance = distance_m(home_lat, home_lon, request.target_lat, request.target_lon)
            if distance > config.max_distance_from_home_m:
                errors.append(
                    f"target {distance:.0f}m from home exceeds max "
                    f"{config.max_distance_from_home_m:.0f}m"
                )

    if not math.isnan(battery_percent) and battery_percent < config.min_battery_percent:
        errors.append(
            f"battery {battery_percent:.0f}% below min "
            f"{config.min_battery_percent:.0f}%"
        )

    return errors
```

运行：

```bash
pytest tests/test_schema.py tests/test_safety.py -v
```

预期：全部通过。

- [ ] **Step 4: 自测（20 分钟）**

回答：
1. Schema 的结构约束与安全层的运行约束分别防什么？为什么需要两层？
2. `altitude_m` 的结构上限是 500 米，但安全层只允许 30 米，这样设计有什么好处？
3. 如果 LLM 输出 `goto` 但没有坐标，系统会在哪一层拒绝？
4. 如果电量读数异常为 NaN，系统应该继续还是拒绝？为什么？

**验收标准：**
- Schema 与校验测试全部通过。
- 能说清「解析约束 → 结构约束 → 安全约束 → 执行前二次校验」的分层。

---

### Task 8: LangGraph Agent 与工具封装（第 7 周）

**Files:**
- Create: `projects/agent-uav-demo/src/uav_agent/tools.py`
- Create: `projects/agent-uav-demo/src/uav_agent/agent.py`
- Create: `projects/agent-uav-demo/src/uav_agent/cli.py`
- Create: `projects/agent-uav-demo/tests/test_agent.py`
- Create: `projects/agent-uav-demo/.env.example`
- Create: `labs/stage1/week07/README.md`
- Modify: `notes/week07.md`

**Interfaces:**
- Consumes: `MissionRequest`、`validate_request()`、`arm_and_takeoff()`、`execute_mission()`、`land_and_wait()`
- Produces: `UavTools.execute(req) -> str`
- Produces: `parse_offline(prompt) -> MissionRequest`
- Produces: `build_graph(executor=None, offline=None) -> CompiledGraph`

**阅读（2 小时）：**
- LangGraph 快速开始：https://langchain-ai.github.io/langgraph/
- LangChain 结构化输出：https://python.langchain.com/docs/how_to/structured_output/

- [ ] **Step 1: 写 Agent 测试（30 分钟）**

创建 `tests/test_agent.py`：

```python
import pytest

from uav_agent.agent import build_graph, parse_offline


def test_offline_parser_square_altitude() -> None:
    request = parse_offline("绕方形飞一圈，高度10米，然后降落")
    assert request.action == "square"
    assert request.altitude_m == 10.0


@pytest.mark.asyncio
async def test_square_prompt_reaches_executor() -> None:
    calls = []

    async def fake_executor(request):
        calls.append(request)
        return "OK"

    graph = build_graph(executor=fake_executor, offline=True)
    state = await graph.ainvoke(
        {"prompt": "绕方形飞一圈，高度10米，然后降落", "errors": []}
    )

    assert state["mission"].action == "square"
    assert state["errors"] == []
    assert state["result"] == "OK"
    assert calls[0].altitude_m == 10.0


@pytest.mark.asyncio
async def test_high_altitude_is_rejected_before_executor() -> None:
    async def fake_executor(request):
        raise AssertionError("executor must not be called")

    graph = build_graph(executor=fake_executor, offline=True)
    state = await graph.ainvoke({"prompt": "飞到100米高", "errors": []})

    assert state["errors"]
    assert "outside allowed" in state["errors"][0]
```

运行：

```bash
pytest tests/test_agent.py -v
```

预期：失败（`agent` 模块不存在）。

- [ ] **Step 2: 实现工具封装（40 分钟）**

创建 `tools.py`：

```python
import asyncio

from uav_agent.config import DEFAULT_CONFIG, Config
from uav_agent.connection import connect
from uav_agent.flight import arm_and_takeoff, land_and_wait
from uav_agent.mission import build_goto_mission, build_square_mission, execute_mission
from uav_agent.safety import validate_request
from uav_agent.schema import MissionRequest


class UavTools:
    def __init__(self, config: Config = DEFAULT_CONFIG) -> None:
        self.config = config

    async def execute(self, request: MissionRequest) -> str:
        drone = await connect(self.config.system_address, self.config.connection_timeout_s)
        home = await anext(drone.telemetry.home())
        battery = await anext(drone.telemetry.battery())

        errors = validate_request(
            request,
            home.latitude_deg,
            home.longitude_deg,
            battery.remaining_percent,
            self.config,
        )
        if errors:
            return "REJECTED: " + "; ".join(errors)

        if request.action == "takeoff_land":
            await arm_and_takeoff(drone, request.altitude_m)
            await asyncio.sleep(5)
            await land_and_wait(drone)
            return f"COMPLETED takeoff/land at {request.altitude_m}m"

        if request.action == "goto":
            assert request.target_lat is not None and request.target_lon is not None
            plan = build_goto_mission(
                request.target_lat,
                request.target_lon,
                request.altitude_m,
            )
        else:
            plan = build_square_mission(
                home.latitude_deg,
                home.longitude_deg,
                request.altitude_m,
                request.leg_m,
            )

        await arm_and_takeoff(drone, request.altitude_m)
        try:
            await execute_mission(drone, plan, self.config.mission_timeout_s)
        finally:
            await land_and_wait(drone)
        return f"COMPLETED {request.action} mission"
```

- [ ] **Step 3: 实现离线解析与 LangGraph（90 分钟）**

创建 `agent.py`：

```python
import os
import re
from typing import Awaitable, Callable, Optional, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from pydantic import ValidationError

from uav_agent.config import DEFAULT_CONFIG
from uav_agent.safety import validate_request
from uav_agent.schema import MissionRequest

Executor = Callable[[MissionRequest], Awaitable[str]]

SYSTEM_PROMPT = (
    "你是无人机任务规划助手。只输出高层任务参数，"
    "不输出姿态、速度、位置控制量。"
)


class AgentState(TypedDict, total=False):
    prompt: str
    mission: Optional[MissionRequest]
    errors: list[str]
    result: Optional[str]


def parse_offline(prompt: str) -> MissionRequest:
    text = prompt.strip()
    lower = text.lower()
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:米|m)", text)
    altitude = float(match.group(1)) if match else 10.0

    if "方形" in text or "square" in lower:
        return MissionRequest(action="square", altitude_m=altitude)
    return MissionRequest(action="takeoff_land", altitude_m=altitude)


def build_graph(executor: Optional[Executor] = None, offline: Optional[bool] = None):
    offline = os.getenv("OFFLINE", "0") == "1" if offline is None else offline

    parser = None
    if not offline:
        parser = ChatOpenAI(
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            api_key=os.getenv("LLM_API_KEY"),
            base_url=os.getenv("LLM_BASE_URL") or None,
            temperature=0,
        ).with_structured_output(MissionRequest)

    async def parse_node(state: AgentState) -> dict:
        try:
            if offline:
                mission = parse_offline(state["prompt"])
            else:
                assert parser is not None
                mission = await parser.ainvoke(
                    [
                        SystemMessage(content=SYSTEM_PROMPT),
                        HumanMessage(content=state["prompt"]),
                    ]
                )
            return {"mission": mission}
        except ValidationError as error:
            return {"errors": [str(error)]}

    async def validate_node(state: AgentState) -> dict:
        mission = state.get("mission")
        if mission is None:
            return {"errors": state.get("errors", []) + ["could not parse mission"]}

        home_lat = float(os.getenv("HOME_LAT", "47.397742"))
        home_lon = float(os.getenv("HOME_LON", "8.545594"))
        battery = float(os.getenv("BATTERY_PERCENT", "100"))
        errors = validate_request(mission, home_lat, home_lon, battery, DEFAULT_CONFIG)
        return {"errors": errors}

    async def execute_node(state: AgentState) -> dict:
        mission = state["mission"]
        assert mission is not None
        if executor is None:
            return {"result": f"DRY-RUN: {mission.model_dump_json()}"}
        return {"result": await executor(mission)}

    def route_after_validate(state: AgentState) -> str:
        return "execute" if not state.get("errors") else "end"

    graph = StateGraph(AgentState)
    graph.add_node("parse", parse_node)
    graph.add_node("validate", validate_node)
    graph.add_node("execute", execute_node)
    graph.add_edge(START, "parse")
    graph.add_edge("parse", "validate")
    graph.add_conditional_edges(
        "validate",
        route_after_validate,
        {"execute": "execute", "end": END},
    )
    graph.add_edge("execute", END)
    return graph.compile()
```

- [ ] **Step 4: 实现 CLI（20 分钟）**

创建 `cli.py`：

```python
import argparse
import asyncio

from dotenv import load_dotenv

from uav_agent.agent import build_graph
from uav_agent.tools import UavTools


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Natural-language UAV mission demo")
    parser.add_argument("prompt", help="自然语言任务，例如：绕方形飞一圈，高度10米")
    parser.add_argument("--offline", action="store_true", help="不调用 LLM，用规则解析")
    parser.add_argument("--dry-run", action="store_true", help="只打印任务 JSON，不飞行")
    args = parser.parse_args()

    executor = None if args.dry_run else UavTools().execute
    graph = build_graph(executor=executor, offline=args.offline or args.dry_run)
    state = asyncio.run(
        graph.ainvoke({"prompt": args.prompt, "errors": []})
    )

    print(f"mission: {state.get('mission')}")
    print(f"errors: {state.get('errors')}")
    print(f"result: {state.get('result')}")


if __name__ == "__main__":
    main()
```

创建 `.env.example`：

```
LLM_MODEL=gpt-4o-mini
LLM_BASE_URL=
LLM_API_KEY=
OFFLINE=0
HOME_LAT=47.397742
HOME_LON=8.545594
BATTERY_PERCENT=100
```

复制一份本地配置并填写：

```bash
cp .env.example .env
```

不要把真实的 API Key 写进笔记、README 或代码；`.env` 只留在本机。

- [ ] **Step 5: 运行测试（10 分钟）**

```bash
pytest tests/ -v
```

预期：全部通过。

- [ ] **Step 6: 三种模式验证（45 分钟）**

规则解析 + 不飞行：

```bash
python -m uav_agent.cli "绕方形飞一圈，高度10米，然后降落" --offline --dry-run
```

预期：打印 `mission:`、`errors: []`、`result: DRY-RUN: ...`。

反例（必须被拒绝）：

```bash
python -m uav_agent.cli "飞到100米高" --offline --dry-run
```

预期：`errors` 包含 `outside allowed`，`result` 为 `None`。

LLM 模式（如已配置 API Key）：

```bash
python -m uav_agent.cli "绕方形飞一圈，高度10米，然后降落"
```

预期：无 API Key 时跳过此步，以离线模式作为本阶段验收；有 API Key 时应输出同样的任务结构。若模型不支持结构化输出，记录报错，阶段 2 再补 JSON 解析兜底。不要为了这一步阻塞阶段 1 的交付。

- [ ] **Step 7: 自测（20 分钟）**

回答：
1. 为什么 LLM 不能直接输出姿态/速度指令？
2. LangGraph 的 parse、validate、execute 三个节点分别负责什么？为什么 validate 必须在 execute 之前？
3. `tools.py` 在执行前为什么还要用真实 home 和电量再校验一次？
4. 如果 LLM 输出非法动作或缺失坐标，系统会在哪一层拒绝？
5. 离线模式的价值是什么？它能替代真实 LLM 测试吗？

**验收标准：**
- 测试全部通过。
- 离线模式正例通过、反例被拒绝。
- 若没有 API Key，离线模式即为本阶段验收；若已配置，LLM 模式需产出同样的任务结构。
- 能说清分层安全设计与各节点职责。

---

### Task 9: 端到端联调（第 7-8 周）

**Files:**
- Modify: `notes/week08.md`
- Create: `labs/stage1/week08/README.md`

**Interfaces:**
- Consumes: 全部已实现模块

- [ ] **Step 1: 启动完整环境（10 分钟）**

WSL2 启动 PX4 SITL + jMAVSim；Windows 启动 QGC；确认连接正常。

- [ ] **Step 2: 正例联调（30 分钟）**

先 dry-run 确认任务结构，再真实执行：

```bash
python -m uav_agent.cli "绕方形飞一圈，高度10米，然后降落" --offline
```

若已配置 LLM，再运行不带 `--offline` 的版本。

验收：Agent 输出任务 → 校验通过 → 起飞 → 方形航线 → 返回 → 降落。全程记录 QGC 截图和终端日志。

- [ ] **Step 3: 反例联调（30 分钟）**

依次测试并记录结果：
1. 高度 100 米：应被拒绝，不得起飞。
2. 电量阈值调低（`BATTERY_PERCENT=20`）：应被拒绝。
3. 目标点超出 200 米（`goto`）：应被拒绝。离线解析暂不生成 goto，可用 Python 直接构造请求测试校验器，或等待阶段 2 的真实 LLM 解析。
4. PX4 未启动时执行：应连接超时并干净报错。

- [ ] **Step 4: 故障演练（30 分钟）**

飞机在方形航线途中停止 SITL。预期：脚本报错退出，QGC 显示失联。记录现象，并思考真机上应该由谁接管。

- [ ] **Step 5: 写联调记录（20 分钟）**

在 `labs/stage1/week08/README.md` 记录：运行命令、终端输出、QGC 截图路径、异常现象、结论。

**验收标准：**
- 正例全链路完成，反例全部被拦截。
- 有截图/日志证据，不是口头描述。
- 能解释 PX4 未启动、中途失联两种故障的行为差异。

---

### Task 10: 打包、文档与阶段验收（第 8 周）

**Files:**
- Create: `projects/agent-uav-demo/README.md`
- Create: `projects/agent-uav-demo/README.en.md`
- Create: `notes/stage1_review.md`
- Modify: `labs/stage1/week08/README.md`

**Interfaces:**
- Consumes: 全部阶段 1 成果

- [ ] **Step 1: 完善 README（90 分钟）**

中文 `README.md` 至少包含：
1. 项目简介与演示 GIF/视频链接。
2. 架构图（Mermaid）：用户 → CLI → LangGraph（parse/validate/execute）→ UavTools → MAVSDK → PX4 SITL。
3. 环境要求：Windows 11 + WSL2 Ubuntu 24.04 + PX4 v1.16.2 SITL + Gazebo（`gz_x500`）+ QGC。
4. 安装与运行命令（venv、pip、PX4、QGC）。
5. 安全设计：分层校验、限制值、为什么 LLM 不输出控制量。
6. 测试命令与预期结果。
7. 已知限制：仅 SITL、仅多旋翼、未接入真机、未做多机。
8. 路线图（阶段 2：MAVLink 精通、地面站、云链路）。

`README.en.md` 是英文摘要版，不要求逐字翻译。

- [ ] **Step 2: 录制演示视频（90 分钟）**

3–5 分钟，按脚本：
1. 展示自然语言输入。
2. 展示任务 JSON 和校验结果。
3. 展示 PX4 SITL 起飞、方形航线、降落。
4. 展示一个被拒绝的危险指令（100 米高度）。
5. 用 30 秒讲清安全分层。

录制前先跑一遍全流程，避免现场翻车。是否公开上传视频与代码仓库由你决定；发布前确认没有 API Key、个人信息或本地路径泄露。

- [ ] **Step 3: 全新环境复现检查（45 分钟）**

新建虚拟环境，按 README 从零执行：

```bash
python3 -m venv /tmp/uav_check
source /tmp/uav_check/bin/activate
cd /mnt/d/Code/UAV/projects/agent-uav-demo
pip install -e ".[dev]"
pytest -q
python -m uav_agent.cli "绕方形飞一圈，高度10米" --offline --dry-run
```

预期：测试通过，dry-run 输出任务 JSON。把过程中缺失的依赖或步骤补回 README。

- [ ] **Step 4: 阶段验收问答（60 分钟）**

在 `notes/stage1_review.md` 回答，准备口头讲解：

1. 画出完整数据流：自然语言 → Agent → MAVSDK → PX4 → 仿真器 → 遥测。
2. 讲清 MAVLink 心跳、命令/确认、任务上传三条消息流。
3. 讲清 NED/ENU、相对/绝对高度、空速/地速。
4. 讲清 Mission 与 Offboard 的区别和适用场景。
5. 讲清你的安全分层：解析约束、结构约束、任务校验、执行前二次校验。
6. 如果接入真机，还需要补什么？（硬件、权限、地理围栏、日志、失控保护、现场流程）
7. 本项目最大的安全风险是什么？如何缓解？
8. 你在本阶段最没把握的三个知识点是什么？下一步怎么补？

- [ ] **Step 5: 复盘与阶段 2 准备（30 分钟）**

在 `notes/stage1_review.md` 写：
- 8 周实际投入时间 vs 计划。
- 卡住最久的问题及原因。
- 哪些知识只是「会用」，还没到「能讲清」。
- 阶段 2 第一周要复习的内容。

**验收标准：**
- README 能让陌生人在新环境复现。
- 视频完整展示正例与反例。
- 8 个验收问题能脱稿讲清。
- 阶段复盘完成。

---

## 资源清单

**官方文档**
- PX4 Gazebo 仿真：https://docs.px4.io/main/en/simulation/gz.html
- PX4 飞行模式：https://docs.px4.io/main/en/flight_modes/
- PX4 消息定义：https://docs.px4.io/main/en/msg_docs/
- PX4 地理围栏：https://docs.px4.io/main/en/config/geofence.html
- PX4 日志分析：https://review.px4.io/
- QGC 文档：https://docs.qgroundcontrol.com/master/en/
- MAVSDK-Python：https://mavsdk.mavlink.io/main/en/python/
- MAVLink 消息：https://mavlink.io/en/messages/common.html
- LangGraph：https://langchain-ai.github.io/langgraph/
- LangChain 结构化输出：https://python.langchain.com/docs/how_to/structured_output/

**使用原则**
- 官方文档优先，社区翻译只作参考。
- 遇到版本差异，以实际安装版本为准，并记录到 `notes/`。
- 不要为了「看完」而看文档；每个任务带着问题查文档。

## 阶段完成定义（Definition of Done）

- [ ] `pytest` 全部通过。
- [ ] 正例：自然语言指令 → 方形航线 → 降落，全流程在 SITL 完成。
- [ ] 反例：超高度、低电量、超距离、断连，全部被正确拦截或安全退出。
- [ ] README 中英文版完成，含架构图、安装、运行、安全说明。
- [ ] 3–5 分钟演示视频完成。
- [ ] 8 个阶段验收问题能脱稿讲清。
- [ ] 阶段复盘写入 `notes/stage1_review.md`。
