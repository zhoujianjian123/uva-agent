# Week 01 学习笔记（2026-10-20）

## 1. 环境版本

| 项目 | 值 | 获取方式 |
|---|---|---|
| Windows | Windows 11 Pro 10.0.26200 | 系统信息 |
| WSL2 | Ubuntu 24.04.5 LTS | `wsl -l -v` / `uname -a` |
| Python | 3.12.3 | `python3 --version` |
| PX4 | v1.16.2 | `git -C ~/PX4-Autopilot describe --tags --always` |
| 仿真器 | Gazebo（`gz` CLI，`gz_x500` 机型） | `make px4_sitl gz_x500` |
| QGC | 4.4.5.0 | QGC → About |
| MAVSDK-Python | 3.17.4（gRPC API） | `importlib.metadata.version("mavsdk")` |

关键路径：

- 项目目录：`D:\Code\UAV\projects\agent-uav-demo`
- WSL2 项目路径：`/mnt/d/Code/UAV/projects/agent-uav-demo`
- Python 虚拟环境：`~/.venvs/uav`
- PX4 源码：`~/PX4-Autopilot`
- QGC：`D:\Software\QGroundControl\QGroundControl.exe`

## 2. 连接方式

- WSL2 使用 **mirrored 网络模式**
- QGC 运行在 Windows，通过 **UDP 14550** 接收遥测
- MAVSDK 运行在 WSL2，通过 **`udp://:14540`** 连接 PX4 SITL
- SITL 启动命令：

```bash
cd ~/PX4-Autopilot
make px4_sitl gz_x500
```

- 预期启动标志：Gazebo 窗口打开，PX4 终端出现 `Ready for takeoff!`，QGC 自动连接
- MAVSDK 3.17.4 对 `udp://` 有弃用提示，建议未来迁移 `udpin://` / `udpout://`；阶段 2 再处理
- `mavsdk` 包有 FutureWarning：未来会更名为 `mavsdk-grpc`；阶段 1 固定 `mavsdk>=2.8,<4`，暂不迁移

## 3. MAVLink 消息观察

在 QGC 的 **Analyze Tools → MAVLink 检测** 中观察：

| 消息 | ID | 观察结果 |
|---|---|---|
| HEARTBEAT | 0 | 约 0.8 Hz，已确认 |
| SYS_STATUS | 1 | 约 0.2–0.8 Hz，已确认；包含电量字段 |
| ATTITUDE | 30 | 约 26.5 Hz |
| LOCAL_POSITION_NED | 32 | 约 28.9 Hz |
| GLOBAL_POSITION_INT | 33 | 约 31.0 Hz |
| COMMAND_LONG | 76 | 事件驱动，切换飞行模式时出现（本周未完整观察） |
| COMMAND_ACK | 77 | 事件驱动，命令后紧跟着出现（本周未完整观察） |
| BATTERY_STATUS | 147 | PX4 SITL 未持续发送；电量信息在 SYS_STATUS 中 |

结论：

- MAVLink 消息分为**周期消息**和**事件驱动消息**
- 不是所有消息都会一直出现在 Inspection 列表里
- 电池数据可能出现在 SYS_STATUS 而不是 BATTERY_STATUS
- QGC 的 MAVLink Inspector 路径：Q 图标 → Analyze Tools → MAVLink 检测

## 4. check_env.py 运行输出

首次运行（电量格式有 bug）：

```text
Connected to SITL
battery=10000%
lat=47.397971 lon=8.546164 rel_alt=0.1m
mode=HOLD
```

原因：MAVSDK 3.17.4 的 `remaining_percent` 已经是 0–100，`:.0%` 又乘了 100。

修正为 `:.0f}%` 后的预期输出：

```text
Connected to SITL
battery=100%
lat=47.397971 lon=8.546164 rel_alt=0.1m
mode=HOLD
```

说明：

- `lat/lon` 是 PX4 SITL 默认 home 附近的坐标
- `rel_alt` 是相对 home 的高度，不是海拔
- `mode=HOLD` 是当前飞行模式；不同启动时刻可能显示其他模式

## 5. 本周问题与结论

### 5.1 Battery unhealthy

现象：

```text
WARN [health_and_arming_checks] Preflight Fail: Battery unhealthy
```

排查：

- `commander check` 只报 Battery unhealthy
- `uorb top -1 battery_status` 显示 0 Hz
- `listener battery_status -n 1` 显示最后一次更新在 1538 秒前
- 电池数据本身正常：`connected=True`、`warning=0`、`faults=0`、`remaining=99.995%`
- `SIM_BAT_ENABLE=1`，`battery_simulator` 状态为 running

