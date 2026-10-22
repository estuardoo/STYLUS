# Runbook DRP / HA

Principio: todo lo derivado se reconstruye desde Bronze (GCS raw, versionado). Se protege Bronze y el estado transaccional.

| Componente | Falla | Recuperación (comandos) | RPO | RTO objetivo |
|---|---|---|---|---|
| GCS raw (Bronze) | Objeto borrado o sobrescrito | `gcloud storage ls -a gs://$GCS_RAW_BUCKET/hm/articles.csv` y `gcloud storage cp gs://...#<generación> gs://$GCS_RAW_BUCKET/hm/articles.csv` | 0 | < 15 min |
| BigQuery Silver/Gold | Tabla dañada | Time travel: `CREATE OR REPLACE TABLE x AS SELECT * FROM x FOR SYSTEM_TIME AS OF TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 HOUR)`; o `make silver-gcp bq-silver bq-gold` | 0 | < 1 h |
| Pub/Sub | Consumidor caído | Los mensajes se retienen; reanudar el consumidor. Reprocesar: `gcloud pubsub subscriptions seek retail-events-dataflow --time=<ISO8601>` | 0 | < 15 min |
| Dataflow | Job fallido | `make dataflow-stop` y `make dataflow-start` (la suscripción BigQuery sigue capturando) | 0 | < 30 min |
| Cloud SQL | Corrupción / borrado | PITR: `gcloud sql instances clone retail-pg-dev retail-pg-restore --point-in-time=<ISO8601>`; apuntar el secreto `retail-db-url` al clon y redeploy | ≤ 5 min | < 1 h |
| Cloud Run | Revisión defectuosa | `gcloud run services update-traffic retail-api --to-revisions=<revisión-anterior>=100 --region $GCP_REGION` | N/A | < 5 min |
| Región | Caída de us-central1 | `terraform apply -var region=us-east1` en otro estado + restaurar Bronze y backup de Cloud SQL | ≤ 24 h (prototipo) | < 4 h |

## Prueba de recuperación (Paso 3, registrar evidencia)

1. Anotar `SELECT COUNT(*) FROM orders` y el saldo de `demo` (API `/api/v1/wallet`).
2. `gcloud sql instances clone retail-pg-dev retail-pg-restore --point-in-time=$(date -u -d '-10 min' +%Y-%m-%dT%H:%M:%SZ)`.
3. Conectar al clon con Cloud SQL Auth Proxy y comparar conteos y saldo. Medir el tiempo total (RTO real).
4. `gcloud sql instances delete retail-pg-restore` para no pagar el clon.
5. Para GCS: sobrescribir `hm/articles.csv` con un archivo vacío, restaurar la generación anterior y verificar el SHA-256 contra `data/manifests/hm_raw_manifest.json`.
