"""
Mock 后端服务
提供与真实 backend/app.py 完全相同的 API 接口，但返回模拟数据。
用于前端开发、演示和测试，无需真实 GPU 硬件。

用法:
    python -m mock.mock_app              # 在 backend/ 目录下运行
    python backend/mock/mock_app.py      # 在项目根目录运行

默认端口: 15897
"""

import os
import sys
import json
import logging
from datetime import datetime
from flask import Flask, jsonify, request, make_response, send_from_directory
from flask_cors import CORS

# 确保可以导入 mock_data
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mock_data import generate_mock_all_info, generate_mock_history

# --- 配置 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, '..', '..'))
FRONT_DIR = os.path.join(PROJECT_ROOT, 'front')
CONFIG_FILE = os.path.join(FRONT_DIR, 'config.json')
PORT = int(os.environ.get('MOCK_PORT', 15897))

# 日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [MOCK] %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)


def no_cache_response(response):
    """Prevent browsers from keeping stale dashboard assets."""
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


# --- 前端静态资源（与 dashboard.py 一致） ---

@app.route('/')
def serve_index():
    """提供前端主页面"""
    if os.path.exists(os.path.join(FRONT_DIR, 'index.html')):
        response = make_response(send_from_directory(FRONT_DIR, 'index.html'))
        return no_cache_response(response)
    return jsonify({"error": "front/index.html not found"}), 404


@app.route('/<path:filename>')
def serve_static(filename):
    """提供 front/ 目录下的静态资源"""
    if filename.endswith(('.js', '.css', '.html', '.json', '.png', '.jpg', '.ico')):
        if os.path.exists(os.path.join(FRONT_DIR, filename)):
            response = make_response(send_from_directory(FRONT_DIR, filename))
            return no_cache_response(response)
    return jsonify({"error": "File not found"}), 404


@app.route('/api/config')
def get_config():
    """提供服务器配置（mock 模式下返回单机配置）"""
    return jsonify({
        "servers": [
            {
                "id": "mock-server",
                "name": "Mock Server (本地模拟)",
                "url": f"http://localhost:{PORT}"
            }
        ]
    })


# --- Mock 监控 API（与真实 backend/app.py 一致） ---

@app.route('/api/status', methods=['GET'])
def get_current_status():
    """返回模拟的实时监控数据"""
    try:
        data = generate_mock_all_info()
        return jsonify({"code": 200, "data": data, "msg": "success"})
    except Exception as e:
        logger.error(f"生成 mock 数据失败: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route('/api/history', methods=['GET'])
def get_history():
    """返回模拟的历史数据"""
    limit = min(request.args.get('limit', 100, type=int), 1000)
    try:
        data = generate_mock_history(limit)
        return jsonify({"code": 200, "data": data, "msg": "success"})
    except Exception as e:
        logger.error(f"生成 mock 历史数据失败: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route('/api/health')
def health_check():
    """健康检查"""
    return jsonify({
        "status": "ok",
        "mode": "mock",
        "gpu_count": 8,
        "time": datetime.now().isoformat()
    })


# --- 中转代理模式（模拟 dashboard.py 的 /api/proxy） ---

@app.route('/api/proxy')
def proxy_request():
    """
    模拟中转代理，在 mock 模式下直接返回本地模拟数据。
    前端请求 /api/proxy?id=mock-server 时走这里。
    """
    server_id = request.args.get('id')
    if not server_id:
        return jsonify({"code": 400, "msg": "缺少参数: id"}), 400

    use_history = request.args.get('history') == '1'
    if use_history:
        limit = min(request.args.get('limit', 100, type=int), 1000)
        data = generate_mock_history(limit)
        return jsonify({"code": 200, "data": data, "msg": "success"})
    else:
        data = generate_mock_all_info()
        return jsonify({"code": 200, "data": data, "msg": "success"})


if __name__ == '__main__':
    print(f"""
╔══════════════════════════════════════════════╗
║       GPU Web Monitor - Mock Server          ║
║                                              ║
║  模拟 8 卡 B300 服务器 (8x B300 SXM6 AC)       ║
║  端口: {PORT:<38}║
║  前端: http://localhost:{PORT:<22}║
║  API:  http://localhost:{PORT}/api/status    ║
╚══════════════════════════════════════════════╝
""")
    logger.info(f"Mock 服务启动，模拟 GPU 数量: 8")
    app.run(host='0.0.0.0', port=PORT, debug=True)
