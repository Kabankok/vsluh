# -*- coding: utf-8 -*-
"""Открыть страницу настроек в браузере, взяв порт и токен из runtime.json
(его пишет движок при старте)."""
import json
import sys
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    rt_path = ROOT / "runtime.json"
    for _ in range(15):  # движок мог ещё не подняться
        if rt_path.exists():
            try:
                rt = json.loads(rt_path.read_text(encoding="utf-8"))
                webbrowser.open(f"http://127.0.0.1:{rt['port']}/settings?t={rt['token']}")
                return
            except Exception:
                pass
        time.sleep(1)
    print("«Вслух» ещё не запущен. Сначала запустите start.bat.")
    sys.exit(1)


if __name__ == "__main__":
    main()
