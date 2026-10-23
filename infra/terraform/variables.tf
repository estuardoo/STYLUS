# Todos los valores llegan de config/control_plataforma.xlsx -> plataforma.auto.tfvars.json (python ops.py config).
# No editar valores aquí.
variable "project_id" { type = string }
variable "region" { type = string }
variable "env" { type = string }
variable "labels" { type = map(string) }
variable "apis" { type = list(string) }

variable "billing_account" { type = string }
variable "monthly_budget_usd" { type = number }
variable "budget_thresholds" { type = list(number) }
variable "budget_topic" { type = string }

variable "buckets" { type = object({ raw = string, lake = string }) }
variable "force_destroy_buckets" { type = bool }
variable "images_nearline_days" { type = number }
variable "noncurrent_version_days" { type = number }

variable "datasets" {
  type = map(object({ dataset_id = string, description = string, delete_contents_on_destroy = bool }))
}

variable "tables" {
  type = list(object({
    dataset         = string, table_id = string, description = string,
    partition_field = string, clustering = list(string), schema = string
  }))
}

variable "pubsub" {
  type = object({
    topic                 = string, dlq_topic = string, bq_subscription = string, bq_table = string,
    dataflow_subscription = string, dlq_subscription = string, max_delivery_attempts = number, retention = string
  })
}

variable "service_accounts" {
  type = map(object({ account_id = string, display_name = string, description = string }))
}

# member: sa:<clave> | user:<email> | group:<email> | compute-default | pubsub-agent
# scope : project | bucket:raw|lake | dataset:<clave> | topic:events|dlq | subscription:bq|dataflow | sa:<clave>
variable "iam" { type = list(object({ member = string, role = string, scope = string })) }

variable "artifact_repo" { type = string }

variable "cloudsql" {
  type = object({
    enabled = bool, instance = string, version = string, tier = string, ha = bool, disk_gb = number,
    db_name = string, user = string, backup_start = string, deletion_protection = bool
  })
}

variable "secrets" { type = object({ db_url = string, admin_token = string }) }

variable "cloudrun" {
  type = object({
    enabled = bool, service = string, image = string, min_instances = number, max_instances = number,
    cpu     = string, memory = string, public = bool
  })
}

variable "api_env" { type = map(string) }

variable "github" { type = object({ repo = string, pool_id = string, deployer_key = string }) }
