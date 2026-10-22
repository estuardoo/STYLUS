-- Vistas para Looker Studio (tablero gerencial y operativo). Variables: ${PROJECT}
CREATE OR REPLACE VIEW `${PROJECT}.retail_gold.v_ventas_mensuales` AS
SELECT d.anio_mes, c.canal, o.source, o.is_synthetic,
       COUNT(*) AS pedidos, SUM(o.unidades) AS unidades, SUM(o.importe) AS importe,
       SAFE_DIVIDE(SUM(o.importe), COUNT(*)) AS ticket_medio
FROM `${PROJECT}.retail_gold.fact_orders` o
JOIN `${PROJECT}.retail_gold.dim_date` d ON d.date_key = o.order_date
LEFT JOIN `${PROJECT}.retail_gold.dim_channel` c USING (sales_channel_id)
GROUP BY 1, 2, 3, 4;

CREATE OR REPLACE VIEW `${PROJECT}.retail_gold.v_top_articulos` AS
SELECT d.anio_mes, a.index_group_name, a.product_type_name, a.prod_name, s.article_id,
       COUNT(*) AS lineas, SUM(s.price * s.qty) AS importe
FROM `${PROJECT}.retail_gold.fact_sales` s
JOIN `${PROJECT}.retail_gold.dim_article` a USING (article_id)
JOIN `${PROJECT}.retail_gold.dim_date` d ON d.date_key = s.sale_date
GROUP BY 1, 2, 3, 4, 5;

CREATE OR REPLACE VIEW `${PROJECT}.retail_gold.v_recurrencia_clientes` AS
SELECT c.age_band, COUNT(DISTINCT o.customer_id) AS clientes, COUNT(*) AS pedidos,
       SAFE_DIVIDE(COUNT(*), COUNT(DISTINCT o.customer_id)) AS pedidos_por_cliente
FROM `${PROJECT}.retail_gold.fact_orders` o
LEFT JOIN `${PROJECT}.retail_gold.dim_customer` c USING (customer_id)
WHERE o.source = 'hm_hist'
GROUP BY 1;

-- Operativo: volumen y latencia del streaming (publicación -> disponible en BigQuery)
CREATE OR REPLACE VIEW `${PROJECT}.retail_ops.v_stream_salud` AS
SELECT TIMESTAMP_TRUNC(publish_time, MINUTE) AS minuto, source_system,
       COUNT(*) AS eventos, COUNT(DISTINCT event_id) AS eventos_unicos,
       COUNT(*) - COUNT(DISTINCT event_id) AS duplicados
FROM (SELECT publish_time, JSON_VALUE(data, '$.event_id') AS event_id, JSON_VALUE(data, '$.source_system') AS source_system
      FROM `${PROJECT}.retail_bronze.events_raw`)
GROUP BY 1, 2;
