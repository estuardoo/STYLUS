-- Bronze H&M: tablas externas sobre GCS (todo texto: conserva ceros a la izquierda de article_id)
-- + copia nativa particionada de transacciones. Ejecutar: python ops.py bronze (variables desde el Excel).

CREATE OR REPLACE EXTERNAL TABLE `${PROJECT}.${DS_BRONZE}.ext_articles` (
  article_id STRING,
  product_code STRING,
  prod_name STRING,
  product_type_no STRING,
  product_type_name STRING,
  product_group_name STRING,
  graphical_appearance_no STRING,
  graphical_appearance_name STRING,
  colour_group_code STRING,
  colour_group_name STRING,
  perceived_colour_value_id STRING,
  perceived_colour_value_name STRING,
  perceived_colour_master_id STRING,
  perceived_colour_master_name STRING,
  department_no STRING,
  department_name STRING,
  index_code STRING,
  index_name STRING,
  index_group_no STRING,
  index_group_name STRING,
  section_no STRING,
  section_name STRING,
  garment_group_no STRING,
  garment_group_name STRING,
  detail_desc STRING
)
OPTIONS (format = 'CSV', uris = ['gs://${RAW_BUCKET}/hm/articles.csv'], skip_leading_rows = 1, allow_quoted_newlines = TRUE);

CREATE OR REPLACE EXTERNAL TABLE `${PROJECT}.${DS_BRONZE}.ext_customers` (
  customer_id STRING,
  FN STRING,
  Active STRING,
  club_member_status STRING,
  fashion_news_frequency STRING,
  age STRING,
  postal_code STRING
)
OPTIONS (format = 'CSV', uris = ['gs://${RAW_BUCKET}/hm/customers.csv'], skip_leading_rows = 1);

CREATE OR REPLACE EXTERNAL TABLE `${PROJECT}.${DS_BRONZE}.ext_transactions` (
  t_dat DATE, customer_id STRING, article_id STRING, price FLOAT64, sales_channel_id INT64
)
OPTIONS (format = 'CSV', uris = ['gs://${RAW_BUCKET}/hm/transactions_train.csv'], skip_leading_rows = 1);

-- Copia nativa: particionada por día y agrupada por cliente/artículo -> consultas baratas
CREATE OR REPLACE TABLE `${PROJECT}.${DS_BRONZE}.transactions`
PARTITION BY t_dat
CLUSTER BY customer_id, article_id AS
SELECT *, CURRENT_TIMESTAMP() AS _ingested_at, 'hm_kaggle' AS _source_system
FROM `${PROJECT}.${DS_BRONZE}.ext_transactions`;

-- Control de carga (debe cuadrar con data/manifests/hm_raw_manifest.json: 31,788,324)
SELECT COUNT(*) AS filas, MIN(t_dat) AS desde, MAX(t_dat) AS hasta
FROM `${PROJECT}.${DS_BRONZE}.transactions`;
