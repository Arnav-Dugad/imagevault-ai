# Cost analysis

The main deployment uses Azure for Students credit, not unlimited free hosting. The offer and regional quotas can change: check the [current student offer](https://azure.microsoft.com/free/students/) and Azure pricing calculator before provisioning.

| Component | Cost consideration |
|---|---|
| Ubuntu VM, default 8 GiB | Consumes student credit while allocated; needed for CPU image models |
| Managed OS disk | Billed while the VM is stopped/deallocated too |
| Public IP | Can have ongoing charges even while compute is stopped |
| Azure Blob Storage | Stored originals, thumbnails, transactions, download traffic and retained soft-deleted data |
| PostgreSQL, Redis, Caddy, API, worker | Run on the same VM; no separate managed database/queue bill |
| OpenCLIP, OCR, face recognition | Inference uses VM compute; no hosted AI API fee |
| GitHub CI and release downloads | Subject to applicable repository usage limits |

Keep the spending limit enabled, inspect actual cost in the Azure portal, and deallocate compute between rehearsals. The template schedules daily shutdown; it does not restart the VM for class. To end ongoing disk/IP/storage charges, remove resources after taking necessary backups. Per-user upload quotas limit original file sizes, not the entire Azure bill.

Five application containers replace the previous seven in the Azure deployment. PostgreSQL, Redis and the worker remain separate because this protects data integrity, background processing and responsiveness. Optional Kubernetes/Terraform/local monitoring examples do not need to run for the classroom website.

The local MinIO alternative has no Azure usage bill when it runs solely on existing hardware; hardware, electricity and internet still have costs. It is a development or rubric extension, not the primary public website deployment.
