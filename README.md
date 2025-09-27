# MasterMobile — Middleware & Integrations (FastAPI)

[![Docs CI](https://github.com/mastermobile/mastermobile/actions/workflows/docs-ci.yml/badge.svg)](https://github.com/mastermobile/mastermobile/actions/workflows/docs-ci.yml)

## Что это
Единый middleware-сервис: интеграция 1С (УТ 10.3/11), Bitrix24 и «Walking Warehouse».

## Предварительные требования

- Docker Engine с установленным Compose-плагином (тестировалось на версии 2.24+).
- Локальный файл `.env`, собранный из `.env.example` (в нём заданы параметры приложения, Postgres и Redis).

## Быстрый старт (локально)
1. `make init`
2. `make up`
3. `make seed` — по мере появления данных
4. `make test`

> Для запуска только зависимостей можно выполнить `docker compose up -d db redis`.

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
| `JWT_SECRET`    | `changeme`             | Секрет для подписи JWT-токенов      |
| `JWT_ISSUER`    | `mastermobile`         | Значение `iss` в выданных JWT       |
| `CORS_ORIGINS`  | `http://localhost:3000` | Разрешённые источники CORS (через запятую) |
| `MAX_PAGE_SIZE` | `100`                   | Максимальный размер страницы для пагинации |
| `REQUEST_TIMEOUT_S` | `30`                | Таймаут исходящих запросов (секунды) |
| `ENABLE_TRACING` | `false`                | Включение экспорта трассировок OpenTelemetry |
| `PII_MASKING_ENABLED` | `false`           | Маскирование персональных данных в логах |
| `DISK_ENCRYPTION_FLAG` | `false`          | Флаг шифрования томов/дисков (prod → `true`) |

> Все значения можно переопределить в `.env` перед запуском `docker compose` / `make up`.
> `docker-compose.yml` подключает `.env.example` **до** `.env`, поэтому локальные
> переопределения и дополнительные переменные из `.env` всегда имеют приоритет.

> При пустом `OPENAI_API_KEY` или значении `STT_MAX_FILE_MINUTES=0` сервис стартует без обработки STT: запросы на транскрибацию пропускаются, очередь заданий не создаётся.

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
