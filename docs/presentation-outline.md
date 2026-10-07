# ImageVault AI presentation outline

Updated 7 October 2026 for application 1.2.1. Use real deployment screenshots and measured results. State “deployment planned” until the Azure website has been tested.

| Slide | Content and evidence |
|---|---|
| 1. Title | Azure-hosted private media vault; student, department and supervisor placeholders |
| 2. Problem | Duplicate backups/exports, difficult search and risks of relying on semantic resemblance |
| 3. Objectives | Private storage, explainable review, async processing and reproducible cloud deployment |
| 4. Main user flow | Upload → Gallery → Duplicate review → Dashboard; advanced features listed briefly |
| 5. Azure architecture | Browser → Caddy/API/worker/PostgreSQL/Redis on VM → private Blob; use architecture diagram |
| 6. Identity/security | HTTPS, VM managed identity, Blob contributor role, expiring SAS, invite signup, user isolation |
| 7. Detection evidence | SHA exact bytes; multi-hash plus aligned-pixel near duplicates; semantic manual suggestions |
| 8. Reliability | Pair-complete families, visible enrichment warnings, smart-index retry, durable object cleanup |
| 9. DevOps/delivery | Bicep, cloud-init, Compose, GitHub Actions and checksum-verified compiled releases |
| 10. Live demo/results | Six synthetic examples, confirmed exact-copy cleanup, passing CI and actual deployment checks |
| 11. Cost/limits | Student credit, 8 GiB CPU VM, shutdown/deallocation, retained disk/IP/storage costs; single VM |
| 12. Conclusion/future work | Backups/restore, independent evaluation, larger-library scale and account recovery |

For a five-minute presentation use [demo-script.md](demo-script.md). Keep OCR, people, video and optional local Kubernetes/Terraform/monitoring for questions or a separate rubric section.

Evidence to capture after Azure connection:

- HTTPS site and authenticated System status reporting Azure Blob.
- Private Blob container and VM managed identity role assignment.
- Exact-copy and verified near-duplicate evidence, and guarded deletion.
- Actual passing GitHub Actions run and release/source metadata.
- Resource group, daily shutdown, remaining credit and measured usage.
- Database/media backup and persistence verification.

Do not label screenshot evidence as a live demo, turn synthetic regression counts into a universal accuracy percentage, or describe all Azure resources as permanently free.