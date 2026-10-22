# ---------- GitHub Actions -> GCP sin llaves (Workload Identity Federation) ----------
resource "google_iam_workload_identity_pool" "github" {
  count                     = var.github_repo == "" ? 0 : 1
  workload_identity_pool_id = "github-${var.env}"
  display_name              = "GitHub ${var.env}"
}

resource "google_iam_workload_identity_pool_provider" "github" {
  count                              = var.github_repo == "" ? 0 : 1
  workload_identity_pool_id          = google_iam_workload_identity_pool.github[0].workload_identity_pool_id
  workload_identity_pool_provider_id = "github-oidc"
  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
  }
  attribute_condition = "assertion.repository == '${var.github_repo}'"
  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account" "deployer" {
  count        = var.github_repo == "" ? 0 : 1
  account_id   = "sa-retail-deployer"
  display_name = "Retail deployer (GitHub Actions)"
}

resource "google_project_iam_member" "deployer" {
  for_each = toset(var.github_repo == "" ? [] : ["roles/run.admin", "roles/artifactregistry.writer"])
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.deployer[0].email}"
}

# El deployer puede desplegar revisiones que corren como sa-retail-api (y nada más)
resource "google_service_account_iam_member" "deployer_acts_as_api" {
  count              = var.github_repo == "" ? 0 : 1
  service_account_id = google_service_account.sa["api"].name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deployer[0].email}"
}

resource "google_service_account_iam_member" "wif" {
  count              = var.github_repo == "" ? 0 : 1
  service_account_id = google_service_account.deployer[0].name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github[0].name}/attribute.repository/${var.github_repo}"
}
