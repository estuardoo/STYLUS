terraform {
  required_version = ">= 1.6"
  required_providers {
    google = { source = "hashicorp/google", version = "~> 6.0" }
    random = { source = "hashicorp/random", version = "~> 3.6" }
  }
  backend "gcs" {} # bucket y prefix: python ops.py bootstrap
}

provider "google" {
  project               = var.project_id
  region                = var.region
  billing_project       = var.project_id
  user_project_override = true
  default_labels        = var.labels
}

resource "google_project_service" "apis" {
  for_each           = toset(var.apis)
  service            = each.value
  disable_on_destroy = false
}

data "google_project" "this" {}

data "google_compute_default_service_account" "default" {
  depends_on = [google_project_service.apis]
}

# ---------- Data Lake (medallion) ----------
resource "google_storage_bucket" "raw" {
  name                        = var.buckets.raw
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = var.force_destroy_buckets
  versioning { enabled = true }

  lifecycle_rule {
    condition {
      age            = var.images_nearline_days
      matches_prefix = ["hm/images/"]
    }
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }
  lifecycle_rule {
    condition {
      days_since_noncurrent_time = var.noncurrent_version_days
      with_state                 = "ARCHIVED"
    }
    action { type = "Delete" }
  }
  depends_on = [google_project_service.apis]
}

resource "google_storage_bucket" "lake" {
  name                        = var.buckets.lake
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = var.force_destroy_buckets
  versioning { enabled = true }

  lifecycle_rule {
    condition {
      days_since_noncurrent_time = var.noncurrent_version_days
      with_state                 = "ARCHIVED"
    }
    action { type = "Delete" }
  }
  depends_on = [google_project_service.apis]
}

# ---------- Data Warehouse ----------
resource "google_bigquery_dataset" "ds" {
  for_each                   = var.datasets
  dataset_id                 = each.value.dataset_id
  description                = each.value.description
  location                   = var.region
  delete_contents_on_destroy = each.value.delete_contents_on_destroy
  depends_on                 = [google_project_service.apis]
}

# Solo tablas con creado_por = terraform en la hoja Tablas (las demás las crea SQL/Spark)
resource "google_bigquery_table" "t" {
  for_each            = { for t in var.tables : "${t.dataset}.${t.table_id}" => t }
  dataset_id          = google_bigquery_dataset.ds[each.value.dataset].dataset_id
  table_id            = each.value.table_id
  description         = each.value.description
  schema              = each.value.schema
  clustering          = length(each.value.clustering) > 0 ? each.value.clustering : null
  deletion_protection = false

  dynamic "time_partitioning" {
    for_each = each.value.partition_field == "" ? [] : [each.value.partition_field]
    content {
      type  = "DAY"
      field = time_partitioning.value
    }
  }
}

# ---------- Streaming ----------
resource "google_pubsub_topic" "events" {
  name       = var.pubsub.topic
  depends_on = [google_project_service.apis]
}

resource "google_pubsub_topic" "dlq" {
  name       = var.pubsub.dlq_topic
  depends_on = [google_project_service.apis]
}

resource "google_pubsub_subscription" "bq" {
  name  = var.pubsub.bq_subscription
  topic = google_pubsub_topic.events.id
  bigquery_config {
    table          = "${var.project_id}.${google_bigquery_table.t[var.pubsub.bq_table].dataset_id}.${google_bigquery_table.t[var.pubsub.bq_table].table_id}"
    write_metadata = true
  }
  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dlq.id
    max_delivery_attempts = var.pubsub.max_delivery_attempts
  }
  depends_on = [google_bigquery_dataset_iam_member.iam, google_project_iam_member.iam]
}

resource "google_pubsub_subscription" "dataflow" {
  name                       = var.pubsub.dataflow_subscription
  topic                      = google_pubsub_topic.events.id
  ack_deadline_seconds       = 60
  message_retention_duration = var.pubsub.retention
  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dlq.id
    max_delivery_attempts = var.pubsub.max_delivery_attempts
  }
}

