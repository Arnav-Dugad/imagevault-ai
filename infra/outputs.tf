output "website_url" {
  value = "https://${azurerm_linux_web_app.main.default_hostname}"
}

output "web_app_name" {
  value = azurerm_linux_web_app.main.name
}

output "github_setup_commands" {
  description = "Run these once so GitHub Actions can deploy to Azure"
  value       = <<-EOT
    gh variable set AZURE_WEBAPP_NAME --body ${azurerm_linux_web_app.main.name}
    gh secret set AZURE_CLIENT_ID --body ${azurerm_user_assigned_identity.github.client_id}
    gh secret set AZURE_TENANT_ID --body ${data.azurerm_client_config.current.tenant_id}
    gh secret set AZURE_SUBSCRIPTION_ID --body ${var.subscription_id}
  EOT
}
