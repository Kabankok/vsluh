# -*- coding: utf-8 -*-
"""Глобальные горячие клавиши и захват выделенного текста — чистый ctypes,
без сторонних библиотек (keyboard/pynput ловятся антивирусами как кейлоггеры).

- Регистрируем клавиши через WinAPI RegisterHotKey (это НЕ хук, всех клавиш не
  читает — антивирусы к нему спокойны). Ловим WM_HOTKEY в цикле сообщений.
- По нажатию: снимаем физически зажатые модификаторы, шлём Ctrl+C, ждём
  изменения буфера обмена (по номеру последовательности), читаем текст,
  возвращаем буфер как был.
"""
import ctypes
import threading
import time
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

# На 64-битной Windows ctypes по умолчанию считает результат int32 и усекает
# указатели/хендлы -> access violation. Объявляем прототипы явно.
_c_void_p = ctypes.c_void_p
user32.OpenClipboard.argtypes = [_c_void_p]
user32.OpenClipboard.restype = wintypes.BOOL
user32.CloseClipboard.restype = wintypes.BOOL
user32.EmptyClipboard.restype = wintypes.BOOL
user32.GetClipboardData.argtypes = [wintypes.UINT]
user32.GetClipboardData.restype = _c_void_p
user32.SetClipboardData.argtypes = [wintypes.UINT, _c_void_p]
user32.SetClipboardData.restype = _c_void_p
user32.GetClipboardSequenceNumber.restype = wintypes.DWORD
user32.SendInput.argtypes = [wintypes.UINT, _c_void_p, ctypes.c_int]
user32.SendInput.restype = wintypes.UINT
user32.RegisterHotKey.argtypes = [_c_void_p, ctypes.c_int, wintypes.UINT, wintypes.UINT]
user32.RegisterHotKey.restype = wintypes.BOOL
user32.GetMessageW.argtypes = [_c_void_p, _c_void_p, wintypes.UINT, wintypes.UINT]
user32.GetMessageW.restype = ctypes.c_int
user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT,
                                      _c_void_p, _c_void_p]
user32.PostThreadMessageW.restype = wintypes.BOOL
kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = _c_void_p
kernel32.GlobalLock.argtypes = [_c_void_p]
kernel32.GlobalLock.restype = _c_void_p
kernel32.GlobalUnlock.argtypes = [_c_void_p]
kernel32.GlobalUnlock.restype = wintypes.BOOL
kernel32.GetCurrentThreadId.restype = wintypes.DWORD

# --- модификаторы RegisterHotKey ---
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312

# коды клавиш
VK = {
    "a": 0x41, "b": 0x42, "c": 0x43, "d": 0x44, "e": 0x45, "f": 0x46,
    "g": 0x47, "h": 0x48, "i": 0x49, "j": 0x4A, "k": 0x4B, "l": 0x4C,
    "m": 0x4D, "n": 0x4E, "o": 0x4F, "p": 0x50, "q": 0x51, "r": 0x52,
    "s": 0x53, "t": 0x54, "u": 0x55, "v": 0x56, "w": 0x57, "x": 0x58,
    "y": 0x59, "z": 0x5A,
    "0": 0x30, "1": 0x31, "2": 0x32, "3": 0x33, "4": 0x34, "5": 0x35,
    "6": 0x36, "7": 0x37, "8": 0x38, "9": 0x39,
    "space": 0x20, "insert": 0x2D, "f1": 0x70, "f2": 0x71, "f3": 0x72,
    "f4": 0x73, "f5": 0x74, "f6": 0x75, "f7": 0x76, "f8": 0x77,
    "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
}
MOD_NAMES = {"ctrl": MOD_CONTROL, "control": MOD_CONTROL, "alt": MOD_ALT,
             "shift": MOD_SHIFT, "win": MOD_WIN}


def parse_hotkey(s):
    """'ctrl+alt+z' -> (mods, vk) либо None."""
    mods, vk = 0, None
    for part in s.lower().replace(" ", "").split("+"):
        if part in MOD_NAMES:
            mods |= MOD_NAMES[part]
        elif part in VK:
            vk = VK[part]
    if vk is None:
        return None
    return mods | MOD_NOREPEAT, vk


# --- SendInput для синтетических нажатий ---
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
VK_CONTROL, VK_MENU, VK_SHIFT, VK_LWIN, VK_RWIN = 0x11, 0x12, 0x10, 0x5B, 0x5C
VK_C = 0x43


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG))]