# Sin suscripción, los mensajes enviados a la DLQ se perderían
resource "google_pubsub_subscription" "dlq" {
  name                       = var.pubsub.dlq_subscription
  topic                      = google_pubsub_topic.dlq.id
  message_retention_duration = "604800s"
}

# ---------- Identidades y permisos (hoja Permisos y Usuarios) ----------
resource "google_service_account" "sa" {
  for_each     = var.service_accounts
  account_id   = each.value.account_id
  display_name = each.value.display_name
  description  = each.value.description
  depends_on   = [google_project_service.apis]
}

locals {
  members = merge(
    { for k, s in google_service_account.sa : "sa:${k}" => s.member },
    {
      "compute-default" = "serviceAccount:${data.google_compute_default_service_account.default.email}"
      "pubsub-agent"    = "serviceAccount:service-${data.google_project.this.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
    }
  )
  iam     = { for b in var.iam : "${b.member}|${b.role}|${b.scope}" => merge(b, { m = lookup(local.members, b.member, b.member) }) }
  buckets = { raw = google_storage_bucket.raw.name, lake = google_storage_bucket.lake.name }
  topics  = { events = google_pubsub_topic.events.name, dlq = google_pubsub_topic.dlq.name }
  subs    = { bq = google_pubsub_subscription.bq.name, dataflow = google_pubsub_subscription.dataflow.name }
}

resource "google_project_iam_member" "iam" {
  for_each = { for k, b in local.iam : k => b if b.scope == "project" }
  project  = var.project_id
  role     = each.value.role
  member   = each.value.m
}

resource "google_storage_bucket_iam_member" "iam" {
  for_each = { for k, b in local.iam : k => b if startswith(b.scope, "bucket:") }
  bucket   = local.buckets[trimprefix(each.value.scope, "bucket:")]
  role     = each.value.role
  member   = each.value.m
}

resource "google_bigquery_dataset_iam_member" "iam" {
  for_each   = { for k, b in local.iam : k => b if startswith(b.scope, "dataset:") }
  dataset_id = google_bigquery_dataset.ds[trimprefix(each.value.scope, "dataset:")].dataset_id
  role       = each.value.role
  member     = each.value.m
}

resource "google_pubsub_topic_iam_member" "iam" {
  for_each = { for k, b in local.iam : k => b if startswith(b.scope, "topic:") }
  topic    = local.topics[trimprefix(each.value.scope, "topic:")]
  role     = each.value.role
  member   = each.value.m
}

resource "google_pubsub_subscription_iam_member" "iam" {
  for_each     = { for k, b in local.iam : k => b if startswith(b.scope, "subscription:") }
  subscription = local.subs[trimprefix(each.value.scope, "subscription:")]
  role         = each.value.role
  member       = each.value.m
}

resource "google_service_account_iam_member" "iam" {
  for_each           = { for k, b in local.iam : k => b if startswith(b.scope, "sa:") }
  service_account_id = google_service_account.sa[trimprefix(each.value.scope, "sa:")].name
  role               = each.value.role
  member             = each.value.m
}

resource "google_artifact_registry_repository" "containers" {
  location      = var.region
  repository_id = var.artifact_repo
  format        = "DOCKER"
  depends_on    = [google_project_service.apis]
}

# ---------- Control de costos ----------
resource "google_pubsub_topic" "budget" {
  name       = var.budget_topic
  depends_on = [google_project_service.apis]
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
    for_each = var.budget_thresholds
    content { threshold_percent = threshold_rules.value }
  }
  threshold_rules {
    threshold_percent = 1.0
    spend_basis       = "FORECASTED_SPEND"
  }

  all_updates_rule {
    pubsub_topic   = google_pubsub_topic.budget.id
    schema_version = "1.0"
  }
}
