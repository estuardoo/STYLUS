# ---------- Base transaccional (carrito, pedidos, wallet) ----------
resource "random_id" "sql" {
  byte_length = 2 # los nombres de Cloud SQL no se pueden reutilizar por ~1 semana tras borrar
}

resource "random_password" "db" {
  length  = 24
  special = false
}

resource "random_password" "admin_token" {
  length  = 32
  special = false
}

resource "google_sql_database_instance" "main" {
  count               = var.cloudsql.enabled ? 1 : 0
  name                = "${var.cloudsql.instance}-${var.env}-${random_id.sql.hex}"
  database_version    = var.cloudsql.version
  region              = var.region
  deletion_protection = var.cloudsql.deletion_protection

  settings {
    tier              = var.cloudsql.tier
    edition           = "ENTERPRISE"
    availability_type = var.cloudsql.ha ? "REGIONAL" : "ZONAL"
    disk_size         = var.cloudsql.disk_gb
    user_labels       = var.labels
    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
      start_time                     = var.cloudsql.backup_start
    }
    ip_configuration {
      ipv4_enabled = true # sin redes autorizadas: solo conector Cloud SQL con IAM
    }
  }
  depends_on = [google_project_service.apis]
}

resource "google_sql_database" "app" {
  count    = var.cloudsql.enabled ? 1 : 0
  name     = var.cloudsql.db_name
  instance = google_sql_database_instance.main[0].name
}

resource "google_sql_user" "app" {
  count    = var.cloudsql.enabled ? 1 : 0
  name     = var.cloudsql.user
  instance = google_sql_database_instance.main[0].name
  password = random_password.db.result
}

resource "google_secret_manager_secret" "db_url" {
  count     = var.cloudsql.enabled ? 1 : 0
  secret_id = var.secrets.db_url
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "db_url" {
  count  = var.cloudsql.enabled ? 1 : 0
  secret = google_secret_manager_secret.db_url[0].id
  secret_data = join("", [
    "postgresql+pg8000://", var.cloudsql.user, ":", random_password.db.result, "@/", var.cloudsql.db_name,
    "?unix_sock=/cloudsql/", google_sql_database_instance.main[0].connection_name, "/.s.PGSQL.5432"
  ])
}

resource "google_secret_manager_secret" "admin_token" {
  secret_id = var.secrets.admin_token
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "admin_token" {
  secret      = google_secret_manager_secret.admin_token.id
  secret_data = random_password.admin_token.result
}