结论：

- 健康检查包含**数据新鲜度**：超过 5 秒没有更新就判定为 unhealthy
- 重启 SITL 后恢复
- 这不是电池没电，而是 `battery_status` 停止发布

### 5.2 MAVSDK 版本

- 第一次 `pip install` 装到 4.0.6，4.x 是新的原生绑定，API 不兼容
- `from mavsdk.mission import MissionItem` 在 4.x 会报 `LegacyModuleError`
- 解决：`pyproject.toml` 固定 `mavsdk>=2.8,<4`，最终安装 3.17.4
- 3.17.4 没有 `mavsdk.__version__`，版本查询用：

```bash
python -c "from importlib.metadata import version; print(version('mavsdk'))"
```

### 5.3 连接地址

- 错误写法：`udp//:14540` → `Unknown protocol` / `Invalid connection URL`
- 正确写法：`udp://:14540`
- `connection.py` 的 30 秒超时是**启动握手**，不是长期连接监督
- 断链监控、自动重连、命令闸门属于阶段 2 的 ConnectionManager

### 5.4 下降命令与速度

- PX4 自动降落速度受 `MPC_LAND_SPEED = 0.7 m/s` 限制
- 接近地面时 `MPC_LAND_ALT1/2/3 = 10 / 5 / 1 m` 会进一步减速
- `MPC_Z_VEL_MAX_DN = 1.5 m/s` 是位置控制的最大下降速度
- 看起来“执行不力”是安全限速，不是故障

### 5.5 其他环境问题

- WSL2 缺少 `python3.12-venv` 时，`python3 -m venv` 会报 `ensurepip is not available`
  - 解决：`sudo apt install -y python3.12-venv`，然后 `python3 -m venv --clear ~/.venvs/uav`
- 在 Windows PowerShell 里不能用 `source` 激活 Linux venv
  - 解决：在 WSL2 Ubuntu 终端里操作，提示符应为 `zhoujianjian@DESKTOP-PNHNJPD:...$`
- `pip install` 报 `externally-managed-environment`
  - 原因：没有激活 venv，调用了系统 pip
  - 解决：先 `source ~/.venvs/uav/bin/activate`，确认 `(uav)` 出现

## 6. 自测问题与参考答案

### 1. `sysid` 和 `compid` 分别标识什么？

- `sysid`：系统/载具 ID。一个 MAVLink 网络里，一架飞机是一个 system
- `compid`：系统内部组件 ID。飞控、云台、相机、地面站可以是同一 system 下的不同组件
- PX4 飞控默认 `sysid=1`、`compid=1`；QGC 通常使用 `sysid=255`
- 心跳里的 sysid/compid 用来判断“这条消息来自谁”

### 2. 14540 和 14550 分别是什么角色？

- PX4 SITL 会启动多个 MAVLink 实例：
  - **Normal** 实例发送到 **14550**，给 QGC 用
  - **Onboard** 实例发送到 **14540**，给 MAVSDK/机载程序用
- QGC 监听 14550；MAVSDK 通过 `udp://:14540` 连接
- 两者是不同端口，避免地面站和机载程序抢同一条链路

### 3. 心跳丢失后，QGC 和飞控各自会发生什么？

- QGC：遥测停止，显示连接丢失
- PX4：超过 `COM_DL_LOSS_T` 后触发数据链丢失失效保护，按 `NAV_DLL_ACT` 执行 Hold / RTL / Land
- 实测：之前的连接丢失出现了 `Failsafe activated → Hold for 5 seconds → RTL`
- 结论：飞控有独立兜底，地面程序不是唯一安全层

### 4. 画出 Agent → MAVSDK → PX4 → 仿真器的数据流

```text
用户自然语言
    ↓
Agent（LangGraph：parse → validate → execute）
    ↓ 工具调用
MAVSDK-Python（System/Action/Mission/Telemetry）
    ↓ MAVLink over UDP 14540
PX4（mavlink 模块 → commander/navigator → 控制模块）
    ↓ 执行器输出
Gazebo（x500 模型）
    ↓ 传感器/状态
PX4（estimator → mavlink 遥测）
    ↓
MAVSDK → Agent（以及 QGC 经 14550 显示）
```

## 7. 下周目标

- 写 `telemetry_logger.py`，记录 60 秒遥测 CSV
- 理解并解释：
  - NED 与 ENU
  - 相对高度与绝对高度
  - 空速与地速
  - Position / Altitude / Hold 模式的区别
  - RTL 的高度逻辑
- 完成 `notes/week02.md` 和 `labs/stage1/week02/README.md`
- 复习 Task 1 自测题，能脱稿讲清
