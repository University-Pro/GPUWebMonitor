# GPUWebMonitor - GPU Server Cluster Monitoring Dashboard

[中文](README.md) | [English](README.en.md) | [日本語](README.ja.md)

[![License](https://img.shields.io/badge/license-GPL_V3-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12+-green.svg)](https://www.python.org/)
[![Vue](https://img.shields.io/badge/Vue-3-4FC08D.svg)](https://vuejs.org/)
[![Flask](https://img.shields.io/badge/Flask-2.x-000000.svg)](https://flask.palletsprojects.com/)

**GPUWebMonitor** is a lightweight GPU server monitoring system for viewing real-time status, system resources, and GPU process information across multiple GPU servers from a single dashboard.

> This project is still under development. Use it in a trusted intranet or controlled test environment. It is not recommended for direct production use yet.

![GPUWebMonitor Preview](pictures/readme1.png)

## Features

- **Centralized multi-server monitoring**: View multiple Agent nodes from one Dashboard
- **Live refresh**: Manual refresh and 3-second auto-refresh
- **GPU monitoring**: Core utilization, VRAM usage, temperature, power, fan speed, memory controller utilization
- **Process monitoring**: Per-GPU compute process PID, user, GPU memory usage, command line
- **System resources**: CPU usage and frequency, memory usage, cumulative and real-time network I/O
- **Utilization trend chart**: SVG polyline chart for CPU / Memory / GPU average, supporting live mode and historical mode (10 min, 30 min, 1 hour, 6 hours, 12 hours)
- **Historical data recording**: Agent writes to SQLite every 30 seconds, retains 30 days by default
- **Three-language support**: 中文, English, 日本語 with auto-detection from browser locale
- **Theme switching**: Auto / Light / Dark modes, follows system preference
- **Responsive design**: Adapts to desktop, tablet, and mobile with automatic layout switching
- **Self-contained deployment**: All frontend assets served locally, no external CDN dependencies

## Architecture

```text
Browser
  |
  | Visit Dashboard: http://<dashboard-host>:28456
  v
Dashboard service backend/dashboard.py
  |
  | Reads front/config.json and proxies requests to the selected Agent
  v
Agent service backend/app.py
  |
  | Uses nvitop / NVML / psutil to collect data
  v
GPU and system status
```

Default ports:

| Service | File | Default Port | Description |
| --- | --- | ---: | --- |
| Agent | `backend/app.py` | `15896` | Runs on each monitored GPU server |
| Dashboard | `backend/dashboard.py` | `28456` | Monitoring entry point; can also run on the same machine as an Agent |

## Requirements

- Python 3.12+
- NVIDIA driver and a working NVML environment
- Monitored nodes should be able to run `nvidia-smi`
- systemd is recommended for service management on Linux

## Quick Start

### 1. Clone the project

```bash
git clone https://github.com/University-Pro/GPUWebMonitor.git
cd GPUWebMonitor
```

### 2. Create a Python environment

It is recommended to create an isolated Python environment. Choose either `venv` or `conda`.

Using `venv`:

```bash
python -m venv .venv
source .venv/bin/activate
```

Using `conda`:

```bash
conda create -n gpuwebmonitor python=3.12
conda activate gpuwebmonitor
```

After activating the environment, check the Python path:

```bash
where python    # Windows
which python    # Linux / macOS
```

Use this absolute path in `ExecStart` when configuring systemd later.

### 3. Install backend dependencies

Install on both the Dashboard server and every Agent server:

```bash
cd backend
pip install -r requirements.txt
```

### 4. Configure the server list

Edit `front/config.json` and add each Agent to `servers`:

```json
{
  "servers": [
    {
      "id": "server1",
      "name": "5090D Server",
      "url": "http://192.168.30.107:15896"
    },
    {
      "id": "server2",
      "name": "4090 Server",
      "url": "http://192.168.30.16:15896"
    }
  ]
}
```

| Field | Description |
| --- | --- |
| `id` | Unique node ID. English letters, numbers, and hyphens are recommended |
| `name` | Display name in the frontend |
| `url` | Agent service URL. The default port is `15896` |

### 5. Start the Agent

Run on each monitored GPU server:

```bash
cd backend
python app.py
```

Verify the Agent is working:

```bash
curl http://127.0.0.1:15896/
curl http://127.0.0.1:15896/api/status
```

### 6. Start the Dashboard

Run on the monitoring entry server:

```bash
cd backend
python dashboard.py
```

Open in your browser:

```text
http://<dashboard-host>:28456
```

Local access:

```text
http://127.0.0.1:28456
```

## systemd Deployment

### Agent service

After confirming the Python path, create `/etc/systemd/system/gpu-monitor-agent.service`:

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

### Dashboard service

Create `/etc/systemd/system/gpu-monitor-dashboard.service`:

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

Enable and start the services:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now gpu-monitor-agent
sudo systemctl enable --now gpu-monitor-dashboard
```

Check status and logs:

```bash
systemctl status gpu-monitor-agent
systemctl status gpu-monitor-dashboard
journalctl -u gpu-monitor-agent -f
journalctl -u gpu-monitor-dashboard -f
```

## Configuration

### Agent configuration

Main settings are at the top of `backend/app.py`:

| Setting | Default | Description |
| --- | ---: | --- |
| `PORT` | `15896` | Agent listen port |
| `RECORD_INTERVAL` | `30` | Historical data collection interval (seconds) |
| `KEEP_HISTORY_DAYS` | `30` | SQLite history retention period (days) |
| `DB_FILE` | `backend/monitor_data.db` | Historical data file path |

### Dashboard configuration

Dashboard reads `front/config.json` for the server list and forwards requests via `/api/proxy?id=<server_id>` to the target Agent.

## API

### Agent

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/` | Health check |
| `GET` | `/api/status` | Get current GPU and system status |
| `GET` | `/api/history?limit=100` | Get historical data. Max `limit` is 1000 |

### Dashboard

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/` | Frontend page |
| `GET` | `/api/config` | Get server configuration |
| `GET` | `/api/proxy?id=<server_id>` | Proxy to Agent. Supports `history=1&limit=N` for historical data |

## Project Structure

```text
GPUWebMonitor/
├── backend/
│   ├── app.py             # Agent service, runs on monitored servers
│   ├── dashboard.py       # Dashboard service, frontend proxy and request forwarding
│   ├── gpu_monitor.py     # GPU and system metric collection logic
│   ├── stress.py          # Stress test script
│   └── requirements.txt   # Python dependencies
├── front/
│   ├── index.html         # Frontend page
│   ├── app.js             # Frontend application logic
│   ├── style.css          # Frontend styles
│   ├── config.json        # Monitored server configuration
│   ├── vendor/            # Localized frontend dependencies
│   │   ├── vue.global.prod.js
│   │   ├── element-plus.js
│   │   ├── element-plus.css
│   │   └── element-plus-icons.js
│   └── favicon / icon     # Browser icon assets
├── pictures/
│   └── readme1.png        # README preview screenshot
├── LICENSE
└── README.md
```

## Tech Stack

- **Backend**: Python, Flask, Flask-CORS, nvitop, psutil, SQLite
- **Frontend**: Vue 3, Element Plus, vanilla JavaScript (no build step)
- **Deployment**: Run Python services directly, or manage with systemd

## Troubleshooting

### Dashboard cannot load the server list

- Make sure the Dashboard is running at `http://<dashboard-host>:28456`
- Make sure `front/config.json` is valid JSON
- Check Dashboard logs for config path or JSON parsing errors

### A node fails to return data

- Make sure the target Agent is running: `curl http://<agent-host>:15896/api/status`
- Make sure the Dashboard server can reach the Agent URL
- Check that the node `url` in `front/config.json` includes the correct port

### GPU information is empty or permission is insufficient

- Make sure the NVIDIA driver is installed and `nvidia-smi` works
- Make sure the user running the Agent has permission to read GPU and process information
- Viewing complete command lines for other users' processes may require elevated permissions

### Port is already in use

```bash
ss -ltnp | grep -E '15896|28456'
```

To change ports, update `PORT` in `backend/app.py` and `app.run(..., port=28456)` in `backend/dashboard.py`.

## License

This project is open-sourced under the GNU General Public License v3.0. See [LICENSE](LICENSE) for details.

## Acknowledgements

- [nvitop](https://github.com/XuehaiPan/nvitop)
- [psutil](https://github.com/giampaolo/psutil)
- [Vue](https://vuejs.org/)
- [Element Plus](https://element-plus.org/)
