# ---------- GitHub Actions -> GCP sin llaves (Workload Identity Federation) ----------
resource "google_iam_workload_identity_pool" "github" {
  count                     = var.github.repo == "" ? 0 : 1
  workload_identity_pool_id = var.github.pool_id
  display_name              = "GitHub ${var.env}"
  depends_on                = [google_project_service.apis]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  count                              = var.github.repo == "" ? 0 : 1
  workload_identity_pool_id          = google_iam_workload_identity_pool.github[0].workload_identity_pool_id
  workload_identity_pool_provider_id = "github-oidc"
  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
  }
  attribute_condition = "assertion.repository == '${var.github.repo}'"
  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account_iam_member" "wif" {
  count              = var.github.repo == "" ? 0 : 1
  service_account_id = google_service_account.sa[var.github.deployer_key].name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github[0].name}/attribute.repository/${var.github.repo}"
}
