# GPUWebMonitor - GPU 服务器集群监控面板

[中文](README.md) | [English](README.en.md) | [日本語](README.ja.md)

[![License](https://img.shields.io/badge/license-GPL_V3-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12+-green.svg)](https://www.python.org/)
[![Vue](https://img.shields.io/badge/Vue-3-4FC08D.svg)](https://vuejs.org/)
[![Flask](https://img.shields.io/badge/Flask-2.x-000000.svg)](https://flask.palletsprojects.com/)

**GPUWebMonitor** 是一个轻量级 GPU 服务器集群监控系统，可通过一个面板集中查看多台 GPU 服务器的实时状态、系统资源和 GPU 进程信息。

> 本项目仍在开发中，建议在可信内网或受控测试环境中使用，暂不建议直接用于生产环境。

![GPUWebMonitor 预览](pictures/readme1.png)

## 功能特性

- **多节点集中监控**：通过 Dashboard 统一查看所有 Agent 节点
- **实时刷新**：支持手动刷新和 3 秒间隔自动刷新
- **GPU 监控**：核心利用率、显存占用、温度、功耗、风扇转速、显存控制器利用率
- **进程监控**：每个 GPU 的计算进程 PID、用户、显存占用、命令行
- **系统进程监控**：折叠查看高占用系统进程，CPU 使用整机口径，内存使用可相加的 PSS，并支持按 CPU、内存或用户汇总查看
- **系统资源**：CPU 使用率与频率、内存使用量、网络累计收发与实时速率
- **利用率趋势图**：CPU / 内存 / GPU 平均利用率的 SVG 折线图，支持实时模式和历史模式（10 分钟、30 分钟、1 小时、6 小时、12 小时）
- **历史数据记录**：Agent 每 30 秒写入 SQLite，默认保留 30 天
- **三语支持**：中文、English、日本語，自动检测浏览器语言
- **主题切换**：自动 / 浅色 / 深色三种模式，跟随系统偏好
- **响应式设计**：适配桌面、平板和手机，移动端自动切换布局
- **本地化部署**：前端资源全部本地加载，无外部 CDN 依赖

## 架构

```text
浏览器
  |
  | 访问 Dashboard: http://<dashboard-host>:28456
  v
Dashboard 服务 backend/dashboard.py
  |
  | 读取 front/config.json，将请求代理到目标 Agent
  v
Agent 服务 backend/app.py
  |
  | 使用 nvitop / NVML / psutil 采集数据
  v
GPU 与系统状态
```

默认端口：

| 服务 | 文件 | 默认端口 | 说明 |
| --- | --- | ---: | --- |
| Agent | `backend/app.py` | `15896` | 运行在每台被监控的 GPU 服务器上 |
| Dashboard | `backend/dashboard.py` | `28456` | 监控入口，也可与 Agent 运行在同一台机器 |

## 环境要求

- Python 3.12+
- NVIDIA 驱动和可用的 NVML 环境
- 被监控节点需能正常运行 `nvidia-smi`
- Linux 下建议使用 systemd 管理服务

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/University-Pro/GPUWebMonitor.git
cd GPUWebMonitor
```

### 2. 创建 Python 环境

建议创建独立的 Python 环境，可选择 `venv` 或 `conda`。

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

激活环境后，确认当前使用的 Python 路径：

```bash
where python    # Windows
which python    # Linux / macOS
```

后续配置 systemd 时需要使用该绝对路径。

### 3. 安装后端依赖

在 Dashboard 服务器和每台 Agent 服务器上安装：

```bash
cd backend
pip install -r requirements.txt
```

### 3.1 预编译前端模板

仅在修改 `front/index.html` 或升级 Vue 时需要执行。构建过程会生成 CSP 兼容的渲染函数和 runtime-only Vue 文件，线上浏览器不需要 `unsafe-eval`：

```bash
pnpm install
pnpm run build:front
pnpm run check:front
```

部署时需要包含生成的 `front/app.render.js` 和 `front/vendor/vue.runtime.global.prod.js`。

### 4. 配置服务器列表

编辑 `front/config.json`，将各 Agent 添加到 `servers` 数组：

```json
{
  "servers": [
    {
      "id": "server1",
      "name": "5090D 服务器",
      "url": "http://192.168.1.101:15896"
    },
    {
      "id": "server2",
      "name": "4090 服务器",
      "url": "http://192.168.1.102:15896"
    }
  ]
}
```

| 字段 | 说明 |
| --- | --- |
| `id` | 节点唯一标识，建议使用英文字母、数字和连字符 |
| `name` | 前端显示名称 |
| `url` | Agent 服务地址，默认端口 `15896` |

### 5. 启动 Agent

在每台被监控的 GPU 服务器上运行：

```bash
cd backend
python app.py
```

验证 Agent 是否正常：

```bash
curl http://127.0.0.1:15896/
curl http://127.0.0.1:15896/api/status
```

### 6. 启动 Dashboard

在监控入口服务器上运行：

```bash
cd backend
python dashboard.py
```

浏览器打开：

```text
http://<dashboard-host>:28456
```

本机访问可使用：

```text
http://127.0.0.1:28456
```

## systemd 部署

### Agent 服务

确认 Python 路径后，创建 `/etc/systemd/system/gpu-monitor-agent.service`：

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

查看状态和日志：

```bash
systemctl status gpu-monitor-agent
systemctl status gpu-monitor-dashboard
journalctl -u gpu-monitor-agent -f
journalctl -u gpu-monitor-dashboard -f
```

## 配置说明

### 部署模式

`GPU_MONITOR_DEPLOYMENT_MODE` 是服务器端安全开关，支持 `public` 和 `lan`。未设置时保持原项目兼容行为：使用 `lan` 模式和 `front/config.json`。该模式必须通过环境变量或 systemd 配置，不能由网页切换。

| 能力 | `public` 公网模式 | `lan` 局域网模式 |
| --- | --- | --- |
| Dashboard 登录 | 强制 HTTP Basic；缺少凭据时返回 503 | 不需要用户名和密码 |
| Agent API | 强制 Bearer Token；缺少 Token 时返回 503 | 不需要 Token |
| 节点 URL | `/api/config` 只返回 ID 和名称 | 返回完整内网 URL，兼容原 GitHub 版 |
| `/config.json` | 禁止访问所有节点配置 JSON | 返回当前局域网节点配置 |
| CORS | 关闭，仅允许同源网页通过 Dashboard 访问 | 开启，允许局域网网页直接访问 API |
| HTTPS/CSP | 建议使用 `deploy/nginx-gpu-monitor.conf` | 可直接使用 HTTP，不发送 HSTS |

公网模式示例：

```bash
export GPU_MONITOR_DEPLOYMENT_MODE=public
export GPU_MONITOR_DASHBOARD_USERNAME='monitor'
export GPU_MONITOR_DASHBOARD_PASSWORD='replace-with-strong-password'
export GPU_MONITOR_AGENT_TOKEN='replace-with-random-token'
```

局域网模式示例：

```bash
export GPU_MONITOR_DEPLOYMENT_MODE=lan
export GPU_MONITOR_DASHBOARD_HOST=0.0.0.0
export GPU_MONITOR_DASHBOARD_PORT=28456
```

两个模式可以使用不同端口和 systemd 服务同时运行。公网和局域网的默认节点列表分别为 `front/config.public.json` 与 `front/config.lan.json`；`GPU_MONITOR_CONFIG_FILE` 仍可覆盖默认路径。

### Agent 配置

主要配置项位于 `backend/app.py` 顶部：

| 配置项 | 默认值 | 说明 |
| --- | ---: | --- |
| `PORT` | `15896` | Agent 监听端口 |
| `RECORD_INTERVAL` | `30` | 历史数据采集间隔（秒） |
| `KEEP_HISTORY_DAYS` | `30` | SQLite 历史数据保留天数 |
| `DB_FILE` | `backend/monitor_data.db` | 历史数据文件路径 |

以下环境变量可用于部署加固：

| 环境变量 | 作用 |
| --- | --- |
| `GPU_MONITOR_DEPLOYMENT_MODE` | `public` 或 `lan`；未设置时兼容原版 `lan` 行为 |
| `GPU_MONITOR_AGENT_TOKEN` | 公网模式必须设置；所有 Agent `/api/*` 请求需携带同值 Bearer Token |
| `GPU_MONITOR_HOST` | Agent 监听地址，默认 `0.0.0.0` |
| `GPU_MONITOR_PORT` | Agent 监听端口，默认 `15896` |

### Dashboard 配置

Dashboard 根据部署模式读取 `front/config.public.json` 或 `front/config.lan.json`，并通过 `/api/proxy?id=<server_id>` 将请求转发到目标 Agent。未设置模式时继续读取原有的 `front/config.json`。

| 环境变量 | 作用 |
| --- | --- |
| `GPU_MONITOR_DEPLOYMENT_MODE` | `public` 或 `lan`；未设置时兼容原版 `lan` 行为 |
| `GPU_MONITOR_DASHBOARD_USERNAME` | 公网模式必须设置的 HTTP Basic 用户名；局域网模式忽略 |
| `GPU_MONITOR_DASHBOARD_PASSWORD` | 公网模式必须设置的 HTTP Basic 密码；局域网模式忽略 |
| `GPU_MONITOR_AGENT_TOKEN` | 公网模式必须设置；局域网模式不会发送 |
| `GPU_MONITOR_DASHBOARD_HOST` | Dashboard 监听地址，默认 `0.0.0.0` |
| `GPU_MONITOR_DASHBOARD_PORT` | Dashboard 监听端口，默认 `28456` |
| `GPU_MONITOR_CONFIG_FILE` | 可选的节点配置文件路径，默认 `front/config.json` |
| `GPU_MONITOR_VERIFY_AGENT_TLS` | 是否校验 HTTPS Agent 证书；公网默认开启，局域网默认关闭 |

公网部署时建议同时配置 Dashboard 用户名、密码和 Agent Token，并使用 HTTPS 反向代理。`/api/config` 仅向浏览器返回节点 ID 与名称，不公开 Agent 内网地址。

## API

### Agent

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/` | 健康检查 |
| `GET` | `/api/status` | 获取当前 GPU 和系统状态 |
| `GET` | `/api/history?limit=100` | 获取历史监控数据，`limit` 最大值为 1000 |

### Dashboard

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/` | 前端页面 |
| `GET` | `/api/config` | 获取服务器配置 |
| `GET` | `/api/proxy?id=<server_id>` | 代理请求到目标 Agent，支持 `history=1&limit=N` 查询历史数据 |

## 项目结构

```text
GPUWebMonitor/
├── backend/
│   ├── app.py             # Agent 服务，运行在被监控服务器上
│   ├── dashboard.py       # Dashboard 服务，前端代理和请求转发
│   ├── gpu_monitor.py     # GPU 和系统指标采集逻辑
│   ├── stress.py          # 压力测试脚本
│   └── requirements.txt   # Python 依赖
├── front/
│   ├── index.html         # 前端页面
│   ├── app.js             # 前端业务逻辑
│   ├── app.render.js      # 预编译模板生成的渲染函数
│   ├── style.css          # 前端样式
│   ├── config.json        # 监控节点配置
│   ├── config.public.json # 公网模式节点配置
│   ├── config.lan.json    # 局域网模式节点配置
│   ├── vendor/            # 本地化前端依赖
│   │   ├── vue.runtime.global.prod.js
│   │   ├── element-plus.js
│   │   ├── element-plus.css
│   │   └── element-plus-icons.js
│   └── favicon / icon     # 浏览器图标资源
├── pictures/
│   └── readme1.png        # README 预览截图
├── scripts/
│   └── build-front.mjs    # CSP 兼容的前端预编译脚本
├── package.json
├── LICENSE
└── README.md
```

## 技术栈

- **后端**：Python、Flask、Flask-CORS、nvitop、psutil、SQLite
- **前端**：Vue 3 runtime-only、Element Plus、预编译渲染函数
- **部署**：直接运行 Python 服务，或通过 systemd 管理

## 常见问题

### Dashboard 无法加载服务器列表

- 确认 Dashboard 正在运行，且访问地址为 `http://<dashboard-host>:28456`
- 确认 `front/config.json` 是有效的 JSON
- 查看 Dashboard 日志是否有配置文件路径或 JSON 解析错误

### 节点无法返回数据

- 确认目标 Agent 正在运行：`curl http://<agent-host>:15896/api/status`
- 确认 Dashboard 服务器可以访问 Agent URL
- 检查 `front/config.json` 中该节点的 `url` 是否包含正确端口

### GPU 信息为空或权限不足

- 确认 NVIDIA 驱动已安装且 `nvidia-smi` 可正常运行
- 确认运行 Agent 的用户有权限读取 GPU 和进程信息
- 查看其他用户进程的完整命令行可能需要调整系统权限

### 端口被占用

```bash
ss -ltnp | grep -E '15896|28456'
```

修改端口：编辑 `backend/app.py` 中的 `PORT` 和 `backend/dashboard.py` 中的 `app.run(..., port=28456)`。

## 许可证

本项目基于 GNU General Public License v3.0 开源，详见 [LICENSE](LICENSE)。

## 致谢

- [nvitop](https://github.com/XuehaiPan/nvitop)
- [psutil](https://github.com/giampaolo/psutil)
- [Vue](https://vuejs.org/)
- [Element Plus](https://element-plus.org/)
