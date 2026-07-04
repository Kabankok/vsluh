# -*- coding: utf-8 -*-
"""Оркестратор озвучки: текст -> нормализация -> нарезка -> синтез в фоне ->
потоковое воспроизведение по кускам. Первый (маленький) кусок звучит через
секунду, остальное досинтезируется, пока играет начало."""
import queue
import tempfile
import threading
from pathlib import Path

import numpy as np

from . import config, normalize
from .tts import VslukhTTS, write_wav
from .player import Player

FIRST_CHUNK_MAX = 200
CHUNK_MAX = 450
MAX_CHARS = 10000
MODEL_WAIT = 40.0

PREVIEW_TEXT = ("Так я буду читать выделенный вами текст. "
                "Цена три тысячи девятьсот рублей, поставка по схеме эф бэ о.")


class Core:
    def __init__(self, base_dir):
        self.base_dir = Path(base_dir)
        self.cfg = config.load(base_dir)
        model_path = self.base_dir / "models" / "v5_cis_base.pt"
        self.tts = VslukhTTS(str(model_path), device_pref=self.cfg["device"])
        self.player = Player()
        self.ready = threading.Event()
        self._gen = 0
        self._gen_lock = threading.Lock()
        self._play_lock = threading.Lock()
        self.tmp = Path(tempfile.gettempdir())
        self.on_state_change = None  # трей перерисовать меню/иконку

    # --- жизненный цикл ---
    def load(self):
        self.tts.load()
        self.ready.set()

    # --- настройки ---
    def get_config(self):
        c = dict(self.cfg)
        c["dictionary"] = dict(self.cfg["dictionary"])
        c["device_actual"] = self.tts.device if self.ready.is_set() else "loading"
        return c

    def update_config(self, patch):
        for k, v in patch.items():
            if k == "dictionary" and isinstance(v, dict):
                self.cfg["dictionary"] = v
            elif k in config.DEFAULTS:
                self.cfg[k] = v
        config.save(self.base_dir, self.cfg)
        if self.on_state_change:
            self.on_state_change()

    def toggle_enabled(self):
        self.update_config({"enabled": not self.cfg.get("enabled", True)})
        if not self.cfg.get("enabled", True):
            self.stop()

    # --- управление воспроизведением ---
    def stop(self):
        with self._gen_lock:
            self._gen += 1
        self.player.stop()

    def _prep(self, raw):
        cleaned = normalize.clean_markdown(raw)
        if not cleaned:
            return None
        if len(cleaned) > MAX_CHARS:
            cut = cleaned[:MAX_CHARS]
            dot = cut.rfind(". ")
            cleaned = (cut[: dot + 1] if dot > 200 else cut) + " далее в тексте."
        speakable = normalize.to_speakable(cleaned, self.cfg.get("dictionary"))
        return normalize.split_chunks(speakable, FIRST_CHUNK_MAX, CHUNK_MAX)

    def speak(self, raw, voice=None, rate=None, force=False):
        if not force and not self.cfg.get("enabled", True):
            return
        if not raw or not raw.strip():
            return
        voice = voice or self.cfg.get("voice")
        rate = rate if rate is not None else self.cfg.get("rate")

        with self._gen_lock:
            self._gen += 1
            gen = self._gen
        self.player.stop()  # текущий плеер умирает -> прошлый speak отпускает лок

        with self._play_lock:
            if self._gen != gen:
                return
            if not self.ready.wait(MODEL_WAIT):
                return
            chunks = self._prep(raw)
            if not chunks:
                return

            q = queue.Queue()

            def producer():
                for ch in chunks:
                    if self._gen != gen:
                        break
                    pcm = self.tts.synth(ch, voice, rate)
                    if pcm is not None and len(pcm):
                        q.put(pcm)
                q.put(None)

            threading.Thread(target=producer, daemon=True).start()

            i = 0
            while self._gen == gen:
                item = q.get()
                if item is None:
                    break
                batch = [item]
                while True:  # добрать всё уже готовое, чтобы паузы были на границах фраз
                    try:
                        nx = q.get_nowait()
                    except queue.Empty:
                        break
                    if nx is None:
                        q.put(None)
                        break
                    batch.append(nx)
                pcm = np.concatenate(batch) if len(batch) > 1 else batch[0]
                path = self.tmp / f"vsluh_{i % 2}.wav"
                write_wav(path, pcm)
                if self._gen != gen:
                    break
                self.player.play_blocking(path)
                i += 1

    def preview(self, voice=None, rate=None):
        # превью работает даже при выключенной озвучке
        self.speak(PREVIEW_TEXT, voice=voice, rate=rate, force=True)
