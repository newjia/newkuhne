# Docker 部署指南

## 概述

为了支持图表生成功能，项目已切换到 Docker 部署，同时包含 Python 和 Node.js 环境。

## 部署步骤

### 在 Render 上部署

#### 方法一：自动检测（推荐）

Render 会自动检测到 `render.yaml` 和 `Dockerfile`，并使用 Docker 部署。

1. **推送代码到 GitHub**
   ```bash
   git push
   ```

2. **Render 自动部署**
   - Render 检测到 `env: docker`
   - 自动构建 Docker 镜像
   - 部署容器

3. **等待部署完成**（约 3-5 分钟）
   - 构建 Docker 镜像
   - 安装 Python 依赖
   - 安装 Node.js 和 mcp-echarts
   - 启动服务

#### 方法二：手动触发

如果自动部署没有触发：

1. 登录 Render Dashboard
2. 找到 `kuhne-mcp-server` 服务
3. 点击 "Manual Deploy" → "Clear build cache & deploy"

### 验证部署

#### 1. 检查服务状态

访问：https://newkuhne.onrender.com/

应该返回：
```json
{
  "status": "SQLite MCP Server running",
  "tools": 9,
  "features": ["data_query", "chart_generation"]
}
```

#### 2. 检查 Node.js 环境

查看 Render 日志，应该看到：
```
✅ Node.js installed
✅ mcp-echarts installed
✅ MCP Server 初始化完成
```

#### 3. 测试图表生成

在 Copilot Studio 中输入：
```
Generate a bar chart for top 5 customers
```

应该返回：
```
📊 Chart generated successfully!

View chart: https://newkuhne.onrender.com/charts/xxx.png

Data summary:
- Customer 1: $xxx
- Customer 2: $xxx
...
```

## Docker 配置说明

### Dockerfile

- **基础镜像**：`python:3.13-slim`
- **Node.js 版本**：20.x LTS
- **Python 依赖**：从 `requirements.txt` 安装
- **Node.js 依赖**：全局安装 `mcp-echarts`
- **端口**：10000

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| PORT | 10000 | 服务端口 |
| DB_PATH | orders.db | 数据库文件路径 |

### 目录结构

```
/app/
├── mcp_server_http.py      # 主服务
├── requirements.txt         # Python 依赖
├── orders.db               # SQLite 数据库（运行时创建）
└── static/
    └── charts/             # 图表存储目录
        └── *.png           # 生成的图表
```

## 本地测试

### 构建 Docker 镜像

```bash
docker build -t kuhne-mcp-server .
```

### 运行容器

```bash
docker run -p 10000:10000 \
  -e PORT=10000 \
  -e DB_PATH=orders.db \
  kuhne-mcp-server
```

### 测试服务

```bash
# 检查状态
curl http://localhost:10000/

# 测试工具列表
curl -X POST http://localhost:10000/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": "1", "method": "tools/list", "params": {}}'

# 测试图表生成
curl -X POST http://localhost:10000/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "tools/call",
    "params": {
      "name": "generate_customer_chart",
      "arguments": {"chart_type": "bar", "limit": 5}
    }
  }'
```

## 故障排查

### 问题 1：Docker 构建失败

**症状**：Render 显示 "Build failed"

**解决**：
1. 检查 Dockerfile 语法
2. 查看 Render 构建日志
3. 确认 requirements.txt 中的依赖版本

### 问题 2：Node.js 安装失败

**症状**：日志显示 "Node.js not found"

**解决**：
1. 检查 Dockerfile 中的 Node.js 安装命令
2. 确认网络连接正常
3. 尝试使用不同的 Node.js 版本

### 问题 3：mcp-echarts 安装失败

**症状**：日志显示 "npm install failed"

**解决**：
1. 检查 npm 版本：`npm --version`
2. 清除 npm 缓存：`npm cache clean --force`
3. 手动安装：`npm install -g mcp-echarts`

### 问题 4：图表生成超时

**症状**：返回 "Chart generation timed out"

**解决**：
1. 增加超时时间（在 `mcp_server_http.py` 中修改 `timeout=30`）
2. 检查数据量是否过大
3. 查看 Render 资源使用情况

### 问题 5：图表 URL 404

**症状**：点击图表 URL 显示 404

**解决**：
1. 检查 `static/charts/` 目录是否存在
2. 确认图表文件已生成
3. 检查 FastAPI 静态文件配置

## 性能优化

### 1. 图表缓存

可以添加缓存机制，避免重复生成相同的图表：

```python
# 在生成图表前检查缓存
cache_key = f"{chart_type}_{limit}_{hash(data)}"
if cache_key in chart_cache:
    return chart_cache[cache_key]
```

### 2. 异步生成

对于大数据量，可以使用异步任务队列：

```python
# 使用 Celery 或 RQ 异步生成图表
task = generate_chart.delay(data)
return {"task_id": task.id, "status": "processing"}
```

### 3. CDN 加速

将图表上传到 CDN（如 Cloudflare）：

```python
# 上传到 CDN
cdn_url = upload_to_cdn(chart_file)
return cdn_url
```

## 安全建议

1. **限制图表生成频率**：添加 rate limiting
2. **清理旧图表**：定期删除超过 24 小时的图表
3. **验证输入参数**：防止恶意输入
4. **使用 HTTPS**：确保图表 URL 使用 HTTPS

## 成本估算

### Render 资源使用

- **CPU**：构建时较高，运行时较低
- **内存**：约 512MB - 1GB
- **存储**：图表文件约 50-200KB/张
- **带宽**：取决于图表访问频率

### 优化建议

- 使用 Render 的免费套餐（有限制）
- 升级到 Starter 套餐（$7/月）获得更好性能
- 使用外部对象存储（MinIO/S3）减少本地存储

## 更新日志

### v1.2.0 (2026-02-26)

- ✅ 切换到 Docker 部署
- ✅ 集成 Node.js 环境
- ✅ 启用图表生成功能
- ✅ 添加健康检查端点
- ✅ 优化构建流程
