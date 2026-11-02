"""
Local SQLite / SQL Data Quality & Medallion Architecture Test Suite
Validates:
1. Bronze -> Silver deduplication via ROW_NUMBER() window logic
2. Primary Key uniqueness in Silver and Gold tables
3. Referential integrity between fact_orders and dim_customers
4. Domain rules (non-negative delivery times, valid status normalization)
5. Star Schema aggregation consistency (agg_daily_sales_performance)
"""

import sqlite3
import pytest


@pytest.fixture
def medallion_db():
    """Creates an in-memory relational database simulating Bronze, Silver, and Gold layers."""
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()

    # 1. Bronze Layer: Raw ingested orders (includes duplicates, whitespace, mixed case, nulls)
    cur.execute("""
        CREATE TABLE raw_orders (
            order_id TEXT,
            customer_id TEXT,
            order_status TEXT,
            order_purchase_timestamp TEXT,
            order_delivered_customer_date TEXT,
            order_estimated_delivery_date TEXT
        )
    """)

    raw_rows = [
        # Duplicate order_id 'ord_001' with different timestamps (latest should win)
        (" ord_001 ", "cust_A", " DELIVERED ", "2026-01-10 10:00:00", "2026-01-15 14:00:00", "2026-01-18 00:00:00"),
        ("ord_001", "cust_A", "SHIPPED", "2026-01-09 08:00:00", None, "2026-01-18 00:00:00"),
        # Delayed delivery order 'ord_002'
        ("ord_002", "cust_B", "delivered", "2026-01-10 12:00:00", "2026-01-25 18:00:00", "2026-01-20 00:00:00"),
        # Canceled order 'ord_003'
        ("ord_003", "cust_C", "CANCELED", "2026-01-11 09:30:00", None, "2026-01-22 00:00:00"),
        # Null order_id row (should be filtered out in Silver)
        (None, "cust_D", "delivered", "2026-01-11 11:00:00", "2026-01-14 10:00:00", "2026-01-16 00:00:00"),
    ]
    cur.executemany("INSERT INTO raw_orders VALUES (?, ?, ?, ?, ?, ?)", raw_rows)

    # Dimension table for customers
    cur.execute("""
        CREATE TABLE dim_customers (
            customer_id TEXT PRIMARY KEY,
            customer_state TEXT
        )
    """)
    cur.executemany("INSERT INTO dim_customers VALUES (?, ?)", [
        ("cust_A", "SP"),
        ("cust_B", "MG"),
        ("cust_C", "RJ"),
    ])

    # 2. Silver Layer: Deduplication, trimming, lowercasing, and date diff calculation
    cur.execute("""
        CREATE TABLE stg_orders AS
        WITH ranked_orders AS (
            SELECT
                TRIM(order_id) AS order_id,
                TRIM(customer_id) AS customer_id,
                LOWER(TRIM(order_status)) AS order_status,
                order_purchase_timestamp,
                order_delivered_customer_date,
                order_estimated_delivery_date,
                ROW_NUMBER() OVER (
                    PARTITION BY TRIM(order_id)
                    ORDER BY order_purchase_timestamp DESC
                ) AS rn
            FROM raw_orders
            WHERE order_id IS NOT NULL
        )
        SELECT
            order_id,
            customer_id,
            order_status,
            order_purchase_timestamp,
            order_delivered_customer_date,
            order_estimated_delivery_date,
            CAST(julianday(date(order_delivered_customer_date)) - julianday(date(order_purchase_timestamp)) AS INTEGER) AS delivery_time_days,
            CAST(julianday(date(order_delivered_customer_date)) - julianday(date(order_estimated_delivery_date)) AS INTEGER) AS delay_vs_estimate_days
        FROM ranked_orders
        WHERE rn = 1
    """)

    # 3. Gold Layer: Fact Orders & Daily Aggregations
    cur.execute("""
        CREATE TABLE fct_orders AS
        SELECT
            order_id,
            customer_id,
            order_status,
            order_purchase_timestamp,
            order_delivered_customer_date,
            order_estimated_delivery_date,
            delivery_time_days,
            delay_vs_estimate_days,
            CASE WHEN delay_vs_estimate_days > 0 THEN 1 ELSE 0 END AS is_delivery_delayed
        FROM stg_orders
    """)

    cur.execute("""
        CREATE TABLE agg_daily_sales_performance AS
        SELECT
            date(order_purchase_timestamp) AS sale_date,
            COUNT(DISTINCT order_id) AS total_orders,
            COUNT(DISTINCT CASE WHEN order_status = 'delivered' THEN order_id END) AS delivered_orders,
            COUNT(DISTINCT CASE WHEN delay_vs_estimate_days > 0 THEN order_id END) AS delayed_orders,
            ROUND(AVG(delivery_time_days), 2) AS avg_delivery_time_days
        FROM fct_orders
        GROUP BY date(order_purchase_timestamp)
    """)

    conn.commit()
    yield conn
    conn.close()


def test_silver_deduplication_and_null_filtering(medallion_db):
    cur = medallion_db.cursor()
    cur.execute("SELECT COUNT(*), COUNT(DISTINCT order_id) FROM stg_orders")
    total, distinct_ids = cur.fetchone()
    # 5 raw rows -> 1 null filtered, 1 duplicate removed -> 3 unique valid orders
    assert total == 3
    assert total == distinct_ids


def test_silver_string_normalization(medallion_db):
    cur = medallion_db.cursor()
    cur.execute("SELECT order_status FROM stg_orders WHERE order_id = 'ord_001'")
    status = cur.fetchone()[0]
    assert status == "delivered"


def test_referential_integrity_fact_to_dim(medallion_db):
    cur = medallion_db.cursor()
    cur.execute("""
        SELECT COUNT(*)
        FROM fct_orders f
        LEFT JOIN dim_customers d ON f.customer_id = d.customer_id
        WHERE d.customer_id IS NULL
    """)
    orphan_records = cur.fetchone()[0]
    assert orphan_records == 0


def test_gold_sla_delay_calculation(medallion_db):
    cur = medallion_db.cursor()
    # ord_001 delivered 2026-01-15 vs estimated 2026-01-18 (-3 days, not delayed)
    cur.execute("SELECT delivery_time_days, delay_vs_estimate_days, is_delivery_delayed FROM fct_orders WHERE order_id = 'ord_001'")
    deliv_days, delay_days, is_delayed = cur.fetchone()
    assert deliv_days == 5
    assert delay_days == -3
    assert is_delayed == 0

    # ord_002 delivered 2026-01-25 vs estimated 2026-01-20 (+5 days, delayed)
    cur.execute("SELECT delivery_time_days, delay_vs_estimate_days, is_delivery_delayed FROM fct_orders WHERE order_id = 'ord_002'")
    deliv_days_2, delay_days_2, is_delayed_2 = cur.fetchone()
    assert deliv_days_2 == 15
    assert delay_days_2 == 5
    assert is_delayed_2 == 1


def test_gold_daily_aggregation_consistency(medallion_db):
    cur = medallion_db.cursor()
    cur.execute("SELECT total_orders, delivered_orders, delayed_orders, avg_delivery_time_days FROM agg_daily_sales_performance WHERE sale_date = '2026-01-10'")
    total, delivered, delayed, avg_days = cur.fetchone()
    assert total == 2
    assert delivered == 2
    assert delayed == 1
    assert avg_days == 10.0  # (5 + 15) / 2

