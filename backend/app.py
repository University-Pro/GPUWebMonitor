import os
import sqlite3
import json
import time
import threading
import logging
import gc
import secrets
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, g
from flask_cors import CORS
from deployment_mode import LAN_MODE, load_deployment_mode

# 假设 gpu_monitor 存在于路径中
try:
    import gpu_monitor
except ImportError:
    # 模拟环境（仅供测试）
    class DummyMonitor:
        def get_all_info(self):
            return {"system": {"cpu": {"percent": 0}, "memory": {"percent": 0}}, "gpu": {"gpus": [], "summary": {}}}
    gpu_monitor = DummyMonitor()

# --- 配置 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, 'monitor_data.db')
RECORD_INTERVAL = 30
KEEP_HISTORY_DAYS = 30
PORT = int(os.environ.get('GPU_MONITOR_PORT', '15896'))
HOST = os.environ.get('GPU_MONITOR_HOST', '0.0.0.0')
AGENT_TOKEN = os.environ.get('GPU_MONITOR_AGENT_TOKEN', '')
DEPLOYMENT_MODE = load_deployment_mode()

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
if DEPLOYMENT_MODE == LAN_MODE:
    # Match the original LAN deployment, where browsers may query Agents
    # directly from another intranet origin. Public Agents are private APIs.
    CORS(app)


@app.before_request
def require_agent_token():
    """Require a token in public mode and preserve the original LAN behavior."""
    if not request.path.startswith('/api/') or DEPLOYMENT_MODE == LAN_MODE:
        return None

    if not AGENT_TOKEN:
        logger.error("Public Agent mode requires GPU_MONITOR_AGENT_TOKEN")
        return jsonify({"code": 503, "msg": "Public Agent security is not configured"}), 503

    authorization = request.headers.get('Authorization', '')
    scheme, _, supplied_token = authorization.partition(' ')
    if scheme.lower() != 'bearer' or not secrets.compare_digest(supplied_token, AGENT_TOKEN):
        return jsonify({"code": 401, "msg": "Unauthorized"}), 401
    return None

# --- 数据库核心逻辑 ---

def get_db_connection():
    """
    创建一个统一配置的数据库连接。
    使用 DELETE 模式确保不产生 .wal 和 .shm 文件。
    """
    try:
        # 增加 timeout 到 30s，防止 DELETE 模式下的并发锁竞争
        conn = sqlite3.connect(DB_FILE, timeout=30)
        conn.row_factory = sqlite3.Row
        
        # 关键配置：DELETE 模式在事务完成后会删除日志文件
        # synchronous FULL 保证在非WAL模式下的数据完整性
        conn.execute("PRAGMA journal_mode=DELETE;")
        conn.execute("PRAGMA synchronous=FULL;")
        # 优化内存使用
        conn.execute("PRAGMA cache_size=-2000;") # 约 2MB 缓存
        return conn
    except Exception as e:
        logger.error(f"无法连接数据库: {e}")
        return None

def get_db():
    """Flask 请求上下文内复用数据库连接"""
    if 'db' not in g:
        g.db = get_db_connection()
    return g.db

@app.teardown_appcontext
def close_connection(exception):
    """确保 Flask 请求结束后彻底关闭连接，释放 FD"""
    db = g.pop('db', None)
    if db is not None:
        try:
            db.close()
        except Exception as e:
            logger.error(f"关闭数据库连接失败: {e}")

