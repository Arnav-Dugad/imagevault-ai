#!/usr/bin/env python3
"""Generate small, presentation-safe API traffic for Prometheus and Grafana."""

import argparse
import time
from pathlib import Path

import httpx


def authenticate(client: httpx.Client, email: str, password: str) -> str:
    login = client.post("/api/auth/login", json={"email": email, "password": password})
    if login.status_code == 401:
        login = client.post(
            "/api/auth/register",
            json={"email": email, "display_name": "Demo Operator", "password": password},
        )
    login.raise_for_status()
    return login.json()["access_token"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost")
    parser.add_argument("--email", default="demo@imagevault.local")
    parser.add_argument("--password", required=True, help="Password for the local demo account")
    parser.add_argument("--iterations", type=int, default=20)
    parser.add_argument("--interval", type=float, default=0.4)
    parser.add_argument("--images", type=Path, default=Path("demo-images"))
    args = parser.parse_args()
    if not 1 <= args.iterations <= 500:
        raise SystemExit("--iterations must be between 1 and 500")

    with httpx.Client(base_url=args.base_url, timeout=30) as client:
        token = authenticate(client, args.email, args.password)
        headers = {"Authorization": f"Bearer {token}"}
        images = list(args.images.glob("*")) if args.images.exists() else []
        if images:
            files = [("files", (path.name, path.read_bytes(), "image/png" if path.suffix == ".png" else "image/jpeg")) for path in images]
            response = client.post("/api/images/upload", headers=headers, files=files)
            print(f"Upload batch: HTTP {response.status_code}")
        for index in range(args.iterations):
            health = client.get("/health/live")
            gallery = client.get("/api/images?page_size=12", headers=headers)
            dashboard = client.get("/api/dashboard", headers=headers)
            print(
                f"{index + 1:03d}: health={health.status_code} "
                f"gallery={gallery.status_code} dashboard={dashboard.status_code}"
            )
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
