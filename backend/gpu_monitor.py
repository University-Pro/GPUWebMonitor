"""
优化版 GPU 和系统监控工具
1. 强化了资源回收，防止 FD 泄露
2. 增加了线程锁，确保 NVML 调用安全
3. 优化了 psutil 读取性能
"""

import psutil
import json
import logging
import os
import threading
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
import atexit

# 日志配置
logger = logging.getLogger(__name__)

# 全局锁，防止多线程竞争 NVML 句柄导致不稳定
_nvml_lock = threading.Lock()

# Keep a non-blocking CPU sample between refreshes. A Process.cpu_percent()
# instance needs two calls on the same object, while this monitor creates fresh
# Process objects for every request. Tracking CPU time here gives meaningful
# values without pausing every API request.
_process_sample_lock = threading.Lock()
_process_cpu_samples = {}
SYSTEM_PROCESS_LIMIT = 50
MEMORY_SNAPSHOT_PATH = os.environ.get(
    'GPU_MONITOR_MEMORY_SNAPSHOT',
    '/run/gpuwebmonitor-memory/process-memory.json',
)
MEMORY_SNAPSHOT_MAX_AGE = 15

try:
    import nvitop
    import pynvml
    NVITOP_AVAILABLE = True
except ImportError:
    logger.warning("nvitop or pynvml not installed. GPU monitoring will be limited.")
    NVITOP_AVAILABLE = False

_NVML_INITIALIZED = False


def _load_memory_snapshot() -> Dict[str, Dict[str, Any]]:
    """Load a fresh privileged PSS snapshot, or return an empty mapping."""
    try:
        with open(MEMORY_SNAPSHOT_PATH, 'r', encoding='utf-8') as handle:
            snapshot = json.load(handle)
        timestamp = float(snapshot.get('timestamp') or 0)
        if time.time() - timestamp > MEMORY_SNAPSHOT_MAX_AGE:
            return {}
        processes = snapshot.get('processes')
        return processes if isinstance(processes, dict) else {}
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {}


def _get_process_memory(process, info, memory_snapshot):
    """Return ``(accounted_bytes, rss_bytes, metric)`` for a process.

    PSS is preferred because it proportionally distributes shared pages and
    can therefore be summed across processes. RSS is retained only as a clearly
    identified fallback when no fresh privileged snapshot is available.
    """
    memory_info = info.get('memory_info')
    rss = max(int(memory_info.rss or 0), 0)
    pid = int(info['pid'])
    create_time = float(info.get('create_time') or 0)
    snapshot_entry = memory_snapshot.get(str(pid))
    if isinstance(snapshot_entry, dict):
        snapshot_create_time = float(snapshot_entry.get('create_time') or 0)
        pss = snapshot_entry.get('pss')
        if abs(snapshot_create_time - create_time) < 0.01 and isinstance(pss, (int, float)) and pss >= 0:
            return int(pss), rss, 'pss'

    try:
        pss = getattr(process.memory_full_info(), 'pss', None)
        if isinstance(pss, (int, float)) and pss >= 0:
            return int(pss), rss, 'pss'
    except (psutil.NoSuchProcess, psutil.ZombieProcess, psutil.AccessDenied, AttributeError, OSError):
        pass
    return rss, rss, 'rss'


