"""
Mock 数据生成器
模拟 8 卡 B300 服务器的监控数据，用于前端开发和调试。
数据会在每次调用时产生小幅波动，模拟真实场景。

服务器配置:
  - CPU: 128 核心 / 256 线程
  - 内存: 2 TB
  - GPU: 8 × NVIDIA B300 SXM6 AC (268.6 GB / 1100W)
"""

import random
import math
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any

# --- 模拟的 GPU 配置: 8 × B300 SXM6 AC ---
_B300_MEM_MB = 275040
_B300_MEM_BYTES = _B300_MEM_MB * 1024 * 1024          # 288378757120 bytes
_B300_MEM_GB = round(_B300_MEM_BYTES / (1024**3), 2)   # ≈ 268.59 GB
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

# 模拟进程名（B300 集群常见负载）
MOCK_PROCESS_NAMES = [
    "python3", "torch-train", "deepspeed", "megatron-lm",
    "vllm", "llama_server", "transformers", "flash-attn",
    "nccl-tests", "horovod", "tensorflow", "jax",
]

# 用于产生缓慢波动的内部状态
_phase = time.time()


def _fluctuate(base: float, amplitude: float, speed: float = 1.0) -> float:
    """基于正弦波 + 随机噪声产生缓慢波动的数值"""
    global _phase
    wave = math.sin(_phase * speed + random.uniform(0, math.pi))
    noise = random.uniform(-amplitude * 0.3, amplitude * 0.3)
    return max(0, base + wave * amplitude + noise)


def _mock_processes(gpu_index: int, mem_used: int, gpu_util: int = 0) -> List[Dict[str, Any]]:
    """根据显存占用和利用率模拟进程列表"""
    if mem_used < 500 * 1024 * 1024 or gpu_util < 10:
        return []

    procs = []
    # 模拟 1~3 个进程
    count = random.randint(1, 3)
    remaining_mem = mem_used
    for i in range(count):
        if i == count - 1:
            proc_mem = remaining_mem
        else:
            proc_mem = random.randint(
                int(remaining_mem * 0.1),
                int(remaining_mem * 0.6),
            )
            remaining_mem -= proc_mem

        procs.append({
            "pid": 10000 + gpu_index * 100 + i + random.randint(0, 50),
            "name": random.choice(MOCK_PROCESS_NAMES),
            "username": "tzz",
            "gpu_memory": proc_mem,
            "command": f"/usr/bin/python3 train.py --gpu {gpu_index} --batch-size 32",
            "type": "C",
        })
    return procs


# 每张 GPU 的负载场景预设（GPU 0、1 满载训练，其余空闲）
_GPU_LOAD_PROFILES = [
    {"util_base": 92, "mem_ratio": 0.85, "desc": "满载训练"},   # GPU 0: 满载
    {"util_base": 90, "mem_ratio": 0.83, "desc": "满载训练"},   # GPU 1: 满载
    {"util_base": 3,  "mem_ratio": 0.01, "desc": "空闲"},      # GPU 2: 空闲
    {"util_base": 3,  "mem_ratio": 0.01, "desc": "空闲"},      # GPU 3: 空闲
    {"util_base": 3,  "mem_ratio": 0.01, "desc": "空闲"},      # GPU 4: 空闲
    {"util_base": 3,  "mem_ratio": 0.01, "desc": "空闲"},      # GPU 5: 空闲
    {"util_base": 3,  "mem_ratio": 0.01, "desc": "空闲"},      # GPU 6: 空闲
    {"util_base": 3,  "mem_ratio": 0.01, "desc": "空闲"},      # GPU 7: 空闲
]


def generate_mock_gpu_info() -> Dict[str, Any]:
    """生成模拟的 8 卡 B300 SXM6 AC GPU 信息，结构与 gpu_monitor.get_gpu_info() 一致"""
    global _phase
    _phase = time.time()  # 推进波动相位

    gpus = []
    total_gpu_util = 0
    total_mem_used = 0
    total_mem_total = 0
    total_processes = 0

    for cfg in MOCK_GPU_CONFIGS:
        idx = cfg["index"]
        total_bytes = cfg["total_bytes"]
        profile = _GPU_LOAD_PROFILES[idx]

        util_base = profile["util_base"]
        mem_ratio = profile["mem_ratio"]

        # GPU 利用率：正弦波缓慢波动 + 随机噪声
        gpu_util = int(round(_fluctuate(util_base, 8, speed=0.3 + idx * 0.05)))
        gpu_util = max(0, min(100, gpu_util))

        # 显存使用：基于利用率的比率 + 随机抖动
        mem_used = int(total_bytes * mem_ratio * (1 + random.uniform(-0.03, 0.03)))
        mem_percent = int(round(mem_used / total_bytes * 100)) if total_bytes > 0 else 0

        processes = _mock_processes(idx, mem_used, gpu_util)

        # B300 温度范围：空闲 ~40°C，满载 ~83°C
        temp_base = 40 + gpu_util * 0.48
        # B300 功耗：空闲 ~100W，满载 ~1050W
        power_base = 100000 + (cfg["power_limit"] - 100000) * (gpu_util / 100) * 0.9

        gpus.append({
            "index": idx,
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
            "utilization": {
                "gpu": gpu_util,
                "memory": int(round(_fluctuate(mem_percent, 3, speed=0.2))),
            },
            "temperature": int(round(_fluctuate(temp_base, 3, speed=0.15))),
            "power": {
                "usage": int(round(_fluctuate(power_base, 25000, speed=0.25))),
                "limit": cfg["power_limit"],
            },
            "processes": processes,
            "process_count": len(processes),
        })

        total_gpu_util += gpu_util
        total_mem_used += mem_used
        total_mem_total += total_bytes
        total_processes += len(processes)

    return {
        "gpus": gpus,
        "summary": {
            "avg_gpu_utilization": int(round(total_gpu_util / len(gpus))),
            "total_memory_used": total_mem_used,
            "total_memory_total": total_mem_total,
            "total_processes": total_processes,
        },
        "timestamp": datetime.now().isoformat(),
    }


