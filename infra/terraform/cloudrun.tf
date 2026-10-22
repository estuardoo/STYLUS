# ---------- API + web en Cloud Run (la imagen la actualiza GitHub Actions) ----------
resource "google_cloud_run_v2_service" "api" {
  count               = var.enable_cloud_run && var.enable_cloudsql ? 1 : 0
  name                = "retail-api"
  location            = var.region
  deletion_protection = false
  ingress             = "INGRESS_TRAFFIC_ALL"
  labels              = local.labels

  template {
    service_account = google_service_account.sa["api"].email
    scaling {
      min_instance_count = var.api_min_instances
      max_instance_count = var.api_max_instances
    }
    containers {
      image = var.api_image
      resources {
        limits = { cpu = "1", memory = "512Mi" }
      }
      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "GCP_REGION"
        value = var.region
      }
      env {
        name  = "ASSISTANT_MODE"
        value = var.assistant_mode
      }
      env {
        name  = "GEMINI_MODEL"
        value = var.gemini_model
      }
      env {
        name  = "PUBSUB_TOPIC"
        value = google_pubsub_topic.events.name
      }
      env {
        name  = "IMAGES_BUCKET"
        value = google_storage_bucket.raw.name
      }
      env {
        name  = "PRICE_DEMO_FACTOR"
        value = tostring(var.price_demo_factor)
      }
      env {
        name = "DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.app["retail-db-url"].secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "ADMIN_TOKEN"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.app["retail-admin-token"].secret_id
            version = "latest"
          }
        }
      }
      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }
      startup_probe {
        http_get {
          path = "/health"
        }
      }
    }
    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.main[0].connection_name]
      }
    }
  }

  lifecycle {
    ignore_changes = [template[0].containers[0].image, client, client_version]
  }
  depends_on = [google_secret_manager_secret_version.db_url, google_secret_manager_secret_version.admin_token,
  google_project_iam_member.sa_roles]
}

resource "google_cloud_run_v2_service_iam_member" "public" {
  count    = var.enable_cloud_run && var.enable_cloudsql && var.api_public ? 1 : 0
  name     = google_cloud_run_v2_service.api[0].name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}
