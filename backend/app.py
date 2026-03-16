import os
import sqlite3
import json
import time
import threading
import logging
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, g
from flask_cors import CORS
import gpu_monitor

# --- 配置 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, 'monitor_data.db')
RECORD_INTERVAL = 30
KEEP_HISTORY_DAYS = 30
PORT = 15896

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Flask
app = Flask(__name__)
CORS(app)


# --- 工具函数 ---
def get_fd_count():
    """获取当前进程打开的文件描述符数量，仅 Linux 可用。"""
    try:
        return len(os.listdir('/proc/self/fd'))
    except Exception:
        return -1


# --- 数据库处理 ---
def get_db():
    """
    Flask 请求上下文内复用数据库连接。
    每个请求结束后由 teardown 关闭。
    """
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DB_FILE, timeout=10)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        try:
            db.close()
        except Exception:
            pass


def init_db():
    """初始化数据库，仅在启动时执行一次 WAL 配置。"""
    try:
        with sqlite3.connect(DB_FILE, timeout=10) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
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
            cursor.close()
            logger.info("数据库初始化完成")
    except Exception as e:
        logger.exception(f"初始化数据库失败：{e}")


# --- 后台记录任务 ---
def background_recorder():
    logger.info(
        f"后台记录服务启动，间隔：{RECORD_INTERVAL}秒，保留天数：{KEEP_HISTORY_DAYS}天"
    )

    last_checkpoint_time = time.time()
    CHECKPOINT_INTERVAL = 24 * 60 * 60  # 每 24 小时执行一次 checkpoint

    while True:
        try:
            logger.info(f"后台任务开始，当前FD数量: {get_fd_count()}")

            # 1. 获取监控数据，并记录 get_all_info 前后 FD 变化
            fd_before = get_fd_count()
            full_data = gpu_monitor.get_all_info()
            fd_after = get_fd_count()
            logger.info(f"get_all_info() FD变化: {fd_before} -> {fd_after}")

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            sys_data = full_data.get('system', {})
            cpu_percent = sys_data.get('cpu', {}).get('percent', 0)
            mem_percent = sys_data.get('memory', {}).get('percent', 0)

            gpu_info = full_data.get('gpu', {})
            gpu_json = json.dumps(gpu_info.get('gpus', []), default=str)
            summary_json = json.dumps(gpu_info.get('summary', {}), default=str)

            # 2. 写入数据库
            with sqlite3.connect(DB_FILE, timeout=10) as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    INSERT INTO system_metrics (timestamp, cpu_percent, memory_percent, gpu_data, summary)
                    VALUES (?, ?, ?, ?, ?)
                ''', (timestamp, cpu_percent, mem_percent, gpu_json, summary_json))

                # 3. 清理过期数据
                cleanup_threshold = (
                    datetime.now() - timedelta(days=KEEP_HISTORY_DAYS)
                ).strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute(
                    "DELETE FROM system_metrics WHERE timestamp < ?",
                    (cleanup_threshold,)
                )

                deleted_count = cursor.rowcount
                if deleted_count > 0:
                    logger.info(f"清理过期数据：{deleted_count} 条记录")

                conn.commit()
                cursor.close()

            # 4. 定期执行 checkpoint，而不是 VACUUM
            current_time = time.time()
            if current_time - last_checkpoint_time > CHECKPOINT_INTERVAL:
                try:
                    with sqlite3.connect(DB_FILE, timeout=10) as conn_ckpt:
                        conn_ckpt.execute("PRAGMA wal_checkpoint(TRUNCATE);")
                    logger.info("执行数据库 wal_checkpoint(TRUNCATE) 完成")
                    last_checkpoint_time = current_time
                except sqlite3.OperationalError as e:
                    logger.warning(f"checkpoint 执行失败（可能数据库正忙）: {e}")
                except Exception as e:
                    logger.exception(f"checkpoint 发生错误：{e}")

            logger.info(f"后台任务结束，当前FD数量: {get_fd_count()}")

        except Exception as e:
            logger.exception(f"后台记录失败：{e}")

        time.sleep(RECORD_INTERVAL)


# --- API 路由 ---
@app.route('/')
def health_check():
    return jsonify({
        "status": "ok",
        "role": "gpu-agent",
        "time": datetime.now().isoformat()
    })


@app.route('/api/status', methods=['GET'])
def get_current_status():
    try:
        data = gpu_monitor.get_all_info()
        return jsonify({"code": 200, "data": data, "msg": "success"})
    except Exception as e:
        logger.exception(f"获取状态失败：{e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route('/api/history', methods=['GET'])
def get_history():
    limit = request.args.get('limit', 100, type=int)

    # 防止恶意请求拖慢数据库
    if limit > 1000:
        limit = 1000
    elif limit <= 0:
        limit = 100

    query = '''
        SELECT timestamp, cpu_percent, memory_percent, gpu_data, summary
        FROM system_metrics
        ORDER BY id DESC
        LIMIT ?
    '''

    try:
        db = get_db()
        cursor = db.execute(query, (limit,))
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
            except Exception:
                continue

        return jsonify({"code": 200, "data": history_data, "msg": "success"})
    except Exception as e:
        logger.exception(f"获取历史数据失败：{e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


if __name__ == '__main__':
    init_db()

    recorder_thread = threading.Thread(
        target=background_recorder,
        daemon=True
    )
    recorder_thread.start()

    logger.info(f"Agent running on port {PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=False, threaded=True)