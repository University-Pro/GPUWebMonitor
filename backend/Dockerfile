# 使用官方 Python 基础镜像
FROM python:latest

# 设置工作目录
WORKDIR /app

# 安装必要的系统依赖 (GCC用于编译psutil等)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    procps \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
# nvitop 依赖 pynvml, psutil, flask, flask-cors
RUN pip install --no-cache-dir \
    flask \
    flask-cors \
    nvitop \
    psutil

# 复制应用程序代码
COPY app.py .
COPY gpu_monitor.py .

# 暴露端口
EXPOSE 5000

# 启动命令
CMD ["python", "app.py"]