def init_db():
    """初始化数据库表结构"""
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS system_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME NOT NULL,
                    cpu_percent REAL,
                    memory_percent REAL,
                    gpu_data TEXT,
                    summary TEXT
                )
            ''')
            cursor.execute(
                'CREATE INDEX IF NOT EXISTS idx_timestamp ON system_metrics (timestamp)'
            )
            conn.commit()
            logger.info("数据库初始化完成（Mode: DELETE）")
        except Exception as e:
            logger.exception(f"初始化数据库失败：{e}")
        finally:
            conn.close()

# --- FD 监控辅助 ---
def get_fd_count():
    try:
        return len(os.listdir('/proc/self/fd'))
    except:
        return -1

# --- 后台记录任务 ---
def background_recorder():
    logger.info(f"后台记录服务启动，保留天数：{KEEP_HISTORY_DAYS}")

    while True:
        conn = None
        try:
            # 1. 采集数据（注意：如果 gpu_monitor 内部有 FD 泄漏，此处最危险）
            # 建议检查 gpu_monitor 是否正确关闭了所有 subprocess
            full_data = gpu_monitor.get_all_info()
            
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            sys_data = full_data.get('system', {})
            cpu_percent = sys_data.get('cpu', {}).get('percent', 0)
            mem_percent = sys_data.get('memory', {}).get('percent', 0)
            gpu_info = full_data.get('gpu', {})
            gpu_json = json.dumps(gpu_info.get('gpus', []), default=str)
            summary_json = json.dumps(gpu_info.get('summary', {}), default=str)

            # 2. 写入数据库
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO system_metrics (timestamp, cpu_percent, memory_percent, gpu_data, summary)
                    VALUES (?, ?, ?, ?, ?)
                ''', (timestamp, cpu_percent, mem_percent, gpu_json, summary_json))

                # 3. 清理过期数据
                cleanup_threshold = (
                    datetime.now() - timedelta(days=KEEP_HISTORY_DAYS)
                ).strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute("DELETE FROM system_metrics WHERE timestamp < ?", (cleanup_threshold,))
                
                conn.commit()
                logger.debug(f"数据记录成功，当前 FD: {get_fd_count()}")

        except Exception as e:
            logger.error(f"后台记录循环发生错误: {e}")
        finally:
            # 显式关闭连接，释放 FD
            if conn:
                try:
                    conn.close()
                except:
                    pass
            # 强制进行垃圾回收，防止某些对象持有的 FD 延迟释放
            if int(time.time()) % 300 == 0: 
                gc.collect()

        time.sleep(RECORD_INTERVAL)

# --- API 路由 ---

@app.route('/')
def health_check():
    return jsonify({
        "status": "ok",
        "deployment_mode": DEPLOYMENT_MODE,
        "fd_count": get_fd_count(),
        "time": datetime.now().isoformat()
    })

@app.route('/api/status', methods=['GET'])
def get_current_status():
    try:
        # 直接调用监控函数，不涉及 DB
        data = gpu_monitor.get_all_info()
        return jsonify({"code": 200, "data": data, "msg": "success"})
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e)}), 500

@app.route('/api/history', methods=['GET'])
def get_history():
    limit = min(request.args.get('limit', 100, type=int), 1000)
    
    try:
        db = get_db()
        if not db:
            return jsonify({"code": 500, "msg": "Database connection failed"}), 500
            
        cursor = db.execute('''
            SELECT timestamp, cpu_percent, memory_percent, gpu_data, summary
            FROM system_metrics
            ORDER BY id DESC
            LIMIT ?
        ''', (limit,))
        rows = cursor.fetchall()

        history_data = []
        for row in reversed(rows):
            try:
                history_data.append({
                    "timestamp": row['timestamp'],
                    "cpu_percent": row['cpu_percent'],
                    "memory_percent": row['memory_percent'],
                    "gpus": json.loads(row['gpu_data']) if row['gpu_data'] else [],
                    "summary": json.loads(row['summary']) if row['summary'] else {}
                })
            except:
                continue

        return jsonify({"code": 200, "data": history_data, "msg": "success"})
    except Exception as e:
        logger.error(f"查询历史失败: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500

if __name__ == '__main__':
    # 确保数据库初始化
    init_db()

    # 启动后台线程
    recorder_thread = threading.Thread(
        target=background_recorder,
        daemon=True
    )
    recorder_thread.start()

    logger.info(f"Agent 启动在 {HOST}:{PORT}，部署模式：{DEPLOYMENT_MODE}")
    # 使用 threaded=True 处理并发请求，但限制线程数（可选）
    app.run(host=HOST, port=PORT, debug=False, threaded=True)
