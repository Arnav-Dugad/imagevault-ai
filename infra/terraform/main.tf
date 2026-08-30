locals {
  namespace = "imagevault"
  manifest_files = toset([
    "config.yaml",
    "data-services.yaml",
    "app-services.yaml",
    "observability.yaml",
  ])
  manifests = merge([
    for name, document in data.kubectl_file_documents.resources : document.manifests
  ]...)
}

resource "kubernetes_namespace_v1" "imagevault" {
  metadata {
    name = local.namespace
    labels = {
      "app.kubernetes.io/name"       = "imagevault-ai"
      "app.kubernetes.io/managed-by" = "terraform"
    }
  }
}

resource "kubernetes_secret_v1" "imagevault" {
  metadata {
    name      = "imagevault-secrets"
    namespace = kubernetes_namespace_v1.imagevault.metadata[0].name
  }
  type = "Opaque"
  data = {
    POSTGRES_USER                    = var.postgres_user
    POSTGRES_DB                      = var.postgres_database
    POSTGRES_PASSWORD                = var.postgres_password
    DATABASE_URL                     = "postgresql+asyncpg://${var.postgres_user}:${urlencode(var.postgres_password)}@postgres:5432/${var.postgres_database}"
    MINIO_ACCESS_KEY                 = var.minio_access_key
    MINIO_SECRET_KEY                 = var.minio_secret_key
    JWT_SECRET                       = var.jwt_secret
    GF_SECURITY_ADMIN_USER           = var.grafana_admin_user
    GF_SECURITY_ADMIN_PASSWORD       = var.grafana_admin_password
  }
}

data "kubectl_file_documents" "resources" {
  for_each = local.manifest_files
  content  = file("${path.module}/../kubernetes/${each.value}")
}

resource "kubectl_manifest" "resources" {
  for_each  = local.manifests
  yaml_body = each.value

  depends_on = [
    kubernetes_namespace_v1.imagevault,
    kubernetes_secret_v1.imagevault,
  ]
}
