-- =====================================================================
-- LOOKER STUDIO VIEWS: CONSUMO ANALÍTICO DE ALTA PERFORMANCE
-- Otimizado para dashboards executivos sem varredura excessiva de dados
-- =====================================================================

-- 1. View Executiva: KPIs Diários de Eficiência Logística
CREATE OR REPLACE VIEW `ecommerce_gold.vw_looker_daily_kpis` AS
SELECT
    sale_date,
    total_orders,
    delivered_orders,
    delayed_orders,
    avg_delivery_time_days,
    delayed_orders_rate_pct,
    -- Indicador de Saúde Operacional (SLA de 90% sem atraso)
    CASE 
        WHEN delayed_orders_rate_pct <= 10.0 THEN 'Excelente (Dentro do SLA)'
        WHEN delayed_orders_rate_pct <= 15.0 THEN 'Atenção'
        ELSE 'Crítico (Fora do SLA)'
    END AS sla_status
FROM `ecommerce_gold.agg_daily_sales_performance`;

-- 2. View Geográfica: Performance de Entrega por Região/Estado
CREATE OR REPLACE VIEW `ecommerce_gold.vw_looker_regional_performance` AS
SELECT
    DATE_TRUNC(DATE(o.order_purchase_timestamp), MONTH) AS purchase_month,
    o.order_status,
    COUNT(DISTINCT o.order_id) AS total_orders,
    COUNT(DISTINCT CASE WHEN o.delay_vs_estimate_days > 0 THEN o.order_id END) AS delayed_orders,
    ROUND(AVG(o.delivery_time_days), 1) AS avg_delivery_days,
    ROUND(AVG(o.delay_vs_estimate_days), 1) AS avg_delay_days,
    ROUND(
        SAFE_DIVIDE(
            COUNT(DISTINCT CASE WHEN o.delay_vs_estimate_days > 0 THEN o.order_id END) * 100.0,
            COUNT(DISTINCT o.order_id)
        ), 2
    ) AS delay_rate_pct
FROM `ecommerce_gold.fct_orders` o
GROUP BY purchase_month, o.order_status;
