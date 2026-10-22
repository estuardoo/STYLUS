# ---------- Base transaccional (carrito, pedidos, wallet) ----------
resource "random_password" "db" {
  length  = 24
  special = false
}

resource "random_password" "admin_token" {
  length  = 32
  special = false
}

resource "google_sql_database_instance" "main" {
  count               = var.enable_cloudsql ? 1 : 0
  name                = "retail-pg-${var.env}"
  database_version    = "POSTGRES_15"
  region              = var.region
  deletion_protection = var.cloudsql_deletion_protection

  settings {
    tier              = var.cloudsql_tier
    edition           = "ENTERPRISE"
    availability_type = var.cloudsql_ha ? "REGIONAL" : "ZONAL"
    disk_size         = 10
    user_labels       = local.labels
    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true # RPO <= 5 min
      start_time                     = "06:00"
    }
    ip_configuration {
      ipv4_enabled = true # sin redes autorizadas: solo conector Cloud SQL con IAM
    }
  }
  depends_on = [google_project_service.apis]
}

resource "google_sql_database" "app" {
  count    = var.enable_cloudsql ? 1 : 0
  name     = "retail"
  instance = google_sql_database_instance.main[0].name
}

resource "google_sql_user" "app" {
  count    = var.enable_cloudsql ? 1 : 0
  name     = "retail_app"
  instance = google_sql_database_instance.main[0].name
  password = random_password.db.result
}

locals {
  db_url = var.enable_cloudsql ? join("", [
    "postgresql+pg8000://retail_app:", random_password.db.result, "@/retail?unix_sock=/cloudsql/",
    google_sql_database_instance.main[0].connection_name, "/.s.PGSQL.5432"
  ]) : ""
}

resource "google_secret_manager_secret" "app" {
  for_each  = toset(var.enable_cloudsql ? ["retail-db-url", "retail-admin-token"] : [])
  secret_id = each.value
  labels    = local.labels
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "db_url" {
  count       = var.enable_cloudsql ? 1 : 0
  secret      = google_secret_manager_secret.app["retail-db-url"].id
  secret_data = local.db_url
}

resource "google_secret_manager_secret_version" "admin_token" {
  count       = var.enable_cloudsql ? 1 : 0
  secret      = google_secret_manager_secret.app["retail-admin-token"].id
  secret_data = random_password.admin_token.result
}
