# -*- coding: utf-8 -*-
"""Движок синтеза речи: Silero v5 CIS base (лицензия MIT) + простановка
ударений RUAccent (Apache-2.0). Всё локально, офлайн, коммерчески чисто.

Silero «base» сам ударения не ставит — поэтому текст сначала прогоняется
через RUAccent (он расставляет знаки «+» перед ударными гласными), а затем
уже идёт в модель. На видеокарте NVIDIA работает на GPU, иначе на процессоре.
"""
import threading
import numpy as np

SAMPLE_RATE = 48000

# русские голоса модели v5_cis_base (все под MIT). label -> speaker id.
# Сначала натурально-русские, затем голоса носителей языков СНГ (лёгкий акцент, «(СНГ)»).
VOICES = [
    ("aleksandr", "ru_alexandr"),
    ("dmitriy",   "ru_dmitriy"),
    ("eduard",    "ru_eduard"),
    ("bogdan",    "ru_bogdan"),
    ("igor",      "ru_igor"),
    ("roman",     "ru_roman"),
    ("ekaterina", "ru_ekaterina"),
    ("vika",      "ru_vika"),
    ("oksana",    "ru_oksana"),
    ("karina",    "ru_karina"),
    ("zinaida",   "ru_zinaida"),
    ("albina",    "ru_albina"),
    ("aigul",     "ru_aigul"),
    ("alfia",     "ru_alfia"),
    ("alfia2",    "ru_alfia2"),
    ("nurgul",    "ru_nurgul"),
    ("ramilia",   "ru_ramilia"),
    ("saida",     "ru_saida"),
    ("zara",      "ru_zara"),
    ("zhadyra",   "ru_zhadyra"),
    ("zhazira",   "ru_zhazira"),
    ("kermen",    "ru_kermen"),
    ("gamat",     "ru_gamat"),
    ("marat",     "ru_marat"),
    ("kejilgan",  "ru_kejilgan"),
    ("safarhuja", "ru_safarhuja"),
    ("miyau",     "ru_miyau"),
    ("onaoy",     "ru_onaoy"),
    ("sibday",    "ru_sibday"),
]
VOICE_LABELS = {
    "ru_alexandr":  "Александр (мужской)",
    "ru_dmitriy":   "Дмитрий (мужской)",
    "ru_eduard":    "Эдуард (мужской)",
    "ru_bogdan":    "Богдан (мужской)",
    "ru_igor":      "Игорь (мужской)",
    "ru_roman":     "Роман (мужской)",
    "ru_ekaterina": "Екатерина (женский)",
    "ru_vika":      "Вика (женский)",
    "ru_oksana":    "Оксана (женский)",
    "ru_karina":    "Карина (женский)",
    "ru_zinaida":   "Зинаида (женский)",
    "ru_albina":    "Альбина (женский)",
    "ru_aigul":     "Айгуль (СНГ)",
    "ru_alfia":     "Альфия (СНГ)",
    "ru_alfia2":    "Альфия 2 (СНГ)",
    "ru_nurgul":    "Нургуль (СНГ)",
    "ru_ramilia":   "Рамиля (СНГ)",
    "ru_saida":     "Саида (СНГ)",
    "ru_zara":      "Зара (СНГ)",
    "ru_zhadyra":   "Жадыра (СНГ)",
    "ru_zhazira":   "Жазира (СНГ)",
    "ru_kermen":    "Кермен (СНГ)",
    "ru_gamat":     "Гамат (СНГ)",
    "ru_marat":     "Марат (СНГ)",
    "ru_kejilgan":  "Кежильган (СНГ)",
    "ru_safarhuja": "Сафархуджа (СНГ)",
    "ru_miyau":     "Мияу (СНГ)",
    "ru_onaoy":     "Онаой (СНГ)",
    "ru_sibday":    "Сибдей (СНГ)",
}
SPEAKER_IDS = [sid for _, sid in VOICES]

WARMUP_TEXT = ("Прогрев модели: замок открывается ключом, "
               "тридцать три коровы стоят на лугу возле старого дуба.")

