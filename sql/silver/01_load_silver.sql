-- Silver en BigQuery: carga los Parquet que produce pipelines/batch/silver_hm.py (Serverless Spark).
-- Variables: ${PROJECT}, ${LAKE_BUCKET}. Ejecutar: python ops.py silver
LOAD DATA OVERWRITE `${PROJECT}.${DS_SILVER}.articles`
FROM FILES (format = 'PARQUET', uris = ['gs://${LAKE_BUCKET}/silver/articles/*.parquet']);

LOAD DATA OVERWRITE `${PROJECT}.${DS_SILVER}.customers`
CLUSTER BY customer_id
FROM FILES (format = 'PARQUET', uris = ['gs://${LAKE_BUCKET}/silver/customers/*.parquet']);

LOAD DATA OVERWRITE `${PROJECT}.${DS_SILVER}.transactions`
PARTITION BY t_dat
CLUSTER BY customer_id, article_id
FROM FILES (format = 'PARQUET', uris = ['gs://${LAKE_BUCKET}/silver/transactions/*.parquet']);  -- '*' cruza carpetas year_month=...

-- Eventos streaming: ruta económica (suscripción Pub/Sub -> bronze.events_raw), deduplicados por event_id
CREATE OR REPLACE VIEW `${PROJECT}.${DS_SILVER}.v_events` AS
SELECT * EXCEPT (rn) FROM (
  SELECT
    JSON_VALUE(data, '$.event_id')                              AS event_id,
    JSON_VALUE(data, '$.event_type')                            AS event_type,
    TIMESTAMP(JSON_VALUE(data, '$.event_time'))                 AS event_time,
    SAFE.PARSE_DATE('%F', JSON_VALUE(data, '$.source_t_dat'))   AS source_t_dat,
    JSON_VALUE(data, '$.customer_id')                           AS customer_id,
    JSON_VALUE(data, '$.article_id')                            AS article_id,
    SAFE_CAST(JSON_VALUE(data, '$.price') AS FLOAT64)           AS price,
    COALESCE(SAFE_CAST(JSON_VALUE(data, '$.qty') AS INT64), 1)  AS qty,
    SAFE_CAST(JSON_VALUE(data, '$.sales_channel_id') AS INT64)  AS sales_channel_id,
    JSON_VALUE(data, '$.order_id')                              AS order_id,
    JSON_VALUE(data, '$.source_system')                         AS source_system,
    SAFE_CAST(JSON_VALUE(data, '$.is_synthetic') AS BOOL)       AS is_synthetic,
    JSON_VALUE(data, '$.simulation_run_id')                     AS simulation_run_id,
    publish_time,
    ROW_NUMBER() OVER (PARTITION BY JSON_VALUE(data, '$.event_id') ORDER BY publish_time) AS rn
  FROM `${PROJECT}.${DS_BRONZE}.events_raw`
) WHERE rn = 1 AND event_id IS NOT NULL;
