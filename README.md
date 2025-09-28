# MasterMobile — Middleware & Integrations (FastAPI)

[![CI](https://github.com/Offonika/mastermobile/actions/workflows/ci.yml/badge.svg)](https://github.com/Offonika/mastermobile/actions/workflows/ci.yml)
[![Docs CI](https://github.com/Offonika/mastermobile/actions/workflows/docs-ci.yml/badge.svg)](https://github.com/Offonika/mastermobile/actions/workflows/docs-ci.yml)

## Что это
Единый middleware-сервис: интеграция 1С (УТ 10.3/11), Bitrix24 и «Walking Warehouse».

## Предварительные требования

- Docker Engine с установленным Compose-плагином (тестировалось на версии 2.24+).
- Локальный файл `.env`, собранный из `.env.example` (в нём заданы параметры приложения, Postgres и Redis).

## Быстрый старт (локально)
1. `make init`
2. `make up`
3. `make worker` — запускает отдельный STT-воркер (в отдельном терминале)
4. `make seed` — по мере появления данных
5. `make test`

> Для запуска только зависимостей можно выполнить `docker compose up -d db redis`.
> Метрики Prometheus для FastAPI-приложения доступны по адресу `http://localhost:8000/metrics`.
> Экспортер фонового STT-воркера публикует метрики на `http://localhost:${WORKER_METRICS_PORT:-9100}/metrics`.

## CI и Docs-CI

Основной workflow [`ci.yml`](.github/workflows/ci.yml) запускает два набора проверок:

- **Quality** — Python-инструменты (`make lint`, `make typecheck`, `make test` и STT smoke-плейлист при наличии ключей).
- **Docs quality** — проверки документации и ссылок: `make docs-markdownlint`, `make docs-links`, `make docs-spellcheck` и смоук-тест `make docs-ci-smoke`, который подтверждает, что link-checker корректно ловит ошибочные URL.

Для локального запуска docs-проверок доступны команды Makefile:

- `make docs-markdownlint` — проверка Markdown по правилам из `.markdownlint.yml` (использует контейнер `ghcr.io/igorshubovych/markdownlint-cli`).
- `make docs-links` — сканирование ссылок через `lychee` с конфигом `.lychee.toml` (контейнер `ghcr.io/lycheeverse/lychee`).
- `make docs-spellcheck` — орфография через `codespell` c параметрами из `.codespellrc`.
- `make docs-ci` — последовательный запуск всех проверок.
- `make docs-ci-smoke` — временно создаёт тестовый markdown с «битой» ссылкой и убеждается, что `lychee` падает с ошибкой.

## Smoke-тест распознавания речи

### Предварительные условия
- Подготовьте `.env` с ключами `OPENAI_API_KEY`, выставленным лимитом `STT_MAX_FILE_MINUTES` и при необходимости прокси `CHATGPT_PROXY_URL` — см. таблицу переменных ниже.
- Выполните `make init` и `make up`, чтобы скрипт имел доступ к зависимостям (Postgres, Redis) и установленным Python-пакетам.
- Подложите тестовый плейлист в `playlists/`: каждая папка содержит `playlist.yaml`, подпапку `audio/` с исходными файлами и `expected/` с эталонными транскриптами/отчётами. Подробности и чеклист см. в [docs/testing/stt_smoke.md](docs/testing/stt_smoke.md).

### Команда запуска
```bash
python scripts/stt_smoke.py \
  --playlist playlists/smoke_demo/playlist.yaml \
  --report build/stt_smoke_report.json
```

Скрипт складывает транскрипции в `build/stt_smoke/<timestamp>/` и формирует отчёт `build/stt_smoke_report.json`.

### Отчёт и интерпретация
- Блок `summary` повторяет агрегаты production-отчёта `summary_<period>.md`: количество записей, покрытие, длительность и стоимость (см. [SRS — Тексты звонков Bitrix24](docs/SRS%20—%20Тексты%20звонков%20Bitrix24%20(выгрузка%20за%2060%20дней).md#73-%D0%BE%D1%82%D1%87%D1%91%D1%82-summary_periodmd)).
- Записи со `status="success"` содержат путь до транскрипта и расчётную стоимость; `status="failure"` включают `error_code`/`error_message` и сверяются с [docs/testing/error_catalog.json](docs/testing/error_catalog.json).
- Результат CI архивирует как артефакт `stt-smoke-report` (файл `build/stt_smoke_report.json`) внутри workflow **CI › quality**; загрузить можно со страницы запуска в GitHub Actions.
- Для расширенного runbook и UAT-чеклиста переходите по ссылкам: [docs/runbooks/call_export.md](docs/runbooks/call_export.md), [docs/b24-transcribe/ONE-PAGER.md#uat-чеклист](docs/b24-transcribe/ONE-PAGER.md#uat-%D1%87%D0%B5%D0%BA%D0%BB%D0%B8%D1%81%D1%82), [docs/testing/strategy.md](docs/testing/strategy.md).

## Переменные окружения Compose

| Переменная      | Значение по умолчанию | Назначение                          |
|-----------------|------------------------|-------------------------------------|
| `APP_ENV`       | `local`                | Режим работы приложения             |
| `APP_HOST`      | `0.0.0.0`              | Адрес, на котором слушает uvicorn   |
| `APP_PORT`      | `8000`                 | Порт приложения и проброс наружу    |
| `DATABASE_URL`  | —                      | Полный DSN Postgres (перекрывает настройки ниже) |
| `DB_HOST`       | `db`                   | Хост Postgres внутри docker-compose |
| `DB_PORT`       | `5432`                 | Порт Postgres                       |
| `DB_USER`       | `postgres`             | Имя пользователя БД                 |
| `DB_PASSWORD`   | `postgres`             | Пароль пользователя БД              |
| `DB_NAME`       | `mastermobile`         | Имя базы данных                     |
| `REDIS_HOST`    | `redis`                | Хост Redis                          |
| `REDIS_PORT`    | `6379`                 | Порт Redis                          |
| `B24_BASE_URL`  | `https://example.bitrix24.ru/rest` | Базовый URL REST Bitrix24 (можно указывать с или без завершающего `/rest`) |
| `B24_WEBHOOK_USER_ID` | `1`            | Идентификатор пользователя webhook Bitrix24 |
| `B24_WEBHOOK_TOKEN` | `changeme`        | Токен webhook Bitrix24 (замените в `.env`) |
| `B24_RATE_LIMIT_RPS` | `2.0`            | Лимит запросов к Bitrix24 в секунду |
| `B24_BACKOFF_SECONDS` | `5`             | Стартовый шаг экспоненциального бэкоффа |
| `OPENAI_API_KEY` | —                    | Ключ OpenAI; оставьте пустым, если STT недоступно |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | Базовый URL OpenAI/совместимого API |
| `WHISPER_RATE_PER_MIN_USD` | `0.006`    | Ставка Whisper за минуту аудио (для расчёта стоимости) |
| `STT_MAX_FILE_MINUTES` | `0`            | Максимальная длительность файла для STT; `0` отключает обработку |
| `CHATGPT_PROXY_URL` | `http://proxy.example.com:8080` | HTTP-прокси для исходящих запросов к ChatGPT/Whisper |
| `STORAGE_BACKEND` | `local`             | Тип хранилища (`local` или `s3`) |
| `S3_ENDPOINT_URL` | —                   | Кастомный endpoint S3 (для minio/совместимых сервисов) |
| `S3_REGION`     | —                     | Регион S3 |
| `S3_BUCKET`     | —                     | Имя S3-бакета для хранения артефактов |
| `S3_ACCESS_KEY_ID` | —                  | Access key для S3 |
| `S3_SECRET_ACCESS_KEY` | —             | Secret key для S3 |
| `LOCAL_STORAGE_DIR` | `/app/storage`    | Путь локального хранилища (монтируется в контейнер `app`) |
| `LOG_LEVEL`     | `INFO`                 | Уровень логирования приложения      |
| `WORKER_METRICS_HOST` | `0.0.0.0`        | Адрес, на котором слушает экспортер метрик STT-воркера |
| `WORKER_METRICS_PORT` | `9100`           | Порт экспортера метрик STT-воркера  |
| `JWT_SECRET`    | `changeme`             | Секрет для подписи JWT-токенов      |
| `JWT_ISSUER`    | `mastermobile`         | Значение `iss` в выданных JWT       |
| `CORS_ORIGINS`  | `http://localhost:3000` | Разрешённые источники CORS (через запятую) |
| `MAX_PAGE_SIZE` | `100`                   | Максимальный размер страницы для пагинации |
| `REQUEST_TIMEOUT_S` | `30`                | Таймаут исходящих запросов (секунды) |
| `ENABLE_TRACING` | `false`                | Включение экспорта трассировок OpenTelemetry |
| `PII_MASKING_ENABLED` | `false`           | Маскирование персональных данных в логах |
| `DISK_ENCRYPTION_FLAG` | `false`          | Флаг шифрования томов/дисков (prod → `true`) |
| `CALL_SUMMARY_ENABLED` | `false`          | Автогенерация Markdown-саммари для расшифровок звонков |

> Все значения можно переопределить в `.env` перед запуском `docker compose` / `make up`.
> `docker-compose.yml` подключает `.env.example` **до** `.env`, поэтому локальные
> переопределения и дополнительные переменные из `.env` всегда имеют приоритет.

> При пустом `OPENAI_API_KEY` или значении `STT_MAX_FILE_MINUTES=0` сервис стартует без обработки STT: запросы на транскрибацию пропускаются, очередь заданий не создаётся.

## CI

- Основной workflow `.github/workflows/ci.yml` после `make test` запускает `python scripts/stt_smoke.py` с плейлистом из репозитория (`docs/testing/stt_smoke_playlist.json` по умолчанию).
- Для запуска STT-smoke проверок необходимо добавить секрет `OPENAI_API_KEY` в настройках репозитория.
- Если плейлист хранится в другом месте, задайте относительный путь в переменной репозитория `STT_SMOKE_PLAYLIST_PATH`.

## Bitrix24 клиент

Асинхронный помощник для получения статистики звонков теперь доступен из пакета `apps.mw.src.integrations.b24`:

```python
from datetime import datetime, UTC

from apps.mw.src.integrations.b24 import list_calls


calls = await list_calls(
    date_from=datetime(2024, 8, 1, tzinfo=UTC),
    date_to=datetime(2024, 8, 31, 23, 59, 59, tzinfo=UTC),
)
```

Клиент автоматически использует переменные окружения `B24_BASE_URL`, `B24_WEBHOOK_USER_ID`, `B24_WEBHOOK_TOKEN`, `B24_RATE_LIMIT_RPS` и `B24_BACKOFF_SECONDS`, применяя пагинацию и экспоненциальный бэкофф (`429`/`5xx`).

## Архитектура (вкратце)
- FastAPI (apps/mw/src)
- Postgres (данные)
- Redis (кэш/очереди)
- OpenAPI: ./openapi.yaml
- CI: .github/workflows/ci.yml

## Полезное
- Архитектура: [docs/architecture/overview.md](docs/architecture/overview.md)
- Документация: ./docs
- Контрибьютинг: ./CONTRIBUTING.md
- Лицензия: ./LICENSE

## Документация

### B24 Transcribe

- [PRD — Тексты звонков Bitrix24](docs/PRD%20—%20Тексты%20звонков%20Bitrix24.md)
- [SRS — Тексты звонков Bitrix24 (выгрузка за 60 дней)](docs/SRS%20—%20Тексты%20звонков%20Bitrix24%20(выгрузка%20за%2060%20дней).md)
- [ONE-PAGER — Тексты всех звонков за 60 дней](docs/b24-transcribe/ONE-PAGER.md)
- [Runbook: экспорт звонков](docs/runbooks/call_export.md)
- [Calls CSV schema](docs/specs/call_registry_schema.yaml)

## API v1 — быстрые вызовы

- `GET /api/v1/system/ping` — пинг сервисного слоя; заголовок `X-Request-Id` опционален (будет сгенерирован, если не передан).
- `GET /api/v1/returns` — пагинированный список возвратов. Необязательные query-параметры: `page`, `page_size`.
- `POST /api/v1/returns` — создание возврата. Требует `Idempotency-Key` (уникальный ≤128 символов) и желательно `X-Request-Id`.
- `GET /api/v1/returns/{return_id}` — просмотр конкретного возврата.
- `PUT /api/v1/returns/{return_id}` — полная замена возврата. Требует `Idempotency-Key` и рекомендуемый `X-Request-Id`.
- `DELETE /api/v1/returns/{return_id}` — удаление возврата. Требует `Idempotency-Key`.

Пример запроса на создание возврата:

```bash
curl -X POST http://localhost:8000/api/v1/returns \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $(uuidgen)" \
  -H "X-Request-Id: $(uuidgen)" \
  -d '{
        "source": "warehouse",
        "courier_id": "courier-001",
        "items": [
          {"sku": "SKU-1001", "qty": 1, "quality": "new", "reason_code": "customer_changed_mind"}
        ]
      }'
```
