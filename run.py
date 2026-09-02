"""防災調整池 計算ソフト — 起動ランチャー。

サーバーを起動し、既定のブラウザで自動的に画面を開きます。

使い方:
    python run.py       （または python3 run.py）
"""
import threading
import webbrowser

import uvicorn

HOST = "127.0.0.1"
PORT = 8000


def _open_browser() -> None:
    webbrowser.open(f"http://{HOST}:{PORT}")


if __name__ == "__main__":
    threading.Timer(1.5, _open_browser).start()
    uvicorn.run("app.main:app", host=HOST, port=PORT)
