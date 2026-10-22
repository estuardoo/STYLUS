-- Costo REAL por pedido (cierra el ciclo de la calculadora con la factura).
-- Prerrequisito (una vez, en consola): Billing > Billing export > BigQuery export (detallado)
-- hacia el dataset retail_ops. Reemplazar ${PROJECT} y ${BILLING_TABLE}
-- (ej. gcp_billing_export_resource_v1_XXXXXX_XXXXXX_XXXXXX).
CREATE OR REPLACE VIEW `${PROJECT}.retail_ops.v_costo_real_mensual` AS
WITH costo AS (
  SELECT FORMAT_DATE('%Y-%m', DATE(usage_start_time)) AS mes,
         service.description AS servicio,
         SUM(cost) + SUM(IFNULL((SELECT SUM(c.amount) FROM UNNEST(credits) c), 0)) AS usd_neto
  FROM `${PROJECT}.retail_ops.${BILLING_TABLE}`
  WHERE project.id = '${PROJECT}'
  GROUP BY 1, 2
),
pedidos AS (  -- pedidos simulados/reales procesados por la plataforma (capa gold, Entrega 2)
  SELECT FORMAT_DATE('%Y-%m', DATE(event_time)) AS mes, COUNT(DISTINCT order_id) AS pedidos
  FROM `${PROJECT}.retail_gold.fact_orders`
  GROUP BY 1
)
SELECT c.mes, c.servicio, c.usd_neto,
       SUM(c.usd_neto) OVER (PARTITION BY c.mes) AS usd_total_mes,
       p.pedidos,
       SAFE_DIVIDE(SUM(c.usd_neto) OVER (PARTITION BY c.mes), p.pedidos) AS usd_por_pedido
FROM costo c LEFT JOIN pedidos p USING (mes);
