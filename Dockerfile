# 基于 Python 3.12 官方镜像
FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖（如果需要编译某些 Python 包）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 先复制依赖文件并安装（利用 Docker 缓存层）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY . .

# 创建数据目录
RUN mkdir -p data

# 暴露服务端口
EXPOSE 8010

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8010"]
