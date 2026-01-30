# 使用官方极其轻量的 Nginx Alpine 镜像
FROM docker.1ms.run/library/nginx:alpine

# 设置维护者信息 (可选)
LABEL maintainer="Jason"

# 删除 Nginx 默认的欢迎页面
RUN rm -rf /usr/share/nginx/html/*

# 将当前目录下的 index.html 和 config.json 复制到镜像中
# 这一步是为了让镜像在不挂载卷的情况下也能有默认内容运行
COPY index.html /usr/share/nginx/html/
COPY config.json /usr/share/nginx/html/

# 暴露 80 端口
EXPOSE 80

# 启动 Nginx
# daemon off; 让 Nginx 在前台运行，保证容器不退出
CMD ["nginx", "-g", "daemon off;"]