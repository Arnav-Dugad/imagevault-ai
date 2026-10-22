"""Start ImageVault.

  python -m app             open ImageVault in its own app window
  python -m app --browser   open ImageVault in your web browser instead
  python -m app --server    run as a website (used on Azure App Service)
"""

import argparse
import os
import socket
import sys
import threading
import time
import webbrowser

import uvicorn

from app.config import data_dir


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="ImageVault photo vault")
    parser.add_argument("--browser", action="store_true", help="open in the web browser instead of an app window")
    parser.add_argument("--server", action="store_true", help="run as a website on 0.0.0.0:$PORT")
    args = parser.parse_args()

    if sys.stdout is None:  # the packaged Windows app has no console, so log to a file
        sys.stdout = sys.stderr = open(data_dir() / "imagevault.log", "a", buffering=1, encoding="utf-8")

    from app.server import app

    if args.server:
        port = int(os.environ.get("PORT", "8000"))
        # Azure App Service forwards HTTPS traffic through its own proxy, so trust its headers.
        uvicorn.run(app, host="0.0.0.0", port=port, proxy_headers=True, forwarded_allow_ips="*")
        return

    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.05)
    url = f"http://127.0.0.1:{port}"

    if not args.browser:
        try:
            import webview

            webview.settings["ALLOW_DOWNLOADS"] = True
            webview.create_window("ImageVault", url, width=1280, height=820, min_size=(900, 600))
            webview.start()
            server.should_exit = True
            return
        except Exception as exc:  # no app window available on this computer: fall back to the browser
            print(f"Could not open the app window ({exc}); opening the browser instead.")

    print(f"ImageVault is running at {url}  (press Ctrl+C to stop)")
    webbrowser.open(url)
    try:
        thread.join()
    except KeyboardInterrupt:
        server.should_exit = True


if __name__ == "__main__":
    main()
