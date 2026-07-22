# 中转后端，用于代理前端请求到内网的服务器
import os
import json
import requests
import secrets
from flask import Flask, jsonify, request, make_response, send_from_directory, Response
from flask_cors import CORS
from deployment_mode import (
    LAN_MODE,
    PUBLIC_MODE,
    load_boolean_setting,
    load_deployment_mode,
)

# 设置Flask
app = Flask(__name__)

# --- 路径配置 ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DEPLOYMENT_MODE = load_deployment_mode()
DEFAULT_CONFIG_FILE = (
    os.path.join(CURRENT_DIR, '..', 'front', f'config.{DEPLOYMENT_MODE}.json')
    if 'GPU_MONITOR_DEPLOYMENT_MODE' in os.environ
    else os.path.join(CURRENT_DIR, '..', 'front', 'config.json')
)
CONFIG_FILE = os.environ.get(
    'GPU_MONITOR_CONFIG_FILE',
    DEFAULT_CONFIG_FILE,
)
DASHBOARD_USERNAME = os.environ.get('GPU_MONITOR_DASHBOARD_USERNAME', '')
DASHBOARD_PASSWORD = os.environ.get('GPU_MONITOR_DASHBOARD_PASSWORD', '')
AGENT_TOKEN = os.environ.get('GPU_MONITOR_AGENT_TOKEN', '')
DASHBOARD_HOST = os.environ.get('GPU_MONITOR_DASHBOARD_HOST', '0.0.0.0')
DASHBOARD_PORT = int(os.environ.get('GPU_MONITOR_DASHBOARD_PORT', '28456'))
VERIFY_AGENT_TLS = load_boolean_setting(
    'GPU_MONITOR_VERIFY_AGENT_TLS',
    DEPLOYMENT_MODE == PUBLIC_MODE,
)

if DEPLOYMENT_MODE == LAN_MODE:
    # Match the original GitHub LAN deployment and allow intranet origins.
    CORS(app, resources={r"/api/*": {"origins": "*"}})


@app.before_request
def require_dashboard_login():
    """Enforce Basic auth publicly; LAN mode deliberately has no login."""
    if DEPLOYMENT_MODE == LAN_MODE:
        return None

    if not DASHBOARD_USERNAME or not DASHBOARD_PASSWORD or not AGENT_TOKEN:
        return jsonify({
            "code": 503,
            "msg": "Public Dashboard security is not configured",
        }), 503

    auth = request.authorization
    valid = (
        auth is not None
        and secrets.compare_digest(auth.username or '', DASHBOARD_USERNAME)
        and secrets.compare_digest(auth.password or '', DASHBOARD_PASSWORD)
    )
    if valid:
        return None
    return Response(
        'Authentication required',
        401,
        {'WWW-Authenticate': 'Basic realm="GPU Cluster Monitor", charset="UTF-8"'},
    )

def load_config():
    """读取配置文件"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config from {CONFIG_FILE}: {e}")
            return {"servers": [], "error": str(e)}
    else:
        print(f"Config file not found at: {CONFIG_FILE}")
    return {"servers": []}


def no_cache_response(response):
    """Prevent browsers from keeping stale dashboard assets."""
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.route('/')
def serve_index():
    """提供前端主页面"""
    response = make_response(send_from_directory(os.path.join(CURRENT_DIR, '..', 'front'), 'index.html'))
    return no_cache_response(response)

@app.route('/<path:filename>')
def serve_static(filename):
    """提供 front/ 目录下的静态资源（app.js, style.css 等）"""
    if filename == 'config.json' and DEPLOYMENT_MODE == LAN_MODE:
        return no_cache_response(jsonify(load_config()))
    if filename.endswith('.json') and DEPLOYMENT_MODE == PUBLIC_MODE:
        return jsonify({"error": "File not allowed"}), 403
    # 安全限制：只允许特定后缀，防止路径遍历
    if filename.endswith(('.js', '.css', '.html', '.json', '.png', '.jpg', '.ico')):
        response = make_response(send_from_directory(os.path.join(CURRENT_DIR, '..', 'front'), filename))
        return no_cache_response(response)
    else:
        return jsonify({"error": "File not allowed"}), 403

@app.route('/api/config')
def get_config():
    """
    前端获取服务器列表
    前端会请求这个接口来获取 config.json 的内容
    """
    config = load_config()
    if DEPLOYMENT_MODE == LAN_MODE:
        # Compatibility with the original GitHub version, which returned the
        # full intranet Agent configuration and did not require a login.
        return jsonify({**config, "deployment_mode": LAN_MODE})

    # Public browsers only need display metadata. Keep Agent URLs private.
    public_servers = [
        {"id": server.get("id"), "name": server.get("name")}
        for server in config.get("servers", [])
    ]
    return jsonify({"deployment_mode": PUBLIC_MODE, "servers": public_servers})

@app.route('/api/proxy')
def proxy_request():
    """
    核心代理逻辑
    前端请求: /api/proxy?id=node1
    后端执行: 查找 node1 URL -> 请求内网 -> 返回结果
    """
    server_id = request.args.get('id')
    if not server_id:
        return jsonify({"code": 400, "msg": "缺少参数: id"}), 400

    config = load_config()
    servers = config.get('servers', [])
    
    # 根据 ID 查找对应的服务器配置
    target_server = next((s for s in servers if s['id'] == server_id), None)
    
    if not target_server:
        return jsonify({"code": 404, "msg": "未找到该服务器配置"}), 404
    
    base_url = target_server.get('url', '').rstrip('/')
    if not base_url:
        return jsonify({"code": 500, "msg": "该服务器配置缺少 URL"}), 500

    # 拼接目标 Agent 的 API 地址
    use_history = request.args.get('history') == '1'
    if use_history:
        limit = request.args.get('limit', '100')
        target_api = f"{base_url}/api/history?limit={limit}"
    else:
        target_api = f"{base_url}/api/status"

    try:
        # Public mode verifies HTTPS Agents by default. LAN mode keeps the
        # original self-signed-certificate compatibility unless overridden.
        print(f"Proxying request to: {target_api}")
        headers = {}
        if DEPLOYMENT_MODE == PUBLIC_MODE:
            headers['Authorization'] = f'Bearer {AGENT_TOKEN}'
        resp = requests.get(
            target_api,
            timeout=10,
            verify=VERIFY_AGENT_TLS,
            headers=headers,
        )

        # 返回数据
        return jsonify(resp.json()), resp.status_code

    except requests.exceptions.Timeout:
        return jsonify({"code": 504, "msg": "连接目标服务器超时"}), 504
    except requests.exceptions.ConnectionError:
        return jsonify({"code": 502, "msg": "无法连接到目标服务器 (Connection Refused)"}), 502
    except Exception as e:
        print(f"Proxy Error: {e}")
        return jsonify({"code": 500, "msg": f"代理服务内部错误: {str(e)}"}), 500

if __name__ == '__main__':
    print(f"Dashboard Proxy running on {DASHBOARD_HOST}:{DASHBOARD_PORT} ({DEPLOYMENT_MODE})")
    print(f"Looking for config at: {CONFIG_FILE}")
    app.run(host=DASHBOARD_HOST, port=DASHBOARD_PORT, debug=False)
