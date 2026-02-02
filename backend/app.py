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
DB_FILE = os.path.join(BASE_DIR, 'monitor_data.db') # 使用绝对路径
RECORD_INTERVAL = 30
KEEP_HISTORY_DAYS = 7
PORT = 5000

# 设置日志配置
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 配置Flask
app = Flask(__name__)
CORS(app) # 允许跨域

# --- 数据库处理 ---
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DB_FILE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# 初始化数据库
def init_db():
    try:
        with sqlite3.connect(DB_FILE) as conn:
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
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON system_metrics (timestamp)')
            conn.commit()
    except Exception as e:
        logger.error(f"初始化数据库失败: {e}")

# --- 后台记录任务 ---
def background_recorder():
    logger.info(f"后台记录服务启动，间隔: {RECORD_INTERVAL}秒")
    while True:
        try:
            full_data = gpu_monitor.get_all_info()
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            sys_data = full_data.get('system', {})
            cpu_percent = sys_data.get('cpu', {}).get('percent', 0)
            mem_percent = sys_data.get('memory', {}).get('percent', 0)
            gpu_info = full_data.get('gpu', {})
            
            gpu_json = json.dumps(gpu_info.get('gpus', []), default=str)
            summary_json = json.dumps(gpu_info.get('summary', {}), default=str)
            
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO system_metrics (timestamp, cpu_percent, memory_percent, gpu_data, summary)
                    VALUES (?, ?, ?, ?, ?)
                ''', (timestamp, cpu_percent, mem_percent, gpu_json, summary_json))
                
                # 简单的清理逻辑
                if datetime.now().hour == 3 and datetime.now().minute < 2:
                     cleanup_threshold = (datetime.now() - timedelta(days=KEEP_HISTORY_DAYS)).strftime('%Y-%m-%d %H:%M:%S')
                     cursor.execute("DELETE FROM system_metrics WHERE timestamp < ?", (cleanup_threshold,))
                conn.commit()
        except Exception as e:
            logger.error(f"后台记录失败: {e}")
        time.sleep(RECORD_INTERVAL)

# --- API 路由 ---
@app.route('/')
def health_check():
    return jsonify({"status": "ok", "role": "gpu-agent", "time": datetime.now().isoformat()})

@app.route('/api/status', methods=['GET'])
def get_current_status():
    try:
        data = gpu_monitor.get_all_info()
        return jsonify({"code": 200, "data": data, "msg": "success"})
    except Exception as e:
        logger.error(f"获取状态失败: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500

@app.route('/api/history', methods=['GET'])
def get_history():
    limit = request.args.get('limit', 100, type=int)
    query = 'SELECT timestamp, cpu_percent, memory_percent, gpu_data, summary FROM system_metrics ORDER BY id DESC LIMIT ?'
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
                    "gpus": json.loads(row['gpu_data']),
                    "summary": json.loads(row['summary'])
                })
            except: continue
        return jsonify({"code": 200, "data": history_data, "msg": "success"})
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e)}), 500

if __name__ == '__main__':
    # 确保数据库存在
    init_db()
    
    recorder_thread = threading.Thread(target=background_recorder, daemon=True)
    recorder_thread.start()
    
    # 监听所有 IP，端口 5000
    print(f"Agent running on port {PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=False)