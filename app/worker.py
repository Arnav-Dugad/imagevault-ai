"""Run the free AI on your laptop for the ImageVault website on Azure ("edge computing").

    python -m app.worker

Your laptop logs in to the website over HTTPS, just like your browser does, asks for photos that
need analysing (people, smart search, same subject, text), runs the AI models on them and sends back
what it found. Because it only needs normal web access, it works on any Wi-Fi: at home, in the
college lab, or on a phone hotspot. While it runs, the website leaves new photos to it; when you stop
it (Ctrl+C), the website goes back to doing the work itself, so nothing breaks.

The first time, it asks for the website's address and password and saves them in worker.env
(which git ignores). The Cloud page has a switch to choose where the AI runs.
"""

import getpass
import http.cookiejar
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ENV_FILE = Path("worker.env")
IDLE_SECONDS = 3      # how often to ask for new photos when there is nothing to do
OFFLINE_SECONDS = 10  # how long to wait before trying again when the website can't be reached


def load_env_file(path: Path) -> None:
    """Read KEY=value lines into the environment."""
    raw = path.read_bytes()
    encoding = "utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"  # PowerShell may write UTF-16
    for line in raw.decode(encoding).splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"'))


def ask_for_settings() -> None:
    """First run: ask for the website and its password, and offer to remember them."""
    print("Which ImageVault website should this laptop work for?")
    url = input("  Website address (e.g. https://imagevault-xxxxx.azurewebsites.net): ").strip()
    password = getpass.getpass("  Website password (hidden while you type): ")
    os.environ["IMAGEVAULT_URL"], os.environ["IMAGEVAULT_PASSWORD"] = url, password
    if input("  Remember these in worker.env? [Y/n] ").strip().lower() in ("", "y", "yes"):
        ENV_FILE.write_text(f"IMAGEVAULT_URL={url}\nIMAGEVAULT_PASSWORD={password}\n", encoding="utf-8")
        print("  Saved. (worker.env is never uploaded to GitHub.)\n")


class Website:
    """A tiny HTTPS client that logs in once and keeps the session cookie, like a browser."""

    def __init__(self, url: str, password: str):
        self.url = url.rstrip("/")
        if not self.url.startswith("http"):
            self.url = f"https://{self.url}"
        self.password = password
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def _send(self, path: str, body: dict | None = None, retry: bool = True) -> bytes:
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(self.url + path, data=data, method="POST" if data is not None else "GET",
                                         headers={"Content-Type": "application/json"})
        try:
            with self.opener.open(request, timeout=120) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 401 and retry:  # session expired (for example, the website restarted): log in again
                self.login()
                return self._send(path, body, retry=False)
            raise

    def login(self) -> None:
        try:
            self._send("/api/login", {"password": self.password}, retry=False)
        except urllib.error.HTTPError as exc:
            detail = json.loads(exc.read() or b"{}").get("detail", exc.reason)
            sys.exit(f"Could not log in: {detail}\n"
                     "Check the password in worker.env (or delete the file to enter it again).")

    def post(self, path: str, body: dict) -> dict:
        return json.loads(self._send(path, body))

    def download(self, path: str) -> bytes:
        return self._send(path)


def main() -> None:
    if ENV_FILE.exists():
        load_env_file(ENV_FILE)
    if not os.environ.get("IMAGEVAULT_URL"):
        ask_for_settings()
    os.environ.setdefault("IMAGEVAULT_AI", "on")

    from app import ai, intelligence

    site = Website(os.environ["IMAGEVAULT_URL"], os.environ.get("IMAGEVAULT_PASSWORD", ""))
    print("ImageVault laptop AI worker")
    print(f"  Website: {site.url}")
    if not ai.models_ready():
        print("  Downloading the AI models (about 225 MB, once)...")
        ai.download_models()
    site.login()
    name = socket.gethostname()
    print("  Connected. Press Ctrl+C to stop; the website takes over again when you stop.\n")

    last_note = ""

    def note(message: str) -> None:  # print a status line only when it changes
        nonlocal last_note
        if message != last_note:
            print(f"[status] {message}")
            last_note = message

    try:
        while True:
            try:
                reply = site.post("/api/worker/next", {"name": name})
            except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
                note(f"Can't reach the website ({getattr(exc, 'reason', exc)}). Trying again...")
                time.sleep(OFFLINE_SECONDS)
                continue
            photo = reply["photo"]
            if photo is None:
                note("The Cloud page is set to run the AI on Azure, so this laptop is resting."
                     if reply["mode"] == "azure" else "Waiting for new photos.")
                time.sleep(IDLE_SECONDS)
                continue
            note("Working")
            started = time.perf_counter()
            try:
                found = intelligence.compute(site.download(photo["file_url"]))
                site.post(f"/api/worker/result/{photo['id']}", found.to_json())
                words = f", {len(found.text.split())} words" if found.text else ""
                print(f"[done]   photo {photo['id'][:8]}: {len(found.faces)} faces{words} "
                      f"({time.perf_counter() - started:.1f} s)")
            except Exception as exc:  # one bad photo must not stop the worker
                print(f"[failed] photo {photo['id'][:8]}: {exc}")
                try:
                    site.post(f"/api/worker/failed/{photo['id']}", {})
                except Exception:
                    pass
    except KeyboardInterrupt:
        print("\nStopped. The website will analyse new photos itself.")


if __name__ == "__main__":
    main()
