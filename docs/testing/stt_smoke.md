# STT smoke-тест и плейлисты

## Назначение
`scripts/stt_smoke.py` запускает короткий прогон распознавания речи на подготовленном плейлисте, чтобы подтвердить, что пайплайн Bitrix24 → транскрипции работает end-to-end перед релизом или инцидентным раскаткой. Скрипт воспроизводит минимальный набор шагов большого `call_export` (см. runbook) и формирует отчёты с длительностью/статусами для каждого файла.

## Предварительные требования
- В `.env` заданы ключи STT: `OPENAI_API_KEY`, `STT_MAX_FILE_MINUTES>0`, при необходимости `CHATGPT_PROXY_URL` и `WHISPER_RATE_PER_MIN_USD` (см. таблицу переменных в README).
- Выполнен `make init` для установки зависимостей и `make up` для доступа к Postgres/Redis (скрипт проверяет очередь `stt:jobs`).
- Локально установлен `ffmpeg` или совместимый декодер, если аудио в плейлисте не в формате WAV.

## Структура плейлиста
CLI принимает **каталог** с аудиофайлами. Рекомендуемая структура плейлиста — отдельная папка в `playlists/`:

```
playlists/
  smoke_demo/
    playlist.yaml          # (опционально) метаданные периода и используемого движка STT
    audio/
      call_001.mp3
      call_002.mp3
    expected/
      transcripts/
        call_001.txt
        call_002.txt
      summary/
        summary_2025-01-01_2025-01-02.md
```

- `playlist.yaml` хранит диапазон дат, идентификаторы звонков, ссылки на исходные записи и ожидаемый движок (`openai-whisper`, `stub`).
- Подпапка `audio/` содержит исходные файлы. Скрипт проходит по каталогу рекурсивно и собирает все аудиофайлы, совпадающие с паттернами (`*.wav`, `*.mp3`, `*.m4a`, `*.flac`, `*.ogg` по умолчанию).
- `expected/` — эталоны для ручной сверки (первые строки текста, рассчитанная стоимость, ошибки); скрипт их не использует, но отчёт удобно сравнивать с сохранёнными эталонами.
- Плейлисты не версионируются в репозитории (объём аудио и потенциальные PII), поэтому путь до каталога настраивается в переменной окружения/репозитория `STT_SMOKE_PLAYLIST_PATH`.

## Запуск
```bash
python scripts/stt_smoke.py \
  --playlist playlists/smoke_demo \
  --report-dir reports/stt_smoke \
  --report-name smoke_demo
```

Скрипт сохраняет транскрипции в каталоге `LOCAL_STORAGE_DIR/transcripts` (по умолчанию `/app/storage/transcripts`, см. настройки приложения) и генерирует два отчёта: `reports/stt_smoke/smoke_demo.json` и `reports/stt_smoke/smoke_demo.md`. Аргументы `--json-report` и `--markdown-report` позволяют указать конкретные пути.

## Формат отчёта
JSON-отчёт (`reports/stt_smoke/smoke_demo.json`) содержит:

```json
{
  "generated_at": "2025-01-01T12:00:00+00:00",
  "playlist_dir": "/abs/path/to/playlists/smoke_demo",
  "patterns": ["*.wav", "*.mp3", "*.m4a", "*.flac", "*.ogg"],
  "engine": "placeholder",
  "language": null,
  "total_files": 2,
  "success_count": 2,
  "error_count": 0,
  "results": [
    {
      "source_file": "audio/call_001.mp3",
      "status": "success",
      "duration_seconds": 0.42,
      "transcript_path": "/app/storage/transcripts/call_001.txt",
      "error": null,
      "language": null
    }
  ]
}
```

- `generated_at`, `playlist_dir`, `patterns` и `engine` фиксируют контекст запуска.
- Каждый элемент `results[]` содержит относительный путь до исходного файла, длительность обработки, путь до транскрипта (если провайдер его создал) и текст ошибки при сбое.
- Markdown-отчёт (`reports/stt_smoke/smoke_demo.md`) добавляет табличное представление для QA.
- В CI результат архивируется как артефакт `stt-smoke-report` (Markdown/JSON из каталога отчётов) в workflow `CI › quality`. Загрузить можно из вкладки **Artifacts** на странице запуска.

## Дополнительные материалы
- Runbook выгрузки звонков: [docs/runbooks/call_export.md](../runbooks/call_export.md)
- Требования и агрегаты отчёта: [docs/SRS — Тексты звонков Bitrix24 (выгрузка за 60 дней).md](../SRS — Тексты звонков Bitrix24 (выгрузка за 60 дней).md)
- UAT-чеклист и ожидания QA: [docs/b24-transcribe/ONE-PAGER.md](../b24-transcribe/ONE-PAGER.md#uat-чеклист)
- Тестовая стратегия и обязанности команд: [docs/testing/strategy.md](strategy.md)
