# Despliegue en GCP con Terraform

Orden de ejecución por paso. Todos los nombres de variables y recursos están fijados aquí y en `infra/terraform`.

## Pasos

| Paso | # | Acción | Comando | Responsable | Variables | Verificación |
|---|---|---|---|---|---|---|
| 1 | D01 | Instalar herramientas | gcloud, terraform >= 1.6, python 3.11, git (docker opcional) | Winston Quispe |  | gcloud --version; terraform -version |
| 1 | D02 | Crear proyecto y vincular facturación | gcloud projects create $GCP_PROJECT_ID && gcloud billing projects link $GCP_PROJECT_ID --billing-account=$BILLING_ACCOUNT | Winston Quispe | GCP_PROJECT_ID, BILLING_ACCOUNT | Proyecto visible en consola con facturación |
| 1 | D03 | Autenticarse | gcloud auth login && gcloud auth application-default login | Todo el equipo |  | gcloud config list |
| 1 | D04 | Configurar variables | cp .env.example .env; cp infra/terraform/terraform.tfvars.example infra/terraform/terraform.tfvars; editar ambos | Winston Quispe | Hoja Variables | make -n tf-plan muestra el proyecto correcto |
| 1 | D05 | Publicar repo | git remote add origin https://github.com/OWNER/REPO.git && git push -u origin main | Winston Quispe | github_repo | Workflow ci en verde |
| 2 | D06 | Habilitar APIs base y acceso privado | make gcp-setup | Winston Quispe | GCP_PROJECT_ID, GCP_REGION | Subred default con Private Google Access |
| 2 | D07 | Bucket de estado de Terraform | make tf-bootstrap | Winston Quispe | GCP_PROJECT_ID | gs://$GCP_PROJECT_ID-tfstate versionado |
| 2 | D08 | Inicializar y planificar | make tf-init tf-plan | Winston Quispe | terraform.tfvars | Plan sin errores; revisar recursos y costos |
| 2 | D09 | Aplicar infraestructura | make tf-apply && terraform -chdir=infra/terraform output | Winston Quispe |  | Buckets, datasets, Pub/Sub, Cloud SQL, Cloud Run creados |
| 2 | D10 | Cargar Bronze | make ingest-raw bq-bronze (luego make ingest-images) | Nicole Arenas | GCS_RAW_BUCKET | COUNT(*) = 31,788,324 en retail_bronze.transactions |
| 2 | D11 | Silver con Spark | make silver-gcp bq-silver | Nicole Arenas | GCS_LAKE_BUCKET | _quality_report con conciliado=true |
| 2 | D12 | Gold y vistas BI | make bq-gold | Nicole Arenas | PRICE_DEMO_FACTOR | Tablas fact_/dim_ y vistas v_* |
| 2 | D13 | Streaming de prueba | make dataflow-start; make replay; make dataflow-stop | Winston Quispe | PUBSUB_TOPIC | Filas en retail_ops.stream_metrics_1m y retail_silver.v_events |
| 3 | D14 | Variables de GitHub | Settings > Secrets and variables > Actions > Variables | Winston Quispe | GCP_PROJECT_ID, GCP_REGION, GCP_WIF_PROVIDER, GCP_DEPLOYER_SA | Variables creadas |
| 3 | D15 | Desplegar API/web | Actions > deploy-api > Run workflow (o make deploy-api) | Winston Quispe |  | Smoke test /health y /ready en verde |
| 3 | D16 | Cargar catálogo a Cloud SQL | cloud-sql-proxy $(terraform output -raw cloudsql_connection) & ; export DATABASE_URL=postgresql+pg8000://retail_app:CLAVE@127.0.0.1:5432/retail; make catalog-gcp | Nicole Arenas | DATABASE_URL | /ready devuelve 105,542 artículos |
| 3 | D17 | Recarga de saldo demo | curl -X POST $API_URL/api/v1/wallet/demo-topups -H 'X-Admin-Token: '$(gcloud secrets versions access latest --secret=retail-admin-token) -H 'Content-Type: application/json' -d '{"amount_cents":20000}' | Estuardo Oliver | API_URL | Saldo visible en la web |
| 3 | D18 | Tableros | Looker Studio > Agregar datos > BigQuery > retail_gold.v_* y retail_ops.* | Gianmarco Mejia |  | Tablero gerencial y operativo |
| 3 | D19 | Costos reales | Consola: Facturación > Exportar a BigQuery (dataset retail_ops); ejecutar cost/real_cost_per_order.sql | Winston Quispe | billing_account | Vista v_costo_real_mensual con datos |
| 3 | D20 | Apagado | make dataflow-stop; make tf-destroy (o enable_cloudsql=false y api_min_instances=0) | Winston Quispe |  | Facturación diaria ~0 |

## Variables

