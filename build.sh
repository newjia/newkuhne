#!/bin/bash
# Render 构建脚本

echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

echo "📦 Installing Node.js dependencies..."
# 检查 Node.js 是否已安装
if ! command -v node &> /dev/null; then
    echo "⚠️  Node.js not found. Chart generation will not work."
    echo "   Please enable Node.js in Render dashboard."
else
    echo "✅ Node.js version: $(node --version)"
    echo "📦 Installing mcp-echarts..."
    npm install -g mcp-echarts
    echo "✅ mcp-echarts installed"
fi

echo "✅ Build complete!"
