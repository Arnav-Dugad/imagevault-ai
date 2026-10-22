# Live demo guide (about 8 minutes)

A script for the Lab 12 presentation. Practise it once the day before.

## Before the presentation

- [ ] The site is deployed and the **Cloud** page shows four green *Healthy* badges.
- [ ] Open the site once 5 minutes before you present. The free F1 plan sleeps when nobody uses it, and the first request takes about a minute.
- [ ] Clear old demo data: Duplicates → *Remove exact copies*, then delete the rest from Photos (or start with an empty site).
- [ ] Download and unzip [`demo-photos.zip`](../frontend/public/demo-photos.zip) on the presenting laptop.
- [ ] Open these browser tabs: the website, the Azure Portal resource group **imagevault-rg**, Application Insights → *Live metrics*, and GitHub → *Actions*.
- [ ] Have a small code change ready to push (for example, a word on the Home page).

## The script

**1. The problem (30 s).** "Phones and backups fill up with copies: the same photo saved twice, a WhatsApp version, an edited version. ImageVault stores photos in the cloud and finds these duplicates."

**2. Architecture (1 min).** Open the **Cloud** page. Walk through the diagram: the browser talks to App Service; App Service uses PostgreSQL, Blob Storage and Application Insights. Point out the live health checks and response times.

**3. Upload (1.5 min).** Go to **Upload** and drag in all 17 demo photos. As each one finishes, it shows *Saved*, *Exact copy of …* or *99% similar to …*. Optionally switch to **Live metrics** in the portal to show the requests arriving.

**4. Duplicates (1.5 min).** Open **Duplicates**:
- the fjord group: an exact copy, a WhatsApp-style copy and an edited copy, with the best copy marked;
- point out what was *not* matched: the two different pug photos and the two waterfalls;
- click **Remove 1 exact copy**, then show the Home page "saved by storing them once" figure.

**5. Cloud storage (1 min).** In the portal, go to the storage account, then **Containers → photos → originals**. The files are named by their SHA-256 fingerprint, which is why identical photos are stored once.

**6. Infrastructure as Code (1 min).** Show `infra/main.tf` on GitHub: every resource above is defined in code and created with `terraform apply`. Mention the managed identity (no keys) and the budget alert.

**7. CI/CD (1.5 min).** Push the prepared change. In GitHub → Actions, show the jobs: tests (local and cloud mode), website build, Terraform check, then deploy with OIDC and the smoke test. When it's done, refresh the site: the change is live, and the Cloud page shows the new commit.

**8. Wrap-up (30 s).** Lessons learned (see the technical design document) and what you'd build next.

## If something goes wrong

- **Site is slow or shows an error:** it's waking up. Wait 60 seconds and refresh.
- **A service shows "Problem":** the error text on the card says why. Check the Web App → Log stream.
- **The deploy job is skipped:** the GitHub secrets aren't set (deployment guide, step 5).
- **No internet:** run it locally with `python -m app` and present the Cloud page in local mode.
