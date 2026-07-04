# -*- coding: utf-8 -*-
"""Пост-установка: скачать голосовую модель Silero v5 (MIT) и прогреть RUAccent
(чтобы его модели скачались заранее, а не при первом запуске)."""
import sys
from pathlib import Path

MODEL_URL = "https://models.silero.ai/models/tts/ru/v5_cis_base.pt"
ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = ROOT / "models" / "v5_cis_base.pt"


def download_model():
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    if MODEL_PATH.exists() and MODEL_PATH.stat().st_size > 50_000_000:
        print("Модель уже на месте:", MODEL_PATH.name)
        return
    print("Скачиваю голосовую модель (~90 МБ)…")
    import torch
    torch.hub.download_url_to_file(MODEL_URL, str(MODEL_PATH))
    print("Готово:", round(MODEL_PATH.stat().st_size / 1e6, 1), "МБ")


def warm_ruaccent():
    print("Готовлю расстановку ударений (RUAccent, разово скачает модели)…")
    from ruaccent import RUAccent
    acc = RUAccent()
    acc.load(omograph_model_size="turbo3.1", use_dictionary=True, tiny_mode=False)
    _ = acc.process_all("Проверка ударений: замок и замок.")
    print("Ударения готовы.")


if __name__ == "__main__":
    download_model()
    warm_ruaccent()
    print("Пост-установка завершена.")
    sys.exit(0)
