terraform {
  required_version = ">= 1.6"
  required_providers {
    google = { source = "hashicorp/google", version = "~> 6.0" }
    random = { source = "hashicorp/random", version = "~> 3.6" }
  }
  # Estado remoto en GCS. Bucket creado una vez con: make tf-bootstrap
  backend "gcs" {}
}

provider "google" {
  project               = var.project_id
  region                = var.region
  billing_project       = var.project_id
  user_project_override = true
}

locals {
  labels = { proyecto = "retail-bigdata", entorno = var.env, curso = "utec-bigdata" }
  apis = [
    "storage.googleapis.com", "bigquery.googleapis.com", "pubsub.googleapis.com",
    "dataflow.googleapis.com", "dataproc.googleapis.com", "run.googleapis.com",
    "aiplatform.googleapis.com", "sqladmin.googleapis.com", "secretmanager.googleapis.com",
    "artifactregistry.googleapis.com", "billingbudgets.googleapis.com",
    "cloudbilling.googleapis.com", "monitoring.googleapis.com", "logging.googleapis.com",
  ]
}

resource "google_project_service" "apis" {
  for_each           = toset(local.apis)
  service            = each.value
  disable_on_destroy = false
}

# ---------- Almacenamiento: Data Lake (medallion) ----------
# raw = Bronze inmutable (copia exacta de H&M); lake = Silver/Gold en Parquet
resource "google_storage_bucket" "raw" {
  name                        = "${var.project_id}-retail-raw"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  labels                      = local.labels
  versioning { enabled = true }

  lifecycle_rule { # imágenes poco consultadas -> Nearline
    condition {
      age            = 30
      matches_prefix = ["hm/images/"]
    }
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }
  lifecycle_rule { # versiones antiguas se borran a los 30 días
    condition {
      days_since_noncurrent_time = 30
      with_state                 = "ARCHIVED"
    }
    action { type = "Delete" }
  }
}

resource "google_storage_bucket" "lake" {
  name                        = "${var.project_id}-retail-lake"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  labels                      = local.labels
  versioning { enabled = true }
}

# ---------- Data Warehouse ----------
resource "google_bigquery_dataset" "layers" {
  for_each   = toset(["bronze", "silver", "gold", "ops"])
  dataset_id = "retail_${each.value}"
  location   = var.region
  labels     = local.labels
}

# Tabla destino de la suscripción Pub/Sub -> BigQuery (ruta streaming económica)
resource "google_bigquery_table" "events_raw" {
  dataset_id          = google_bigquery_dataset.layers["bronze"].dataset_id
  table_id            = "events_raw"
  deletion_protection = false
  time_partitioning {
    type  = "DAY"
    field = "publish_time"
  }
  schema = jsonencode([
    { name = "subscription_name", type = "STRING" },
    { name = "message_id", type = "STRING" },
    { name = "publish_time", type = "TIMESTAMP" },
    { name = "data", type = "STRING" },
    { name = "attributes", type = "STRING" },
  ])
}

# ---------- Streaming ----------
resource "google_pubsub_topic" "events" {
  name   = var.pubsub_topic
  labels = local.labels
}

resource "google_pubsub_topic" "events_dlq" {
  name   = "${var.pubsub_topic}-dlq"
  labels = local.labels
}

resource "google_pubsub_subscription" "events_to_bq" {
  name  = "${var.pubsub_topic}-to-bq"
  topic = google_pubsub_topic.events.id
  bigquery_config {
    table          = "${var.project_id}.${google_bigquery_table.events_raw.dataset_id}.${google_bigquery_table.events_raw.table_id}"
    write_metadata = true
  }
  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.events_dlq.id
    max_delivery_attempts = 5
  }
  depends_on = [google_project_iam_member.pubsub_bq]
}

# Suscripción pull para el job Dataflow (enriquecimiento con ventanas) en demo
resource "google_pubsub_subscription" "events_dataflow" {
  name                       = "${var.pubsub_topic}-dataflow"
  topic                      = google_pubsub_topic.events.id
  ack_deadline_seconds       = 60
  message_retention_duration = "86400s"
  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.events_dlq.id
    max_delivery_attempts = 5
  }
}

data "google_project" "this" {}

# El agente de Pub/Sub necesita escribir en BigQuery
resource "google_project_iam_member" "pubsub_bq" {
  for_each = toset(["roles/bigquery.dataEditor", "roles/bigquery.metadataViewer"])
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:service-${data.google_project.this.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

# ---------- Identidades (mínimo privilegio) ----------
locals {
  sa_roles = {
    ingest   = ["roles/storage.objectAdmin", "roles/bigquery.jobUser", "roles/bigquery.dataEditor", "roles/pubsub.publisher"]
    pipeline = ["roles/dataflow.worker", "roles/dataproc.worker", "roles/storage.objectAdmin", "roles/bigquery.dataEditor", "roles/bigquery.jobUser", "roles/pubsub.subscriber", "roles/pubsub.viewer"]
    api      = ["roles/bigquery.dataViewer", "roles/bigquery.jobUser", "roles/aiplatform.user", "roles/cloudsql.client", "roles/secretmanager.secretAccessor", "roles/pubsub.publisher"]
  }
  sa_bindings = flatten([for sa, roles in local.sa_roles : [for r in roles : { sa = sa, role = r }]])
}

resource "google_service_account" "sa" {
  for_each     = local.sa_roles
  account_id   = "sa-retail-${each.key}"
  display_name = "Retail ${each.key}"
}

resource "google_project_iam_member" "sa_roles" {
  for_each = { for b in local.sa_bindings : "${b.sa}-${b.role}" => b }
  project  = var.project_id
  role     = each.value.role
  member   = "serviceAccount:${google_service_account.sa[each.value.sa].email}"
}

resource "google_artifact_registry_repository" "containers" {
  location      = var.region
  repository_id = "retail"
  format        = "DOCKER"
  labels        = local.labels
}

# ---------- Control de costos automatizado ----------
resource "google_pubsub_topic" "budget_alerts" {
  name = "billing-budget-alerts"
}

resource "google_billing_budget" "project" {
  count           = var.billing_account == "" ? 0 : 1
  billing_account = var.billing_account
  display_name    = "retail-bigdata-${var.env}"

  budget_filter { projects = ["projects/${data.google_project.this.number}"] }

  amount {
    specified_amount {
      currency_code = "USD"
      units         = tostring(var.monthly_budget_usd)
    }
  }

  dynamic "threshold_rules" {
    for_each = [0.5, 0.9, 1.0]
    content { threshold_percent = threshold_rules.value }
  }
  threshold_rules {
    threshold_percent = 1.0
    spend_basis       = "FORECASTED_SPEND"
  }

  all_updates_rule {
    pubsub_topic   = google_pubsub_topic.budget_alerts.id
    schema_version = "1.0"
  }
}

# La API lee las imágenes H&M del bucket privado (solo lectura)
resource "google_storage_bucket_iam_member" "api_images" {
  bucket = google_storage_bucket.raw.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.sa["api"].email}"
}
