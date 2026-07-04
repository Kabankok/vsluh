# -*- coding: utf-8 -*-
"""Простой лог в %TEMP%\\vsluh.log — для диагностики (хоткей, захват, синтез)."""
import os
import time
from pathlib import Path

LOG = Path(os.environ.get("TEMP", "/tmp")) / "vsluh.log"


def log(msg):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%H:%M:%S')} {msg}\n")
    except Exception:
        pass
