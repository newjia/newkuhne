# 使用官方 Python 镜像作为基础
FROM python:3.13-slim

# 安装 Node.js 和 npm
RUN apt-get update && apt-get install -y \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 全局安装 mcp-echarts
RUN npm install -g mcp-echarts

# 复制应用代码
COPY . .

# 创建图表存储目录
RUN mkdir -p static/charts

# 暴露端口
EXPOSE 10000

# 启动命令
CMD ["python", "mcp_server_http.py"]
