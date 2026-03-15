"""
使用nvitop和psutil的GPU和系统监控工具。
包含底层 NVML 回退机制以解决权限不足导致的进程不可见问题。
"""

import psutil
import time
from datetime import datetime
from typing import Dict, List, Any
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 尝试导入 nvitop 和 pynvml (nvitop 的依赖)
try:
    import nvitop
    import pynvml # nvitop 安装时会自动安装这个
    NVITOP_AVAILABLE = True
except ImportError:
    logger.warning("nvitop not installed. GPU monitoring will be disabled.")
    NVITOP_AVAILABLE = False

def get_system_info() -> Dict[str, Any]:
    """使用psutil获取CPU和内存信息。"""
    cpu_percent = psutil.cpu_percent(interval=None) # interval=None 非阻塞获取
    memory = psutil.virtual_memory()
    net_io = psutil.net_io_counters()

    return {
        'cpu': {
            'percent': round(cpu_percent, 1), # 保留1位小数
            'count': psutil.cpu_count(),
            'frequency_current': psutil.cpu_freq().current if psutil.cpu_freq() else 0
        },
        'memory': {
            'total': memory.total,
            'used': memory.used,
            'percent': round(memory.percent, 1), # 保留1位小数
        },
        'network': {
            'bytes_sent': net_io.bytes_sent,
            'bytes_recv': net_io.bytes_recv,
        },
        'timestamp': datetime.now().isoformat(),
    }

def try_get_processes_fallback(device_index: int) -> List[Dict]:
    """
    当 nvitop 无法获取进程详情（通常因权限问题）时，
    直接使用底层 NVML 接口获取 PID 和显存占用。
    """
    fallback_processes = []
    try:
        # 初始化 pynvml
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(device_index)
        
        # 定义一个帮助函数来提取 NVML 进程结构体
        def extract_procs(nvml_procs, proc_type):
            for p in nvml_procs:
                # 尝试用 psutil 补全信息，如果没权限则显示 Unknown
                name = "Unknown"
                user = "Unknown"
                cmd = "Permission Denied (Try sudo)"
                try:
                    sys_proc = psutil.Process(p.pid)
                    name = sys_proc.name()
                    user = sys_proc.username()
                    cmd = ' '.join(sys_proc.cmdline())
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
                
                fallback_processes.append({
                    'pid': p.pid,
                    'name': name,
                    'username': user,
                    'gpu_memory': p.usedGpuMemory,
                    'command': cmd,
                    'type': proc_type
                })

        # 1. 获取计算进程 (Compute)
        try:
            compute_procs = pynvml.nvmlDeviceGetComputeRunningProcesses(handle)
            extract_procs(compute_procs, 'C')
        except pynvml.NVMLError: pass

        # 2. 获取图形进程 (Graphics)
        try:
            graphics_procs = pynvml.nvmlDeviceGetGraphicsRunningProcesses(handle)
            extract_procs(graphics_procs, 'G')
        except pynvml.NVMLError: pass
        
    except Exception as e:
        logger.debug(f"NVML Fallback failed: {e}")
    
    return fallback_processes

def get_gpu_info() -> Dict[str, Any]:
    """使用nvitop获取GPU信息。"""
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
                # --- 基础信息 ---
                # 显存
                memory_info = device.memory_info()
                mem_used = memory_info.used
                mem_total = memory_info.total
                mem_percent = (mem_used / mem_total * 100) if mem_total > 0 else 0
                
                # 利用率
                gpu_util = device.gpu_utilization()
                if gpu_util is None: gpu_util = 0
                
                # --- 进程获取逻辑 (核心修改) ---
                processes = []
                try:
                    # 1. 尝试使用 nvitop 高级接口
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
                    # nvitop 出错，忽略，稍后由 fallback 处理
                    pass

                # 2. 如果列表为空，但显存被占用超过 200MB，说明有隐身进程（权限问题）
                if not processes and mem_used > 200 * 1024 * 1024:
                    logger.info(f"GPU {device.index} have hidden processes, using fallback method.")
                    processes = try_get_processes_fallback(device.index)

                # 按显存排序
                processes.sort(key=lambda x: x['gpu_memory'], reverse=True)

                # --- 构建数据 ---
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
                        'percent': int(round(mem_percent)), # 修改：这里转为整数
                    },
                    'utilization': {
                        'gpu': int(round(gpu_util)), # 修改：这里转为整数
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
                
                if gpu_util is not None:
                    total_gpu_util += gpu_util
                    valid_gpu_count += 1
                    
            except Exception as e:
                logger.error(f"Error processing GPU {device.index}: {e}")
                continue
        
        # 汇总信息
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
    # 测试打印
    print(json.dumps(get_all_info(), indent=2, default=str))