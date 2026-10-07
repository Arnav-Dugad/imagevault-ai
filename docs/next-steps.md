# Make ImageVault simpler: suggested next steps

These are recommendations, not features already added. Start by completing and
testing the existing Azure website before adding more services or AI models.

## Keep the main purpose clear

Focus on four things: **upload photos, browse photos, find duplicates, and confirm
cleanup**. Keep the four main pages. Exact copies should be the easiest result to
understand; near duplicates and similar content should always need a closer look.

## Add next, in this order

| Priority | Addition | Why it helps |
|---|---|---|
| 1 | A Trash page with a short undo period | People can recover a mistaken deletion; Blob soft delete alone does not restore the app's metadata |
| 2 | A simple backup/export button and restore instructions | Users need a way to recover their account and photos if the VM disk fails |
| 3 | One clearly labelled retry button on a failed photo | Users should not need to understand “reindex” or rerun the whole library to retry one file |
| 4 | One Windows deployment script | Turns the long copy/paste setup into a few prompts while preserving preview, subscription choice and spending warnings |
| 5 | A small, separate set of labeled real photos for evaluation | Shows what detection actually gets right or wrong instead of adding another model |

Trash and backups need both database records and stored objects. Keep user
confirmation and ownership checks, and test restoring a file before relying on it.

## Remove or postpone complexity

- **Videos and camera RAW:** consider supporting JPG, PNG and WebP first. Video
  processing adds codecs, large uploads and slower analysis. Keep the code only
  if these formats are needed for the project assessment.
- **Face recognition and automatic people albums:** keep them under Advanced or
  postpone them. They need model downloads, correction controls and extra testing.
- **Smart search, OCR, events and bursts:** choose the one extra feature your
  demonstration needs. Make the others optional so basic duplicate processing
  can work without loading every model.
- **Kubernetes, Terraform, Prometheus and Grafana:** keep the Azure path on
  Bicep/Compose. Move these local examples out of the main setup unless the course
  rubric requires them. Do not remove required academic material without checking.
- **Overlapping setup guides:** make the Windows guide the one starting point,
  with links to advanced operations. Avoid repeating the same commands in several
  documents because they can drift apart.
- **Technical wording in the app:** use “Retry analysis,” “Exact copy,” and
  “Similar photo.” Keep model names, thresholds and deployment details in Advanced.

## Do not remove these

Keep private storage, ownership checks, invitation signup, upload limits, HTTPS,
confirmed deletion and automatic cleanup retries. Keep PostgreSQL and the worker
separate: uploads should stay responsive while analysis runs. Keep an offline/local
development option if it helps rehearsal, even when Azure is the main deployment.

## A practical next version

An easy-to-explain version is **a private photo vault with safe duplicate cleanup,
Trash, and backups**. Finish that before adding mobile apps, more cloud services,
new AI models or public signup. Deployment, private previews, persistence and a
real restore still need verification on the student's Azure subscription.
