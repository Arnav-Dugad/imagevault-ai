# Changelog

## 3.5.0 (2026-10-25)

- **Storage card** on the Cloud page: a chart of the space used by photos, thumbnails and face crops, the estimated monthly cost, and how much removing duplicates has saved (in MB and money).
- **Cost forecast:** the cost card shows what the month will cost at the current rate, marked on the budget bar.
- **Costs in rupees:** Azure for Students bills in US dollars; the website converts every cost to ₹ at today's exchange rate (from a free rate service, with a fixed fallback).
- **Delete everything:** one click (plus a confirmation) clears all photos, people and albums, for a fresh demo.
- The Duplicates page shows the space saved so far; album tiles show their size.
- Keyboard shortcuts removed; selecting all and deleting are done with buttons.
- Polish: the selection bar and album menu fit on phones, tidier photo filters on small screens, 10 recent photos on Home.
- New setup guide (PDF) for running ImageVault on your computer and on Azure.

## 3.4.0 (2026-10-25)

- **Batch editing:** select photos (click the circle, Shift-click for a range, or Select all) and favourite, add to an album, remove from an album, download as a ZIP, or delete them together.
- **Albums:** create, rename and delete your own albums, plus automatic ones made by the AI: Beach, Mountains, Food & drink, Pets, Wildlife, City, Landmarks, Nature, Snow, Sunsets and People.
- **Bursts:** photos taken seconds apart are grouped on the Duplicates page with the sharpest first, and one click keeps only the sharpest. Duplicate groups also show which copy is sharpest.
- **Fix the AI's mistakes:** merge people who are the same person, or split faces that belong to someone else. Your corrections stay when new photos are analysed.
- **Browsing:** sort by date taken, upload date, size or name; filter by a date range (uses the camera date when there is one); favourites; three thumbnail sizes; infinite scrolling. Sort, filter and size are remembered.
- **Quality of life:** drop photos anywhere to upload, with progress shown in the sidebar; rename a photo by clicking its name; back-to-top button; page names in the browser tab; short confirmation messages.
- **Demo photos:** 83 photos (was 32): beaches, food, pets, wildlife, mountains, cities, sunsets, a 5-shot burst, more copies, and NASA portraits of Kalpana Chawla and Sunita Williams.
- Shorter text across the site. 27 automated tests.

## 3.3.0 (2026-10-25)

- **Live Azure cost card** on the Cloud page: this month's spending for the project, by service, against the US$5 budget, read from Azure Cost Management with the website's managed identity (Terraform grants the read-only *Cost Management Reader* role). Cached for an hour.
- **Compare slider** on the Duplicates page: drag a divider across a photo and its copy (or same-subject shot) to see exactly how they differ.
- **Full-screen viewer:** a full-screen button (or the F key), and ← → / swipe to move between photos in the viewer and in full screen.
- Login blocks an address for 15 minutes after 5 wrong passwords.

## 3.2.0 (2026-10-25)

**AI on your laptop, Azure for everything else** (edge computing), plus guards that keep Azure credit use at about zero.

- New `python -m app.worker`: your laptop analyses new photos for the live website, connecting straight to the Azure database and Blob Storage (about 10× faster than the free cloud plan).
- Laptop first, cloud as backup: while the laptop is online the website leaves new photos to it, and it takes over automatically about 20 seconds after the laptop stops. Heartbeats and atomic claims mean no photo is analysed twice.
- Terraform: a database firewall rule for your IP address and Blob access for your `az login` account (`laptop_worker = true`), plus a `laptop_worker_env` output for the worker's settings.
- Cost guards: hard daily caps on Log Analytics and Application Insights (0.1 GB/day), and the budget alert lowered to US$5. The deployment guide has a new "Keeping your credit safe" section, including pausing the database.
- The Cloud page shows whether the AI runs on your laptop or in App Service, and the architecture diagram includes the laptop.
- 5 new tests for the laptop/cloud hand-over (19 in total).

## 3.1.0 (2026-10-22)

**Free AI recognition**, running inside the app: no paid AI service, nothing sent to third parties.

- **People:** faces are found (YuNet) and recognised (SFace), so the same person is grouped across photos, even in group photos. People can be named, and photo outlines show who is where.
- **Smart search:** find photos by describing them ("a cat", "a palace at sunset"). Searches for something that isn't in any photo return nothing instead of guesses.
- **Same subject, different shot:** CLIP suggests different photos of the same scene. They're shown separately from copies and never deleted automatically.
- AI analysis runs in the background with live progress on the Home page, and appears as a fifth service on the Cloud page.
- Models are downloaded once from pinned versions and verified by SHA-256 (about 190 MB); they use about 320 MB of memory, so they fit the free App Service plan.
- The demo zip now has 32 photos, including Taj Mahal shots, cats and public-domain portraits for the People page.
- Three new tests use real public-domain photos; the CI pipeline caches the models.

## 3.0.0 (2026-10-22)

ImageVault is now a cloud website on Microsoft Azure, built to the CCD mini-project guidelines.

- **Website on Azure App Service**, replacing the desktop app.
- **Azure Database for PostgreSQL** stores photo data (SQLite is still used when running locally).
- **Azure Blob Storage** holds photos and thumbnails, accessed with a managed identity, so no keys are needed.
- **Application Insights** monitors requests, errors and logs.
- **Terraform** (`infra/`) creates every Azure resource, including a **budget with email alerts**.
- **GitHub Actions CI/CD:** tests run in local and cloud mode (PostgreSQL + Azure Storage emulator). Pushes to `main` deploy to Azure with passwordless OIDC sign-in, followed by a smoke test.
- **New Cloud page** with live health and response time of each Azure service, an architecture diagram and the deployed commit.
- **Real demo photos** (from Unsplash) with exact, resized, compressed and edited copies plus look-alikes, downloadable from the website.
- Clearer duplicate review: the best copy is chosen by resolution and quality, and every other photo is labelled by how it relates to it.
- New docs: Azure deployment guide, technical design document, demo guide.
- Removed: the Windows desktop app, PyInstaller packaging and the in-app Azure connection form.

## 2.0.0 (2026-10-22)

Simple Windows desktop app (FastAPI + SQLite + React) with optional Azure Blob Storage, replacing the multi-container 1.x stack.

## 1.x

Multi-container edition (PostgreSQL, Redis, Celery, MinIO, CLIP, Kubernetes, Terraform). Available in the git history and older releases.
