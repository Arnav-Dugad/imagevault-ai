"""Run the free AI on your laptop for the ImageVault website on Azure ("edge computing").

    python -m app.worker        in a terminal
    pythonw -m app.tray         as a small icon next to the clock, with Start and Stop (see app/tray.py)

Your laptop logs in to the website over HTTPS, just like your browser does, asks for photos that
need analysing (people, smart search, same subject, text), runs the AI models on them and sends back
what it found. Because it only needs normal web access, it works on any Wi-Fi: at home, in the
college lab, or on a phone hotspot. While it runs, the website leaves new photos to it; when you stop
it, the website goes back to doing the work itself, so nothing breaks.

The first time, it asks for the website's address and password and saves them in worker.env
(which git ignores). The Cloud page has a switch to choose where the AI runs.
"""

import getpass
import http.cookiejar
import json
import os
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parent.parent / "worker.env"
IDLE_SECONDS = 3      # how often to ask for new photos when there is nothing to do
OFFLINE_SECONDS = 10  # how long to wait before trying again when the website can't be reached


class LoginError(Exception):
    pass


def load_env_file(path: Path) -> None:
    """Read KEY=value lines into the environment."""
    raw = path.read_bytes()
    encoding = "utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"  # PowerShell may write UTF-16
    for line in raw.decode(encoding).splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"'))


def save_settings(url: str, password: str) -> None:
    ENV_FILE.write_text(f"IMAGEVAULT_URL={url}\nIMAGEVAULT_PASSWORD={password}\n", encoding="utf-8")
    os.environ["IMAGEVAULT_URL"], os.environ["IMAGEVAULT_PASSWORD"] = url, password


def ask_for_settings() -> None:
    """First run in a terminal: ask for the website and its password, and offer to remember them."""
    print("Which ImageVault website should this laptop work for?")
    url = input("  Website address (e.g. https://imagevault-xxxxx.azurewebsites.net): ").strip()
    password = getpass.getpass("  Website password (hidden while you type): ")
    os.environ["IMAGEVAULT_URL"], os.environ["IMAGEVAULT_PASSWORD"] = url, password
    if input("  Remember these in worker.env? [Y/n] ").strip().lower() in ("", "y", "yes"):
        save_settings(url, password)
        print("  Saved. (worker.env is never uploaded to GitHub.)\n")


class Website:
    """A tiny HTTPS client that logs in once and keeps the session cookie, like a browser."""

    def __init__(self, url: str, password: str):
        self.url = url.strip().rstrip("/")
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
            raise LoginError(f"Could not log in: {detail}") from exc

    def post(self, path: str, body: dict) -> dict:
        return json.loads(self._send(path, body))

    def download(self, path: str) -> bytes:
        return self._send(path)


class Runner:
    """The worker loop. `stop()` ends it from another thread (the tray icon's Stop button)."""

    def __init__(self, site: Website, on_status=print, on_done=None):
        self.site = site
        self.on_status = on_status
        self.on_done = on_done or (lambda photo_id, faces, words, seconds: None)
        self.stopping = threading.Event()
        self.analysed = 0
        self._last = ""

    def stop(self) -> None:
        self.stopping.set()

    def _note(self, message: str) -> None:  # report a status only when it changes
        if message != self._last:
            self._last = message
            self.on_status(message)

    def run(self) -> None:
        from app import ai, intelligence

        if not ai.models_ready():
            self._note("Downloading the AI models (about 245 MB, once)")
            ai.download_models()
        self.site.login()
        name = socket.gethostname()
        while not self.stopping.is_set():
            try:
                reply = self.site.post("/api/worker/next", {"name": name})
            except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
                self._note(f"Can't reach the website ({getattr(exc, 'reason', exc)}). Trying again...")
                self.stopping.wait(OFFLINE_SECONDS)
                continue
            photo = reply["photo"]
            if photo is None:
                self._note("Resting: the Cloud page is set to run the AI on Azure"
                           if reply["mode"] == "azure" else "Waiting for new photos")
                self.stopping.wait(IDLE_SECONDS)
                continue
            self._note("Working")
            started = time.perf_counter()
            try:
                found = intelligence.compute(self.site.download(photo["file_url"]))
                self.site.post(f"/api/worker/result/{photo['id']}", found.to_json())
                self.analysed += 1
                self.on_done(photo["id"], len(found.faces), len(found.words), time.perf_counter() - started)
            except Exception as exc:  # one bad photo must not stop the worker
                self.on_status(f"Photo {photo['id'][:8]} failed: {exc}")
                try:
                    self.site.post(f"/api/worker/failed/{photo['id']}", {})
                except Exception:
                    pass
        self._note("Stopped")


def main() -> None:
    if ENV_FILE.exists():
        load_env_file(ENV_FILE)
    if not os.environ.get("IMAGEVAULT_URL"):
        ask_for_settings()
    os.environ.setdefault("IMAGEVAULT_AI", "on")

    site = Website(os.environ["IMAGEVAULT_URL"], os.environ.get("IMAGEVAULT_PASSWORD", ""))
    print("ImageVault laptop AI worker")
    print(f"  Website: {site.url}")
    print("  Press Ctrl+C to stop; the website takes over again when you stop.\n")

    def done(photo_id: str, faces: int, words: int, seconds: float) -> None:
        print(f"[done]   photo {photo_id[:8]}: {faces} faces{f', {words} words' if words else ''} ({seconds:.1f} s)")

    runner = Runner(site, on_status=lambda message: print(f"[status] {message}"), on_done=done)
    try:
        runner.run()
    except LoginError as exc:
        sys.exit(f"{exc}\nCheck the password in worker.env (or delete the file to enter it again).")
    except KeyboardInterrupt:
        print("\nStopped. The website will analyse new photos itself.")


if __name__ == "__main__":
    main()