def generate_mock_system_info() -> Dict[str, Any]:
    """生成模拟的系统信息 (128C/256T, 2TB RAM)，结构与 gpu_monitor.get_system_info() 一致"""
    mem_ratio = 0.45 + random.uniform(-0.03, 0.03)  # 内存使用率 ~45%
    return {
        "cpu": {
            "percent": round(_fluctuate(35, 12, speed=0.2), 1),
            "count": MOCK_CPU_COUNT,  # 256 线程
            "frequency_current": round(_fluctuate(3200, 150, speed=0.1), 1),
        },
        "memory": {
            "total": MOCK_MEM_TOTAL,  # 2 TB
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
    """
    生成完整的模拟监控数据。
    结构与 gpu_monitor.get_all_info() 完全一致。
    """
    return {
        "system": generate_mock_system_info(),
        "gpu": generate_mock_gpu_info(),
        "timestamp": datetime.now().isoformat(),
    }


def generate_mock_history(count: int = 50) -> List[Dict[str, Any]]:
    """
    生成模拟的历史数据，结构与 /api/history 返回格式一致。
    每条记录间隔 30 秒，从当前时间往前推。
    模拟一个训练任务逐渐升温的场景。
    """
    now = datetime.now()
    history = []

    for i in range(count):
        ts = now - timedelta(seconds=30 * (count - 1 - i))
        # t_factor: 0 -> 1，从过去到现在，模拟负载逐渐升高
        t_factor = i / count

        # CPU: 基础 20% + 随训练推进上升到 ~50%
        cpu = round(20 + 30 * t_factor + random.uniform(-4, 4), 1)
        # 内存: 稳定在 ~45%，小幅波动
        mem = round(42 + 6 * t_factor + random.uniform(-2, 2), 1)

        gpu_summaries = []
        for cfg in MOCK_GPU_CONFIGS:
            idx = cfg["index"]
            profile = _GPU_LOAD_PROFILES[idx]
            # 基于 profile 的基础值，叠加时间趋势
            trend = 1.0 + 0.1 * t_factor  # 负载随时间缓慢上升
            base_util = min(99, profile["util_base"] * trend)
            base_mem_ratio = min(0.95, profile["mem_ratio"] * trend)

            # 添加随机噪声
            base_util = max(0, base_util + random.uniform(-3, 3))
            base_mem_ratio = max(0.01, base_mem_ratio + random.uniform(-0.02, 0.02))

            mem_used = int(cfg["total_bytes"] * base_mem_ratio)
            gpu_summaries.append({
                "index": idx,
                "name": cfg["name"],
                "uuid": cfg["uuid"],
                "memory": {
                    "used": mem_used,
                    "used_gb": round(mem_used / (1024**3), 2),
                    "total": cfg["total_bytes"],
                    "total_gb": cfg["total_gb"],
                    "free": cfg["total_bytes"] - mem_used,
                    "percent": int(round(base_mem_ratio * 100)),
                },
                "utilization": {
                    "gpu": int(round(base_util)),
                    "memory": int(round(base_util * 0.75)),
                },
                "temperature": int(round(40 + base_util * 0.48)),
                "power": {
                    "usage": int(100000 + (cfg["power_limit"] - 100000) * (base_util / 100) * 0.9),
                    "limit": cfg["power_limit"],
                },
                "process_count": random.randint(1, 3) if base_mem_ratio > 0.1 else 0,
            })

        summary = {
            "avg_gpu_utilization": int(round(
                sum(g["utilization"]["gpu"] for g in gpu_summaries) / len(gpu_summaries)
            )),
            "total_memory_used": sum(g["memory"]["used"] for g in gpu_summaries),
            "total_memory_total": sum(g["memory"]["total"] for g in gpu_summaries),
            "total_processes": sum(g["process_count"] for g in gpu_summaries),
        }

        history.append({
            "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
            "cpu_percent": cpu,
            "memory_percent": mem,
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
