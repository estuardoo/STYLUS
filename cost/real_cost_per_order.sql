-- Costo REAL por pedido (cierra el ciclo de la calculadora con la factura). Ejecutar: python ops.py costo-real
-- Prerrequisito (una vez, en consola): Facturación > Exportación de facturación > BigQuery (detallado) hacia
-- el dataset de operación, y copiar el nombre de la tabla en el Excel (billing_export_table).
CREATE OR REPLACE VIEW `${PROJECT}.${DS_OPS}.v_costo_real_mensual` AS
WITH costo AS (
  SELECT FORMAT_DATE('%Y-%m', DATE(usage_start_time)) AS mes,
         service.description AS servicio,
         SUM(cost) + SUM(IFNULL((SELECT SUM(c.amount) FROM UNNEST(credits) c), 0)) AS usd_neto
  FROM `${PROJECT}.${DS_OPS}.${BILLING_TABLE}`
  WHERE project.id = '${PROJECT}'
  GROUP BY 1, 2
),
pedidos AS (
  SELECT FORMAT_DATE('%Y-%m', order_date) AS mes, COUNT(DISTINCT order_id) AS pedidos
  FROM `${PROJECT}.${DS_GOLD}.fact_orders`
  WHERE is_synthetic  -- pedidos procesados por la plataforma (replay y web), no el histórico
  GROUP BY 1
)
SELECT c.mes, c.servicio, c.usd_neto,
       SUM(c.usd_neto) OVER (PARTITION BY c.mes) AS usd_total_mes,
       p.pedidos,
       SAFE_DIVIDE(SUM(c.usd_neto) OVER (PARTITION BY c.mes), p.pedidos) AS usd_por_pedido
FROM costo c LEFT JOIN pedidos p USING (mes);
