# -*- coding: utf-8 -*-
"""Движок «Вслух» (engine). Тяжёлый процесс: модель Silero + RUAccent, синтез,
воспроизведение, HTTP-сервер настроек и глобальные горячие клавиши.

Трей вынесен в ОТДЕЛЬНЫЙ процесс (traymain.py): pystray и torch в одном процессе
дают нативный краш при синтезе на фоне двух циклов сообщений Windows. Здесь
циклов сообщений один (хоткей), pystray нет — стабильно.
"""
import json
import os
import secrets
import threading
from pathlib import Path

from .core import Core
from .server import SettingsServer, PORT
from .hotkey import HotkeyListener, capture_selection


def write_runtime(base_dir, port, token):
    (Path(base_dir) / "runtime.json").write_text(
        json.dumps({"port": port, "token": token}), encoding="utf-8")


def main():
    base_dir = Path(__file__).resolve().parent.parent  # корень проекта (config.json, models/)
    core = Core(base_dir)

    stop_event = threading.Event()
    token = secrets.token_urlsafe(8)
    server = SettingsServer(core, token, stop_event)
    server.start()
    write_runtime(base_dir, PORT, token)

    def on_speak():
        from .log import log
        log("on_speak: hotkey fired")
        text = capture_selection()
        if text:
            core.speak(text)
        else:
            log("on_speak: пустой захват — нечего озвучивать")

    def make_listener(speak, stop):
        return HotkeyListener({"speak": speak, "stop": stop},
                              {"speak": on_speak, "stop": core.stop})

    listener = [make_listener(core.cfg["hotkey_speak"], core.cfg["hotkey_stop"])]
    listener[0].start()

    def restart_hotkeys(speak, stop):
        from .log import log
        try:
            listener[0].stop()
        except Exception:
            pass
        listener[0] = make_listener(speak, stop)
        listener[0].start()
        log(f"хоткеи перерегистрированы вживую: speak={speak}, stop={stop}")

    core.on_hotkeys_changed = restart_hotkeys

    threading.Thread(target=core.load, daemon=True).start()

    stop_event.wait()  # держим процесс живым до команды «Выход» от трея (/quit)
    try:
        server.stop()
    except Exception:
        pass
    os._exit(0)


if __name__ == "__main__":
    main()
