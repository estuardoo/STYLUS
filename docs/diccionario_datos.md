# Diccionario de datos

## Silver (`retail_silver`, Parquet en `gs://…-retail-lake/silver/`)

| Tabla | Columna | Tipo | Regla / origen |
|---|---|---|---|
| articles | article_id | STRING | Clave (10 dígitos, conserva ceros). Única |
| articles | product_code, prod_name | STRING | Original H&M |
| articles | product_type_name, product_group_name, index_group_name, section_name, garment_group_name, colour_group_name | STRING | Taxonomía H&M (5 grupos de índice, 131 tipos) |
| articles | *_no, *_code, *_id numéricos | INT64 | Casteados desde CSV |
| articles | detail_desc | STRING | Nulos (416) imputados con prod_name |
| customers | customer_id | STRING | Hash SHA-256 de H&M (seudonimizado). Única |
| customers | age | INT64 | Nulo (1.2%) se conserva; ver age_band |
| customers | age_band | STRING | 16-24, 25-34, 35-44, 45-54, 55+, sin_edad |
| customers | fn, active | INT64 | Vacío = 0 |
| customers | club_member_status, fashion_news_frequency | STRING | Vacío o 'None' = 'NONE' |
| customers | postal_code | STRING | Hash original |
| transactions | t_dat | DATE | Partición. 2018-09-20 a 2020-09-22 |
| transactions | customer_id, article_id | STRING | Deben existir (si no: cuarentena) |
| transactions | price | FLOAT64 | Normalizado por H&M (> 0) |
| transactions | sales_channel_id | INT64 | 1 o 2 |
| transactions | _source_system, _ingested_at | STRING, TIMESTAMP | Linaje |
| quarantine/transactions | _motivo | STRING | fecha_invalida, sin_cliente, articulo_inexistente, precio_invalido, canal_invalido |
| v_events (vista) | event_id … simulation_run_id | varios | Eventos de `bronze.events_raw` deduplicados por event_id |

## Gold (`retail_gold`)

| Tabla | Grano | Claves | Medidas / atributos |
|---|---|---|---|
| fact_sales | Línea de venta | sale_date, customer_id, article_id, sales_channel_id | qty, price, source (hm_hist, hm_transactions_replay, web_demo), is_synthetic, order_id |
| fact_orders | Pedido (cliente + día + fuente) | order_id | lineas, unidades, importe, sales_channel_id |
| dim_article | Artículo | article_id | Taxonomía y descripción |
| dim_customer | Cliente | customer_id | age, age_band, membresía |
| dim_date | Día | date_key | anio, mes, anio_mes, semana_iso, fin_de_semana |
| dim_channel | Canal | sales_channel_id | canal (supuesto: 1 tienda, 2 online) |
| reco_popular | Grupo × artículo | index_group_name, article_id | ventas_7d, rank_grupo |
| v_catalog_serving | Artículo | article_id | price_cents (demo sintético), popularity (28 días) |
| v_ventas_mensuales, v_top_articulos, v_recurrencia_clientes | Vistas BI | — | Para Looker Studio |

## Operación (`retail_ops`)

| Tabla | Contenido |
|---|---|
| stream_metrics_1m | Por ventana de 1 min: eventos, compras, importe, lag p50/p95 (Dataflow) |
| stream_dlq | Mensajes inválidos con motivo y payload |
| v_stream_salud | Eventos y duplicados por minuto desde la ruta económica |
| v_costo_real_mensual | Costo facturado por servicio y USD por pedido (billing export) |

## Transaccional (Cloud SQL `retail`)

users, articles (catálogo de servicio), cart_items, orders (idempotency_key única), order_lines, wallet_ledger (append-only; saldo = suma). Montos en centavos. Ver `api/schema.sql`.
