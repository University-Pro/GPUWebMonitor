"""
Mock 数据生成器。
模拟 8 卡 B300 服务器：仅 GPU 0 满载训练 LLM，GPU 1-7 完全空闲。
"""

import random
import math
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any

# --- 模拟的 GPU 配置: 8 × B300 SXM6 AC ---
_B300_MEM_MB = 275040
_B300_MEM_BYTES = _B300_MEM_MB * 1024 * 1024
_B300_MEM_GB = round(_B300_MEM_BYTES / (1024**3), 2)
_B300_POWER_LIMIT = 1100000  # 1100W，单位 mW

MOCK_GPU_CONFIGS = [
    {
        "index": i,
        "name": "NVIDIA B300 SXM6 AC",
        "uuid": f"GPU-b300-8gpu-{i:04d}-0000-0000-00000000000{i}",
        "total_gb": _B300_MEM_GB,
        "total_bytes": _B300_MEM_BYTES,
        "power_limit": _B300_POWER_LIMIT,
    }
    for i in range(8)
]

# --- 模拟的系统配置 ---
MOCK_CPU_COUNT = 256        # 128 核心 / 256 线程
MOCK_MEM_TOTAL = 2 * 1024**4  # 2 TB = 2199023255552 bytes

_phase = time.time()


def _fluctuate(base: float, amplitude: float, speed: float = 1.0) -> float:
    """基于正弦波和随机噪声产生小幅波动。"""
    wave = math.sin(_phase * speed + random.uniform(0, math.pi))
    noise = random.uniform(-amplitude * 0.3, amplitude * 0.3)
    return max(0, base + wave * amplitude + noise)


def _llm_training_process(mem_used: int) -> List[Dict[str, Any]]:
    """返回 GPU 0 上唯一的 LLM 训练进程。"""
    return [{
        "pid": 10000,
        "name": "vllm",
        "username": "tzz",
        "gpu_memory": mem_used,
        "command": "/usr/bin/python3 train_llm.py --model llama --gpu 0 --batch-size 32",
        "type": "C",
    }]


