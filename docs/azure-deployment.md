# Deploying ImageVault to Azure

This guide assumes you have never used Azure, Terraform or GitHub Actions before. It takes about 30 minutes the first time. You need an **Azure for Students** account (or any Azure subscription) and a GitHub account with access to this repository.

When you're done:

- the website runs at `https://imagevault-xxxxx.azurewebsites.net`, behind a password you choose;
- every `git push` to `main` is tested and deployed automatically;
- you get an email if spending reaches your budget.

## What gets created

Terraform (`infra/main.tf`) creates everything in one resource group called **imagevault-rg**:

| Resource | Size | Cost on Azure for Students |
|---|---|---|
| App Service plan + Linux Web App | F1 (free) | Free |
| Azure Database for PostgreSQL Flexible Server | Burstable B1ms, 32 GB | Free for 12 months under Azure's free services (750 h/month); otherwise about US$13–15/month from your credit |
| Storage account (Blob) | Standard LRS | A few cents per GB per month |
| Log Analytics + Application Insights | Pay-as-you-go, **capped at 0.1 GB a day** | Free: the cap keeps it under the 5 GB/month free allowance |
| Free AI recognition (CLIP, YuNet, SFace, PaddleOCR text readers) | Runs on your laptop, or in the Web App | Free: no AI service is created or billed |
| Managed identity for GitHub Actions | | Free |
| Budget with email alerts | ₹450 (about US$5) a month, in the billing currency | Free |

**Expected total: US$0 a month during your first year** (only a few cents for storage). Azure for Students has no credit card, so real money can never be charged: if your US$100 credit ran out, Azure would switch the resources off rather than bill you.

