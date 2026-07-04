# -*- coding: utf-8 -*-
"""Подготовка текста к синтезу.

Silero молча выбрасывает цифры и латиницу, поэтому переводим их в кириллицу
и убираем всё, что модель не умеет читать. Плюс пользовательский словарь
произношений (бренды, маркетплейс-термины, артикулы).
"""
import re

try:
    from num2words import num2words
except Exception:  # если пакет не поставлен — числа читаем цифрами по одной
    num2words = None


# --- словарь частой латиницы -> как читать по-русски -------------------
LATIN_DICT = {
    "ozon": "озон", "wildberries": "вайлдберрис", "wb": "вэ бэ",
    "yandex": "яндекс", "google": "гугл", "claude": "клод", "code": "код",
    "cursor": "курсор", "github": "гитхаб", "git": "гит",
    "telegram": "телеграм", "python": "питон", "api": "апи", "ai": "ай",
    "it": "айти", "excel": "эксель", "word": "ворд", "windows": "виндовс",
    "next": "некст", "react": "реакт", "prisma": "призма", "redis": "редис",
    "postgres": "постгрес", "online": "онлайн", "web": "веб", "app": "апп",
    "seo": "сео", "ok": "окей", "sku": "эс ка ю", "fbo": "эф бэ о",
    "fbs": "эф бэ эс", "usb": "ю эс бэ", "pdf": "пэ дэ эф",
}

# отдельные заглавные буквы (аббревиатуры) — по названию буквы
CAPS_LETTERS = {
    "a": "а", "b": "бэ", "c": "цэ", "d": "дэ", "e": "е", "f": "эф",
    "g": "гэ", "h": "аш", "i": "и", "j": "йот", "k": "ка", "l": "эль",
    "m": "эм", "n": "эн", "o": "о", "p": "пэ", "q": "ку", "r": "эр",
    "s": "эс", "t": "тэ", "u": "у", "v": "вэ", "w": "дубль вэ", "x": "икс",
    "y": "игрек", "z": "зэт",
}

# грубый транслит для незнакомых латинских слов
TRANSLIT_DIGRAPHS = [
    ("sch", "щ"), ("sh", "ш"), ("ch", "ч"), ("ph", "ф"), ("th", "т"),
    ("ck", "к"), ("qu", "кв"), ("oo", "у"), ("ee", "и"), ("ya", "я"),
    ("yo", "ё"), ("yu", "ю"), ("kh", "х"), ("zh", "ж"), ("ts", "ц"),
]
TRANSLIT = {
    "a": "а", "b": "б", "c": "к", "d": "д", "e": "е", "f": "ф", "g": "г",
    "h": "х", "i": "и", "j": "дж", "k": "к", "l": "л", "m": "м", "n": "н",
    "o": "о", "p": "п", "q": "к", "r": "р", "s": "с", "t": "т", "u": "у",
    "v": "в", "w": "в", "x": "кс", "y": "и", "z": "з",
}


def _translit(word):
    for d, r in TRANSLIT_DIGRAPHS:
        word = word.replace(d, r)
    return "".join(TRANSLIT.get(ch, ch) for ch in word)


def _int_words(s):
    if num2words is None:
        return " ".join(s)
    if len(s) > 12:  # телефоны/длинные ID читаем по цифрам
        return " ".join(num2words(int(ch), lang="ru") for ch in s)
    return num2words(int(s), lang="ru")


def apply_user_dict(text, user_dict):
    """Замены из пользовательского словаря. Ключ ищем как целое слово,
    регистронезависимо; поддержка многословных ключей."""
    if not user_dict:
        return text
    # длинные ключи первыми, чтобы «озон селлер» не перебивался «озон»
    for src in sorted(user_dict, key=len, reverse=True):
        repl = user_dict[src]
        if not src:
            continue
        pat = re.compile(r"(?<!\w)" + re.escape(src) + r"(?!\w)", re.IGNORECASE)
        text = pat.sub(repl, text)
    return text


def to_speakable(text, user_dict=None):
    """Текст -> строка, которую Silero прочитает без потерь."""
    text = apply_user_dict(text, user_dict)

    text = text.replace("₽", " рублей ").replace("€", " евро ")
    text = text.replace("$", " долларов ").replace("№", " номер ")
    text = text.replace("&", " и ").replace("+", " плюс ")
    text = re.sub(r"%", " процентов ", text)

    # 3 900 / 12 000 000 -> 3900 / 12000000 (убрать разделитель тысяч)
    text = re.sub(r"(?<=\d)[\s  ]+(?=\d{3}\b)", "", text)
    # 3,5 / 3.5 -> «три и пять»
    text = re.sub(r"\b(\d+)[.,](\d+)\b",
                  lambda m: _int_words(m.group(1)) + " и " + _int_words(m.group(2)),
                  text)
    # 2026 год -> порядковое числительное

    def _year(m):
        if num2words is None:
            return m.group(0)
        try:
            return num2words(int(m.group(1)), to="ordinal", lang="ru") + " " + m.group(2)
        except Exception:
            return m.group(0)
    text = re.sub(r"\b(\d{4})\s*(год\w*)", _year, text)
    text = re.sub(r"\d+", lambda m: _int_words(m.group(0)), text)

    def _latin(m):
        w = m.group(0)
        lw = w.lower()
        if lw in LATIN_DICT:
            return LATIN_DICT[lw]
        if w.isupper() and len(w) <= 5:  # ФBO/СПА и т.п. — по буквам
            return " ".join(CAPS_LETTERS.get(ch, ch) for ch in lw)
        return _translit(lw)
    text = re.sub(r"[A-Za-z]+", _latin, text)

    # всё нечитаемое (эмодзи, стрелки, спецсимволы) -> пробел
    text = re.sub(r"[^0-9А-Яа-яЁё.,!?…:;()\-—–\s]", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def clean_markdown(text):
    """Срезаем markdown-разметку, чтобы не читать звёздочки и ссылки."""
    if not text:
        return ""
    text = re.sub(r"```[\s\S]*?```", " фрагмент кода. ", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"__([^_]+)__", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^[-_*]{3,}\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^>\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\|.*\|\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_chunks(text, first_max=200, chunk_max=450):
    """Режем на куски по границам предложений. Первый кусок маленький —
    чтобы звук пошёл через ~секунду, остальное досинтезируется в фоне."""
    sents = []
    for raw in re.split(r"(?<=[.!?…])\s+|\n+", text):
        s = raw.strip()
        if not s:
            continue
        while len(s) > chunk_max:  # предложение-монстр режем по словам
            cut = s.rfind(" ", 0, chunk_max)
            cut = cut if cut > 50 else chunk_max
            sents.append(s[:cut])
            s = s[cut:].strip()
        if s:
            sents.append(s)
    out, cur = [], ""
    for s in sents:
        limit = first_max if not out else chunk_max
        if cur and len(cur) + len(s) + 1 > limit:
            out.append(cur)
            cur = s
        else:
            cur = (cur + " " + s).strip()
    if cur:
        out.append(cur)
    return out
