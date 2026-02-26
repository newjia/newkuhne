# 图表生成功能说明

## 概述

新增了试验性的图表生成功能，可以将客户订单统计数据可视化为柱状图、饼图或折线图。

## 功能特点

- ✅ 不影响现有 8 个数据查询工具
- ✅ 独立的图表生成工具
- ✅ 支持 3 种图表类型：bar（柱状图）、pie（饼图）、line（折线图）
- ✅ 返回图表 URL，用户可在浏览器中查看

## 使用方法

### 在 Copilot Studio 中

用户可以这样提问：

```
Show me a chart of top 10 customers by sales
Visualize customer order statistics
Generate a pie chart for top 5 customers
```

智能体会自动调用 `generate_customer_chart` 工具，返回：
- 数据摘要（文本）
- 图表 URL（可点击查看）

### 示例输出

```
📊 Chart generated successfully!

View chart: https://newkuhne.onrender.com/charts/abc123.png

Data summary:
- 阿里巴巴: $125,000.00
- 腾讯科技: $98,500.00
- 字节跳动: $87,200.00
- 美团: $76,800.00
- 拼多多: $65,400.00
```

## 技术实现

### 依赖

需要在服务器上安装 `mcp-echarts`：

```bash
npm install -g mcp-echarts
```

### 工作流程

1. 用户请求可视化
2. MCP Server 查询数据库获取统计数据
3. 调用 `mcp-echarts` 生成图表（PNG 格式）
4. 保存图表到 `static/charts/` 目录
5. 返回图表 URL

### 文件结构

```
kuhne/
├── mcp_server_http.py      # 主服务器（已添加图表功能）
├── static/
│   └── charts/              # 图表存储目录（自动创建）
│       └── {uuid}.png       # 生成的图表文件
└── test_chart.py            # 测试脚本
```

## 限制说明

### 当前限制

1. **仅支持客户订单统计**：目前只实现了按客户分组的订单统计图表
2. **需要 Node.js 环境**：服务器需要安装 Node.js 和 mcp-echarts
3. **图表存储**：图表保存在本地文件系统，重启后会丢失（可以后续改为 MinIO）
4. **Copilot Studio UI 限制**：无法在对话框中直接显示图表，需要用户点击 URL 查看

### 未来改进

- [ ] 支持更多图表类型（按时间、按地区、按产品等）
- [ ] 集成 MinIO 对象存储，持久化图表
- [ ] 支持自定义图表样式和主题
- [ ] 添加图表缓存机制
- [ ] 支持导出为 SVG 或 PDF 格式

## 测试

### 本地测试

1. 启动服务器：
```bash
python mcp_server_http.py
```

2. 运行测试脚本：
```bash
python test_chart.py
```

### 在 Copilot Studio 测试

1. 确保 Generative Orchestration 已开启
2. 在对话中输入：
```
Show me a bar chart of top 5 customers
```

3. 智能体应该会：
   - 显示思考过程（如果已添加 Instructions）
   - 调用 `generate_customer_chart` 工具
   - 返回图表 URL

## 故障排查

### 图表生成失败

**问题**：返回 "Chart generation failed"

**解决**：
1. 检查 Node.js 是否已安装：`node --version`
2. 检查 mcp-echarts 是否已安装：`npx mcp-echarts -h`
3. 查看服务器日志中的详细错误信息

### 图表 URL 无法访问

**问题**：点击 URL 显示 404

**解决**：
1. 检查 `static/charts/` 目录是否存在
2. 检查图表文件是否已生成
3. 确认 FastAPI 静态文件服务已正确配置

### Copilot Studio 不调用图表工具

**问题**：智能体不使用图表功能

**解决**：
1. 确认 Generative Orchestration 已开启
2. 在 Agent Instructions 中明确提到图表功能
3. 使用明确的关键词："chart", "visualize", "graph"

## 安全注意事项

1. **文件存储**：图表文件存储在公开可访问的目录，不要包含敏感信息
2. **资源限制**：考虑添加图表生成频率限制，防止滥用
3. **文件清理**：定期清理旧的图表文件，避免磁盘空间耗尽

## 更新日志

### v1.1.0 (2026-02-26)

- ✅ 新增 `generate_customer_chart` 工具
- ✅ 集成 mcp-echarts
- ✅ 支持 bar/pie/line 三种图表类型
- ✅ 添加静态文件服务
- ✅ 不影响现有功能
