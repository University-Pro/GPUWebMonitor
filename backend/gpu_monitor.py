"""
使用nvitop和psutil的GPU和系统监控工具。
包含底层 NVML 回退机制以解决权限不足导致的进程不可见问题。
"""

import psutil
from datetime import datetime
from typing import Dict, List, Any
import logging
import atexit

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    import nvitop
    import pynvml
    NVITOP_AVAILABLE = True
except ImportError:
    logger.warning("nvitop not installed. GPU monitoring will be disabled.")
    NVITOP_AVAILABLE = False

NVML_INITIALIZED = False

if NVITOP_AVAILABLE:
    try:
        pynvml.nvmlInit()
        NVML_INITIALIZED = True
        logger.info("NVML initialized")
    except Exception as e:
        logger.warning(f"Failed to initialize NVML: {e}")
        NVML_INITIALIZED = False

def _shutdown_nvml():
    global NVML_INITIALIZED
    if NVML_INITIALIZED:
        try:
            pynvml.nvmlShutdown()
            logger.info("NVML shutdown")
        except Exception:
            pass
        NVML_INITIALIZED = False

atexit.register(_shutdown_nvml)

def get_system_info() -> Dict[str, Any]:
    cpu_percent = psutil.cpu_percent(interval=None)
    memory = psutil.virtual_memory()
    net_io = psutil.net_io_counters()
    cpu_freq = psutil.cpu_freq()

    return {
        'cpu': {
            'percent': round(cpu_percent, 1),
            'count': psutil.cpu_count(),
            'frequency_current': cpu_freq.current if cpu_freq else 0
        },
        'memory': {
            'total': memory.total,
            'used': memory.used,
            'percent': round(memory.percent, 1),
        },
        'network': {
            'bytes_sent': net_io.bytes_sent,
            'bytes_recv': net_io.bytes_recv,
        },
        'timestamp': datetime.now().isoformat(),
    }

def try_get_processes_fallback(device_index: int) -> List[Dict]:
    fallback_processes = []

    if not NVML_INITIALIZED:
        return fallback_processes

    try:
        handle = pynvml.nvmlDeviceGetHandleByIndex(device_index)

        def extract_procs(nvml_procs, proc_type):
            for p in nvml_procs:
                name = "Unknown"
                user = "Unknown"
                cmd = "Permission Denied (Try sudo)"
                try:
                    sys_proc = psutil.Process(p.pid)
                    name = sys_proc.name()
                    user = sys_proc.username()
                    cmdline = sys_proc.cmdline()
                    cmd = " ".join(cmdline) if cmdline else ""
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
                except Exception:
                    pass

                fallback_processes.append({
                    'pid': p.pid,
                    'name': name,
                    'username': user,
                    'gpu_memory': getattr(p, 'usedGpuMemory', 0),
                    'command': cmd,
                    'type': proc_type
                })

        try:
            compute_procs = pynvml.nvmlDeviceGetComputeRunningProcesses(handle)
            extract_procs(compute_procs, 'C')
        except pynvml.NVMLError:
            pass

        try:
            graphics_procs = pynvml.nvmlDeviceGetGraphicsRunningProcesses(handle)
            extract_procs(graphics_procs, 'G')
        except pynvml.NVMLError:
            pass

    except Exception as e:
        logger.debug(f"NVML Fallback failed: {e}")

    return fallback_processes

def get_gpu_info() -> Dict[str, Any]:
    if not NVITOP_AVAILABLE:
        return {'error': 'nvitop not available', 'gpus': []}

    try:
        from nvitop import Device
        devices = Device.all()
        gpus = []

        total_gpu_util = 0
        valid_gpu_count = 0

        for device in devices:
            try:
                memory_info = device.memory_info()
                mem_used = memory_info.used
                mem_total = memory_info.total
                mem_percent = (mem_used / mem_total * 100) if mem_total > 0 else 0

                gpu_util = device.gpu_utilization()
                if gpu_util is None:
                    gpu_util = 0

                processes = []
                try:
                    nvitop_procs = device.processes()
                    for proc in nvitop_procs:
                        processes.append({
                            'pid': proc.pid,
                            'name': proc.name(),
                            'username': proc.username(),
                            'gpu_memory': proc.gpu_memory(),
                            'command': ' '.join(proc.cmdline()),
                        })
                except Exception:
                    pass

                if not processes and mem_used > 200 * 1024 * 1024:
                    logger.info(f"GPU {device.index} has hidden processes, using fallback method.")
                    processes = try_get_processes_fallback(device.index)

                processes.sort(key=lambda x: x['gpu_memory'], reverse=True)

                gpu_info = {
                    'index': device.index,
                    'name': device.name(),
                    'uuid': device.uuid(),
                    'memory': {
                        'used': mem_used,
                        'used_gb': mem_used / (1024**3),
                        'total': mem_total,
                        'total_gb': mem_total / (1024**3),
                        'free': memory_info.free,
                        'percent': int(round(mem_percent)),
                    },
                    'utilization': {
                        'gpu': int(round(gpu_util)),
                        'memory': int(round(device.memory_utilization() or 0)),
                    },
                    'temperature': device.temperature(),
                    'power': {
                        'usage': device.power_usage(),
                        'limit': device.power_limit(),
                    },
                    'fan_speed': device.fan_speed(),
                    'processes': processes,
                    'process_count': len(processes),
                }
                gpus.append(gpu_info)

                total_gpu_util += gpu_util
                valid_gpu_count += 1

            except Exception as e:
                logger.error(f"Error processing GPU {device.index}: {e}")
                continue

        total_mem_used = sum(g['memory']['used'] for g in gpus)
        total_mem_total = sum(g['memory']['total'] for g in gpus)

        return {
            'gpus': gpus,
            'summary': {
                'avg_gpu_utilization': int(round(total_gpu_util / valid_gpu_count)) if valid_gpu_count else 0,
                'total_memory_used': total_mem_used,
                'total_memory_total': total_mem_total,
                'total_processes': sum(g['process_count'] for g in gpus),
            },
            'timestamp': datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Global GPU Error: {e}")
        return {'error': str(e), 'gpus': []}

def get_all_info() -> Dict[str, Any]:
    return {
        'system': get_system_info(),
        'gpu': get_gpu_info(),
        'timestamp': datetime.now().isoformat(),
    }

if __name__ == '__main__':
    import json
    print(json.dumps(get_all_info(), indent=2, default=str))