def _idle_gpu_info(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """返回零显存、零利用率、零进程的空闲 GPU 数据。"""
    total_bytes = cfg["total_bytes"]
    return {
        "index": cfg["index"],
        "name": cfg["name"],
        "uuid": cfg["uuid"],
        "memory": {
            "used": 0,
            "used_gb": 0,
            "total": total_bytes,
            "total_gb": cfg["total_gb"],
            "free": total_bytes,
            "percent": 0,
        },
        "utilization": {"gpu": 0, "memory": 0},
        "temperature": int(round(_fluctuate(25, 1, speed=0.1))),
        "power": {
            "usage": int(round(_fluctuate(30000, 2000, speed=0.2))),
            "limit": cfg["power_limit"],
        },
        "processes": [],
        "process_count": 0,
    }


def generate_mock_gpu_info() -> Dict[str, Any]:
    """生成 GPU 0 满载 LLM 训练、GPU 1-7 完全空闲的模拟 GPU 信息。"""
    global _phase
    _phase = time.time()

    gpus = []
    total_gpu_util = 0
    total_mem_used = 0
    total_mem_total = 0

    for cfg in MOCK_GPU_CONFIGS:
        if cfg["index"] != 0:
            gpu = _idle_gpu_info(cfg)
        else:
            total_bytes = cfg["total_bytes"]
            gpu_util = min(100, int(round(_fluctuate(96, 3, speed=0.3))))
            mem_used = int(total_bytes * 0.9 * (1 + random.uniform(-0.01, 0.01)))
            mem_percent = int(round(mem_used / total_bytes * 100))
            temp_base = 40 + gpu_util * 0.48
            power_base = 100000 + (cfg["power_limit"] - 100000) * (gpu_util / 100) * 0.9

            gpu = {
                "index": 0,
                "name": cfg["name"],
                "uuid": cfg["uuid"],
                "memory": {
                    "used": mem_used,
                    "used_gb": round(mem_used / (1024**3), 2),
                    "total": total_bytes,
                    "total_gb": cfg["total_gb"],
                    "free": total_bytes - mem_used,
                    "percent": mem_percent,
                },
                "utilization": {"gpu": gpu_util, "memory": mem_percent},
                "temperature": int(round(_fluctuate(temp_base, 2, speed=0.15))),
                "power": {
                    "usage": int(round(_fluctuate(power_base, 15000, speed=0.25))),
                    "limit": cfg["power_limit"],
                },
                "processes": _llm_training_process(mem_used),
                "process_count": 1,
            }

        gpus.append(gpu)
        total_gpu_util += gpu["utilization"]["gpu"]
        total_mem_used += gpu["memory"]["used"]
        total_mem_total += gpu["memory"]["total"]

    return {
        "gpus": gpus,
        "summary": {
            "avg_gpu_utilization": int(round(total_gpu_util / len(gpus))),
            "total_memory_used": total_mem_used,
            "total_memory_total": total_mem_total,
            "total_processes": 1,
        },
        "timestamp": datetime.now().isoformat(),
    }


def generate_mock_system_info() -> Dict[str, Any]:
    """生成模拟的系统信息 (128C/256T, 2TB RAM)。"""
    mem_ratio = 0.45 + random.uniform(-0.03, 0.03)
    return {
        "cpu": {
            "percent": round(_fluctuate(35, 12, speed=0.2), 1),
            "count": MOCK_CPU_COUNT,
            "frequency_current": round(_fluctuate(3200, 150, speed=0.1), 1),
        },
        "memory": {
            "total": MOCK_MEM_TOTAL,
            "used": int(MOCK_MEM_TOTAL * mem_ratio),
            "percent": round(mem_ratio * 100, 1),
        },
        "network": {
            "bytes_sent": 158_231_785_242 + random.randint(0, 50_000_000),
            "bytes_recv": 237_409_482_841 + random.randint(0, 50_000_000),
        },
        "timestamp": datetime.now().isoformat(),
    }


def generate_mock_all_info() -> Dict[str, Any]:
    """生成完整的模拟监控数据。"""
    return {
        "system": generate_mock_system_info(),
        "gpu": generate_mock_gpu_info(),
        "timestamp": datetime.now().isoformat(),
    }


def generate_mock_history(count: int = 50) -> List[Dict[str, Any]]:
    """生成 GPU 0 LLM 满载、其余 GPU 全部为空闲状态的历史数据。"""
    now = datetime.now()
    history = []

    for i in range(count):
        ts = now - timedelta(seconds=30 * (count - 1 - i))
        gpu_summaries = []

        for cfg in MOCK_GPU_CONFIGS:
            total_bytes = cfg["total_bytes"]
            if cfg["index"] == 0:
                gpu_util = min(100, max(90, int(round(95 + random.uniform(-3, 3)))))
                mem_used = int(total_bytes * (0.9 + random.uniform(-0.01, 0.01)))
                mem_percent = int(round(mem_used / total_bytes * 100))
                gpu = {
                    "index": 0,
                    "name": cfg["name"],
                    "uuid": cfg["uuid"],
                    "memory": {
                        "used": mem_used,
                        "used_gb": round(mem_used / (1024**3), 2),
                        "total": total_bytes,
                        "total_gb": cfg["total_gb"],
                        "free": total_bytes - mem_used,
                        "percent": mem_percent,
                    },
                    "utilization": {"gpu": gpu_util, "memory": mem_percent},
                    "temperature": int(round(40 + gpu_util * 0.48)),
                    "power": {
                        "usage": int(100000 + (cfg["power_limit"] - 100000) * (gpu_util / 100) * 0.9),
                        "limit": cfg["power_limit"],
                    },
                    "process_count": 1,
                }
            else:
                gpu = {
                    "index": cfg["index"],
                    "name": cfg["name"],
                    "uuid": cfg["uuid"],
                    "memory": {
                        "used": 0,
                        "used_gb": 0,
                        "total": total_bytes,
                        "total_gb": cfg["total_gb"],
                        "free": total_bytes,
                        "percent": 0,
                    },
                    "utilization": {"gpu": 0, "memory": 0},
                    "temperature": int(round(25 + random.uniform(-2, 2))),
                    "power": {
                        "usage": int(round(30000 + random.uniform(-3000, 3000))),
                        "limit": cfg["power_limit"],
                    },
                    "process_count": 0,
                }
            gpu_summaries.append(gpu)

        summary = {
            "avg_gpu_utilization": int(round(sum(g["utilization"]["gpu"] for g in gpu_summaries) / len(gpu_summaries))),
            "total_memory_used": sum(g["memory"]["used"] for g in gpu_summaries),
            "total_memory_total": sum(g["memory"]["total"] for g in gpu_summaries),
            "total_processes": 1,
        }
        history.append({
            "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
            "cpu_percent": round(45 + random.uniform(-4, 4), 1),
            "memory_percent": round(46 + random.uniform(-2, 2), 1),
            "gpus": gpu_summaries,
            "summary": summary,
        })

    return history


if __name__ == "__main__":
    import json
    print("=== 实时模拟数据 ===")
    print(json.dumps(generate_mock_all_info(), indent=2, default=str))
    print("\n=== 历史数据 (前3条) ===")
    for item in generate_mock_history(3):
        print(json.dumps(item, indent=2, default=str))
        print("---")
