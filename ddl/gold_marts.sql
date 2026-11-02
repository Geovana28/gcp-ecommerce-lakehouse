-- =====================================================================
-- CAMADA GOLD: MODELAGEM DIMENSIONAL (STAR SCHEMA) & MÉTRICAS
-- Objetivo: Alimentar Dashboards e consultas analíticas de alto nível
-- =====================================================================

-- 1. Fato de Pedidos e Entregas (Fct_Orders)
CREATE OR REPLACE TABLE `ecommerce_gold.fct_orders`
PARTITION BY DATE(order_purchase_timestamp)
CLUSTER BY order_status
AS
SELECT
    order_id,
    customer_id,
    order_status,
    order_purchase_timestamp,
    order_delivered_customer_date,
    order_estimated_delivery_date,
    delivery_time_days,
    delay_vs_estimate_days,
    CASE 
        WHEN delay_vs_estimate_days > 0 THEN TRUE 
        ELSE FALSE 
    END AS is_delivery_delayed
FROM `ecommerce_silver.stg_orders`;

-- 2. Tabela Agregada Diária para Dashboard de Performance Operacional
CREATE OR REPLACE TABLE `ecommerce_gold.agg_daily_sales_performance`
PARTITION BY sale_date
AS
SELECT
    DATE(order_purchase_timestamp) AS sale_date,
    COUNT(DISTINCT order_id) AS total_orders,
    COUNT(DISTINCT CASE WHEN order_status = 'delivered' THEN order_id END) AS delivered_orders,
    COUNT(DISTINCT CASE WHEN delay_vs_estimate_days > 0 THEN order_id END) AS delayed_orders,
    ROUND(AVG(delivery_time_days), 2) AS avg_delivery_time_days,
    ROUND(
        SAFE_DIVIDE(
            COUNT(DISTINCT CASE WHEN delay_vs_estimate_days > 0 THEN order_id END) * 100.0,
            COUNT(DISTINCT CASE WHEN order_status = 'delivered' THEN order_id END)
        ), 2
    ) AS delayed_orders_rate_pct
FROM `ecommerce_gold.fct_orders`
GROUP BY sale_date;
