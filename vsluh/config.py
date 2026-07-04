# -*- coding: utf-8 -*-
"""Настройки «Вслух». Хранятся рядом с программой в config.json,
чтобы всё было портативно (скопировал папку — настройки с собой)."""
import json
import os
from pathlib import Path

DEFAULTS = {
    "voice": "ru_alexandr",   # голос по умолчанию (id спикера Silero v5)
    "rate": 1.15,             # скорость речи, множитель 0.7..1.5
    "hotkey_speak": "ctrl+alt+z",
    "hotkey_stop": "ctrl+alt+x",
    "device": "auto",         # auto | cpu | cuda
    "enabled": True,          # общий тумблер озвучки
    "autostart": True,        # автозапуск при входе в Windows
    "dictionary": {           # свой словарь произношений: как_написано -> как_читать
        "Ozon": "озон",
        "Wildberries": "вайлдберриз",
        "WB": "вэ бэ",
        "FBO": "эф бэ о",
        "FBS": "эф бэ эс",
    },
}


def config_path(base_dir):
    return Path(base_dir) / "config.json"


def load(base_dir):
    p = config_path(base_dir)
    cfg = dict(DEFAULTS)
    cfg["dictionary"] = dict(DEFAULTS["dictionary"])
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                for k, v in data.items():
                    if k == "dictionary" and isinstance(v, dict):
                        cfg["dictionary"] = v
                    elif k in DEFAULTS:
                        cfg[k] = v
        except Exception:
            pass  # битый конфиг -> дефолты
    return cfg


def save(base_dir, cfg):
    """Атомарная запись: пишем во временный файл и переименовываем,
    чтобы падение на середине не покалечило конфиг."""
    p = config_path(base_dir)
    clean = {k: cfg.get(k, DEFAULTS[k]) for k in DEFAULTS}
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, p)
    return p
