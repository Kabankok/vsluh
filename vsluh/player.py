# -*- coding: utf-8 -*-
"""Воспроизведение WAV. Играем ДОЧЕРНИМ процессом PowerShell + WPF MediaPlayer:
у него своя аудио-сессия и дефолтное устройство вывода. Из самого pythonw.exe
звук «глухой» (нет аудио-сессии), поэтому только так. Стоп = kill процесса."""
import subprocess
import threading

CREATE_NO_WINDOW = 0x08000000


class Player:
    def __init__(self):
        self._proc = None
        self._lock = threading.Lock()

    def stop(self):
        with self._lock:
            p = self._proc
            if p and p.poll() is None:
                try:
                    p.kill()
                except Exception:
                    pass
            self._proc = None

    def play_blocking(self, path):
        uri = str(path).replace("\\", "/")
        ps = (
            "Add-Type -AssemblyName presentationCore;"
            "$p=New-Object System.Windows.Media.MediaPlayer;"
            f"$p.Open([uri]'{uri}');"
            "$n=0; while(-not $p.NaturalDuration.HasTimeSpan -and $n -lt 50)"
            "{Start-Sleep -Milliseconds 100; $n++};"
            "$p.Volume=1.0; $p.Play();"
            "if($p.NaturalDuration.HasTimeSpan){Start-Sleep -Milliseconds "
            "([int]$p.NaturalDuration.TimeSpan.TotalMilliseconds + 200)}"
            "else{Start-Sleep -Seconds 30};"
            "$p.Stop(); $p.Close();"
        )
        proc = subprocess.Popen(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps],
            creationflags=CREATE_NO_WINDOW,
        )
        with self._lock:
            self._proc = proc
        try:
            proc.wait()
        finally:
            with self._lock:
                if self._proc is proc:
                    self._proc = None
