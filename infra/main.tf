# Everything ImageVault needs on Azure. Create it with:  terraform init  then  terraform apply
#
#   Resource group ─┬─ App Service plan + Linux Web App (Python)  ← runs the website
#                   ├─ Storage account + "photos" container       ← stores photos (Blob Storage)
#                   ├─ PostgreSQL Flexible Server + database      ← stores photo details
#                   ├─ Log Analytics workspace + Application Insights ← monitoring (capped, so always free)
#                   ├─ Managed identity for GitHub Actions        ← passwordless deployments
#                   ├─ Access for your laptop's AI worker         ← "edge" AI, optional
#                   └─ Monthly budget with email alerts           ← cost control

data "azurerm_client_config" "current" {}

resource "random_string" "suffix" {
  length  = 5
  upper   = false
  special = false
}

resource "random_password" "database" {
  length  = 32
  special = false # letters and numbers only, so it is safe inside a connection URL
}

locals {
  name = "imagevault-${random_string.suffix.result}"
  tags = { project = "imagevault" }
}

resource "azurerm_resource_group" "main" {
  name     = "imagevault-rg"
  location = var.location
  tags     = local.tags
}

# --- Blob Storage: the photos ---------------------------------------------------

resource "azurerm_storage_account" "photos" {
  name                            = "imagevault${random_string.suffix.result}"
  resource_group_name             = azurerm_resource_group.main.name
  location                        = azurerm_resource_group.main.location
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  min_tls_version                 = "TLS1_2"
  allow_nested_items_to_be_public = false
  tags                            = local.tags
}

resource "azurerm_storage_container" "photos" {
  name                  = "photos"
  storage_account_id    = azurerm_storage_account.photos.id
  container_access_type = "private"
}

# --- PostgreSQL: photo details and duplicate matches ------------------------------

resource "azurerm_postgresql_flexible_server" "main" {
  name                          = "${local.name}-db"
  resource_group_name           = azurerm_resource_group.main.name
  location                      = azurerm_resource_group.main.location
  version                       = "16"
  sku_name                      = "B_Standard_B1ms"
  storage_mb                    = 32768
  backup_retention_days         = 7
  administrator_login           = "imagevault"
  administrator_password        = random_password.database.result
  public_network_access_enabled = true
  tags                          = local.tags

  lifecycle {
    ignore_changes = [zone] # Azure picks an availability zone; don't fight it
  }
}

resource "azurerm_postgresql_flexible_server_database" "main" {
  name      = "imagevault"
  server_id = azurerm_postgresql_flexible_server.main.id
  charset   = "UTF8"
  collation = "en_US.utf8"
}

# 0.0.0.0 is Azure's special rule for "allow other Azure services", such as App Service.
resource "azurerm_postgresql_flexible_server_firewall_rule" "azure_services" {
  name             = "allow-azure-services"
  server_id        = azurerm_postgresql_flexible_server.main.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}

# --- Monitoring -----------------------------------------------------------------

resource "azurerm_log_analytics_workspace" "main" {
  name                = "${local.name}-logs"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "PerGB2018"
  retention_in_days   = 30
  daily_quota_gb      = 0.1 # hard cap: 3 GB a month at most, well inside the 5 GB free allowance
  tags                = local.tags
}

resource "azurerm_application_insights" "main" {
  name                 = "${local.name}-insights"
  resource_group_name  = azurerm_resource_group.main.name
  location             = azurerm_resource_group.main.location
  workspace_id         = azurerm_log_analytics_workspace.main.id
  application_type     = "web"
  daily_data_cap_in_gb = 0.1
  tags                 = local.tags
}

# --- App Service: the website -------------------------------------------------------

resource "azurerm_service_plan" "main" {
  name                = "${local.name}-plan"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  os_type             = "Linux"
  sku_name            = var.app_service_sku
  tags                = local.tags
}

