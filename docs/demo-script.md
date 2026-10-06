# Five-minute classroom presentation

## Before class

1. Deploy the Azure website using [azure-students.md](azure-students.md). Start the VM well before presenting; daily shutdown does not automatically start it again.
2. Download the latest GitHub release. It includes six synthetic files under `demo-images/`. Source checkouts can generate them with `python scripts/generate_demo.py` after installing Pillow.
3. Sign in with a demonstration account. Upload `01-original.png` beforehand to download/cache the model, then wait for processing to finish. In **Advanced → System status**, check API, storage, worker, and model. Model downloads require internet access on the VM.
4. Rehearse the remaining five uploads. Check that the resized and JPEG copies show verified near-duplicate evidence, the exact copy shows SHA-256 evidence, and the document is unrelated. The mirrored image may appear as similar content, depending on the model; it must stay for manual review.
5. Clear the rehearsal images, retaining the original, before class. Save screenshots of the successful run and GitHub checks as a fallback if the network fails. Do not claim screenshots are a live demo.

## 0:00–0:40 — Problem and purpose

“People collect repeated photos and waste space. ImageVault stores photos privately, detects identical files with hashes, and finds visually similar content with AI. It is a website, so classmates can use a browser.”

## 0:40–1:40 — Upload

Open **Upload** and add files 02–06. Explain that the exact copy can be identified immediately from SHA-256, while a background worker handles the expensive image analysis. The browser stays responsive.

## 1:40–3:00 — Detection and evidence

Open **Duplicate review**. Show the exact-copy evidence and a resized/recompressed near duplicate. Explain the three levels:

| Result | Meaning | Action |
|---|---|---|
| Exact copy | Identical file bytes | Can select with “Select exact” |
| Near duplicate | Multiple fingerprints and aligned pixels agree | Compare manually |
| Similar content | AI recognizes related content | Keep for manual review |

“An AI similarity score is resemblance, not a probability that deleting the photo is safe. We do not infer a match just because two photos each resemble a third.”

## 3:00–3:40 — Safe cleanup and dashboard

Use **Select exact**, then **Review delete**. Explain what will be removed and show the confirmation. Delete only the demonstration copy. Open **Dashboard** to show storage and upload totals.

## 3:40–4:30 — Architecture

Show the compact diagram in [architecture.md](architecture.md). Five containers run on the VM: Caddy, API, worker, PostgreSQL, and Redis. Private originals are in Azure Blob Storage. Managed identity avoids storage account keys; signed preview links expire.

## 4:30–5:00 — Reproducibility and limits

Show a passing GitHub Actions run and the downloadable release. Explain that Azure for Students credit funds the AI-capable VM; it is not unlimited free hosting. Crops, heavy edits, low-detail pictures, and video can require manual review. Face albums and OCR are advanced features with their own limits, rather than proof that duplicate detection is perfect.

## Optional rubric material

Only if your lecturer requires them, show the existing local Kubernetes/Terraform examples and Prometheus/Grafana monitoring. They are separate extensions, not required to use the Azure website. Keep the main explanation focused on one deployed stack.
