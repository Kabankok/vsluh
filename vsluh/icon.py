# -*- coding: utf-8 -*-
"""Иконка «Вслух» — современная градиентная плитка с динамиком.
Используется и треем (разные состояния), и генератором ассетов."""
from PIL import Image, ImageDraw

_cache = {}

# состояние -> (цвет1 сверху-слева, цвет2 снизу-справа)
_PALETTE = {
    "on":      ((76, 130, 251), (123, 92, 245)),   # синий -> фиолетовый
    "off":     ((150, 154, 162), (108, 112, 120)),  # серый (выключено)
    "loading": ((178, 184, 196), (150, 156, 168)),  # светло-серый (загрузка)
}


def _gradient(size, c1, c2):
    base = Image.new("RGB", (size, size), c1)
    px = base.load()
    r1, g1, b1 = c1
    r2, g2, b2 = c2
    for y in range(size):
        for x in range(size):
            t = (x + y) / (2 * (size - 1))
            px[x, y] = (int(r1 + (r2 - r1) * t),
                        int(g1 + (g2 - g1) * t),
                        int(b1 + (b2 - b1) * t))
    return base.convert("RGBA")


def _rounded_mask(size, radius):
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, size - 1, size - 1],
                                        radius=radius, fill=255)
    return m


def make_icon(size=64, state="on"):
    key = (size, state)
    if key in _cache:
        return _cache[key]
    S = 256
    c1, c2 = _PALETTE.get(state, _PALETTE["on"])
    grad = _gradient(S, c1, c2)
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    img.paste(grad, (0, 0), _rounded_mask(S, 60))
    d = ImageDraw.Draw(img)

    white = (255, 255, 255, 255)
    # корпус динамика: узкий слева, раструб вправо
    d.polygon([(70, 108), (104, 108), (146, 74),
               (146, 182), (104, 148), (70, 148)], fill=white)
    if state == "on":
        # звуковые волны
        d.arc([150, 86, 190, 170], -58, 58, fill=white, width=13)
        d.arc([150, 58, 224, 198], -52, 52, fill=white, width=13)

    out = img.resize((size, size), Image.LANCZOS) if size != S else img
    _cache[key] = out
    return out
