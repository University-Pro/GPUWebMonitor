# 中转后端，用于代理前端请求到内网的服务器
import os
import json
import requests
from flask import Flask, jsonify, request, make_response, send_from_directory
from flask_cors import CORS

# 设置Flask
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# --- 路径配置 ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(CURRENT_DIR, '..', 'front', 'config.json')

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

@app.route('/')
def serve_index():
    """提供前端主页面"""
    return send_from_directory(os.path.join(CURRENT_DIR, '..', 'front'), 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    """提供 front/ 目录下的静态资源（app.js, style.css 等）"""
    # 安全限制：只允许特定后缀，防止路径遍历
    if filename.endswith(('.js', '.css', '.html', '.json', '.png', '.jpg', '.ico')):
        return send_from_directory(os.path.join(CURRENT_DIR, '..', 'front'), filename)
    else:
        return jsonify({"error": "File not allowed"}), 403

@app.route('/api/config')
def get_config():
    """
    前端获取服务器列表
    前端会请求这个接口来获取 config.json 的内容
    """
    config = load_config()
    return jsonify(config)

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
    target_api = f"{base_url}/api/status"
    
    try:
        # 替前端发起请求，设置超时时间防止后端卡死
        # verify=False 是为了防止目标如果是 https 自签名证书报错
        print(f"Proxying request to: {target_api}")
        resp = requests.get(target_api, timeout=5, verify=False)
        
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
    # 监听 8080 端口
    print(f"Dashboard Proxy running on port 28456")
    print(f"Looking for config at: {CONFIG_FILE}")
    app.run(host='0.0.0.0', port=28456, debug=False)