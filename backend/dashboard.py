import os
import json
import requests
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

app = Flask(__name__)

# 启用跨域支持，允许前端(如本地打开HTML)访问此API
CORS(app)

# 配置文件名
CONFIG_FILE = 'config.json'

def load_config():
    """读取配置文件"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
    return {"servers": []}

@app.route('/')
def serve_index():
    """
    (可选) 如果你想直接访问这个端口看网页，它会把当前目录下的 index.html 发给你。
    如果你是把 html 部署在别处，可以忽略这个路由。
    """
    if os.path.exists('index.html'):
        return send_from_directory('.', 'index.html')
    return "Backend is running. Please open index.html separately.", 200

@app.route('/api/config')
def get_config():
    """前端获取服务器列表"""
    config = load_config()
    return jsonify(config)

@app.route('/api/proxy')
def proxy_request():
    """
    核心代理逻辑
    前端请求: /api/proxy?id=node1
    后端执行: 找到 node1 的 URL -> requests.get(URL) -> 返回结果
    """
    server_id = request.args.get('id')
    if not server_id:
        return jsonify({"code": 400, "msg": "缺少参数: id"}), 400

    config = load_config()
    # 根据 ID 查找对应的服务器配置
    target_server = next((s for s in config.get('servers', []) if s['id'] == server_id), None)

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
        resp = requests.get(target_api, timeout=5, verify=False)
        
        # 直接透传后端的状态码和 JSON 数据
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
    print("Dashboard Proxy running on port 8080")
    app.run(host='0.0.0.0', port=8080, debug=False)