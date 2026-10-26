# Live demo guide (about 10 minutes)

A script for the Lab 12 presentation. Practise it once the day before.

## Before the presentation

- [ ] The site is deployed, and the **Cloud** page shows five green *Healthy* badges (including *Free AI recognition*).
- [ ] Start the laptop AI worker on the presenting laptop: `python -m app.worker` (see the deployment guide, step 8). It works on the college Wi-Fi too. The Cloud page should show *Laptop worker online*.
- [ ] Open the site once 5 minutes before you present. The free F1 plan sleeps when nobody uses it, and the first request takes about a minute.
- [ ] Clear old demo data: Cloud → Storage → **Delete everything**.
- [ ] Download and unzip [`demo-photos.zip`](../frontend/public/demo-photos.zip) on the presenting laptop (it's also on the website's empty Home page).
- [ ] Optional, and very effective: 2–3 selfies of each team member, taken with their permission.
- [ ] Open these browser tabs: the website, the Azure Portal resource group **imagevault-rg**, Application Insights → *Live metrics*, and GitHub → *Actions*.
- [ ] Have a small code change ready to push (for example, a word on the Home page).

## The script

**1. The problem (30 s).** "Phones and backups fill up with copies: the same photo saved twice, a WhatsApp version, an edited version. ImageVault stores photos in the cloud, finds these duplicates, and uses free AI to organise photos by people and content."

**2. Architecture (1 min).** Open the **Cloud** page. Walk through the diagram: the browser talks to App Service, which uses PostgreSQL, Blob Storage and Application Insights. The AI models run on your laptop, with App Service as backup, so they're free. Point out the live health checks and response times, the **cost card** (this month's real Azure spending, read live from Cost Management, with a forecast for the whole month; it should be about US$0.00 of US$5), and the **storage card**: how much space the photos take, what that costs per month, and how much removing duplicates saved.

**3. Upload (1.5 min).** Go to **Upload** and drag in all 102 demo photos (plus your selfies). As each one finishes, it shows *Saved*, *Exact copy of …* or *99% similar to …*. On the **Home** page, the AI strip counts down while the photos are analysed. Optionally switch to **Live metrics** in the portal to show the requests arriving.

**4. Duplicates (1.5 min).** Open **Duplicates**:
- the fjord group: an exact copy, a WhatsApp-style copy and an edited copy, with the best copy marked;
- click **Compare** on the edited copy and drag the divider: the brightness edit is obvious side by side;
- open any photo and click the full-screen button, then use ← → to flip through the group;
- point out what was *not* matched as a copy: the two different pugs and the two waterfalls;
- scroll to **Bursts**: five pelican photos taken one second apart. The sharp one is first; click **Keep sharpest, delete 4**;
- **Same subject, different shot**: the four Taj Mahal photos, taken from different angles and in different light;
- click **Remove 1 exact copy**, then show the Home page "saved by storing them once" figure.

**5. People (1.5 min).** Open **People**: each person appears once, with how many photos they're in. Open one, click the name and type it in. Then open the cabinet group photo: the outlines lock on to all 23 faces, and the named people are labelled. Kalpana Chawla and Sunita Williams are found in their crew photos too. If you added selfies, show your own team being recognised. To show that mistakes can be fixed: **Merge people** joins two people into one, and on a person's page *Not all the same person?* moves faces to a new person.

**6. Smart search (1 min).** In **Photos**, switch the search to **Smart** and try "cat", "a palace at sunset" and "a man in a suit". Then try "a car": nothing comes back, because there's no car, so it doesn't guess.

**6a. Albums and batch editing (1 min).** Open **Albums**: Beach, Food & drink, Pets, Mountains and the others were made by the AI. Back in **Photos**, sort by *Date taken*, set a date range (for example May 2025: the beach trip), select the photos (click the circle on one, then **Select all**), then **Album → New album** "Beach trip". Select a few more and click **Download** to get them as one ZIP file.

**6a+. Text and clean-up (1 min).** In **Photos**, type "vegas" in the normal search box: the Las Vegas sign is found by the words on it, and when you open it, the words light up and "LAS VEGAS" stays outlined. Search "परिग", "பரங்க", "అంగల" or "ಮಂಟಪ" to find the boards by their Hindi, Tamil, Telugu or Kannada text, and try Smart search "menu with nachos". Click **Text** to show only photos with text. Open the Green Basket receipt from 12 Oct: its QR code is outlined and opens as a link, the phone number has an **Add to contacts** button (a .vcf file) and the date an **Add to calendar** button (a .ics file), every chip has **Copy**, and **Copy** above the text copies all of it. Open **Receipts**: the two Green Basket bills are grouped with their total, and **Download CSV** gives the table as a spreadsheet. On **Duplicates**, *Same meme, different caption* shows the two cat memes. In **Albums**, show *Documents & receipts*, *Screenshots*, *Memes* and *Forwarded*; select a few beach photos, choose **Album**, and pick a suggested name. On **Duplicates**, the **Free up** list shows the biggest space-wasters with what would be kept. Finally, drag a photo you already uploaded onto the page: ImageVault warns that it's already stored instead of uploading it again.

**6b. Edge computing (1 min).** Start the worker with `start-ai-worker.cmd` (icon next to the clock) or show the terminal version printing `[done] photo …` lines as you upload, and the Cloud page's *Laptop worker online*. Flip the **Where the AI runs** switch to *Azure*: the worker prints that it is resting, and App Service does the next upload. Set it back to *Automatic*, press **Ctrl+C** on the worker, and upload one more photo: about 20 seconds later the cloud takes over on its own.

**7. Cloud storage (30 s).** In the portal, go to the storage account, then **Containers → photos**. The `originals/` files are named by their SHA-256 fingerprint (that's why identical photos are stored once), and `faces/` holds the face crops.

**8. Infrastructure as Code (1 min).** Show `infra/main.tf` on GitHub: every resource above is defined in code and created with `terraform apply`. Mention the managed identity (no keys) and the budget alert.

**9. CI/CD (1.5 min).** Push the prepared change. In GitHub → Actions, show the jobs: tests (local and cloud mode, including the AI tests), website build, Terraform check, then deploy with OIDC and the smoke test. When it's done, refresh the site: the change is live, and the Cloud page shows the new commit.

**10. Wrap-up (30 s).** Lessons learned (see the technical design document) and what you'd build next.

## If something goes wrong

- **Site is slow or shows an error:** it's waking up. Wait 60 seconds and refresh.
- **AI card says "Getting ready":** after the very first deployment, the models (240 MB) are being downloaded. This takes 1–2 minutes, once.
- **A service shows "Problem":** the error text on the card says why. Check the Web App → Log stream.
- **The deploy job is skipped:** the GitHub secrets aren't set (deployment guide, step 5).
- **No internet:** run it locally with `python -m app` and present in local mode (the AI works offline once the models are downloaded).