_ONNX_PATCHED = False


def _patch_onnx_token_type_ids():
    """Совместимость RUAccent с новыми transformers/onnxruntime: ONNX-модель
    ударений требует вход token_type_ids, а токенайзер его больше не отдаёт →
    put_accent падает, ударения не проставляются, и голос звучит с «акцентом».
    Дописываем token_type_ids=нули (для одного предложения это верно) любой
    сессии, которая их требует. Silero работает на torch, его это не касается."""
    global _ONNX_PATCHED
    if _ONNX_PATCHED:
        return
    import onnxruntime as ort
    _orig_run = ort.InferenceSession.run

    def run(self, output_names, input_feed, run_options=None):
        try:
            required = {i.name for i in self.get_inputs()}
            if ("token_type_ids" in required and "token_type_ids" not in input_feed
                    and "input_ids" in input_feed):
                input_feed = dict(input_feed)
                input_feed["token_type_ids"] = np.zeros_like(input_feed["input_ids"])
        except Exception:
            pass
        return _orig_run(self, output_names, input_feed, run_options)

    ort.InferenceSession.run = run
    _ONNX_PATCHED = True


class VslukhTTS:
    def __init__(self, model_path, device_pref="auto", ruaccent_size="turbo3.1"):
        self.model_path = str(model_path)
        self.device_pref = device_pref
        self.ruaccent_size = ruaccent_size
        self._model = None
        self._accent = None
        self._device = "cpu"
        self._lock = threading.Lock()  # apply_tts не потокобезопасен

    @property
    def device(self):
        return self._device

    def load(self):
        import torch
        if self.device_pref == "cuda" and torch.cuda.is_available():
            dev = "cuda"
        elif self.device_pref == "cpu":
            dev = "cpu"
        else:
            dev = "cuda" if torch.cuda.is_available() else "cpu"

        imp = torch.package.PackageImporter(self.model_path)
        model = imp.load_pickle("tts_models", "model")
        if dev == "cuda":
            model.to(torch.device("cuda"))
        else:
            torch.set_num_threads(max(4, (torch.get_num_threads() or 4)))
        self._model = model
        self._device = dev

        _patch_onnx_token_type_ids()
        from ruaccent import RUAccent
        acc = RUAccent()
        acc.load(omograph_model_size=self.ruaccent_size,
                 use_dictionary=True, tiny_mode=False)
        self._accent = acc

        self._warmup()
        return dev

    def _warmup(self):
        # первый прогон тянет словари/модель ударений — платим цену здесь,
        # а не на первом нажатии хоткея
        self.synth(WARMUP_TEXT, SPEAKER_IDS[0])

    def accentize(self, text):
        if self._accent is None:
            return text
        try:
            return self._accent.process_all(text)
        except Exception:
            return text

    def synth(self, text, speaker="ru_alexandr", rate=None):
        """Готовый (нормализованный, по-русски) текст -> np.int16 PCM 48kHz.
        rate — множитель скорости 0.5..2.0, применяется через SSML, если модель
        его поддерживает; иначе игнорируется."""
        model = self._model
        if model is None or not text.strip():
            return None
        if speaker not in SPEAKER_IDS:
            speaker = "ru_alexandr"
        accented = self.accentize(text)
        try:
            with self._lock:
                if rate and abs(rate - 1.0) > 0.01:
                    pct = int(round(rate * 100))
                    ssml = f'<speak><prosody rate="{pct}%">{accented}</prosody></speak>'
                    try:
                        audio = model.apply_tts(ssml_text=ssml, speaker=speaker,
                                                sample_rate=SAMPLE_RATE)
                    except Exception:
                        audio = model.apply_tts(text=accented, speaker=speaker,
                                                sample_rate=SAMPLE_RATE)
                else:
                    audio = model.apply_tts(text=accented, speaker=speaker,
                                            sample_rate=SAMPLE_RATE)
        except Exception:
            return None
        return (audio.numpy() * 32767).astype(np.int16)


def write_wav(path, pcm):
    import wave
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm.tobytes())
