# -*- coding: utf-8 -*-
"""Локальный HTTP-сервер настроек (только 127.0.0.1). Отдаёт страницу
/settings и API для чтения/записи конфига и превью голоса. POST-запросы
защищены токеном, который знает только трей (открывает /settings?t=...)."""
import json
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path

from .tts import VOICES, VOICE_LABELS

PORT = 5577  # свой порт, чтобы не конфликтовать с другими локальными TTS-инструментами
UI_DIR = Path(__file__).parent / "ui"

# ссылка на Telegram-канал в футере настроек (лид-магнит); подставляется в HTML.
# Ведём через редирект на своём домене, а не прямо в Telegram: 13.07.2026 домен
# t.me умер, и у всех, кто уже поставил Вслух, кнопка стала вести в никуда —
# обновление им не разошлёшь. Через /tg такое чинится на нашей стороне.
TELEGRAM_URL = "https://vladimir-kabanov.ru/tg"


def make_handler(core, token, stop_event=None):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code, body=b"", ctype="text/plain; charset=utf-8"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if body:
                self.wfile.write(body)

        def _json(self, obj, code=200):
            self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8")

        def _read_body(self):
            n = int(self.headers.get("Content-Length", 0) or 0)
            if not n:
                return {}
            try:
                return json.loads(self.rfile.read(n).decode("utf-8"))
            except Exception:
                return {}

        def _check_token(self):
            # токен из query (?t=) или заголовка
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            t = (q.get("t", [None])[0]) or self.headers.get("X-Token")
            return t == token

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path == "/settings":
                html = (UI_DIR / "settings.html").read_text(encoding="utf-8")
                html = html.replace("__TOKEN__", token)
                html = html.replace("__TELEGRAM_URL__", TELEGRAM_URL)
                self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")
            elif path == "/config":
                cfg = core.get_config()
                cfg["voices"] = [{"id": sid, "label": VOICE_LABELS.get(sid, sid)}
                                 for _, sid in VOICES]
                self._json(cfg)
            elif path == "/ping":
                self._send(200, b"ok" if core.ready.is_set() else b"loading")
            else:
                self._send(404, b"not found")

        def do_POST(self):
            path = self.path.split("?", 1)[0]
            if not self._check_token():
                self._send(403, b"forbidden")
                return
            body = self._read_body()
            if path == "/config":
                core.update_config(body)
                self._json({"ok": True})
            elif path == "/preview":
                voice = body.get("voice")
                rate = body.get("rate")
                threading.Thread(target=lambda: core.preview(voice, rate),
                                 daemon=True).start()
                self._json({"ok": True})
            elif path == "/stop":
                core.stop()
                self._json({"ok": True})
            elif path == "/quit":
                self._json({"ok": True})
                if stop_event is not None:
                    stop_event.set()
            else:
                self._send(404, b"not found")

        def log_message(self, *a, **k):
            pass

    return Handler


class SettingsServer:
    def __init__(self, core, token, stop_event=None):
        self.core = core
        self.token = token
        self.stop_event = stop_event
        self._srv = None

    def start(self):
        self._srv = ThreadingHTTPServer(
            ("127.0.0.1", PORT),
            make_handler(self.core, self.token, self.stop_event))
        threading.Thread(target=self._srv.serve_forever, daemon=True).start()

    def stop(self):
        if self._srv:
            self._srv.shutdown()

    @property
    def url(self):
        return f"http://127.0.0.1:{PORT}/settings?t={self.token}"
