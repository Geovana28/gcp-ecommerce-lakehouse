-- =====================================================================
-- CAMADA SILVER: STAGING & LIMPEZA DE DADOS
-- Objetivo: Tipagem estrita, deduplicação e tratamento de nulos
-- Particionamento por dia da compra para otimizar custos e consultas
-- =====================================================================

CREATE OR REPLACE TABLE `ecommerce_silver.stg_orders`
PARTITION BY DATE(order_purchase_timestamp)
CLUSTER BY order_status
AS
WITH ranked_orders AS (
    SELECT
        TRIM(order_id) AS order_id,
        TRIM(customer_id) AS customer_id,
        LOWER(TRIM(order_status)) AS order_status,
        PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%E*S', order_purchase_timestamp) AS order_purchase_timestamp,
        SAFE.PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%E*S', order_delivered_customer_date) AS order_delivered_customer_date,
        SAFE.PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%E*S', order_estimated_delivery_date) AS order_estimated_delivery_date,
        ROW_NUMBER() OVER (
            PARTITION BY order_id 
            ORDER BY order_purchase_timestamp DESC
        ) AS rn
    FROM `ecommerce_bronze.raw_orders`
    WHERE order_id IS NOT NULL
)
SELECT
    order_id,
    customer_id,
    order_status,
    order_purchase_timestamp,
    order_delivered_customer_date,
    order_estimated_delivery_date,
    -- Métricas de Logística (Calculadas em dias)
    DATE_DIFF(DATE(order_delivered_customer_date), DATE(order_purchase_timestamp), DAY) AS delivery_time_days,
    DATE_DIFF(DATE(order_delivered_customer_date), DATE(order_estimated_delivery_date), DAY) AS delay_vs_estimate_days
FROM ranked_orders
WHERE rn = 1;
