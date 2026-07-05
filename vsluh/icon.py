# -*- coding: utf-8 -*-
"""Иконка «Вслух» — стеклянная плитка с динамиком (assets/vsluh-icon.png).
Трею отдаёт состояния: on (цветная), off/loading (приглушённая ч/б)."""
from pathlib import Path

from PIL import Image, ImageEnhance

_SRC = Path(__file__).resolve().parent.parent / "assets" / "vsluh-icon.png"
_base = None
_cache = {}


def _load():
    global _base
    if _base is None:
        _base = Image.open(_SRC).convert("RGBA")
    return _base


def make_icon(size=64, state="on"):
    key = (size, state)
    if key in _cache:
        return _cache[key]
    img = _load().resize((size, size), Image.LANCZOS)
    if state != "on":
        r, g, b, alpha = img.split()
        rgb = Image.merge("RGB", (r, g, b))
        rgb = ImageEnhance.Color(rgb).enhance(0.0 if state == "off" else 0.30)
        rgb = ImageEnhance.Brightness(rgb).enhance(0.72 if state == "off" else 0.88)
        img = Image.merge("RGBA", (*rgb.split(), alpha))
    _cache[key] = img
    return img
