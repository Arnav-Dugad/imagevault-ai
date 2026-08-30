variable "kubeconfig_path" {
  description = "Path to the local Kubernetes configuration."
  type        = string
  default     = "~/.kube/config"
}

variable "kube_context" {
  description = "Local Kubernetes context to manage."
  type        = string
  default     = "minikube"
}

variable "postgres_user" {
  type    = string
  default = "imagevault"
}

variable "postgres_database" {
  type    = string
  default = "imagevault"
}

variable "postgres_password" {
  description = "Random local PostgreSQL password. Pass via TF_VAR_postgres_password."
  type        = string
  sensitive   = true
}

variable "minio_access_key" {
  type    = string
  default = "imagevault"
}

variable "minio_secret_key" {
  description = "Random local MinIO secret. Pass via TF_VAR_minio_secret_key."
  type        = string
  sensitive   = true
}

variable "jwt_secret" {
  description = "At least 48 random characters. Pass via TF_VAR_jwt_secret."
  type        = string
  sensitive   = true
  validation {
    condition     = length(var.jwt_secret) >= 48
    error_message = "jwt_secret must contain at least 48 characters."
  }
}

variable "grafana_admin_user" {
  type    = string
  default = "admin"
}

variable "grafana_admin_password" {
  description = "Random local Grafana password. Pass via TF_VAR_grafana_admin_password."
  type        = string
  sensitive   = true
}
