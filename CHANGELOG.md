# Changelog

## 3.10.1 (2026-10-26)

A polish pass over every page, on a computer and on a phone, with automatic checks for console errors, sideways scrolling, unlabelled buttons and small tap targets.

- **Photos of a person** are cropped around their face, so heads are no longer cut off.
- **Phones:** the Home numbers sit two by two; the search box fits (Name/Smart become icons); the menu slides in from the side; the Select circle on each photo is bigger and always visible on touch screens; "Free up" tick boxes and the back links are easier to tap; the Upload page says "Tap to choose photos".
- **Free up** lists the ticked photos first.
- **Clearer numbers on Home:** "Photo files" (each file stored once) next to the photos' size with copies.
- **Browser tabs** show the album's or person's name.
- **People page** explains that you can name and merge people.
- Every photo button has a label for screen readers; with "reduce motion" on, the scanning line stands still.

## 3.10.0 (2026-10-26)

- **Check and correct receipts:** click a receipt to see the photo next to what was read, with the shop, date and total outlined on the photo. Fix any of them by hand, go back to the AI's reading, or say "Not a receipt". Photos the AI missed can be added with "This is a receipt".
- **Items on receipts** are read ("Basmati Rice 5kg – ₹450"), and the Receipts page shows **what you buy most**. Prices are matched to their items by where they are on the photo, even when it is a little turned.
- **UPI payment screenshots** count as receipts: who was paid, when and how much.
- **The same receipt photographed twice** is counted once, and offered on the Duplicates page.
- **A scanning line** sweeps over a photo while the AI reads it; the photo viewer updates by itself when it's done.
- **Bigger chips you can swipe** on phones (phone numbers, QR codes, dates and prices).
- **Failed uploads shake**, and an upload that works on a second try flashes green.
- Fixed: a phone number could run on into the next line ("98450 12345 08"); on phones, long chips pushed the photo details off the screen.
- Malayalam and Gujarati are not read: PaddleOCR has no trained model for either.
- Demo photos: 104, with the same bill photographed twice and a made-up UPI payment screenshot. 48 automated tests.

## 3.9.0 (2026-10-26)

- **Receipts page:** the shop, date and total of each receipt in a small spending table, grouped by shop, with totals, each shop's share of the spending and a CSV download.
- **Kannada text** is read too (PaddleOCR's Kannada model, converted for the app).
- **Save a phone number as a contact** (.vcf) and **add a date to your calendar** (.ics) from the photo viewer.
- **QR codes** are read, outlined on the photo and can be opened. Their text is searchable.
- **Copy button on every chip** (phone numbers, dates, prices, emails, links, QR codes); long lists show the first 8.
- **"Text" filter** on the Photos page: only photos with text in them.
- **Same meme, different caption:** the Duplicates page groups memes made from the same picture.
- **Failed uploads** are listed in the upload panel with the reason, and a Retry button for the ones that can work on a second try (not for files that aren't photos or are too big).
- Fixed: a total printed before its "TOTAL" label wasn't read; screenshots full of words also landed in Documents & receipts.
- Demo photos: 102, with made-up receipts from two made-up shops, a second cat meme and a Kannada temple notice. 44 automated tests.

## 3.8.0 (2026-10-25)

- **Telugu text** is read too, next to English, Hindi and Tamil.
- **Better English reading:** PaddleOCR's reader keeps capitals, spaces and punctuation, is twice as fast and much smaller than the old one.
- **Phone numbers, dates, prices, emails and links** are picked out of the text and shown as chips: tap to call, email or open, or click to copy.
- **Copy the text** of a photo with one click.
- **Matching words are outlined on thumbnails** in search results, not just in the photo viewer.
- **Memes and Forwarded** albums (WhatsApp, Telegram and Signal images, or heavily compressed images without camera details). Both are offered, unticked, in the "Free up" list.
- **Album name suggestions** from the words in the photos, what they show and when they were taken.
- Fixed: dropping photos on the Upload page left the "Drop to upload" overlay on top of the queue.
- New upload panel in the corner while photos upload, on every page and on phones.
- Long word lists in the viewer are shortened, with "Show all".
- Demo photos: 97, with a Telugu station board, memes and WhatsApp-style forwards. 40 automated tests.

## 3.7.2 (2026-10-25)

- Fixed: a photo rejected from an outdated laptop worker now goes back in the queue instead of being marked failed, and each worker run has its own name, so two workers on one laptop can't hide each other's stuck photos.

## 3.7.1 (2026-10-25)

- Fixed: a laptop worker started before an update kept running the old code and saved photos without their text positions. Workers now report which analysis version they run; older ones get no photos (and the website takes over in Automatic mode), and photos analysed by an older version are analysed again automatically.

## 3.7.0 (2026-10-25)

- **Hindi and Tamil text:** two more free readers (PaddleOCR PP-OCRv3, Apache 2.0) read Devanagari and Tamil on signs and boards, next to English. Search works in all three scripts.
- **Matching words are highlighted** on the photo when you open it from a search, and all the words light up one after another as the photo opens. Hover a word in the list to see where it is.
- **Smart search uses the text in photos:** "menu with nachos" finds a menu board that says nachos.
- **New automatic albums:** Documents & receipts, and Screenshots. Screenshots are also offered, unticked, in the "Free up" list.
- **Tray app for the laptop worker:** double-click `start-ai-worker.cmd` for an icon next to the clock with Start, Stop, Open ImageVault and "Start when Windows starts".
- **Storage bar in the sidebar:** space used, the monthly cost in rupees, and a bar against Azure's 5 GB free allowance.
- Better and faster English reading: lines are cut into separate words before reading ("TOTAL 14.21 CASH" instead of nonsense), and the reader runs about 7 times faster.
- Polish: the "Free up" heading counts only ticked photos; stronger outlines for matched words.
- Demo photos: 92, with a receipt, a typed letter, a menu board and two screenshots. 37 automated tests.

## 3.6.1 (2026-10-25)

- Fixed: on Azure, the website's AI worker could get stuck on one photo while a laptop worker was also sending results. OpenCV now runs single-threaded, face crops are uploaded before the database transaction, database lock waits give up after 30 seconds, and a photo held by a silent worker is handed to the laptop. If a photo ever takes over 5 minutes, the stack of every thread is written to the log.

## 3.6.0 (2026-10-25)

- **Laptop AI works on any Wi-Fi:** `python -m app.worker` now talks to the website over HTTPS, like a browser, instead of connecting to the database. It only needs the website address and password, and Terraform no longer opens the database to your home IP address.
- **Switch for where the AI runs** on the Cloud page: Automatic (laptop first, Azure as backup), My laptop, or Azure.
- **Text in photos is searchable (OCR):** free PP-OCR and CRNN models read words on signs, boards and receipts; the normal search box finds them, and the photo viewer lists them.
- **Biggest space-wasters:** the Duplicates page lists lower-quality copies, blurrier burst shots and very blurry photos, biggest first, with what will be kept, ready to delete together.
- **Warning before uploading a photo that's already stored:** the browser checks each file's fingerprint first; you can skip them or upload anyway.
- Demo photos: 87, including four photos with readable signs.
- 33 automated tests.

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
