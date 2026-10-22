-- Gold: modelo estrella. Variables: ${PROJECT}, ${PRICE_DEMO_FACTOR}. Ejecutar: make bq-gold
-- Grano fact_sales = 1 línea de venta. Pedido = cliente + día + fuente (H&M no trae order_id).

CREATE OR REPLACE TABLE `${PROJECT}.retail_gold.dim_date` AS
SELECT d AS date_key, EXTRACT(YEAR FROM d) AS anio, EXTRACT(MONTH FROM d) AS mes,
       FORMAT_DATE('%Y-%m', d) AS anio_mes, EXTRACT(ISOWEEK FROM d) AS semana_iso,
       FORMAT_DATE('%A', d) AS dia_semana, EXTRACT(DAYOFWEEK FROM d) IN (1, 7) AS fin_de_semana
FROM UNNEST(GENERATE_DATE_ARRAY('2018-09-01', '2027-12-31')) AS d;

CREATE OR REPLACE TABLE `${PROJECT}.retail_gold.dim_channel` AS
SELECT * FROM UNNEST([
  STRUCT(1 AS sales_channel_id, 'Tienda física' AS canal, 'Supuesto: H&M no documenta los canales' AS nota),
  STRUCT(2, 'Online', 'Supuesto: H&M no documenta los canales')]);

CREATE OR REPLACE TABLE `${PROJECT}.retail_gold.dim_article` CLUSTER BY article_id AS
SELECT article_id, product_code, prod_name, product_type_name, product_group_name, colour_group_name,
       perceived_colour_master_name, department_name, index_name, index_group_name, section_name,
       garment_group_name, detail_desc
FROM `${PROJECT}.retail_silver.articles`;

CREATE OR REPLACE TABLE `${PROJECT}.retail_gold.dim_customer` CLUSTER BY customer_id AS
SELECT customer_id, age, age_band, club_member_status, fashion_news_frequency, fn, active
FROM `${PROJECT}.retail_silver.customers`;

CREATE OR REPLACE TABLE `${PROJECT}.retail_gold.fact_sales`
PARTITION BY sale_date CLUSTER BY customer_id, article_id AS
SELECT t_dat AS sale_date, customer_id, article_id, sales_channel_id, 1 AS qty, price,
       'hm_hist' AS source, FALSE AS is_synthetic, CAST(NULL AS STRING) AS order_id
FROM `${PROJECT}.retail_silver.transactions`
UNION ALL
SELECT DATE(event_time), customer_id, article_id, sales_channel_id, qty, price,
       source_system, is_synthetic, order_id
FROM `${PROJECT}.retail_silver.v_events`
WHERE event_type = 'purchase';

CREATE OR REPLACE TABLE `${PROJECT}.retail_gold.fact_orders`
PARTITION BY order_date CLUSTER BY customer_id AS
SELECT COALESCE(ANY_VALUE(order_id), TO_HEX(MD5(CONCAT(customer_id, CAST(sale_date AS STRING), source)))) AS order_id,
       sale_date AS order_date, customer_id, ANY_VALUE(sales_channel_id) AS sales_channel_id, source, is_synthetic,
       COUNT(*) AS lineas, SUM(qty) AS unidades, SUM(price * qty) AS importe
FROM `${PROJECT}.retail_gold.fact_sales`
GROUP BY sale_date, customer_id, source, is_synthetic, IFNULL(order_id, '');

-- Popularidad reciente por grupo (insumo del recomendador baseline)
CREATE OR REPLACE TABLE `${PROJECT}.retail_gold.reco_popular` AS
WITH ult AS (SELECT MAX(sale_date) AS d FROM `${PROJECT}.retail_gold.fact_sales` WHERE source = 'hm_hist')
SELECT a.index_group_name, s.article_id, COUNT(*) AS ventas_7d,
       RANK() OVER (PARTITION BY a.index_group_name ORDER BY COUNT(*) DESC) AS rank_grupo
FROM `${PROJECT}.retail_gold.fact_sales` s
JOIN `${PROJECT}.retail_gold.dim_article` a USING (article_id), ult
WHERE s.source = 'hm_hist' AND s.sale_date > DATE_SUB(ult.d, INTERVAL 7 DAY)
GROUP BY 1, 2;

-- Catálogo de servicio que copia api/load_catalog.py a Cloud SQL (precio demo declarado como sintético)
CREATE OR REPLACE VIEW `${PROJECT}.retail_gold.v_catalog_serving` AS
WITH ult AS (SELECT MAX(sale_date) AS d FROM `${PROJECT}.retail_gold.fact_sales` WHERE source = 'hm_hist'),
pop AS (
  SELECT article_id, COUNT(*) AS popularity, APPROX_QUANTILES(price, 2)[OFFSET(1)] AS p50
  FROM `${PROJECT}.retail_gold.fact_sales`, ult
  WHERE source = 'hm_hist' AND sale_date > DATE_SUB(ult.d, INTERVAL 28 DAY)
  GROUP BY article_id),
tipo AS (
  SELECT a.product_type_name, APPROX_QUANTILES(p.p50, 2)[OFFSET(1)] AS p50_tipo
  FROM pop p JOIN `${PROJECT}.retail_gold.dim_article` a USING (article_id) GROUP BY 1)
SELECT a.article_id, a.prod_name, a.product_type_name AS product_type, a.product_group_name AS product_group,
       a.index_group_name AS index_group, a.section_name AS section, a.colour_group_name AS colour, a.detail_desc,
       GREATEST(99, CAST(ROUND(COALESCE(p.p50, t.p50_tipo, 0.03) * ${PRICE_DEMO_FACTOR} * 100) AS INT64)) AS price_cents,
       COALESCE(p.popularity, 0) AS popularity
FROM `${PROJECT}.retail_gold.dim_article` a
LEFT JOIN pop p USING (article_id)
LEFT JOIN tipo t USING (product_type_name);
