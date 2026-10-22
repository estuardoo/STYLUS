-- Bronze H&M: tablas externas sobre GCS (sin copiar datos) + carga nativa particionada de transacciones.
-- Reemplazar ${PROJECT} y ${RAW_BUCKET} (make bq-bronze lo hace con envsubst).

CREATE OR REPLACE EXTERNAL TABLE `${PROJECT}.retail_bronze.ext_articles`
OPTIONS (format = 'CSV', uris = ['gs://${RAW_BUCKET}/hm/articles.csv'], skip_leading_rows = 1);

CREATE OR REPLACE EXTERNAL TABLE `${PROJECT}.retail_bronze.ext_customers`
OPTIONS (format = 'CSV', uris = ['gs://${RAW_BUCKET}/hm/customers.csv'], skip_leading_rows = 1);

CREATE OR REPLACE EXTERNAL TABLE `${PROJECT}.retail_bronze.ext_transactions` (
  t_dat DATE, customer_id STRING, article_id STRING, price FLOAT64, sales_channel_id INT64
)
OPTIONS (format = 'CSV', uris = ['gs://${RAW_BUCKET}/hm/transactions_train.csv'], skip_leading_rows = 1);

-- Copia nativa: particionada por día y agrupada por cliente/artículo -> consultas baratas
CREATE OR REPLACE TABLE `${PROJECT}.retail_bronze.transactions`
PARTITION BY t_dat
CLUSTER BY customer_id, article_id
OPTIONS (require_partition_filter = TRUE) AS
SELECT *, CURRENT_TIMESTAMP() AS _ingested_at, 'hm_kaggle' AS _source_system
FROM `${PROJECT}.retail_bronze.ext_transactions`;

-- Control de carga (debe cuadrar con data/manifests/hm_raw_manifest.json)
SELECT COUNT(*) AS filas, MIN(t_dat) AS desde, MAX(t_dat) AS hasta
FROM `${PROJECT}.retail_bronze.transactions` WHERE t_dat IS NOT NULL;
