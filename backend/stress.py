# 这个脚本用于模拟压力测试，向后端接口发起大量请求，观察系统的响应情况。

import requests
import threading
import time

URL = "http://localhost:15896/api/history?limit=100"

def make_request():
    try:
        resp = requests.get(URL)
        print(f"Status: {resp.status_code}, Data length: {len(resp.text)}")
    except Exception as e:
        print(f"Request failed: {e}")

# 模拟 50 个线程同时发起 5000 次请求
threads = []
for i in range(5000):
    t = threading.Thread(target=make_request)
    threads.append(t)
    t.start()
    if i % 10 == 0: time.sleep(0.1) # 稍微错开

for t in threads:
    t.join()