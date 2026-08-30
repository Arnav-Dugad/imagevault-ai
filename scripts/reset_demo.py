#!/usr/bin/env python3
"""Delete images owned by one local demo account through the protected API."""

import argparse

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()
    print("WARNING: This permanently deletes every image owned by the supplied local account.")
    if input(f"Type DELETE {args.email} to continue: ").strip() != f"DELETE {args.email}":
        raise SystemExit("Reset cancelled; no data was changed.")

    with httpx.Client(base_url=args.base_url, timeout=30) as client:
        login = client.post("/api/auth/login", json={"email": args.email, "password": args.password})
        login.raise_for_status()
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        deleted = 0
        while True:
            response = client.get("/api/images?page=1&page_size=100", headers=headers)
            response.raise_for_status()
            items = response.json()["items"]
            if not items:
                break
            for image in items:
                deletion = client.delete(f"/api/images/{image['id']}?confirm=true", headers=headers)
                deletion.raise_for_status()
                deleted += 1
        print(f"Deleted {deleted} images. The account itself was preserved.")


if __name__ == "__main__":
    main()
