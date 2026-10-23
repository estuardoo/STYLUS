# ---------- API + web en Cloud Run (la imagen la actualizan ops.py api o GitHub Actions) ----------
resource "google_cloud_run_v2_service" "api" {
  count               = var.cloudrun.enabled && var.cloudsql.enabled ? 1 : 0
  name                = var.cloudrun.service
  location            = var.region
  deletion_protection = false
  ingress             = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.sa["api"].email
    scaling {
      min_instance_count = var.cloudrun.min_instances
      max_instance_count = var.cloudrun.max_instances
    }
    containers {
      image = var.cloudrun.image
      resources {
        limits = { cpu = var.cloudrun.cpu, memory = var.cloudrun.memory }
      }
      dynamic "env" {
        for_each = merge(var.api_env, {
          GCP_PROJECT_ID = var.project_id
          GCP_REGION     = var.region
          PUBSUB_TOPIC   = google_pubsub_topic.events.name
          IMAGES_BUCKET  = google_storage_bucket.raw.name
        })
        content {
          name  = env.key
          value = env.value
        }
      }
      env {
        name = "DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.db_url[0].secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "ADMIN_TOKEN"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.admin_token.secret_id
            version = "latest"
          }
        }
      }
      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
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
  google_project_iam_member.iam]
}

resource "google_cloud_run_v2_service_iam_member" "public" {
  count    = length(google_cloud_run_v2_service.api) > 0 && var.cloudrun.public ? 1 : 0
  name     = google_cloud_run_v2_service.api[0].name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}