resource "azurerm_linux_web_app" "main" {
  name                = local.name
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  service_plan_id     = azurerm_service_plan.main.id
  https_only          = true
  tags                = local.tags

  # Deployments use GitHub Actions with a managed identity, so password-based publishing is turned off.
  ftp_publish_basic_authentication_enabled       = false
  webdeploy_publish_basic_authentication_enabled = false

  identity {
    type = "SystemAssigned" # lets the website use Blob Storage without any keys
  }

  site_config {
    always_on        = false # not available on the free F1 plan
    ftps_state       = "Disabled"
    app_command_line = "python -m uvicorn app.server:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips=*"
    application_stack {
      python_version = "3.12"
    }
  }

  app_settings = {
    SCM_DO_BUILD_DURING_DEPLOYMENT        = "true" # install requirements.txt on deploy
    DATABASE_URL                          = "postgresql+psycopg://${azurerm_postgresql_flexible_server.main.administrator_login}:${random_password.database.result}@${azurerm_postgresql_flexible_server.main.fqdn}:5432/${azurerm_postgresql_flexible_server_database.main.name}?sslmode=require"
    AZURE_STORAGE_ACCOUNT_URL             = azurerm_storage_account.photos.primary_blob_endpoint
    AZURE_STORAGE_CONTAINER               = azurerm_storage_container.photos.name
    APPLICATIONINSIGHTS_CONNECTION_STRING = azurerm_application_insights.main.connection_string
    APP_PASSWORD                          = var.app_password
    IMAGEVAULT_MODEL_DIR                  = "/home/models" # free AI models, downloaded once and kept across restarts
  }
}

resource "azurerm_role_assignment" "web_reads_and_writes_blobs" {
  scope                = azurerm_storage_account.photos.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_linux_web_app.main.identity[0].principal_id
}

# --- GitHub Actions: passwordless deployment with OpenID Connect ----------------------

resource "azurerm_user_assigned_identity" "github" {
  name                = "${local.name}-github"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  tags                = local.tags
}

resource "azurerm_federated_identity_credential" "github_main" {
  name      = "github-main-branch"
  parent_id = azurerm_user_assigned_identity.github.id
  audience  = ["api://AzureADTokenExchange"]
  issuer    = "https://token.actions.githubusercontent.com"
  subject   = "repo:${var.github_repository}:ref:refs/heads/main"
}

resource "azurerm_role_assignment" "github_deploys_website" {
  scope                = azurerm_resource_group.main.id
  role_definition_name = "Website Contributor"
  principal_id         = azurerm_user_assigned_identity.github.principal_id
}

# --- Laptop AI worker ("edge computing", optional) -------------------------------------------
# Lets the computer that runs `terraform apply` run `python -m app.worker`. If your IP address
# changes (for example, on another Wi-Fi), run `terraform apply` again to update the rule.

data "http" "my_ip" {
  count = var.laptop_worker ? 1 : 0
  url   = "https://api.ipify.org"
}

resource "azurerm_postgresql_flexible_server_firewall_rule" "laptop" {
  count            = var.laptop_worker ? 1 : 0
  name             = "laptop-ai-worker"
  server_id        = azurerm_postgresql_flexible_server.main.id
  start_ip_address = trimspace(data.http.my_ip[0].response_body)
  end_ip_address   = trimspace(data.http.my_ip[0].response_body)
}

resource "azurerm_role_assignment" "laptop_reads_and_writes_blobs" {
  count                = var.laptop_worker ? 1 : 0
  scope                = azurerm_storage_account.photos.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = data.azurerm_client_config.current.object_id # your own "az login" account
}

# --- Budget alert: email when spending reaches 50%, 80% or (forecast) 100% ------------------

resource "azurerm_consumption_budget_resource_group" "main" {
  count             = var.create_budget ? 1 : 0
  name              = "imagevault-monthly-budget"
  resource_group_id = azurerm_resource_group.main.id
  amount            = var.monthly_budget
  time_grain        = "Monthly"

  time_period {
    start_date = formatdate("YYYY-MM-01'T'00:00:00Z", timestamp())
  }

  notification {
    threshold      = 50
    operator       = "GreaterThanOrEqualTo"
    threshold_type = "Actual"
    contact_emails = [var.alert_email]
  }

  notification {
    threshold      = 80
    operator       = "GreaterThanOrEqualTo"
    threshold_type = "Actual"
    contact_emails = [var.alert_email]
  }

  notification {
    threshold      = 100
    operator       = "GreaterThanOrEqualTo"
    threshold_type = "Forecasted"
    contact_emails = [var.alert_email]
  }

  lifecycle {
    ignore_changes = [time_period] # the start date is only needed when the budget is created
  }
}