class _INPUTunion(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTunion)]


def _key(vk, up=False):
    ki = KEYBDINPUT(vk, 0, KEYEVENTF_KEYUP if up else 0, 0, None)
    return INPUT(INPUT_KEYBOARD, _INPUTunion(ki=ki))


def _send(inputs):
    n = len(inputs)
    arr = (INPUT * n)(*inputs)
    user32.SendInput(n, arr, ctypes.sizeof(INPUT))


def _release_modifiers():
    # снять физически зажатые Ctrl/Alt/Shift/Win, иначе к Ctrl+C приклеится Alt
    ups = [_key(vk, up=True) for vk in (VK_CONTROL, VK_MENU, VK_SHIFT, VK_LWIN, VK_RWIN)]
    _send(ups)


def _send_ctrl_c():
    _send([_key(VK_CONTROL), _key(VK_C), _key(VK_C, up=True), _key(VK_CONTROL, up=True)])


# --- буфер обмена ---
CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002


def _clipboard_seq():
    return user32.GetClipboardSequenceNumber()


def _open_clipboard(retries=10):
    for _ in range(retries):
        if user32.OpenClipboard(None):
            return True
        time.sleep(0.02)
    return False


def _get_clipboard_text():
    if not _open_clipboard():
        return None
    try:
        h = user32.GetClipboardData(CF_UNICODETEXT)
        if not h:
            return None
        ptr = kernel32.GlobalLock(h)
        if not ptr:
            return None
        try:
            return ctypes.c_wchar_p(ptr).value
        finally:
            kernel32.GlobalUnlock(h)
    finally:
        user32.CloseClipboard()


def _set_clipboard_text(text):
    if text is None:
        return
    if not _open_clipboard():
        return
    try:
        user32.EmptyClipboard()
        buf = ctypes.create_unicode_buffer(text)
        size = ctypes.sizeof(buf)
        h = kernel32.GlobalAlloc(GMEM_MOVEABLE, size)
        if not h:
            return
        ptr = kernel32.GlobalLock(h)
        ctypes.memmove(ptr, buf, size)
        kernel32.GlobalUnlock(h)
        user32.SetClipboardData(CF_UNICODETEXT, h)
    finally:
        user32.CloseClipboard()


def _empty_clipboard():
    if _open_clipboard():
        try:
            user32.EmptyClipboard()
        finally:
            user32.CloseClipboard()


def capture_selection(timeout=0.5):
    """Ctrl+C и чтение результата. Возвращает выделенный текст или '' если
    ничего не выделено. Исходный буфер восстанавливается."""
    saved = _get_clipboard_text()
    _empty_clipboard()
    seq0 = _clipboard_seq()  # базовый номер ПОСЛЕ очистки — иначе она сама его меняет
    _release_modifiers()
    time.sleep(0.03)  # дать отпусканию модификаторов дойти
    _send_ctrl_c()

    text = ""
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        if _clipboard_seq() != seq0:
            got = _get_clipboard_text()
            if got:
                text = got
            break
        time.sleep(0.02)

    _set_clipboard_text(saved)  # вернуть как было
    return text


class HotkeyListener:
    """Регистрирует хоткеи и в своём потоке крутит цикл сообщений.
    callbacks: {"speak": fn, "stop": fn}. Возвращает список неудачных биндингов."""

    def __init__(self, bindings, callbacks):
        # bindings: {"speak": "ctrl+alt+z", "stop": "ctrl+alt+x"}
        self.bindings = bindings
        self.callbacks = callbacks
        self._thread = None
        self._thread_id = None
        self.failed = []

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        self._thread_id = kernel32.GetCurrentThreadId()
        ids = {}
        hid = 1
        for name, combo in self.bindings.items():
            parsed = parse_hotkey(combo)
            if not parsed:
                self.failed.append(name)
                continue
            mods, vk = parsed
            if user32.RegisterHotKey(None, hid, mods, vk):
                ids[hid] = name
            else:
                self.failed.append(name)  # клавиша занята другим приложением
            hid += 1

        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            if msg.message == WM_HOTKEY:
                name = ids.get(int(msg.wParam))
                cb = self.callbacks.get(name) if name else None
                if cb:
                    threading.Thread(target=cb, daemon=True).start()

    def stop(self):
        if self._thread_id:
            # WM_QUIT = 0x0012
            user32.PostThreadMessageW(self._thread_id, 0x0012, 0, 0)
