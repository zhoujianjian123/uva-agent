# uva-agent

无人机 + LLM Agent 学习与工程实践项目。

目标：把 Agent 开发能力与无人机系统开发结合，最终实现：

```text
自然语言任务 → Agent 规划 → 安全校验 → MAVSDK → PX4 → 无人机执行
```

## 目录结构

| 目录 | 内容 |
|---|---|
| `docs/` | 学习路线设计、阶段计划 |
| `labs/` | 分阶段实验与记录 |
| `notes/` | 每周学习笔记 |
| `projects/agent-uav-demo/` | 阶段 1 项目：MAVSDK + PX4 SITL |

## 当前进度

- 阶段 1 / 第 1 周
- WSL2 Ubuntu 24.04 + PX4 v1.16.2 SITL + Gazebo（`gz_x500`）
- QGroundControl 4.4.5
- MAVSDK-Python 3.17.4（gRPC API）
- 已完成：环境搭建、MAVSDK 连接、遥测读取、系统链路图

## 快速开始

启动 PX4 SITL：

```bash
cd ~/PX4-Autopilot
make px4_sitl gz_x500
```

准备 Python 环境：

```bash
cd /mnt/d/Code/UAV/projects/agent-uav-demo
python3 -m venv ~/.venvs/uav
source ~/.venvs/uav/bin/activate
pip install -e ".[dev]"
```

读取一次遥测：

```bash
python scripts/check_env.py
```

预期输出：

```text
Connected to SITL
battery=100%
lat=...
lon=...
rel_alt=...
mode=HOLD
```

QGC 运行在 Windows，通过 UDP 14550 接收遥测；MAVSDK 通过 `udp://:14540` 连接 PX4 SITL。

## 安全边界

- 所有实验在 SITL 中完成，不涉及真机
- LLM/Agent 只输出高层任务参数，不直接输出姿态、速度或电机控制量
- 任务必须经过确定性校验后才允许执行
- 飞控的失效保护（Hold / RTL / Land）独立于地面程序
