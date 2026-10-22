"""Run ImageVault on your computer:  python -m app   then open http://127.0.0.1:8000

On Azure, App Service starts it with uvicorn instead (see infra/main.tf).
"""

import os

import uvicorn


def main() -> None:
    port = int(os.environ.get("PORT", "8000"))
    print(f"ImageVault is running at http://127.0.0.1:{port}  (press Ctrl+C to stop)")
    uvicorn.run("app.server:app", host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
