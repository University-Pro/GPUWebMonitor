"""
优化版 GPU 和系统监控工具
1. 强化了资源回收，防止 FD 泄露
2. 增加了线程锁，确保 NVML 调用安全
3. 优化了 psutil 读取性能
"""

import psutil
import logging
import threading
from datetime import datetime
from typing import Dict, List, Any
import atexit

# 日志配置
logger = logging.getLogger(__name__)

# 全局锁，防止多线程竞争 NVML 句柄导致不稳定
_nvml_lock = threading.Lock()

try:
    import nvitop
    import pynvml
    NVITOP_AVAILABLE = True
except ImportError:
    logger.warning("nvitop or pynvml not installed. GPU monitoring will be limited.")
    NVITOP_AVAILABLE = False

_NVML_INITIALIZED = False

def init_nvml():
    """初始化 NVML (线程安全)"""
    global _NVML_INITIALIZED
    if NVITOP_AVAILABLE and not _NVML_INITIALIZED:
        with _nvml_lock:
            try:
                pynvml.nvmlInit()
                _NVML_INITIALIZED = True
                logger.info("NVML 成功初始化")
            except Exception as e:
                logger.error(f"NVML 初始化失败: {e}")
                _NVML_INITIALIZED = False

def _shutdown_nvml():
    """退出时释放资源"""
    global _NVML_INITIALIZED
    if _NVML_INITIALIZED:
        with _nvml_lock:
            try:
                pynvml.nvmlShutdown()
                logger.info("NVML 已安全关闭")
            except:
                pass
            _NVML_INITIALIZED = False

# 注册退出钩子
atexit.register(_shutdown_nvml)

# 预初始化
init_nvml()

def get_system_info() -> Dict[str, Any]:
    """获取系统基础信息，优化了句柄使用"""
    try:
        # psutil.cpu_percent 在 interval=None 时是非阻塞的
        cpu_percent = psutil.cpu_percent(interval=None)
        # 第一次调用可能为 0，可以通过短期缓存或忽略来处理
        
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
    except Exception as e:
        logger.error(f"获取系统信息失败: {e}")
        return {}

def try_get_processes_fallback(device_index: int) -> List[Dict]:
    """底层 NVML 回退机制，增加了 oneshot() 优化以减少 FD 占用"""
    fallback_processes = []
    if not _NVML_INITIALIZED:
        return fallback_processes

    with _nvml_lock:
        try:
            handle = pynvml.nvmlDeviceGetHandleByIndex(device_index)
            
            def extract_procs(nvml_procs, proc_type):
                for p in nvml_procs:
                    proc_info = {
                        'pid': p.pid,
                        'name': "Unknown",
                        'username': "Unknown",
                        'gpu_memory': getattr(p, 'usedGpuMemory', 0),
                        'command': "",
                        'type': proc_type
                    }
                    try:
                        # 使用 oneshot() 可以一次性读取 /proc 信息并自动关闭句柄
                        ps_proc = psutil.Process(p.pid)
                        with ps_proc.oneshot():
                            proc_info['name'] = ps_proc.name()
                            proc_info['username'] = ps_proc.username()
                            cmdline = ps_proc.cmdline()
                            proc_info['command'] = " ".join(cmdline) if cmdline else ""
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        proc_info['command'] = "Permission Denied / Expired"
                    except Exception:
                        pass
                    fallback_processes.append(proc_info)

            # 获取计算进程
            try:
                c_procs = pynvml.nvmlDeviceGetComputeRunningProcesses(handle)
                extract_procs(c_procs, 'C')
            except: pass

            # 获取图形进程
            try:
                g_procs = pynvml.nvmlDeviceGetGraphicsRunningProcesses(handle)
                extract_procs(g_procs, 'G')
            except: pass

        except Exception as e:
            logger.debug(f"NVML Fallback failed for GPU {device_index}: {e}")

    return fallback_processes

def get_gpu_info() -> Dict[str, Any]:
    """获取 GPU 详情，增加了对 nvitop 的异常处理和资源保护"""
    if not NVITOP_AVAILABLE:
        return {'error': 'nvitop not available', 'gpus': []}

    try:
        from nvitop import Device
        # 注意：Device.all() 内部会建立 NVML 连接，确保在锁保护下
        with _nvml_lock:
            devices = Device.all()
        
        gpus = []
        total_gpu_util = 0
        valid_gpu_count = 0

        for device in devices:
            try:
                # 获取基础状态
                memory_info = device.memory_info()
                mem_used = memory_info.used
                mem_total = memory_info.total
                mem_percent = (mem_used / mem_total * 100) if mem_total > 0 else 0
                
                gpu_util = device.gpu_utilization() or 0
                
                processes = []
                try:
                    # nvitop 的 processes 也会打开大量 /proc 文件
                    nvitop_procs = device.processes()
                    for pid, proc in nvitop_procs.items():
                        try:
                            processes.append({
                                'pid': pid,
                                'name': proc.name(),
                                'username': proc.username(),
                                'gpu_memory': proc.gpu_memory(),
                                'command': ' '.join(proc.cmdline() or []),
                            })
                        except: continue
                except Exception:
                    pass

                # 如果 nvitop 没抓到进程（权限问题），尝试 NVML 回退
                # 设定阈值 200MB 判定为“可能有隐藏进程”
                if not processes and mem_used > 200 * 1024 * 1024:
                    processes = try_get_processes_fallback(device.index)

                processes.sort(key=lambda x: x.get('gpu_memory', 0), reverse=True)

                gpus.append({
                    'index': device.index,
                    'name': device.name(),
                    'uuid': device.uuid(),
                    'memory': {
                        'used': mem_used,
                        'used_gb': round(mem_used / (1024**3), 2),
                        'total': mem_total,
                        'total_gb': round(mem_total / (1024**3), 2),
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
                })

                total_gpu_util += gpu_util
                valid_gpu_count += 1

            except Exception as e:
                logger.error(f"处理 GPU {getattr(device, 'index', 'unknown')} 时出错: {e}")
                continue

        return {
            'gpus': gpus,
            'summary': {
                'avg_gpu_utilization': int(round(total_gpu_util / valid_gpu_count)) if valid_gpu_count else 0,
                'total_memory_used': sum(g['memory']['used'] for g in gpus),
                'total_memory_total': sum(g['memory']['total'] for g in gpus),
                'total_processes': sum(g['process_count'] for g in gpus),
            },
            'timestamp': datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Global GPU Error: {e}")
        return {'error': str(e), 'gpus': []}

def get_all_info() -> Dict[str, Any]:
    """主调用接口"""
    # 在每次大循环调用前确保 NVML 状态
    if not _NVML_INITIALIZED:
        init_nvml()
        
    return {
        'system': get_system_info(),
        'gpu': get_gpu_info(),
        'timestamp': datetime.now().isoformat(),
    }

if __name__ == '__main__':
    import json
    # 测试输出
    print(json.dumps(get_all_info(), indent=2, default=str))