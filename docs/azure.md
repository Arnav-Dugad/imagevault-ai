# Using ImageVault with Microsoft Azure

This guide assumes you have never used Azure before. You need an Azure account. **Azure for Students** works well: it gives you free credit and needs no credit card.

There are two separate things you can do:

| | What it does | Cost |
|---|---|---|
| **Part 1: Cloud photo storage** (recommended) | Your photos are saved in Azure Blob Storage instead of on your computer. | A few cents per month for a few GB of photos, paid from your credit |
| **Part 2: Put ImageVault online** (optional) | ImageVault runs as a website that you can open from any device. | Free (F1 plan) |

---

## Part 1: Store your photos in Azure Blob Storage

**Azure Blob Storage** is Microsoft's service for storing files in the cloud. A *storage account* is your space in it, and a *container* is like a folder inside that space.

### Step 1: Create a storage account

1. Go to **[portal.azure.com](https://portal.azure.com)** and sign in with your student account.
2. In the search bar at the top, type **Storage accounts** and open it.
3. Click **+ Create**.
4. Fill in the **Basics** tab:
   - **Subscription:** *Azure for Students*
   - **Resource group:** click **Create new** and type `imagevault-rg`. A resource group is a box that holds related resources, so you can delete everything at once later.
   - **Storage account name:** something unique using only lowercase letters and numbers, such as `imagevaultarnav123`
   - **Region:** one near you, for example *(Asia Pacific) Central India*
   - **Primary service** (if shown): *Azure Blob Storage or Azure Data Lake Storage Gen 2*
   - **Performance:** *Standard*
   - **Redundancy:** *Locally-redundant storage (LRS)*. This is the cheapest option.
5. Click **Review + create**, then **Create**. Wait about a minute until it says *"Your deployment is complete"*.
6. Click **Go to resource**.

### Step 2: Copy the connection string

The connection string is like a password that lets ImageVault use your storage account.

1. In your storage account's left menu, open **Security + networking → Access keys**.
2. Under **key1**, find **Connection string** and click **Show**.
3. Click the copy icon next to it. It starts with `DefaultEndpointsProtocol=https;AccountName=…`

> **Keep it secret.** Anyone with this string can read and delete your files. Don't post it online or commit it to GitHub. If it leaks, click **Rotate key** on the same page to make a new one.

### Step 3: Connect ImageVault

1. Open ImageVault and go to **Settings**.
2. Paste the connection string. Leave the container name as `photos`.
3. Click **Connect to Azure**. ImageVault tests the connection and creates the container for you.

The sidebar now shows **New photos are saved to: Azure**. Upload a photo, then back in the Azure Portal open **Data storage → Containers → photos**. Your photo is there. Its name is its SHA-256 fingerprint, which is how ImageVault stores identical photos only once.

**Good to know**

- Photos you uploaded *before* connecting stay on your computer, and both kinds keep working.
- If you **Disconnect**, new photos go to your computer again. Photos in Azure aren't deleted, but they can't be opened until you reconnect.
- The connection string is saved in `settings.json` in your ImageVault data folder.

---

## Part 2 (optional): Put ImageVault online with Azure App Service

**Azure App Service** runs web apps for you. With this, ImageVault becomes a website at `https://<your-name>.azurewebsites.net`, protected by a password you choose.

You need the project's source code on your computer (see [Run from source](../README.md#run-from-source)) and the **Azure CLI**, a command-line tool for Azure.

### Step 1: Install the Azure CLI and sign in

Open PowerShell and run:

```powershell
winget install -e --id Microsoft.AzureCLI
```

Close and reopen PowerShell, then sign in. A browser window opens; choose your student account:

```powershell
az login
```

### Step 2: Deploy

In PowerShell, go to the project folder and run the deploy script. Choose your own site name (letters, numbers and hyphens, unique across Azure) and a password:

```powershell
cd path\to\imagevault-ai
.\packaging\deploy-azure.ps1 -Name imagevault-arnav -Password "pick-a-good-password"
```

The script builds the website, creates a free App Service plan and uploads the app. This takes 3 to 5 minutes. When it finishes, open `https://imagevault-arnav.azurewebsites.net` and log in with your password.

Then open **Settings** on the website and connect your storage account (Part 1), so the photos are kept in Blob Storage.

**If something goes wrong**

- *"PowerShell cannot run scripts"*: run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, then try again.
- *"The name is already taken"*: choose a different `-Name`.
- *Quota or SKU error for F1*: try another region with `-Location southindia` (or `eastus`), or the paid plan with `-Sku B1` (about US$13/month from your credit).
- *Site shows an error page*: wait a minute and refresh, because the first start is slow. In the portal, open your App Service, then **Log stream**, to see what's happening.
- The free F1 plan sleeps when unused and allows 60 CPU minutes a day. That's fine for a demo, but slow for heavy use.

### Updating the website later

Run the same command again. Your photos and settings are kept.

---

## Cleaning up (stop all costs)

When you're done with the project, delete everything in one go:

1. In the portal, search for **Resource groups** and open **imagevault-rg**.
2. Click **Delete resource group**, type its name and confirm.

This deletes the storage account (and all photos in it) and the website.
