#!/usr/bin/env python3
"""
生成测试订单数据库 - 模拟真实销售场景
覆盖 ask.md 中所有查询需求
"""

import sqlite3
import random
from datetime import datetime, timedelta

DB_PATH = "/Users/lijia/Desktop/Agents26/kuhne/orders.db"

# 数据配置
CUSTOMERS = [
    ("C001", "阿里巴巴", "浙江杭州"),
    ("C002", "腾讯科技", "广东深圳"),
    ("C003", "字节跳动", "北京"),
    ("C004", "美团", "北京"),
    ("C005", "拼多多", "上海"),
    ("C006", "京东", "北京"),
    ("C007", "网易", "浙江杭州"),
    ("C008", "百度", "北京"),
    ("C009", "滴滴出行", "北京"),
    ("C010", "小米科技", "北京"),
    ("C011", "华为技术", "广东深圳"),
    ("C012", "大疆创新", "广东深圳"),
    ("C013", "宁德时代", "福建宁德"),
    ("C014", "比亚迪", "广东深圳"),
    ("C015", "蔚来汽车", "上海"),
]

PRODUCTS = [
    ("P001", "企业服务器", "硬件", 50000),
    ("P002", "云计算资源", "服务", 12000),
    ("P003", "企业路由器", "硬件", 8500),
    ("P004", "网络安全设备", "硬件", 15000),
    ("P005", "企业软件许可", "软件", 25000),
    ("P006", "IT咨询服务", "服务", 18000),
    ("P007", "数据存储服务", "服务", 8000),
    ("P008", "企业交换机", "硬件", 12000),
    ("P009", "云数据库服务", "服务", 9500),
    ("P010", "企业宽带", "服务", 3000),
]

REGIONS = [
    ("R001", "华东区", "杭州"),
    ("R002", "华南区", "深圳"),
    ("R003", "华北区", "北京"),
    ("R004", "西南区", "成都"),
    ("R005", "华中区", "武汉"),
]

STATUSES = ["待付款", "已付款", "已发货", "已完成", "已取消"]

def random_date(start_days=365, end_days=0):
    """生成随机日期"""
    days = random.randint(end_days, start_days)
    return (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

def create_tables(conn):
    """创建表结构"""
    cursor = conn.cursor()
    
    # 地区表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS regions (
            region_id TEXT PRIMARY KEY,
            region_name TEXT NOT NULL,
            city TEXT NOT NULL
        )
    """)
    
    # 客户表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            customer_id TEXT PRIMARY KEY,
            customer_name TEXT NOT NULL,
            region_id TEXT,
            contact TEXT,
            phone TEXT,
            FOREIGN KEY (region_id) REFERENCES regions(region_id)
        )
    """)
    
    # 产品表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            product_id TEXT PRIMARY KEY,
            product_name TEXT NOT NULL,
            category TEXT,
            unit_price REAL NOT NULL
        )
    """)
    
    # 订单表 - 核心表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
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
        )
    """)
    
    print("✅ 表结构创建完成")

def insert_data(conn):
    """插入测试数据"""
    cursor = conn.cursor()
    
    # 插入地区
    for r in REGIONS:
        cursor.execute("INSERT OR IGNORE INTO regions VALUES (?, ?, ?)", r)
    
    # 插入客户
    for c in CUSTOMERS:
        region_id = random.choice(REGIONS)[0]
        cursor.execute(
            "INSERT OR IGNORE INTO customers VALUES (?, ?, ?, ?, ?)",
            (c[0], c[1], region_id, f"联系人{c[0]}", f"1380000{random.randint(1000, 9999)}")
        )
    
    # 插入产品
    for p in PRODUCTS:
        cursor.execute(
            "INSERT OR IGNORE INTO products VALUES (?, ?, ?, ?)",
            (p[0], p[1], p[2], p[3])
        )
    
    # 生成 200 条订单（覆盖过去 1 年）
    orders = []
    for i in range(200):
        order_id = f"OR{2025}{i+1:04d}"
        customer = random.choice(CUSTOMERS)
        product = random.choice(PRODUCTS)
        quantity = random.randint(1, 20)
        unit_price = product[3]
        total = quantity * unit_price * random.uniform(0.8, 1.2)  # 浮动价格
        
        # 状态分布：大部分已完成，少量进行中
        if random.random() < 0.7:
            status = random.choice(["已完成", "已发货"])
        else:
            status = random.choice(STATUSES)
        
        order_date = random_date(365, 1)
        
        orders.append((
            order_id, customer[0], product[0], quantity, round(unit_price, 2),
            round(total, 2), order_date, status,
            f"{customer[2]}市XX路XX号", f"订单备注{i}"
        ))
    
    cursor.executemany("""
        INSERT OR IGNORE INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, orders)
    
    conn.commit()
    print(f"✅ 插入 {len(orders)} 条订单测试数据")

def verify_data(conn):
    """验证数据"""
    cursor = conn.cursor()
    
    print("\n📊 数据统计:")
    cursor.execute("SELECT COUNT(*) FROM orders")
    print(f"   订单总数: {cursor.fetchone()[0]}")
    
    cursor.execute("SELECT COUNT(*) FROM customers")
    print(f"   客户数量: {cursor.fetchone()[0]}")
    
    cursor.execute("SELECT COUNT(*) FROM products")
    print(f"   产品数量: {cursor.fetchone()[0]}")
    
    print("\n📅 订单日期范围:")
    cursor.execute("SELECT MIN(order_date), MAX(order_date) FROM orders")
    min_date, max_date = cursor.fetchone()
    print(f"   {min_date} ~ {max_date}")
    
    print("\n💰 订单金额统计:")
    cursor.execute("SELECT SUM(total_amount), AVG(total_amount) FROM orders")
    total, avg = cursor.fetchone()
    print(f"   总金额: {total:,.2f}")
    print(f"   平均金额: {avg:,.2f}")
    
    print("\n📌 状态分布:")
    cursor.execute("SELECT status, COUNT(*) FROM orders GROUP BY status")
    for row in cursor.fetchall():
        print(f"   {row[0]}: {row[1]}")

def main():
    import os
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    # 删除旧文件（确保干净）
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    
    conn = sqlite3.connect(DB_PATH)
    
    create_tables(conn)
    insert_data(conn)
    verify_data(conn)
    
    conn.close()
    print(f"\n🎉 数据库创建完成: {DB_PATH}")

if __name__ == "__main__":
    main()