| Variable | Dónde se define | Ejemplo | Uso | Quién |
|---|---|---|---|---|
| GCP_PROJECT_ID | .env, GitHub (variable) | retail-hm-utec-2026 | ID único del proyecto (6-30 caracteres) | Winston Quispe |
| GCP_REGION | .env, GitHub (variable) | us-central1 | Región única del prototipo | Winston Quispe |
| BILLING_ACCOUNT | Shell (solo D02) | 012345-6789AB-CDEF01 | Vincular facturación | Winston Quispe |
| GCS_RAW_BUCKET | .env | retail-hm-utec-2026-retail-raw | Bronze (= output raw_bucket) | Winston Quispe |
| GCS_LAKE_BUCKET | .env | retail-hm-utec-2026-retail-lake | Silver/Gold Parquet y tmp de Dataflow (= output lake_bucket) | Winston Quispe |
| PUBSUB_TOPIC | .env | retail-events | Tópico de eventos | Winston Quispe |
| LOCAL_RAW_DIR | .env | data/raw | Datos H&M locales | Nicole Arenas |
| DATABASE_URL | .env (local) / secreto retail-db-url (nube) | sqlite:///./data/retail_demo.db | Base transaccional de la API | Nicole Arenas |
| ADMIN_TOKEN | .env (local) / secreto retail-admin-token (nube) | cambia-este-token | Autoriza recargas de saldo demo | Nicole Arenas |
| ASSISTANT_MODE | .env / tfvars assistant_mode | gemini \| rules | Vertex AI o reglas | Estuardo Oliver |
| GEMINI_MODEL | .env / tfvars gemini_model | gemini-2.5-flash-lite | Modelo del asistente | Estuardo Oliver |
| PRICE_DEMO_FACTOR | .env / tfvars price_demo_factor | 500 | Precio demo = precio H&M x factor (sintético) | Estuardo Oliver |
| IMAGES_DIR / IMAGES_BUCKET | .env / automático en Cloud Run | data/raw/images | Origen de imágenes | Nicole Arenas |
| REPLAY_TARGET_START | .env | 2026-11-01 | Fecha base de los eventos 2026 | Winston Quispe |
| REPLAY_EVENTS_PER_SEC | .env | 50 | Ritmo del replay | Winston Quispe |
| project_id | terraform.tfvars | retail-hm-utec-2026 | Igual a GCP_PROJECT_ID | Winston Quispe |
| region | terraform.tfvars | us-central1 | Igual a GCP_REGION | Winston Quispe |
| env | terraform.tfvars | dev | Sufijo de recursos (dev/demo/prod) | Winston Quispe |
| billing_account | terraform.tfvars | 012345-6789AB-CDEF01 | Crea presupuesto con alertas; vacío = no | Winston Quispe |
| monthly_budget_usd | terraform.tfvars | 50 | Monto del presupuesto | Gianmarco Mejia |
| enable_cloudsql | terraform.tfvars | true | Base transaccional (USD 8-11/mes) | Winston Quispe |
| cloudsql_tier / cloudsql_ha | terraform.tfvars | db-f1-micro / false | Tamaño y alta disponibilidad | Winston Quispe |
| cloudsql_deletion_protection | terraform.tfvars | false | true en producción | Winston Quispe |
| enable_cloud_run / api_public | terraform.tfvars | true / true | Servicio web/API y acceso público | Winston Quispe |
| api_min_instances / api_max_instances | terraform.tfvars | 0 / 3 | Escalado (min=1 en la demo evita arranque en frío) | Winston Quispe |
| api_image | terraform.tfvars | (por defecto hello) | Imagen inicial; luego la publica GitHub Actions | Winston Quispe |
| assistant_mode / gemini_model / price_demo_factor | terraform.tfvars | gemini / gemini-2.5-flash-lite / 500 | Configuración de la API en Cloud Run | Estuardo Oliver |
| github_repo | terraform.tfvars | OWNER/REPO | Habilita WIF para desplegar desde GitHub | Winston Quispe |
| pubsub_topic | terraform.tfvars | retail-events | Nombre del tópico | Winston Quispe |
| GCP_WIF_PROVIDER | GitHub (variable) | terraform output -raw wif_provider | Autenticación sin llaves | Winston Quispe |
| GCP_DEPLOYER_SA | GitHub (variable) | terraform output -raw deployer_sa | Cuenta que despliega | Winston Quispe |
| API_URL | Shell | terraform output -raw api_url | URL pública de la tienda | Winston Quispe |

## Recursos que crea

| Recurso | Nombre | Definido en |
|---|---|---|
| Bucket estado Terraform | ${project}-tfstate | make tf-bootstrap |
| Bucket Bronze | ${project}-retail-raw | main.tf |
| Bucket Silver/Gold | ${project}-retail-lake | main.tf |
| Datasets BigQuery | retail_bronze, retail_silver, retail_gold, retail_ops | main.tf |
| Tópicos Pub/Sub | retail-events, retail-events-dlq, billing-budget-alerts | main.tf |
| Suscripciones | retail-events-to-bq, retail-events-dataflow | main.tf |
| Cuentas de servicio | sa-retail-ingest, sa-retail-pipeline, sa-retail-api, sa-retail-deployer | main.tf, cicd.tf |
| Artifact Registry | retail | main.tf |
| Cloud SQL | retail-pg-${env} / base retail / usuario retail_app | cloudsql.tf |
| Secretos | retail-db-url, retail-admin-token | cloudsql.tf |
| Cloud Run | retail-api | cloudrun.tf |
| Workload Identity | pool github-${env} / provider github-oidc | cicd.tf |
| Presupuesto | retail-bigdata-${env} | main.tf |
| Job Dataflow | retail-events | make dataflow-start |
| Tablas operativas | retail_ops.stream_metrics_1m, retail_ops.stream_dlq | Dataflow |

## Notas

- `plan` antes de `apply`; la CI solo ejecuta `fmt` y `validate`, nunca `apply`.
- Dataflow cobra mientras corre: encenderlo solo para la demo (`make dataflow-start` / `make dataflow-stop`).
- El estado de Terraform vive en `gs://$GCP_PROJECT_ID-tfstate` (versionado); nunca en Git.
- Vertex AI Gemini no es gratuito (~USD 0.0005 por conversación); `assistant_mode = "rules"` lo evita.