def get_system_process_usage(
    limit: int = SYSTEM_PROCESS_LIMIT,
    total_memory: Optional[int] = None,
) -> Dict[str, Any]:
    """Return process groups plus complete per-user CPU/PSS totals.

    CPU usage is normalized against the capacity of the whole machine, so one
    fully occupied logical CPU contributes ``100 / logical_cpu_count`` percent.
    Processes with the same user, executable name, and command line are grouped
    into one row. Memory uses PSS whenever available so shared pages are
    proportionally distributed instead of being counted once per forked worker.

    The result is the union of the top ``limit`` groups by CPU usage and by
    resident memory. This keeps the payload bounded while ensuring that either
    dashboard sort still includes the busiest groups for that resource.
    """
    global _process_cpu_samples

    sample_time = time.monotonic()
    with _process_sample_lock:
        previous_samples = dict(_process_cpu_samples)

    current_samples = {}
    groups = {}
    memory_snapshot = _load_memory_snapshot()
    logical_cpu_count = max(int(psutil.cpu_count(logical=True) or 1), 1)
    if total_memory is None:
        total_memory = int(psutil.virtual_memory().total or 0)
    total_memory = max(int(total_memory or 0), 0)
    attrs = ['pid', 'name', 'username', 'cmdline', 'create_time', 'cpu_times', 'memory_info']

    for process in psutil.process_iter(attrs=attrs, ad_value=None):
        try:
            info = process.info
            pid = info.get('pid')
            create_time = info.get('create_time')
            cpu_times = info.get('cpu_times')
            memory_info = info.get('memory_info')
            if pid is None or cpu_times is None or memory_info is None:
                continue

            process_cpu_time = float(cpu_times.user + cpu_times.system)
            sample_key = (int(pid), float(create_time or 0))
            previous = previous_samples.get(sample_key)
            cpu_percent = 0.0
            if previous:
                elapsed = sample_time - previous[0]
                cpu_delta = process_cpu_time - previous[1]
                if elapsed > 0 and cpu_delta >= 0:
                    cpu_percent = cpu_delta / elapsed * 100 / logical_cpu_count

            current_samples[sample_key] = (sample_time, process_cpu_time)
            name = info.get('name') or 'Unknown'
            username = info.get('username') or 'Unknown'
            cmdline = info.get('cmdline') or []
            command = ' '.join(str(part) for part in cmdline if part) or name
            memory_bytes, memory_rss, memory_metric = _get_process_memory(
                process,
                info,
                memory_snapshot,
            )
            group_key = (username, name, command)
            group = groups.setdefault(group_key, {
                'pid': int(pid),
                'pids': [],
                'instance_count': 0,
                'name': name,
                'username': username,
                'command': command,
                'cpu_percent': 0.0,
                'memory_bytes': 0,
                'memory_rss': 0,
                '_memory_metrics': set(),
            })
            group['pids'].append(int(pid))
            group['instance_count'] += 1
            group['cpu_percent'] += max(cpu_percent, 0.0)
            group['memory_bytes'] += memory_bytes
            group['memory_rss'] += memory_rss
            group['_memory_metrics'].add(memory_metric)
        except (psutil.NoSuchProcess, psutil.ZombieProcess, psutil.AccessDenied):
            continue
        except Exception as exc:
            logger.debug("采集系统进程基础信息失败: %s", exc)

    with _process_sample_lock:
        _process_cpu_samples = current_samples

    candidates = []
    for item in groups.values():
        item['pids'].sort()
        item['pid'] = item['pids'][0]
        item['cpu_percent'] = round(min(item['cpu_percent'], 100.0), 1)
        metrics = item.pop('_memory_metrics')
        item['memory_metric'] = 'pss' if metrics == {'pss'} else ('rss' if metrics == {'rss'} else 'mixed')
        item['memory_percent'] = round(
            item['memory_bytes'] / total_memory * 100 if total_memory else 0.0,
            2,
        )
        candidates.append(item)

    users = {}
    for item in candidates:
        user = users.setdefault(item['username'], {
            'username': item['username'],
            'cpu_percent': 0.0,
            'memory_bytes': 0,
            'memory_rss': 0,
            'process_group_count': 0,
            'instance_count': 0,
            '_memory_metrics': set(),
        })
        user['cpu_percent'] += item['cpu_percent']
        user['memory_bytes'] += item['memory_bytes']
        user['memory_rss'] += item['memory_rss']
        user['process_group_count'] += 1
        user['instance_count'] += item['instance_count']
        user['_memory_metrics'].add(item['memory_metric'])

    user_result = []
    for user in users.values():
        user['cpu_percent'] = round(min(user['cpu_percent'], 100.0), 1)
        user['memory_percent'] = round(
            user['memory_bytes'] / total_memory * 100 if total_memory else 0.0,
            2,
        )
        metrics = user.pop('_memory_metrics')
        user['memory_metric'] = 'pss' if metrics == {'pss'} else ('rss' if metrics == {'rss'} else 'mixed')
        user_result.append(user)

    bounded_limit = max(1, min(int(limit or SYSTEM_PROCESS_LIMIT), 200))
    top_cpu = sorted(candidates, key=lambda item: (item['cpu_percent'], item['memory_bytes']), reverse=True)[:bounded_limit]
    top_memory = sorted(candidates, key=lambda item: (item['memory_bytes'], item['cpu_percent']), reverse=True)[:bounded_limit]
    selected = {
        (item['username'], item['name'], item['command']): item
        for item in top_cpu + top_memory
    }
    result = list(selected.values())

    process_result = sorted(result, key=lambda item: (item['cpu_percent'], item['memory_bytes']), reverse=True)
    return {
        'processes': process_result,
        'users': sorted(user_result, key=lambda item: (item['cpu_percent'], item['memory_bytes']), reverse=True),
        'memory_metric': 'pss' if candidates and all(item['memory_metric'] == 'pss' for item in candidates) else 'mixed',
    }


def get_system_processes(
    limit: int = SYSTEM_PROCESS_LIMIT,
    total_memory: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Compatibility wrapper returning only the bounded process-group list."""
    return get_system_process_usage(limit=limit, total_memory=total_memory)['processes']

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
        cpu_percent = min(max(float(psutil.cpu_percent(interval=None)), 0.0), 100.0)
        # 第一次调用可能为 0，可以通过短期缓存或忽略来处理
        
        memory = psutil.virtual_memory()
        net_io = psutil.net_io_counters()
        cpu_freq = psutil.cpu_freq()

        memory_used = max(int(memory.total) - int(memory.available), 0)
        memory_percent = memory_used / memory.total * 100 if memory.total else 0.0

        process_usage = get_system_process_usage(total_memory=memory.total)

        return {
            'cpu': {
                'percent': round(cpu_percent, 1),
                'count': psutil.cpu_count(),
                'frequency_current': cpu_freq.current if cpu_freq else 0
            },
            'memory': {
                'total': memory.total,
                'used': memory_used,
                'percent': round(memory_percent, 1),
            },
            'network': {
                'bytes_sent': net_io.bytes_sent,
                'bytes_recv': net_io.bytes_recv,
            },
            'processes': process_usage['processes'],
            'users': process_usage['users'],
            'process_memory_metric': process_usage['memory_metric'],
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
