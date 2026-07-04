# Сторонние компоненты и лицензии

«Вслух» (код) — лицензия **MIT**, © 2026 Владимир Кабанов.

Программа использует сторонние компоненты. Все они разрешают коммерческое
использование:

## Голосовая модель — Silero v5 CIS base

- Проект: **Silero Models** — https://github.com/snakers4/silero-models
- Файл: `v5_cis_base.pt` (скачивается установщиком с https://models.silero.ai)
- Лицензия: **MIT** (файл `LICENSE_CIS` в репозитории Silero — покрывает
  именно `v5_cis_base` / `v5_cis_base_nostress`; остальные модели Silero, включая
  `v4_ru`, распространяются по некоммерческой CC BY-NC-SA и здесь НЕ используются).
- © Silero Team. Цитирование:

  ```
  @misc{Silero Models,
    author = {Silero Team},
    title = {Silero Models: pre-trained STT and TTS models made embarrassingly simple},
    year = {2021},
    publisher = {GitHub},
    howpublished = {\url{https://github.com/snakers4/silero-models}}
  }
  ```

## Расстановка ударений — RUAccent

- Проект: **RUAccent** — https://github.com/Den4ikAI/ruaccent
- Лицензия: **Apache-2.0** (коммерческое использование разрешено).
- Модели ударений скачиваются при установке.

## Библиотеки

- **PyTorch** (BSD-3-Clause) — исполнение модели.
- **pystray** (LGPL-3.0) — иконка в трее.
- **Pillow** (MIT-CMU/HPND) — иконка.
- **num2words** (LGPL-2.1) — числа прописью.

Голоса Silero v5 CIS base — синтетические, не привязаны к конкретным людям,
и распространяются под MIT, поэтому синтезированное аудио можно свободно
использовать, в том числе в коммерческих проектах.
