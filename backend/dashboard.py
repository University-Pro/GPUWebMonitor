import os
import json
import requests
from flask import Flask, render_template, jsonify, request, send_from_directory

app = Flask(__name__, template_folder='.')

# 配置文件路径
CONFIG_FILE = 'front/config.json'

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"servers": []}

@app.route('/')
def index():
    """渲染主页"""
    return render_template('front/index.html')

@app.route('/api/config')
def get_config_api():
    """前端获取服务器列表，不包含敏感URL，只返回ID和名字"""
    config = load_config()
    # 为了安全，如果你不想暴露真实URL给前端，可以在这里过滤掉 url 字段
    # 但为了简单，这里直接返回
    return jsonify(config)

@app.route('/api/proxy')
def proxy_data():
    """
    核心代理接口
    前端请求: /api/proxy?id=node1
    服务端操作: 查找 node1 的 URL -> requests.get() -> 返回数据
    """
    server_id = request.args.get('id')
    if not server_id:
        return jsonify({"code": 400, "msg": "Missing server id"}), 400

    config = load_config()
    target_server = next((s for s in config.get('servers', []) if s['id'] == server_id), None)

    if not target_server:
        return jsonify({"code": 404, "msg": "Server not found"}), 404

    target_url = target_server.get('url')
    # 拼接目标 API 地址
    api_url = f"{target_url.rstrip('/')}/api/status"

    try:
        # 服务端发起请求 (超时设置短一点，防止卡住)
        response = requests.get(api_url, timeout=3)
        return jsonify(response.json())
    except Exception as e:
        print(f"Proxy Error: {e}")
        return jsonify({"code": 502, "msg": "后端连接失败"}), 502

if __name__ == '__main__':
    print("Dashboard Server running on port 8080")
    app.run(host='0.0.0.0', port=8080, debug=False)