output "project_number" { value = data.google_project.this.number }
output "raw_bucket" { value = google_storage_bucket.raw.name }
output "lake_bucket" { value = google_storage_bucket.lake.name }
output "datasets" { value = { for k, d in google_bigquery_dataset.ds : k => d.dataset_id } }
output "service_accounts" { value = { for k, s in google_service_account.sa : k => s.email } }
output "artifact_repo" { value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.containers.repository_id}" }
output "cloudsql_connection" { value = var.cloudsql.enabled ? google_sql_database_instance.main[0].connection_name : "" }
output "api_url" { value = length(google_cloud_run_v2_service.api) > 0 ? google_cloud_run_v2_service.api[0].uri : "" }
output "wif_provider" { value = var.github.repo == "" ? "" : google_iam_workload_identity_pool_provider.github[0].name }
