#!/usr/bin/env python3
"""
SQLite MCP Server - HTTP/SSE 模式（支持云端部署）
"""

import json
import sqlite3
import os
from typing import Any
from datetime import datetime, timedelta
import random
import subprocess
import uuid
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.sse import SseServerTransport
import uvicorn

# ============ 配置 ============
# 使用环境变量或默认值（Render 使用相对路径）
DB_PATH = os.getenv("DB_PATH", "orders.db")
PORT = int(os.getenv("PORT", "8000"))
CHARTS_DIR = Path("static/charts")
CHARTS_DIR.mkdir(parents=True, exist_ok=True)


def init_database():
    """初始化数据库（如果不存在）"""
    if os.path.exists(DB_PATH):
        return
    
    print(f"🆕 Creating database at {DB_PATH}", flush=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 创建表
    cursor.executescript("""
        CREATE TABLE regions (
            region_id TEXT PRIMARY KEY,
            region_name TEXT NOT NULL,
            city TEXT NOT NULL
        );
        
        CREATE TABLE customers (
            customer_id TEXT PRIMARY KEY,
            customer_name TEXT NOT NULL,
            region_id TEXT,
            contact TEXT,
            phone TEXT,
            FOREIGN KEY (region_id) REFERENCES regions(region_id)
        );
        
        CREATE TABLE products (
            product_id TEXT PRIMARY KEY,
            product_name TEXT NOT NULL,
            category TEXT,
            unit_price REAL NOT NULL
        );
        
        CREATE TABLE orders (
            order_id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL,
            product_id TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            total_amount REAL NOT NULL,
            order_date TEXT NOT NULL,
            status TEXT NOT NULL,
            shipping_address TEXT,
            notes TEXT,
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
            FOREIGN KEY (product_id) REFERENCES products(product_id)
        );
    """)
    
    # 插入示例数据
    regions = [
        ("R001", "华东区", "杭州"),
        ("R002", "华南区", "深圳"),
        ("R003", "华北区", "北京"),
        ("R004", "西南区", "成都"),
        ("R005", "华中区", "武汉"),
    ]
    
    customers = [
        ("C001", "阿里巴巴", "R001", "联系人1", "13800000001"),
        ("C002", "腾讯科技", "R002", "联系人2", "13800000002"),
        ("C003", "字节跳动", "R003", "联系人3", "13800000003"),
        ("C004", "美团", "R003", "联系人4", "13800000004"),
        ("C005", "拼多多", "R001", "联系人5", "13800000005"),
    ]
    
    products = [
        ("P001", "企业服务器", "硬件", 50000),
        ("P002", "云计算资源", "服务", 12000),
        ("P003", "企业路由器", "硬件", 8500),
        ("P004", "网络安全设备", "硬件", 15000),
        ("P005", "企业软件许可", "软件", 25000),
    ]
    
    cursor.executemany("INSERT INTO regions VALUES (?, ?, ?)", regions)
    cursor.executemany("INSERT INTO customers VALUES (?, ?, ?, ?, ?)", customers)
    cursor.executemany("INSERT INTO products VALUES (?, ?, ?, ?)", products)
    
    # 生成 50 条订单
    statuses = ["待付款", "已付款", "已发货", "已完成", "已取消"]
    for i in range(50):
        order_id = f"OR2025{i+1:04d}"
        customer = random.choice(customers)
        product = random.choice(products)
        quantity = random.randint(1, 10)
        total = quantity * product[3] * random.uniform(0.9, 1.1)
        status = random.choice(statuses)
        days_ago = random.randint(1, 365)
        order_date = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
        
        cursor.execute("""
            INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (order_id, customer[0], product[0], quantity, product[3], 
              round(total, 2), order_date, status, f"{customer[2]}市XX路", f"备注{i}"))
    
    conn.commit()
    conn.close()
    print(f"✅ Database created with sample data", flush=True)


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def dict_from_row(row):
    if row is None:
        return None
    return dict(zip(row.keys(), row))


# ============ MCP Server ============
mcp = Server("sqlite-orders-mcp")
sse = SseServerTransport("/messages")


# 工具定义（带 title 用于 Copilot Studio）
TOOLS_DEF = [
    {
        "name": "get_order_summary",
        "title": "Get Order Summary",
        "description": "Calculate aggregate statistics on orders: total amount, average amount, order count, min or max value. Use this for questions like 'total sales this month', 'average order value', 'how many orders'.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "aggregate": {"type": "string", "enum": ["sum", "avg", "count", "min", "max"], "description": "Aggregation function to apply"},
                "field": {"type": "string", "description": "Field to aggregate: 'total_amount' or 'quantity'"},
                "condition": {"type": "string", "description": "Optional SQL WHERE clause, e.g. \"status='已完成'\" or \"order_date >= '2026-01-01'\""}
            },
            "required": ["aggregate", "field"]
        }
    },
    {
        "name": "get_orders_by_customer",
        "title": "Get Orders by Customer",
        "description": "Group orders by customer or region and return totals, averages, and counts. Use this for 'top 10 customers by sales', 'orders per region', 'which customer has the most orders'.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "group_by": {"type": "string", "enum": ["customer_id", "region_id"], "description": "Group by customer or region"},
                "order": {"type": "string", "enum": ["ASC", "DESC"], "default": "DESC"},
                "limit": {"type": "integer", "default": 10}
            },
            "required": ["group_by"]
        }
    },
    {
        "name": "get_orders_by_date_range",
        "title": "Get Orders by Date Range",
        "description": "Retrieve orders within a specific date range, optionally filtered by status. Use this for 'orders in February', 'orders between Jan 1 and Feb 15', 'completed orders last month'.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string", "description": "Start date in YYYY-MM-DD format"},
                "end_date": {"type": "string", "description": "End date in YYYY-MM-DD format"},
                "status": {"type": "string", "description": "Optional order status filter"}
            },
            "required": ["start_date", "end_date"]
        }
    },
    {
        "name": "list_orders",
        "title": "List Orders",
        "description": "List orders with optional filters by status or customer. Use this for 'show latest orders', 'show all shipped orders', 'show orders from a specific customer', 'show me the latest 5 orders'.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "Filter by status: 待付款, 已付款, 已发货, 已完成, 已取消"},
                "customer_id": {"type": "string", "description": "Filter by customer ID"},
                "limit": {"type": "integer", "default": 20},
                "offset": {"type": "integer", "default": 0}
            }
        }
    },
    {
        "name": "get_order_detail",
        "title": "Get Order Detail",
        "description": "Get full details of a single order by order ID, including customer info, product, quantity, amount, and status. Use this for 'show order OR20250001', 'details for order X'.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string", "description": "The order ID, e.g. OR20250001"}
            },
            "required": ["order_id"]
        }
    },
    {
        "name": "update_order_status",
        "title": "Update Order Status",
        "description": "Update the status of an existing order. Valid statuses: 待付款 (pending payment), 已付款 (paid), 已发货 (shipped), 已完成 (completed), 已取消 (cancelled). Use this for 'change order X to shipped', 'mark order as completed'.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string", "description": "The order ID to update"},
                "new_status": {"type": "string", "description": "New status: 待付款, 已付款, 已发货, 已完成, or 已取消"}
            },
            "required": ["order_id", "new_status"]
        }
    },
    {
        "name": "get_customers",
        "title": "Get Customers",
        "description": "Retrieve the list of customers, optionally filtered by region. Use this for 'show all customers', 'customers in East China region', 'list customers'.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "region_id": {"type": "string", "description": "Optional region ID to filter customers, e.g. R001"}
            }
        }
    },
    {
        "name": "get_products",
        "title": "Get Products",
        "description": "Retrieve the list of products, optionally filtered by category. Use this for 'show all products', 'list hardware products', 'what products do we have'.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Optional category filter: 硬件 (hardware), 软件 (software), 服务 (service)"}
            }
        }
    },
    {
        "name": "generate_customer_chart",
        "title": "Generate Customer Order Chart",
        "description": "IMPORTANT: Use this tool when user explicitly asks for 'chart', 'graph', 'visualize', 'visual representation', or 'show me a chart/graph'. Generate a visual chart (bar/pie/line) showing order statistics by customer. Returns a chart image URL that can be viewed in a browser. DO NOT use this for simple data queries - only when visualization is explicitly requested.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "chart_type": {
                    "type": "string",
                    "enum": ["bar", "pie", "line"],
                    "default": "bar",
                    "description": "Type of chart: bar (comparison), pie (proportion), line (trend)"
                },
                "limit": {
                    "type": "integer",
                    "default": 10,
                    "description": "Number of top customers to show"
                }
            }
        }
    },
]


@mcp.list_tools()
async def list_tools() -> list[Tool]:
    """返回工具列表（兼容 MCP 协议）"""
    tools = []
    for t in TOOLS_DEF:
        # 手动构建 tool dict，包含 title
        tool_dict = {
            "name": t["name"],
            "description": t["description"],
            "inputSchema": t["inputSchema"],
            "title": t.get("title", t["name"]),
        }
        tools.append(Tool(**tool_dict))
    return tools


@mcp.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    try:
        if name == "get_order_summary":
            return await get_order_summary(arguments)
        elif name == "get_orders_by_customer":
            return await get_orders_by_customer(arguments)
        elif name == "get_orders_by_date_range":
            return await get_orders_by_date_range(arguments)
        elif name == "list_orders":
            return await list_orders(arguments)
        elif name == "get_order_detail":
            return await get_order_detail(arguments)
        elif name == "update_order_status":
            return await update_order_status(arguments)
        elif name == "get_customers":
            return await get_customers(arguments)
        elif name == "get_products":
            return await get_products(arguments)
        elif name == "generate_customer_chart":
            return await generate_customer_chart(arguments)
        else:
            return [TextContent(type="text", text=f"未知工具: {name}")]
    except Exception as e:
        return [TextContent(type="text", text=f"错误: {str(e)}")]


async def get_order_summary(args):
    agg = args.get("aggregate", "sum")
    field = args.get("field", "total_amount")
    condition = args.get("condition", "")
    
    valid_fields = ["total_amount", "quantity"]
    if field not in valid_fields:
        return [TextContent(type="text", text=f"无效字段")]
    
    sql = f"SELECT {agg}({field}) as result FROM orders"
    if condition:
        sql += f" WHERE {condition}"
    
    conn = get_db_connection()
    cur = conn.execute(sql)
    row = cur.fetchone()
    conn.close()
    
    result = row[0] if row[0] else 0
    return [TextContent(type="text", text=f"{agg.upper()}({field}) = {result}")]


async def get_orders_by_customer(args):
    group_by = args.get("group_by", "customer_id")
    order = args.get("order", "DESC")
    limit = args.get("limit", 10)
    
    if group_by == "customer_id":
        select_field = "c.customer_name"
    else:
        select_field = "c.region_id"
    
    sql = f"""
        SELECT {select_field} as grp, SUM(o.total_amount) as total, 
               AVG(o.total_amount) as avgAmt, COUNT(*) as cnt
        FROM orders o JOIN customers c ON o.customer_id = c.customer_id
        GROUP BY {select_field}
        ORDER BY total {order}
        LIMIT {limit}
    """
    
    conn = get_db_connection()
    cur = conn.execute(sql)
    rows = cur.fetchall()
    conn.close()
    
    result = [{"分组": r[0], "总额": round(r[1],2), "平均": round(r[2],2), "订单数": r[3]} for r in rows]
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]


async def get_orders_by_date_range(args):
    start = args.get("start_date")
    end = args.get("end_date")
    status = args.get("status")
    
    sql = """
        SELECT o.order_id, c.customer_name, o.total_amount, o.order_date, o.status
        FROM orders o JOIN customers c ON o.customer_id = c.customer_id
        WHERE o.order_date BETWEEN ? AND ?
    """
    params = [start, end]
    if status:
        sql += " AND o.status = ?"
        params.append(status)
    sql += " ORDER BY o.order_date DESC"
    
    conn = get_db_connection()
    cur = conn.execute(sql, params)
    rows = cur.fetchall()
    conn.close()
    
    result = [{"订单ID": r[0], "客户": r[1], "金额": r[2], "日期": r[3], "状态": r[4]} for r in rows]
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]


async def list_orders(args):
    status = args.get("status")
    customer_id = args.get("customer_id")
    limit = args.get("limit", 20)
    offset = args.get("offset", 0)
    
    sql = """
        SELECT o.order_id, c.customer_name, p.product_name, o.quantity, 
               o.total_amount, o.order_date, o.status
        FROM orders o
        JOIN customers c ON o.customer_id = c.customer_id
        JOIN products p ON o.product_id = p.product_id
        WHERE 1=1
    """
    params = []
    if status:
        sql += " AND o.status = ?"
        params.append(status)
    if customer_id:
        sql += " AND o.customer_id = ?"
        params.append(customer_id)
    
    sql += " ORDER BY o.order_date DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    conn = get_db_connection()
    cur = conn.execute(sql, params)
    rows = cur.fetchall()
    conn.close()
    
    result = [{"订单ID": r[0], "客户": r[1], "产品": r[2], "数量": r[3], "金额": r[4], "日期": r[5], "状态": r[6]} for r in rows]
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]


async def get_order_detail(args):
    order_id = args.get("order_id")
    
    sql = """
        SELECT o.*, c.customer_name, c.phone, p.product_name
        FROM orders o
        JOIN customers c ON o.customer_id = c.customer_id
        JOIN products p ON o.product_id = p.product_id
        WHERE o.order_id = ?
    """
    
    conn = get_db_connection()
    cur = conn.execute(sql, [order_id])
    row = cur.fetchone()
    conn.close()
    
    if not row:
        return [TextContent(type="text", text=f"未找到订单")]
    
    return [TextContent(type="text", text=json.dumps(dict_from_row(row), ensure_ascii=False))]


async def update_order_status(args):
    order_id = args.get("order_id")
    new_status = args.get("new_status")
    
    valid = ["待付款", "已付款", "已发货", "已完成", "已取消"]
    if new_status not in valid:
        return [TextContent(type="text", text=f"无效状态")]
    
    conn = get_db_connection()
    cur = conn.execute("UPDATE orders SET status = ? WHERE order_id = ?", [new_status, order_id])
    conn.commit()
    affected = cur.rowcount
    conn.close()
    
    if affected == 0:
        return [TextContent(type="text", text=f"未找到订单")]
    return [TextContent(type="text", text=f"✅ 已更新: {order_id} → {new_status}")]


async def get_customers(args):
    region_id = args.get("region_id")
    sql = "SELECT * FROM customers"
    params = []
    if region_id:
        sql += " WHERE region_id = ?"
        params.append(region_id)
    
    conn = get_db_connection()
    cur = conn.execute(sql, params)
    rows = cur.fetchall()
    conn.close()
    
    result = [dict_from_row(r) for r in rows]
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]


async def get_products(args):
    category = args.get("category")
    sql = "SELECT * FROM products"
    params = []
    if category:
        sql += " WHERE category = ?"
        params.append(category)

    conn = get_db_connection()
    cur = conn.execute(sql, params)
    rows = cur.fetchall()
    conn.close()

    result = [dict_from_row(r) for r in rows]
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]


async def generate_customer_chart(args):
    """生成客户订单统计图表（试验性功能）"""
    chart_type = args.get("chart_type", "bar")
    limit = args.get("limit", 10)

    # 1. 获取客户订单统计数据
    sql = """
        SELECT c.customer_name, SUM(o.total_amount) as total, COUNT(*) as cnt
        FROM orders o JOIN customers c ON o.customer_id = c.customer_id
        GROUP BY c.customer_name
        ORDER BY total DESC
        LIMIT ?
    """

    conn = get_db_connection()
    cur = conn.execute(sql, [limit])
    rows = cur.fetchall()
    conn.close()

    if not rows:
        return [TextContent(type="text", text="No data available for chart generation.")]

    # 2. 准备图表数据
    chart_data = []
    for row in rows:
        chart_data.append({
            "category": row[0],  # customer_name
            "value": float(row[1])  # total_amount
        })

    # 3. 调用 mcp-echarts 生成图表
    try:
        chart_id = str(uuid.uuid4())
        chart_file = CHARTS_DIR / f"{chart_id}.png"

        # 构建 mcp-echarts 输入（使用临时文件）
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            echarts_input = {
                "title": f"Top {limit} Customers by Order Amount",
                "axisXTitle": "Customer",
                "axisYTitle": "Total Amount",
                "data": chart_data,
                "width": 800,
                "height": 600,
                "theme": "default",
                "outputType": "png"
            }
            json.dump(echarts_input, f)
            input_file = f.name

        # 调用 mcp-echarts（使用 stdio 模式）
        tool_name = f"generate_{chart_type}_chart"

        # 创建 MCP 请求
        mcp_request = {
            "jsonrpc": "2.0",
            "id": "1",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": echarts_input
            }
        }

        print(f"📊 Calling mcp-echarts: {tool_name}", flush=True)
        print(f"📊 Input data: {chart_data[:3]}...", flush=True)

        result = subprocess.run(
            ["npx", "-y", "mcp-echarts"],
            input=json.dumps(mcp_request) + "\n",
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "NODE_ENV": "production"}
        )

        print(f"📊 Return code: {result.returncode}", flush=True)
        print(f"📊 Stdout length: {len(result.stdout)}", flush=True)
        print(f"📊 Stderr: {result.stderr[:200] if result.stderr else 'None'}", flush=True)

        # 清理临时文件
        try:
            os.unlink(input_file)
        except:
            pass

        if result.returncode != 0:
            return [TextContent(type="text", text=f"Chart generation failed (exit code {result.returncode}): {result.stderr[:500]}")]

        if not result.stdout.strip():
            return [TextContent(type="text", text=f"Chart generation failed: mcp-echarts returned empty output. Stderr: {result.stderr[:500]}")]

        # 解析返回的 base64 图片
        try:
            response = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            return [TextContent(type="text", text=f"Failed to parse mcp-echarts response: {str(e)}. Output: {result.stdout[:200]}")]

        if "result" in response and "content" in response["result"]:
            base64_data = response["result"]["content"][0]["text"]
            # 移除 data:image/png;base64, 前缀
            if "base64," in base64_data:
                base64_data = base64_data.split("base64,")[1]

            # 保存图片
            import base64
            chart_file.write_bytes(base64.b64decode(base64_data))

            # 返回图表 URL
            chart_url = f"https://newkuhne-dockversion.onrender.com/charts/{chart_id}.png"
            return [TextContent(
                type="text",
                text=f"📊 Chart generated successfully!\n\nView chart: {chart_url}\n\nData summary:\n" +
                     "\n".join([f"- {d['category']}: ${d['value']:,.2f}" for d in chart_data[:5]])
            )]
        else:
            return [TextContent(type="text", text=f"Unexpected response from mcp-echarts: {json.dumps(response)[:500]}")]

    except subprocess.TimeoutExpired:
        return [TextContent(type="text", text="Chart generation timed out. Please try again.")]
    except Exception as e:
        import traceback
        return [TextContent(type="text", text=f"Chart generation error: {str(e)}\n\nTraceback: {traceback.format_exc()[:500]}")]


# ============ FastAPI App ============
# 禁用默认的 OpenAPI，使用自定义的
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


@app.on_event("startup")
async def startup():
    init_database()  # 启动时初始化数据库
    print("✅ MCP Server 初始化完成", flush=True)


# 静态文件服务（用于图表）
app.mount("/charts", StaticFiles(directory=str(CHARTS_DIR)), name="charts")


@app.get("/sse")
async def sse_endpoint(request: Request):
    async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
        await mcp.run(streams[0], streams[1], mcp.create_initialization_options())


@app.post("/messages")
async def messages(request: Request):
    try:
        body = await request.body()
        print(f"Received message: {body}", flush=True)
        await sse.handle_post_message(request.scope, request.receive, request._send, body)
        return Response(status_code=202)
    except Exception as e:
        print(f"Error handling message: {e}", flush=True)
        return Response(status_code=500, content=str(e))


@app.get("/")
async def root_get():
    return {"status": "SQLite MCP Server running", "tools": 9, "features": ["data_query", "chart_generation"]}


@app.post("/")
async def root_post(request: Request):
    """处理 Copilot Studio 的 POST 请求（根路径）"""
    try:
        body = await request.json()
        print(f"Root POST: {body}", flush=True)
        
        # 处理 initialize 请求
        if body.get("method") == "initialize":
            print(f"✅ Initialize request from: {body.get('params', {}).get('clientInfo', {})}", flush=True)
            response = {
                "jsonrpc": "2.0",
                "id": body.get("id"),
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": "sqlite-orders-mcp", "version": "1.0.0"},
                    "capabilities": {
                        "tools": {"listChanged": True}
                    }
                }
            }
            print(f"📤 Initialize response: {response}", flush=True)
            return response
        
        # 处理 tools/list 请求
        if body.get("method") == "tools/list":
            print("📋 Received tools/list request", flush=True)
            tools = await list_tools()
            response = {
                "jsonrpc": "2.0",
                "id": body.get("id"),
                "result": {"tools": [tool.model_dump() for tool in tools]}
            }
            print(f"📤 Returning {len(tools)} tools", flush=True)
            return response
        
        # 处理 tools/call 请求
        if body.get("method") == "tools/call":
            params = body.get("params", {})
            result = await call_tool(params.get("name"), params.get("arguments", {}))
            return {
                "jsonrpc": "2.0",
                "id": body.get("id"),
                "result": {"content": [r.model_dump() for r in result]}
            }

        # 处理 notifications/initialized（关键：必须返回空的 JSON-RPC 响应）
        if body.get("method") == "notifications/initialized":
            print("✅ Received notifications/initialized", flush=True)
            return {"jsonrpc": "2.0"}

        return {"jsonrpc": "2.0", "id": body.get("id"), "error": {"code": -32601, "message": "Method not found"}}
    except Exception as e:
        print(f"Error: {e}", flush=True)
        return {"jsonrpc": "2.0", "id": body.get("id", 0), "error": {"code": -32603, "message": str(e)}}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/tools/{tool_name}")
async def call_tool_rest(tool_name: str, request: Request):
    """REST API 端点：供 Copilot Studio 通过 OpenAPI 调用工具"""
    try:
        body = await request.json()
        print(f"REST tool call: {tool_name} with args: {body}", flush=True)

        # 调用 MCP 工具处理函数
        result = await call_tool(tool_name, body)

        # 返回结果（提取文本内容）
        return {
            "success": True,
            "result": [r.text for r in result]
        }
    except Exception as e:
        print(f"Error in REST tool call: {e}", flush=True)
        return {
            "success": False,
            "error": str(e)
        }


@app.get("/openapi.json")
async def openapi_json():
    """OpenAPI JSON 规范（供 Copilot Studio 发现工具）"""
    return {
        "openapi": "3.0.0",
        "info": {
            "title": "Sales Order MCP Server",
            "description": "SQLite-based sales order management API",
            "version": "1.0.0"
        },
        "servers": [
            {"url": f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME', 'newkuhne.onrender.com')}"}
        ],
        "paths": {
            f"/tools/{t['name']}": {
                "post": {
                    "summary": t["title"],
                    "description": t["description"],
                    "operationId": t["name"],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": t["inputSchema"]
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Successful response",
                            "content": {
                                "application/json": {
                                    "schema": {"type": "object"}
                                }
                            }
                        }
                    }
                }
            }
            for t in TOOLS_DEF
        }
    }


def dict_to_yaml(d, indent=0):
    """简单地将 dict 转为 YAML 字符串"""
    lines = []
    prefix = "  " * indent
    
    if isinstance(d, dict):
        for k, v in d.items():
            if isinstance(v, dict):
                lines.append(f"{prefix}{k}:")
                lines.append(dict_to_yaml(v, indent + 1))
            elif isinstance(v, list):
                lines.append(f"{prefix}{k}:")
                for item in v:
                    if isinstance(item, dict):
                        lines.append(f"{prefix}- {list(item.keys())[0]}: {list(item.values())[0]}" if len(item) == 1 else f"{prefix}-")
                        if len(item) > 1:
                            for sub_k, sub_v in list(item.items())[1:]:
                                lines.append(f"{prefix}  {sub_k}: {sub_v}")
                    else:
                        lines.append(f"{prefix}- {item}")
            else:
                lines.append(f"{prefix}{k}: {v}")
    return "\n".join(lines)


@app.get("/openapi.yaml")
async def openapi_yaml():
    """OpenAPI YAML 规范（供 Copilot Studio 发现工具）"""
    host = os.getenv('RENDER_EXTERNAL_HOSTNAME', 'newkuhne.onrender.com')
    
    yaml_lines = [
        "openapi: 3.0.0",
        "info:",
        "  title: Sales Order MCP Server",
        "  description: SQLite-based sales order management API",
        "  version: 1.0.0",
        "servers:",
        f"  - url: https://{host}",
        "paths:"
    ]
    
    for t in TOOLS_DEF:
        yaml_lines.append(f"  /tools/{t['name']}:")
        yaml_lines.append(f"    post:")
        yaml_lines.append(f"      summary: {t['title']}")
        yaml_lines.append(f"      description: {t['description']}")
        yaml_lines.append(f"      operationId: {t['name']}")
        yaml_lines.append(f"      requestBody:")
        yaml_lines.append(f"        required: true")
        yaml_lines.append(f"        content:")
        yaml_lines.append(f"          application/json:")
        yaml_lines.append(f"            schema:")
        yaml_lines.append(f"              type: object")
        if "properties" in t.get("inputSchema", {}):
            yaml_lines.append(f"              properties:")
            for prop_name, prop_schema in t["inputSchema"]["properties"].items():
                yaml_lines.append(f"                {prop_name}:")
                for k, v in prop_schema.items():
                    if isinstance(v, list):
                        yaml_lines.append(f"                  {k}:")
                        for item in v:
                            yaml_lines.append(f"                    - {item}")
                    else:
                        yaml_lines.append(f"                  {k}: {v}")
        yaml_lines.append(f"      responses:")
        yaml_lines.append(f"        '200':")
        yaml_lines.append(f"          description: Successful response")
    
    return Response(
        content="\n".join(yaml_lines),
        media_type="application/yaml"
    )


if __name__ == "__main__":
    print("🚀 SQLite MCP Server (HTTP/SSE) 启动中...")
    print(f"📁 数据库: {DB_PATH}")
    print(f"🌐 访问: http://localhost:{PORT}/")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
