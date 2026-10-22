# Requiere: Python 3.10+, gcloud, terraform >= 1.6. Variables en .env (ver .env.example)
-include .env
export

TF = terraform -chdir=infra/terraform
.PHONY: ingest-images setup test cost cost-refresh manifest replay-dry silver-local reco-eval catalog-local api-local gcp-setup tf-bootstrap tf-init tf-check tf-plan tf-apply tf-destroy ingest-raw bq-bronze silver-gcp bq-silver bq-gold replay dataflow-start dataflow-stop catalog-gcp deploy-api 

BQ = bq query --use_legacy_sql=false --project_id=$(GCP_PROJECT_ID)
IMAGE = $(GCP_REGION)-docker.pkg.dev/$(GCP_PROJECT_ID)/retail/retail-api:manual

# ---------- Local ----------
setup:
	python -m pip install -r requirements.txt

test:
	python -m unittest discover -s tests -v

cost:
	python cost/estimate_costs.py

cost-refresh:
	python cost/estimate_costs.py --refresh-prices

manifest:
	python ingestion/batch/upload_raw.py --manifest-only

replay-dry:
	python ingestion/streaming/replay_publisher.py --limit 10 --dry-run

silver-local:   ## requiere pyspark + Java
	python pipelines/batch/silver_hm.py --raw data/raw --out data/silver

reco-eval:
	python pipelines/reco/baseline_eval.py

catalog-local:
	python api/load_catalog.py --source local

api-local:      ## http://localhost:8080
	cd api && python -m uvicorn main:app --port 8080 --reload

# ---------- Infraestructura (plan antes de apply; nunca apply en CI) ----------
gcp-setup:      ## una vez: APIs base y acceso privado de Google para Serverless Spark
	gcloud config set project $(GCP_PROJECT_ID)
	gcloud services enable serviceusage.googleapis.com cloudresourcemanager.googleapis.com iam.googleapis.com compute.googleapis.com
	gcloud compute networks subnets update default --region=$(GCP_REGION) --enable-private-ip-google-access

tf-bootstrap:   ## una vez: bucket del estado remoto
	gcloud storage buckets create gs://$(GCP_PROJECT_ID)-tfstate --location=$(GCP_REGION) --uniform-bucket-level-access --public-access-prevention
	gcloud storage buckets update gs://$(GCP_PROJECT_ID)-tfstate --versioning

tf-init:
	$(TF) init -backend-config="bucket=$(GCP_PROJECT_ID)-tfstate" -backend-config="prefix=retail/dev"

tf-check:
	$(TF) fmt -check -recursive && $(TF) validate

tf-plan:
	$(TF) plan -var-file=terraform.tfvars -out=tfplan

tf-apply:
	$(TF) apply tfplan

tf-destroy:     ## apaga todo lo de la demo (los buckets con datos piden confirmación)
	$(TF) destroy -var-file=terraform.tfvars

# ---------- Datos en GCP (Paso 2) ----------
ingest-raw:     ## CSV primero (rápido); las imágenes con: make ingest-images
	python ingestion/batch/upload_raw.py --bucket $(GCS_RAW_BUCKET) --skip-images

ingest-images:
	python ingestion/batch/upload_raw.py --bucket $(GCS_RAW_BUCKET)

bq-bronze:
	PROJECT=$(GCP_PROJECT_ID) RAW_BUCKET=$(GCS_RAW_BUCKET) envsubst < sql/bronze/01_bronze_hm.sql | $(BQ)

silver-gcp:
	gcloud dataproc batches submit pyspark pipelines/batch/silver_hm.py --region=$(GCP_REGION) --version=2.2 \
	  --service-account=sa-retail-pipeline@$(GCP_PROJECT_ID).iam.gserviceaccount.com \
	  -- --raw gs://$(GCS_RAW_BUCKET)/hm --out gs://$(GCS_LAKE_BUCKET)/silver

bq-silver:
	PROJECT=$(GCP_PROJECT_ID) LAKE_BUCKET=$(GCS_LAKE_BUCKET) envsubst < sql/silver/01_load_silver.sql | $(BQ)

bq-gold:
	PROJECT=$(GCP_PROJECT_ID) PRICE_DEMO_FACTOR=$(PRICE_DEMO_FACTOR) envsubst < sql/gold/01_gold_model.sql | $(BQ)
	PROJECT=$(GCP_PROJECT_ID) envsubst < sql/gold/02_kpi_views.sql | $(BQ)

replay:
	python ingestion/streaming/replay_publisher.py --limit 5000 --project $(GCP_PROJECT_ID)

dataflow-start: ## solo durante la demo: cuesta mientras corre
	python pipelines/streaming/dataflow_events.py --runner DataflowRunner --project $(GCP_PROJECT_ID) \
	  --region $(GCP_REGION) --temp_location gs://$(GCS_LAKE_BUCKET)/tmp --job_name retail-events \
	  --subscription projects/$(GCP_PROJECT_ID)/subscriptions/$(PUBSUB_TOPIC)-dataflow \
	  --service_account_email sa-retail-pipeline@$(GCP_PROJECT_ID).iam.gserviceaccount.com \
	  --machine_type n1-standard-2 --max_num_workers 3 --streaming --enable_streaming_engine

dataflow-stop:
	gcloud dataflow jobs drain $$(gcloud dataflow jobs list --region $(GCP_REGION) --status active --filter name=retail-events --format 'value(id)') --region $(GCP_REGION)

# ---------- Exposición (Paso 3) ----------
catalog-gcp:    ## copia Gold -> Cloud SQL (usar con Cloud SQL Auth Proxy: DATABASE_URL apuntando a 127.0.0.1)
	python api/load_catalog.py --source bigquery

deploy-api:     ## despliegue manual (el automático lo hace GitHub Actions)
	gcloud builds submit api --tag $(IMAGE) && gcloud run deploy retail-api --image $(IMAGE) --region $(GCP_REGION)
