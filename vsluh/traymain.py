# -*- coding: utf-8 -*-
"""Трей-процесс «Вслух». Только иконка в трее; всей работой занимается движок
(app.py) в отдельном процессе, с которым трей общается по HTTP на 127.0.0.1.
Здесь нет torch — поэтому pystray работает стабильно."""
import json
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

import pystray
from PIL import Image, ImageDraw
from pystray import Menu, MenuItem

from .tts import VOICES, VOICE_LABELS

BASE = Path(__file__).resolve().parent.parent
POLL_SEC = 2.0


class Client:
    def __init__(self):
        self.port = None
        self.token = None
        self.state = {}  # последний /config

    def _runtime(self):
        try:
            rt = json.loads((BASE / "runtime.json").read_text(encoding="utf-8"))
            self.port, self.token = rt["port"], rt["token"]
            return True
        except Exception:
            return False

    def _ensure(self):
        return (self.port is not None) or self._runtime()

    def refresh(self):
        if not self._ensure():
            self.state = {}
            return
        try:
            with urllib.request.urlopen(
                    f"http://127.0.0.1:{self.port}/config", timeout=2) as r:
                self.state = json.loads(r.read().decode("utf-8"))
        except Exception:
            self.state = {}

    def post(self, path, body=None):
        if not self._ensure():
            return
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{self.port}{path}?t={self.token}",
                data=json.dumps(body or {}).encode("utf-8"), method="POST",
                headers={"Content-Type": "application/json", "X-Token": self.token})
            urllib.request.urlopen(req, timeout=3).read()
        except Exception:
            pass

    @property
    def ready(self):
        return self.state.get("device_actual") in ("cpu", "cuda")

    @property
    def enabled(self):
        return bool(self.state.get("enabled", True))

    @property
    def voice(self):
        return self.state.get("voice")

    @property
    def settings_url(self):
        if not self._ensure():
            return ""
        return f"http://127.0.0.1:{self.port}/settings?t={self.token}"


def _make_icon(on=True, loading=False):
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    col = (160, 160, 160, 255) if loading else ((47, 109, 246, 255) if on else (120, 120, 120, 255))
    d.ellipse([2, 2, 62, 62], fill=col)
    d.polygon([(20, 27), (29, 27), (39, 18), (39, 46), (29, 37), (20, 37)], fill="white")
    if on and not loading:
        d.arc([36, 18, 52, 46], -55, 55, fill="white", width=3)
        d.arc([40, 12, 60, 52], -50, 50, fill="white", width=3)
    return img


def main():
    client = Client()
    client.refresh()
    icon = pystray.Icon("vsluh")

    def voice_item(sid, label):
        return MenuItem(
            label,
            lambda i, it: (client.post("/config", {"voice": sid}), client.refresh(), icon.update_menu()),
            checked=lambda it, sid=sid: client.voice == sid,
            radio=True,
        )

    def toggle(i, it):
        client.post("/config", {"enabled": not client.enabled})
        client.refresh()
        refresh_icon()

    def do_quit(i, it):
        client.post("/quit")
        icon.stop()

    voices_menu = Menu(*[voice_item(sid, VOICE_LABELS.get(sid, sid)) for _, sid in VOICES])
    icon.menu = Menu(
        MenuItem(lambda it: "✓ Озвучка включена" if client.enabled else "✗ Озвучка выключена", toggle),
        MenuItem("Голос", voices_menu),
        Menu.SEPARATOR,
        MenuItem("Настройки…", lambda i, it: webbrowser.open(client.settings_url)),
        MenuItem("Остановить озвучку", lambda i, it: client.post("/stop")),
        Menu.SEPARATOR,
        MenuItem("Выход", do_quit),
    )

    def refresh_icon():
        icon.icon = _make_icon(on=client.enabled, loading=not client.ready)
        icon.title = "Вслух — " + ("готово" if client.ready else "загрузка…")
        icon.update_menu()

    def poll():
        while True:
            time.sleep(POLL_SEC)
            client.refresh()
            try:
                refresh_icon()
            except Exception:
                pass

    threading.Thread(target=poll, daemon=True).start()
    icon.icon = _make_icon(loading=True)
    icon.title = "Вслух — загрузка…"
    icon.run()


if __name__ == "__main__":
    main()