> **Budget caution (course guideline 7):** check your remaining credit in the [Azure for Students portal](https://portal.azure.com/#view/Microsoft_Azure_Education/EducationMenuBlade/~/overview). Terraform creates a monthly budget (default ₹450, about US$5; the amount is in your billing currency) that emails you at 50%, at 80%, and when spending is forecast to reach 100%. See [keeping your credit safe](#keeping-your-credit-safe) below, and when the project is finished, run `terraform destroy` (step 7).

---

## Step 1: Install the tools

Open **PowerShell** and run these three commands. Each one installs a program:

```powershell
winget install -e --id Microsoft.AzureCLI      # "az": talks to Azure
winget install -e --id Hashicorp.Terraform     # "terraform": creates the infrastructure
winget install -e --id GitHub.cli              # "gh": talks to GitHub
```

Close PowerShell and open it again so the new commands are found. Check they work:

```powershell
az version; terraform version; gh --version
```

## Step 2: Sign in

```powershell
az login        # a browser opens: pick your Azure for Students account
gh auth login   # choose GitHub.com → HTTPS → Login with a web browser
```

Show your subscription ID (you need it in the next step):

```powershell
az account show --query id -o tsv
```

## Step 3: Fill in your settings

```powershell
cd path\to\imagevault-ai\infra
copy terraform.tfvars.example terraform.tfvars
notepad terraform.tfvars
```

Fill in:

- `subscription_id`: the ID from step 2
- `app_password`: the password people will type to open the website
- `alert_email`: where budget alerts are sent

`terraform.tfvars` holds secrets and is listed in `.gitignore`, so it is never uploaded to GitHub.

## Step 4: Create the infrastructure

```powershell
terraform init     # downloads the Azure plugin (once)
terraform plan     # shows what will be created; nothing changes yet
terraform apply    # type "yes" to create everything (about 10 minutes, mostly the database)
```

When it finishes, Terraform prints `website_url`. The site shows a default Azure page until the first deployment (step 6).

**If `terraform apply` fails:**

- *"RequestDisallowedByAzure" / region not allowed*: student subscriptions only allow some regions. Add `location = "southindia"` (or `eastus`, `westeurope`) to `terraform.tfvars` and run `terraform apply` again. To see your allowed regions, open the portal, go to **Policy → Assignments**, and look at *Allowed resource deployment regions*.
- *Error about the budget / Cost Management*: some subscription types don't support budgets through the API. Add `create_budget = false` to `terraform.tfvars`, run `terraform apply` again, then create a budget by hand: open the portal, search **Budgets**, then click **+ Add**.
- *PostgreSQL "location is restricted"*: try a different `location`, as above.
- *Quota error for the F1 plan*: you can have only one free F1 plan per region. Use another region, or `app_service_sku = "B1"`.

Running `terraform apply` again is always safe: it only creates what is missing.

## Step 5: Connect GitHub Actions to Azure

GitHub Actions deploys with **OpenID Connect**: GitHub proves its identity to Azure, so no password is stored anywhere. Terraform already created the Azure side. Now tell GitHub which identity to use:

```powershell
terraform output -raw github_setup_commands
```

This prints four `gh` commands. Copy them, run them in the repository folder (`cd ..`), and check:

```powershell
gh secret list; gh variable list
```

You should see `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` and the variable `AZURE_WEBAPP_NAME`.

## Step 6: Deploy

Push any commit to `main`, or start the pipeline by hand:

```powershell
gh workflow run ci-cd.yml
gh run watch
```

The **CI/CD** workflow:

1. runs the tests twice: with SQLite, and with PostgreSQL plus the Azure Storage emulator;
2. lints and builds the website, and checks the Terraform code;
3. signs in to Azure with OIDC and deploys to App Service (Azure installs `requirements.txt` during deployment);
4. calls `/api/health` on the live site until it answers (smoke test).

Then open your `website_url`, log in with your `app_password`, and visit the **Cloud** page. All four Azure services should say **Healthy**, along with the commit that was deployed.

The first start after a deployment can take 1–2 minutes on the free plan. On the very first start, the app also downloads its free AI models (about 190 MB) into `/home/models`; meanwhile, the AI card on the Cloud page says *Getting ready*. They're kept across restarts and deployments. All together, the app uses about 320 MB of the free plan's 1 GB of memory.

## Step 7: Monitoring, and cleaning up

**Monitoring:** in the portal, open **imagevault-rg**, then the Application Insights resource:

- **Live metrics**: requests as they happen (try uploading during the demo)
- **Failures** and **Performance**: errors and slow requests
- **Logs**: run `traces | where message has "Photo uploaded"` to see each upload

**App logs:** open the Web App, then **Log stream**.

**Delete everything** when the course is over (this removes all photos too):

```powershell
cd infra
terraform destroy
```

## Step 8 (recommended): Run the AI on your laptop

Your laptop can do the AI work (people, smart search, same subject, text in photos) instead of Azure. It's much faster, and it keeps the small free App Service plan light. This is **edge computing**: processing happens near the user, and the cloud stores the results.

The laptop worker talks to your website over **HTTPS**, exactly like a browser, so it works on **any Wi-Fi** (home, college lab, phone hotspot). It never needs the database password or storage keys.

**Each time** (for example, before your demo), with your virtual environment activated:

```powershell
python -m app.worker
```

The first time, it asks for your `website_url` and `app_password` and offers to save them in `worker.env` (git ignores this file). It prints a line for every photo it analyses, and the website's **Cloud** page shows *Laptop worker online*. Press **Ctrl+C** to stop.

**As an icon next to the clock (Windows):** double-click `start-ai-worker.cmd` in the project folder (or run `pythonw -m app.tray`). The worker starts, and right-clicking the icon gives **Start**, **Stop**, **Open ImageVault**, **Change website or password**, **Start when Windows starts** and **Quit**. The icon is green while it works, grey when stopped and orange if something needs attention.

You can also write `worker.env` from Terraform:

```powershell
cd infra
terraform output -raw laptop_worker_env | Out-File -Encoding utf8 ..\worker.env
cd ..
```

**Where the AI runs** is a switch on the **Cloud** page:

- **Automatic** (default): your laptop while its worker is running, otherwise Azure. When you stop the laptop, the website takes over within about 20 seconds.
- **My laptop**: only your laptop. New photos wait until you start the worker.
- **Azure**: only App Service. A running laptop worker rests.

## Keeping your credit safe

Everything is chosen to stay inside the free allowances. These habits make sure of it:

- **Check spending weekly:** in the portal, search **Cost Management**, then open **Cost analysis**. It should show about US$0.
- **Don't change the sizes** in `terraform.tfvars` (`app_service_sku = "F1"`). The B1ms database and 32 GB storage match the free allowance exactly.
- **Pause the database when you won't use the site for a while** (stopped servers don't use compute hours; Azure starts them again automatically after 7 days):

  ```powershell
  az postgres flexible-server stop  --resource-group imagevault-rg --name <your-server-name>
  az postgres flexible-server start --resource-group imagevault-rg --name <your-server-name>
  ```

  Find the server name in the portal under **imagevault-rg**, or with `az postgres flexible-server list -o table`. While it's stopped, the website shows a database error.
- **Delete everything after the course** with `terraform destroy`. After 12 months the free database allowance ends, and it would start using credit (about US$13–15 a month).

---

## How the settings reach the app

Terraform sets these **App Settings** on the Web App. `app/config.py` reads them:

| Setting | Value |
|---|---|
| `DATABASE_URL` | PostgreSQL connection (with `sslmode=require`) |
| `AZURE_STORAGE_ACCOUNT_URL` | The Blob endpoint. The app signs in with its **managed identity**, which has the *Storage Blob Data Contributor* role, so no keys are used |
| `AZURE_STORAGE_CONTAINER` | `photos` |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | Where telemetry is sent |
| `APP_PASSWORD` | Website password |
| `IMAGEVAULT_MODEL_DIR` | `/home/models`: where the free AI models are kept (persistent storage) |
| `AZURE_COST_SCOPE`, `MONTHLY_BUDGET` | The resource group and budget for the live cost card. The site reads costs with its managed identity (*Cost Management Reader* role) |
| `SCM_DO_BUILD_DURING_DEPLOYMENT` | Tells Azure to `pip install -r requirements.txt` on deploy |

The startup command is `python -m uvicorn app.server:app --host 0.0.0.0 --port 8000 …` (set in `infra/main.tf`).

**Terraform state:** `terraform apply` writes `infra/terraform.tfstate`, which records what was created and includes secrets. Keep it on your computer (it's ignored by git) and don't delete it, or Terraform can no longer manage the resources. For a team, store it in an Azure Storage *backend* instead; see the [Terraform azurerm backend docs](https://developer.hashicorp.com/terraform/language/backend/azurerm).
