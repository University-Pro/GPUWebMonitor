# GPUWebMonitor - GPU 服务器集群监控面板

[中文](README.md) | [English](README.en.md) | [日本語](README.ja.md)

[![License](https://img.shields.io/badge/license-GPL_V3-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12+-green.svg)](https://www.python.org/)
[![Vue](https://img.shields.io/badge/Vue-3-4FC08D.svg)](https://vuejs.org/)
[![Flask](https://img.shields.io/badge/Flask-2.x-000000.svg)](https://flask.palletsprojects.com/)

**GPUWebMonitor** 是一个轻量级 GPU 服务器监控系统，用于集中查看多台 GPU 服务器的实时状态、系统资源和 GPU 进程信息。

> 项目仍在开发中，建议在可信内网或受控测试环境中使用，暂不建议直接用于生产环境。

![GPUWebMonitor 预览](pictures/readme1.png)

## 功能特性

- **多服务器集中监控**：通过 Dashboard 统一查看多台 Agent 节点状态。
- **实时状态刷新**：前端支持手动刷新和自动刷新。
- **GPU 指标展示**：显示利用率、显存、温度、功耗、风扇转速等信息。
- **进程级监控**：展示占用 GPU 的进程 PID、用户、进程名、显存占用和命令行。
- **系统资源监控**：展示 CPU、内存和网络收发数据。
- **历史数据记录**：Agent 默认每 30 秒写入一次 SQLite 历史数据，并保留 30 天。
- **静态前端部署简单**：Dashboard 服务会直接托管 `front/` 目录下的前端页面和静态资源。

## 系统架构

```text
浏览器
  |
  | 访问 Dashboard: http://<dashboard-host>:28456
  v
Dashboard 服务 backend/dashboard.py
  |
  | 读取 front/config.json，代理请求到对应 Agent
  v
Agent 服务 backend/app.py
  |
  | 调用 nvitop / NVML / psutil
  v
GPU 与系统状态
```

默认端口：

| 服务 | 文件 | 默认端口 | 说明 |
| --- | --- | ---: | --- |
| Agent | `backend/app.py` | `15896` | 部署在每台被监控 GPU 服务器上 |
| Dashboard | `backend/dashboard.py` | `28456` | 部署在监控入口服务器上，也可以和某台 Agent 共用一台机器 |

## 环境要求

- Python 3.12+
- NVIDIA 驱动和可用的 NVML 环境
- 被监控节点建议安装并可正常使用 `nvidia-smi`
- Linux 环境推荐使用 systemd 托管服务

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/University-Pro/GPUWebMonitor.git
cd GPUWebMonitor
```

### 2. 创建 Python 环境

推荐为项目创建独立 Python 环境，避免依赖和系统环境混在一起。下面任选一种方式即可。

使用 `venv`：

```bash
python -m venv .venv
source .venv/bin/activate
```

使用 `conda`：

```bash
conda create -n gpuwebmonitor python=3.12
conda activate gpuwebmonitor
```

激活环境后，可以查看当前正在使用的 Python 路径：

```bash
where python
```

在 Linux/macOS 上也可以使用：

```bash
which python
```

后续配置 systemd 时，建议把这里查到的 Python 绝对路径写入 `ExecStart`。

### 3. 安装后端依赖

在 Dashboard 服务器和每台 Agent 服务器上安装依赖：

```bash
cd backend
pip install -r requirements.txt
```

### 4. 配置服务器列表

编辑 `front/config.json`，把每台 Agent 的地址写入 `servers`：

```json
{
  "servers": [
    {
      "id": "server1",
      "name": "2080Ti 服务器",
      "url": "http://192.168.30.246:15896"
    },
    {
      "id": "server2",
      "name": "4090D 服务器",
      "url": "http://192.168.30.223:15896"
    }
  ]
}
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| `id` | 节点唯一标识，建议使用英文、数字或短横线 |
| `name` | 前端展示名称 |
| `url` | Agent 服务地址，默认端口为 `15896` |

### 5. 启动 Agent

在每台被监控 GPU 服务器上执行：

```bash
cd backend
python app.py
```

启动后可通过下面的接口检查 Agent 是否正常：

```bash
curl http://127.0.0.1:15896/
curl http://127.0.0.1:15896/api/status
```

### 6. 启动 Dashboard

在监控入口服务器上执行：

```bash
cd backend
python dashboard.py
```

浏览器访问：

```text
http://<dashboard-host>:28456
```

如果 Dashboard 和浏览器在同一台机器上，可以访问：

```text
http://127.0.0.1:28456
```

## systemd 部署示例

### Agent 服务

先确认当前环境的 Python 解释器路径：

```bash
where python
# Linux/macOS 也可使用：which python
```

创建 `/etc/systemd/system/gpu-monitor-agent.service`，并将 `ExecStart` 中的 `/path/to/python` 替换为上面查到的绝对路径：

```ini
[Unit]
Description=GPU Monitor Agent
After=network.target

[Service]
User=YOUR_USER
Group=YOUR_GROUP
WorkingDirectory=/path/to/GPUWebMonitor/backend
ExecStart=/path/to/python app.py
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

### Dashboard 服务

同样将 `ExecStart` 中的 `/path/to/python` 替换为当前环境的 Python 绝对路径。

创建 `/etc/systemd/system/gpu-monitor-dashboard.service`：

```ini
[Unit]
Description=GPU Monitor Dashboard
After=network.target

[Service]
User=YOUR_USER
Group=YOUR_GROUP
WorkingDirectory=/path/to/GPUWebMonitor/backend
ExecStart=/path/to/python dashboard.py
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

启用并启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now gpu-monitor-agent
sudo systemctl enable --now gpu-monitor-dashboard
```

查看运行状态和日志：

```bash
systemctl status gpu-monitor-agent
systemctl status gpu-monitor-dashboard
journalctl -u gpu-monitor-agent -f
journalctl -u gpu-monitor-dashboard -f
```

## 配置说明

### Agent 配置

Agent 的主要配置位于 `backend/app.py` 顶部：

| 配置 | 默认值 | 说明 |
| --- | ---: | --- |
| `PORT` | `15896` | Agent 监听端口 |
| `RECORD_INTERVAL` | `30` | 历史数据采集间隔，单位秒 |
| `KEEP_HISTORY_DAYS` | `30` | SQLite 历史数据保留天数 |
| `DB_FILE` | `backend/monitor_data.db` | 历史数据文件路径 |

### Dashboard 配置

Dashboard 会读取：

```text
front/config.json
```

并通过 `/api/proxy?id=<server_id>` 将前端请求转发到对应 Agent 的 `/api/status` 接口。

## API 接口

### Agent

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/` | 健康检查 |
| `GET` | `/api/status` | 获取当前 GPU 和系统状态 |
| `GET` | `/api/history?limit=100` | 获取历史监控数据，最大 `limit` 为 1000 |

### Dashboard

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/` | 前端页面 |
| `GET` | `/api/config` | 获取服务器配置 |
| `GET` | `/api/proxy?id=<server_id>` | 代理请求到指定 Agent |

## 项目结构

```text
GPUWebMonitor/
├── backend/
│   ├── app.py             # Agent 服务，运行在被监控服务器
│   ├── dashboard.py       # Dashboard 服务，托管前端并代理 Agent 请求
│   ├── gpu_monitor.py     # GPU 和系统指标采集逻辑
│   ├── stress.py          # 压力测试脚本
│   └── requirements.txt   # Python 依赖
├── front/
│   ├── index.html         # 前端页面
│   ├── app.js             # 前端业务逻辑
│   ├── style.css          # 前端样式
│   ├── config.json        # 被监控服务器配置
│   └── favicon / icon     # 浏览器图标资源
├── pictures/
│   └── readme1.png        # README 预览图
├── LICENSE
└── README.md
```

## 技术栈

- **后端**：Python、Flask、Flask-CORS、nvitop、psutil、SQLite
- **前端**：Vue 3、Element Plus、原生 JavaScript
- **部署**：直接运行 Python 服务，或使用 systemd 托管

## 故障排查

### Dashboard 页面无法加载服务器列表

- 确认 Dashboard 已启动，并访问的是 `http://<dashboard-host>:28456`。
- 确认 `front/config.json` 是合法 JSON。
- 查看 Dashboard 日志中是否有配置文件路径或 JSON 解析错误。

### 某个节点获取数据失败

- 确认目标 Agent 正在运行：`curl http://<agent-host>:15896/api/status`。
- 确认 Dashboard 服务器可以访问 Agent 地址。
- 检查 `front/config.json` 中该节点的 `url` 是否包含正确端口。

### GPU 信息为空或权限不足

- 确认服务器已安装 NVIDIA 驱动，并且 `nvidia-smi` 可正常输出。
- 确认运行 Agent 的用户有权限读取 GPU 和进程信息。
- 如需查看其他用户进程的完整命令行，可能需要调整系统权限或使用具备相应权限的用户运行 Agent。

### 端口被占用

```bash
ss -ltnp | grep -E '15896|28456'
```

如需修改端口，请分别调整 `backend/app.py` 中的 `PORT` 和 `backend/dashboard.py` 中的 `app.run(..., port=28456)`。

## 许可证

本项目基于 GNU General Public License v3.0 开源，详情见 [LICENSE](LICENSE)。

## 致谢

- [nvitop](https://github.com/XuehaiPan/nvitop)
- [psutil](https://github.com/giampaolo/psutil)
- [Vue](https://vuejs.org/)
- [Element Plus](https://element-plus.org/)
