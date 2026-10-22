# Puts ImageVault online as a website with Azure App Service (Free F1 plan).
# Read docs/azure.md first. Run it from the project folder in PowerShell:
#
#   az login
#   .\packaging\deploy-azure.ps1 -Name my-imagevault-123 -Password "choose-a-password"
#
# Your site will be at https://<Name>.azurewebsites.net

param(
    [Parameter(Mandatory = $true)] [string] $Name,      # must be unique across all of Azure
    [Parameter(Mandatory = $true)] [string] $Password,  # visitors need it to open the site
    [string] $Location = "centralindia",
    [string] $ResourceGroup = "imagevault-rg",
    [string] $Sku = "F1"                                # F1 is free; B1 is faster but uses credit
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

function Check($step) {
    if ($LASTEXITCODE -ne 0) { throw "Step failed: $step" }
}

Write-Host "1/4 Building the website..." -ForegroundColor Cyan
Push-Location "$root\frontend"
npm ci; Check "npm ci"
npm run build; Check "npm run build"
Pop-Location

Write-Host "2/4 Preparing the files to upload..." -ForegroundColor Cyan
$stage = Join-Path $env:TEMP "imagevault-deploy"
Remove-Item $stage -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory $stage | Out-Null
Copy-Item "$root\app" $stage -Recurse
Copy-Item "$root\requirements.txt" $stage
Get-ChildItem $stage -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force

Write-Host "3/4 Creating the Azure resources and uploading (takes a few minutes)..." -ForegroundColor Cyan
az group create --name $ResourceGroup --location $Location --output none; Check "az group create"
Push-Location $stage
az webapp up --name $Name --resource-group $ResourceGroup --location $Location `
    --runtime "PYTHON:3.12" --sku $Sku --output none
Check "az webapp up"
Pop-Location

Write-Host "4/4 Configuring the app..." -ForegroundColor Cyan
az webapp config set --name $Name --resource-group $ResourceGroup `
    --startup-file "python -m app --server" --output none
Check "az webapp config set"
az webapp config appsettings set --name $Name --resource-group $ResourceGroup --output none `
    --settings "IMAGEVAULT_DATA_DIR=/home/imagevault" "APP_PASSWORD=$Password"
Check "az webapp config appsettings set"

Write-Host ""
Write-Host "Done! Open https://$Name.azurewebsites.net (the first visit can take a minute)." -ForegroundColor Green
Write-Host "Tip: in the site's Settings page, connect your Azure Storage account to keep photos in Blob Storage."
