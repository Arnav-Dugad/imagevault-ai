variable "subscription_id" {
  description = "Your Azure subscription ID (run: az account show --query id -o tsv)"
  type        = string
}

variable "location" {
  description = "Azure region. If you get a 'region not allowed' error, try another one (e.g. southindia, eastus)."
  type        = string
  default     = "centralindia"
}

variable "app_password" {
  description = "Password visitors must enter to open the website"
  type        = string
  sensitive   = true
}

variable "alert_email" {
  description = "Email address that receives budget alerts"
  type        = string
}

variable "monthly_budget" {
  description = "Monthly budget in your billing currency (USD for Azure for Students); alerts at 50%, 80% and 100%"
  type        = number
  default     = 10
}

variable "create_budget" {
  description = "Set to false if your subscription type does not support Cost Management budgets"
  type        = bool
  default     = true
}

variable "app_service_sku" {
  description = "App Service plan size: F1 is free, B1 is faster (about US$13/month)"
  type        = string
  default     = "F1"
}

variable "github_repository" {
  description = "GitHub repository (owner/name) allowed to deploy to Azure"
  type        = string
  default     = "Arnav-Dugad/imagevault-ai"
}
