variable "project_id" { type = string }

variable "region" {
  type    = string
  default = "us-central1" # Tier 1: precios más bajos y Gemini disponible
}

variable "env" {
  type    = string
  default = "dev"
}

variable "pubsub_topic" {
  type    = string
  default = "retail-events"
}

variable "billing_account" {
  type        = string
  default     = ""
  description = "ID de la cuenta de facturación (XXXXXX-XXXXXX-XXXXXX). Vacío = no crea presupuesto."
}

variable "monthly_budget_usd" {
  type    = number
  default = 50
}

# ---------- Cloud SQL ----------
variable "enable_cloudsql" {
  type    = bool
  default = true
}

variable "cloudsql_tier" {
  type    = string
  default = "db-f1-micro"
}

variable "cloudsql_ha" {
  type    = bool
  default = false # true = REGIONAL (producción); duplica el costo
}

variable "cloudsql_deletion_protection" {
  type    = bool
  default = false # true en producción
}

# ---------- Cloud Run ----------
variable "enable_cloud_run" {
  type    = bool
  default = true
}

variable "api_image" {
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/hello" # se reemplaza en el primer deploy de GitHub Actions
  description = "Imagen inicial; las siguientes las publica .github/workflows/deploy.yml"
}

variable "api_min_instances" {
  type    = number
  default = 0
}

variable "api_max_instances" {
  type    = number
  default = 3
}

variable "api_public" {
  type    = bool
  default = true
}

variable "assistant_mode" {
  type    = string
  default = "gemini" # "rules" para no usar Vertex AI
}

variable "gemini_model" {
  type    = string
  default = "gemini-2.5-flash-lite"
}

variable "price_demo_factor" {
  type    = number
  default = 500
}

# ---------- CI/CD ----------
variable "github_repo" {
  type        = string
  default     = ""
  description = "owner/repo de GitHub para Workload Identity Federation. Vacío = no se crea."
}
