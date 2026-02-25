#!/usr/bin/env python3
"""
SQLite MCP Server - 使用官方 MCP SDK
"""

import asyncio
import json
import sqlite3
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# ============ 配置 ============
DB_PATH = "/Users/lijia/Desktop/Agents26/kuhne/orders.db"


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def dict_from_row(row):
    if row is None:
        return None
    return dict(zip(row.keys(), row))


# ============ 创建 Server ============
app = Server("sqlite-orders-mcp")


# ============ 列出工具 ============
@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="get_order_summary",
            description="获取订单汇总（总数/总和/平均/最大/最小）",
            inputSchema={
                "type": "object",
                "properties": {
                    "aggregate": {"type": "string", "enum": ["sum", "avg", "count", "min", "max"], "description": "聚合类型"},
                    "field": {"type": "string", "description": "字段名：total_amount, quantity"},
                    "condition": {"type": "string", "description": "可选筛选条件"}
                },
                "required": ["aggregate", "field"]
            }
        ),
        Tool(
            name="get_orders_by_customer",
            description="按客户分组统计订单",
            inputSchema={
                "type": "object",
                "properties": {
                    "group_by": {"type": "string", "enum": ["customer_id", "region_id"], "description": "分组字段"},
                    "order": {"type": "string", "enum": ["ASC", "DESC"], "default": "DESC"},
                    "limit": {"type": "integer", "default": 10}
                },
                "required": ["group_by"]
            }
        ),
        Tool(
            name="get_orders_by_date_range",
            description="按日期范围查询订单",
            inputSchema={
                "type": "object",
                "properties": {
                    "start_date": {"type": "string", "description": "开始日期 YYYY-MM-DD"},
                    "end_date": {"type": "string", "description": "结束日期 YYYY-MM-DD"},
                    "status": {"type": "string", "description": "可选状态筛选"}
                },
                "required": ["start_date", "end_date"]
            }
        ),
        Tool(
            name="list_orders",
            description="列出订单列表（支持分页、筛选、排序）",
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {"type": "string", "description": "状态筛选"},
                    "customer_id": {"type": "string", "description": "客户ID筛选"},
                    "limit": {"type": "integer", "default": 20},
                    "offset": {"type": "integer", "default": 0},
                    "order_by": {"type": "string", "default": "order_date DESC"}
                }
            }
        ),
        Tool(
            name="get_order_detail",
            description="查询单个订单详情",
            inputSchema={
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "订单ID"}
                },
                "required": ["order_id"]
            }
        ),
        Tool(
            name="update_order_status",
            description="更新订单状态",
            inputSchema={
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "订单ID"},
                    "new_status": {"type": "string", "description": "新状态"}
                },
                "required": ["order_id", "new_status"]
            }
        ),
        Tool(
            name="get_customers",
            description="获取客户列表",
            inputSchema={
                "type": "object",
                "properties": {
                    "region_id": {"type": "string", "description": "地区筛选"}
                }
            }
        ),
        Tool(
            name="get_products",
            description="获取产品列表",
            inputSchema={
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "分类筛选"}
                }
            }
        ),
    ]


# ============ 工具实现 ============
@app.call_tool()
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
        else:
            return [TextContent(type="text", text=f"未知工具: {name}")]
    except Exception as e:
        return [TextContent(type="text", text=f"错误: {str(e)}")]


async def get_order_summary(args) -> list[TextContent]:
    agg = args.get("aggregate", "sum")
    field = args.get("field", "total_amount")
    condition = args.get("condition", "")
    
    valid_fields = ["total_amount", "quantity"]
    if field not in valid_fields:
        return [TextContent(type="text", text=f"无效字段: {field}")]
    
    sql = f"SELECT {agg}({field}) as result FROM orders"
    if condition:
        sql += f" WHERE {condition}"
    
    conn = get_db_connection()
    cur = conn.execute(sql)
    row = cur.fetchone()
    conn.close()
    
    result = row[0] if row[0] else 0
    return [TextContent(type="text", text=f"{agg.upper()}({field}) = {result}")]


async def get_orders_by_customer(args) -> list[TextContent]:
    group_by = args.get("group_by", "customer_id")
    order = args.get("order", "DESC")
    limit = args.get("limit", 10)
    
    if group_by == "customer_id":
        select_field = "c.customer_name"
        from_join = "JOIN customers c ON o.customer_id = c.customer_id"
    else:
        select_field = "c.region_id"
        from_join = "JOIN customers c ON o.customer_id = c.customer_id"
    
    sql = f"""
        SELECT {select_field} as grp, SUM(o.total_amount) as total, 
               AVG(o.total_amount) as avgAmt, COUNT(*) as cnt
        FROM orders o {from_join}
        GROUP BY {select_field}
        ORDER BY total {order}
        LIMIT {limit}
    """
    
    conn = get_db_connection()
    cur = conn.execute(sql)
    rows = cur.fetchall()
    conn.close()
    
    result = [{"客户/地区": r[0], "总额": round(r[1],2), "平均": round(r[2],2), "订单数": r[3]} for r in rows]
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]


async def get_orders_by_date_range(args) -> list[TextContent]:
    start = args.get("start_date")
    end = args.get("end_date")
    status = args.get("status")
    
    sql = """
        SELECT o.order_id, c.customer_name, o.total_amount, o.order_date, o.status
        FROM orders o
        JOIN customers c ON o.customer_id = c.customer_id
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
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]


async def list_orders(args) -> list[TextContent]:
    status = args.get("status")
    customer_id = args.get("customer_id")
    limit = args.get("limit", 20)
    offset = args.get("offset", 0)
    order_by = args.get("order_by", "order_date DESC")
    
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
    
    sql += f" ORDER BY {order_by} LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    conn = get_db_connection()
    cur = conn.execute(sql, params)
    rows = cur.fetchall()
    conn.close()
    
    result = [{"订单ID": r[0], "客户": r[1], "产品": r[2], "数量": r[3], "金额": r[4], "日期": r[5], "状态": r[6]} for r in rows]
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]


async def get_order_detail(args) -> list[TextContent]:
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
        return [TextContent(type="text", text=f"未找到订单: {order_id}")]
    
    return [TextContent(type="text", text=json.dumps(dict_from_row(row), ensure_ascii=False, indent=2))]


async def update_order_status(args) -> list[TextContent]:
    order_id = args.get("order_id")
    new_status = args.get("new_status")
    
    valid = ["待付款", "已付款", "已发货", "已完成", "已取消"]
    if new_status not in valid:
        return [TextContent(type="text", text=f"无效状态: {valid}")]
    
    conn = get_db_connection()
    cur = conn.execute("UPDATE orders SET status = ? WHERE order_id = ?", [new_status, order_id])
    conn.commit()
    affected = cur.rowcount
    conn.close()
    
    if affected == 0:
        return [TextContent(type="text", text=f"未找到订单: {order_id}")]
    return [TextContent(type="text", text=f"✅ 订单 {order_id} → {new_status}")]


async def get_customers(args) -> list[TextContent]:
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
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]


async def get_products(args) -> list[TextContent]:
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
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]


# ============ 启动 ============
async def main():
    print("🚀 SQLite MCP Server 启动中...", flush=True)
    print(f"📁 数据库: {DB_PATH}", flush=True)
    
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
