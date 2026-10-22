<p align="center"><img src="packaging/icon.png" width="96" alt="ImageVault icon"></p>

<h1 align="center">ImageVault</h1>

<p align="center">A simple desktop app that keeps your photos in one place and finds duplicates,<br>with optional cloud storage on Microsoft Azure.</p>

<p align="center"><a href="https://github.com/Arnav-Dugad/imagevault-ai/releases/latest"><b>⬇ Download for Windows</b></a></p>

---

## What it does

- **Upload photos** by dragging them into the app (JPG, PNG, WEBP, GIF, BMP).
- **Finds exact copies:** the same file uploaded twice. Each copy is stored only once.
- **Finds similar photos:** resized, compressed or slightly edited versions of the same picture.
- **Review duplicates** side by side and delete the copies you don't need.
- **Store in the cloud (optional):** connect an Azure Storage account and new photos are saved in Azure Blob Storage instead of on your computer.

Everything runs on your own computer. Nothing is sent anywhere unless you connect Azure.

## Download and run (Windows)

1. Go to the [latest release](https://github.com/Arnav-Dugad/imagevault-ai/releases/latest) and download **`ImageVault-…-Windows.exe`**.
2. Double-click it. There is nothing to install.
3. Windows may say *"Windows protected your PC"* because the app isn't code-signed. Click **More info → Run anyway**.

To try duplicate detection straight away, download **`demo-photos.zip`** from the same page, unzip it and upload all the photos.

Your photos and database are kept in `%LOCALAPPDATA%\ImageVault` (the exact path is shown on the Settings page).

## Connect Azure (optional)

Have an Azure account (for example **Azure for Students**)? Open **Settings** in the app and paste your storage account's connection string. The [Azure guide](docs/azure.md) walks you through it step by step, and also shows how to put ImageVault online as a website.

## Run from source

Use this on Mac/Linux, or if you want to change the code. You need [Python 3.11+](https://www.python.org/downloads/) and [Node.js 20+](https://nodejs.org/).

```bash
git clone https://github.com/Arnav-Dugad/imagevault-ai.git
cd imagevault-ai

# 1. Install the Python packages (in a virtual environment)
python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate       # Mac / Linux
pip install -r requirements-dev.txt

# 2. Build the website once
cd frontend
npm install
npm run build
cd ..

# 3. Start the app
python -m app                     # opens the app window
python -m app --browser           # or open it in your web browser
```

**While changing the website**, run the API and the live-reloading website side by side:

```bash
python -m uvicorn app.server:app --reload --port 8000    # terminal 1
cd frontend && npm run dev                               # terminal 2, then open http://localhost:5173
```

**Tests:** `pytest` (backend) and `npm run lint` in `frontend/`.

**Build the Windows app yourself:** `python packaging/build.py` creates `dist/ImageVault.exe`.

## How it works

ImageVault is one Python program (a [FastAPI](https://fastapi.tiangolo.com/) web server with a SQLite database) that serves a React website. The desktop app shows that website in its own window.

To compare photos it uses a SHA-256 fingerprint for exact copies and perceptual hashes for similar photos. [docs/how-it-works.md](docs/how-it-works.md) explains this with diagrams.

```
app/            Python server: API, duplicate detection, storage (local folder or Azure)
frontend/       React website (Vite + Tailwind CSS)
tests/          Automated tests
packaging/      Builds the Windows app and deploys to Azure
demo-photos/    Sample photos for trying duplicate detection
docs/           Azure guide and how-it-works guide
```

## Releasing a new version

1. Update the version in `app/__init__.py` and add a section to `CHANGELOG.md`.
2. Push a tag: `git tag v2.1.0 && git push origin v2.1.0`.
3. GitHub Actions builds the Windows app and publishes the release.

## License

[MIT](LICENSE)
