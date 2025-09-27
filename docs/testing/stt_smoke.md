# STT smoke-тест и плейлисты

## Назначение
`scripts/stt_smoke.py` запускает короткий прогон распознавания речи на подготовленном плейлисте, чтобы подтвердить, что пайплайн Bitrix24 → транскрипции работает end-to-end перед релизом или инцидентным раскаткой. Скрипт воспроизводит минимальный набор шагов большого `call_export` (см. runbook) и формирует такой же отчёт о длительности/стоимости, как production-задача.

## Предварительные требования
- В `.env` заданы ключи STT: `OPENAI_API_KEY`, `STT_MAX_FILE_MINUTES>0`, при необходимости `CHATGPT_PROXY_URL` и `WHISPER_RATE_PER_MIN_USD` (см. таблицу переменных в README).
- Выполнен `make init` для установки зависимостей и `make up` для доступа к Postgres/Redis (скрипт проверяет очередь `stt:jobs`).
- Локально установлен `ffmpeg` или совместимый декодер, если аудио в плейлисте не в формате WAV.

## Структура плейлиста
Каждый плейлист — отдельная папка в `playlists/`:

```
playlists/
  smoke_demo/
    playlist.yaml          # метаданные периода и используемого движка STT
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

- `playlist.yaml` содержит диапазон дат, идентификаторы звонков, ссылки на исходные записи и ожидаемый движок (`openai-whisper`, `stub`).
- Подпапка `audio/` хранит исходные файлы, `expected/` — эталоны для сравнения (первые строки текста, рассчитанная стоимость, ошибки).

## Запуск
```bash
python scripts/stt_smoke.py \
  --playlist playlists/smoke_demo/playlist.yaml \
  --report build/stt_smoke_report.json
```

Скрипт помещает транскрипции во временный каталог `build/stt_smoke/<timestamp>/` и сохраняет отчёт по указанному пути (`--report`).

## Формат отчёта
`build/stt_smoke_report.json` содержит:

```json
{
  "summary": {
    "total": 2,
    "success": 2,
    "failed": 0,
    "duration_minutes": 12.4,
    "cost_usd": 0.07
  },
  "entries": [
    {
      "call_id": "123",
      "record_id": "abc",
      "status": "success",
      "transcript_path": "build/stt_smoke/.../call_001.txt"
    }
  ]
}
```

- `summary` повторяет агрегаты из production отчёта `summary_<period>.md` (см. SRS §7.3).
- Для `status="success"` указывается путь до транскрипта и расчётная стоимость. `status="failure"` содержит поле `error_code` и `error_message`, что позволяет сверить причины с `docs/testing/error_catalog.json`.
- В CI результат архивируется как артефакт `stt-smoke-report` (файл `build/stt_smoke_report.json`) в workflow `CI › quality`. Загрузить можно из вкладки **Artifacts** на странице запуска.

## Дополнительные материалы
- Runbook выгрузки звонков: [docs/runbooks/call_export.md](../runbooks/call_export.md)
- Требования и агрегаты отчёта: [docs/SRS — Тексты звонков Bitrix24 (выгрузка за 60 дней).md](../SRS — Тексты звонков Bitrix24 (выгрузка за 60 дней).md)
- UAT-чеклист и ожидания QA: [docs/b24-transcribe/ONE-PAGER.md](../b24-transcribe/ONE-PAGER.md#uat-чеклист)
- Тестовая стратегия и обязанности команд: [docs/testing/strategy.md](strategy.md)
