"""Run the free AI on your laptop for the ImageVault website on Azure ("edge computing").

    python -m app.worker

Your laptop connects to the same PostgreSQL database and Blob Storage as the website, analyses
new photos (people, smart search, same subject) and saves the results there. While it runs, the
website leaves new photos to it, which keeps the free App Service plan light. When you stop it
(Ctrl+C), the website goes back to doing the work itself, so nothing breaks.

Setup (once, see docs/azure-deployment.md, step 8):
  1. az login                                        (your laptop uses your Azure account for Blob Storage)
  2. cd infra
     terraform output -raw laptop_worker_env | Out-File -Encoding utf8 ..\\worker.env
"""

import os
import sys
from pathlib import Path

ENV_FILE = Path("worker.env")


def load_env_file(path: Path) -> None:
    """Read KEY=value lines (from `terraform output`) into the environment."""
    raw = path.read_bytes()
    encoding = "utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"  # PowerShell may write UTF-16
    for line in raw.decode(encoding).splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"'))


def main() -> None:
    if ENV_FILE.exists():
        load_env_file(ENV_FILE)
    if not os.environ.get("DATABASE_URL"):
        sys.exit("No database settings found. Create worker.env first: see docs/azure-deployment.md, step 8.")
    os.environ.setdefault("IMAGEVAULT_AI", "on")

    from sqlalchemy import make_url

    from app import intelligence
    from app.database import init_db
    from app.storage import get_storage

    print("ImageVault laptop AI worker")
    url = make_url(os.environ["DATABASE_URL"])
    print(f"  Database: {url.host or url.database}")
    try:
        init_db()
        print(f"  Storage:  {get_storage().description}")
    except Exception as exc:
        sys.exit(f"\nCould not connect: {exc}\n\nCheck that you ran 'az login', and that your current IP address "
                 "is allowed (run 'terraform apply' again in infra/ after your IP changes).")
    print("  Press Ctrl+C to stop. The website takes over again when you stop.\n")
    try:
        intelligence.run_worker(
            "laptop",
            on_status=lambda message: print(f"[status] {message}"),
            on_done=lambda photo_id: print(f"[done]   analysed photo {photo_id[:8]}"),
            poll_seconds=3,
        )
    except KeyboardInterrupt:
        print("\nStopped. The website will analyse new photos itself.")


if __name__ == "__main__":
    main()
