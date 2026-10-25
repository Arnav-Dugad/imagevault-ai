"""The laptop AI worker as a small icon next to the clock, with Start and Stop.

    pythonw -m app.tray          (or double-click start-ai-worker.cmd)

Right-click the icon to start or stop the AI worker, open ImageVault, or quit. The icon is green while
the worker runs, grey when it is stopped and orange when something needs attention. The first time,
a small window asks for the website address and password (saved in worker.env, which git ignores).
"""

import os
import sys
import threading
import webbrowser
from pathlib import Path

from PIL import Image, ImageDraw

from app import worker

COLOURS = {"running": "#b9f36a", "stopped": "#949ba6", "problem": "#ff8d6b"}
STARTUP = Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs/Startup/ImageVault AI.cmd"


def icon_image(state: str) -> Image.Image:
    """A rounded square with a small photo frame, coloured by state."""
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((2, 2, 62, 62), radius=14, fill="#111419", outline=COLOURS[state], width=4)
    draw.rounded_rectangle((16, 18, 48, 46), radius=4, outline=COLOURS[state], width=4)
    draw.polygon([(20, 42), (29, 31), (36, 38), (40, 34), (45, 42)], fill=COLOURS[state])
    draw.ellipse((37, 22, 43, 28), fill=COLOURS[state])
    return image


def ask_for_settings() -> bool:
    """A small window for the website address and password. Returns False if cancelled."""
    import tkinter as tk
    from tkinter import simpledialog

    root = tk.Tk()
    root.withdraw()
    url = simpledialog.askstring("ImageVault AI", "Website address\n(e.g. https://imagevault-xxxxx.azurewebsites.net)",
                                 parent=root)
    password = simpledialog.askstring("ImageVault AI", "Website password", show="*", parent=root) if url else None
    root.destroy()
    if not url or password is None:
        return False
    worker.save_settings(url.strip(), password)
    return True


class Tray:
    def __init__(self):
        import pystray

        self.pystray = pystray
        self.runner: worker.Runner | None = None
        self.status = "Stopped"
        self.state = "stopped"
        self.icon = pystray.Icon("imagevault-ai", icon_image("stopped"), "ImageVault AI: stopped", menu=self._menu())

    def _menu(self):
        item, menu = self.pystray.MenuItem, self.pystray.Menu
        return menu(
            item(lambda _: self.status, None, enabled=False),
            item(lambda _: f"Photos analysed: {self.runner.analysed if self.runner else 0}", None, enabled=False),
            menu.SEPARATOR,
            item("Start", lambda: self.start(), enabled=lambda _: not self.running, default=True),
            item("Stop", lambda: self.stop(), enabled=lambda _: self.running),
            item("Open ImageVault", lambda: webbrowser.open(os.environ.get("IMAGEVAULT_URL", ""))),
            item("Start when Windows starts", lambda: self.toggle_startup(), checked=lambda _: STARTUP.exists(),
                 visible=sys.platform == "win32"),
            item("Change website or password", lambda: self.change_settings()),
            menu.SEPARATOR,
            item("Quit", lambda: self.quit()),
        )

    @property
    def running(self) -> bool:
        return self.runner is not None and not self.runner.stopping.is_set()

    def show(self, status: str, state: str | None = None) -> None:
        self.status = status
        if state:
            self.state = state
            self.icon.icon = icon_image(state)
        self.icon.title = f"ImageVault AI: {status}"[:120]
        self.icon.update_menu()

    def start(self) -> None:
        if self.running:
            return
        if not os.environ.get("IMAGEVAULT_URL") and not ask_for_settings():
            return
        site = worker.Website(os.environ["IMAGEVAULT_URL"], os.environ.get("IMAGEVAULT_PASSWORD", ""))
        self.runner = worker.Runner(site, on_status=lambda message: self.show(message),
                                    on_done=lambda *_: self.icon.update_menu())
        self.show("Starting", "running")
        threading.Thread(target=self._run, args=(self.runner,), daemon=True).start()

    def _run(self, runner: worker.Runner) -> None:
        try:
            runner.run()
            if runner is self.runner:
                self.show("Stopped", "stopped")
        except worker.LoginError as exc:
            runner.stop()
            self.show("Wrong password: choose 'Change website or password'", "problem")
            self.icon.notify(str(exc), "ImageVault AI")
        except Exception as exc:  # keep the icon alive and show what went wrong
            runner.stop()
            self.show(f"Stopped: {exc}"[:100], "problem")

    def stop(self) -> None:
        if self.runner:
            self.runner.stop()
        self.show("Stopping", "stopped")

    def change_settings(self) -> None:
        was_running = self.running
        self.stop()
        if ask_for_settings() and was_running:
            self.start()

    def toggle_startup(self) -> None:
        if STARTUP.exists():
            STARTUP.unlink()
        else:
            pythonw = Path(sys.executable).with_name("pythonw.exe")
            project = Path(__file__).resolve().parent.parent
            STARTUP.write_text(f'@echo off\ncd /d "{project}"\nstart "" "{pythonw}" -m app.tray\n', encoding="utf-8")
        self.icon.update_menu()

    def quit(self) -> None:
        if self.runner:
            self.runner.stop()
        self.icon.stop()

    def run(self) -> None:
        self.icon.run(setup=lambda icon: (setattr(icon, "visible", True), self.start()))


def main() -> None:
    if worker.ENV_FILE.exists():
        worker.load_env_file(worker.ENV_FILE)
    os.environ.setdefault("IMAGEVAULT_AI", "on")
    try:
        import pystray  # noqa: F401
    except ImportError:
        sys.exit("The tray icon needs one more package:  pip install pystray")
    Tray().run()


if __name__ == "__main__":
    main()
