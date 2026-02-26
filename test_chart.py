#!/usr/bin/env python3
"""
测试图表生成功能
"""
import requests
import json

# 测试本地服务器
BASE_URL = "http://localhost:8000"

def test_chart_generation():
    """测试图表生成工具"""
    print("🧪 Testing chart generation tool...")

    # 调用 MCP 协议
    payload = {
        "jsonrpc": "2.0",
        "id": "test-chart",
        "method": "tools/call",
        "params": {
            "name": "generate_customer_chart",
            "arguments": {
                "chart_type": "bar",
                "limit": 5
            }
        }
    }

    response = requests.post(f"{BASE_URL}/", json=payload)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")

def test_tools_list():
    """测试工具列表"""
    print("\n🧪 Testing tools/list...")

    payload = {
        "jsonrpc": "2.0",
        "id": "test-list",
        "method": "tools/list",
        "params": {}
    }

    response = requests.post(f"{BASE_URL}/", json=payload)
    result = response.json()

    if "result" in result and "tools" in result["result"]:
        tools = result["result"]["tools"]
        print(f"✅ Found {len(tools)} tools:")
        for tool in tools:
            print(f"  - {tool['name']}: {tool['title']}")
    else:
        print(f"❌ Unexpected response: {result}")

if __name__ == "__main__":
    print("=" * 60)
    print("MCP Server Chart Generation Test")
    print("=" * 60)

    try:
        test_tools_list()
        # test_chart_generation()  # 需要先安装 mcp-echarts
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server. Make sure it's running on localhost:8000")
    except Exception as e:
        print(f"❌ Error: {e}")
