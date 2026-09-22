from __future__ import annotations

import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path


ROOT = Path(__file__).resolve().parent
APP = ROOT / "app.py"
LOG = ROOT / "data" / "streamlit.log"
HOST = "127.0.0.1"
PORT = 8501
URL = f"http://localhost:{PORT}"


def port_is_open() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.4)
        return sock.connect_ex((HOST, PORT)) == 0


def start_streamlit() -> None:
    LOG.parent.mkdir(exist_ok=True)
    creationflags = 0
    if sys.platform.startswith("win"):
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS

    with LOG.open("a", encoding="utf-8") as log:
        subprocess.Popen(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                str(APP),
                "--server.port",
                str(PORT),
                "--server.headless",
                "true",
            ],
            cwd=ROOT,
            stdout=log,
            stderr=log,
            stdin=subprocess.DEVNULL,
            creationflags=creationflags,
            close_fds=False,
        )


def main() -> None:
    if not port_is_open():
        start_streamlit()
        for _ in range(30):
            if port_is_open():
                break
            time.sleep(0.5)

    webbrowser.open(URL)


if __name__ == "__main__":
    main()
