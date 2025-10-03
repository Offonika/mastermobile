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
3. `make seed` — по мере появления данных
4. `make test`

> Для запуска только зависимостей можно выполнить `docker compose up -d db redis`.
> Метрики Prometheus для FastAPI-приложения доступны по адресу `http://localhost:8000/metrics`.

## CI и Docs-CI

Основной workflow [`ci.yml`](.github/workflows/ci.yml) запускает два набора проверок:

- **Quality** — Python-инструменты (`make lint`, `make typecheck`, `make test`).
- **Docs quality** — проверки документации и ссылок: `make docs-markdownlint`, `make docs-links`, `make docs-spellcheck` и смоук-тест `make docs-ci-smoke`, который подтверждает, что link-checker корректно ловит ошибочные URL.

Для локального запуска docs-проверок доступны команды Makefile:

- `make docs-markdownlint` — проверка Markdown по правилам из `.markdownlint.yml` (использует контейнер `ghcr.io/igorshubovych/markdownlint-cli`).
- `make docs-links` — сканирование ссылок через `lychee` с конфигом `.lychee.toml` (контейнер `ghcr.io/lycheeverse/lychee`).
- `make docs-spellcheck` — орфография через `codespell` c параметрами из `.codespellrc`.
- `make docs-ci` — последовательный запуск всех проверок.
- `make docs-ci-smoke` — временно создаёт тестовый markdown с «битой» ссылкой и убеждается, что `lychee` падает с ошибкой.

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


## CI

 - Основной workflow `.github/workflows/ci.yml` после `make test` проверяет сборку и качество кода.

## Архитектура (вкратце)
- FastAPI (apps/mw/src)
- Postgres (данные)
- Redis (кэш/очереди)
- OpenAPI: ./openapi.yaml
- CI: .github/workflows/ci.yml

## Полезное
- Архитектура: [docs/architecture/overview.md](docs/architecture/overview.md)
- Конституция: [docs/constitution.md](docs/constitution.md)
- Документация: ./docs
- Контрибьютинг: ./CONTRIBUTING.md
- Лицензия: ./LICENSE
- Артефакты 1С для SRS КМП4: `1c/config_dump_txt/` хранит выборку ключевых объектов УТ 10.3 (модули возвратов, перемещений, регистров), а внешняя обработка лежит в `1c/external/kmp4_delivery_report/` (распакованный код в `src/`, рядом — собранный XML). Выгрузка фиксирует текущее поведение обмена/форм и служит источником требований при подготовке нового SRS по потоку КМП4.

## Walking Warehouse

«Ходячий склад» (Walking Warehouse) закрывает сквозной процесс доставки и возвратов между 1С УТ 10.3, middleware и мобильным виджетом Bitrix24: менеджер запускает доставку и допродажи из 1С, курьер ведёт маршрут и «рюкзак» в веб-приложении, а сервис фиксирует фото, геометки, наличные и возвраты без новых типов документов. Стратегические договорённости и UX собраны в профильных документах:

- [PRD «Ходячий склад»](docs/PRD%20Ходячий%20склад.md) — цель, роли, потоки доставки/рюкзака/возвратов.
- [ONE-PAGER «Ходячий рюкзак»](docs/ONE-PAGER-%D0%A5%D0%BE%D0%B4%D1%8F%D1%87%D0%B8%D0%B9%D0%A0%D1%8E%D0%BA%D0%B7%D0%B0%D0%BA.md) — сценарии по шагам и ключевые договорённости по деньгам/штрихкодам.
- [SRS «Курьерская доставка с “Ходячим складом”»](docs/Software%20Requirements%20Specification%20SRS.md) — требования к API, рюкзаку, идемпотентности и ролям.
- [UX-скетчи «Рюкзак/Продажа»](docs/UX-%D1%81%D0%BA%D0%B5%D1%82%D1%87%D0%B8-%D0%A0%D1%8E%D0%BA%D0%B7%D0%B0%D0%BA:%D0%9F%D1%80%D0%BE%D0%B4%D0%B0%D0%B6%D0%B0.md) — интерфейс курьера, оффлайн-поведение и правила доступности.
- [00-Core — Синхронизация документации](docs/00%E2%80%91Core%20%E2%80%94%20%D0%A1%D0%B8%D0%BD%D1%85%D1%80%D0%BE%D0%BD%D0%B8%D0%B7%D0%B0%D1%86%D0%B8%D1%8F%20%D0%B4%D0%BE%D0%BA%D1%83%D0%BC%D0%B5%D0%BD%D1%82%D0%B0%D1%86%D0%B8%D0%B8.md) — единые статусы, SoT и style-guide для всех документов.

### Setup & verification

1. Скопируйте `.env.example` в `.env`, задайте доступы 1С/Bitrix24 и флаги Walking Warehouse (например, включение кнопки «Положить в рюкзак» и уведомлений).
2. Поднимите окружение: `make init && make up`. Метрики FastAPI проверяются на `http://localhost:8000/metrics`; health-пинг — `http://localhost:8000/health`.
3. Проверьте REST-контракт возвратов: `curl -H "X-Request-Id: doc-readme" http://localhost:8000/api/v1/returns` должен возвращать пагинированный список. Для CRUD сценариев используйте `tests/test_returns_api.py`.
4. Запустите профильные тесты Walking Warehouse: `pytest tests/test_returns_api.py tests/test_db_models_returns.py` (или общий `make test`). Они подтверждают идемпотентность `/api/v1/returns`, ORM-схему и ограничения по причинам возврата.

### Docs linting

Перед релизом изменений по Walking Warehouse обязательно прогоняйте Docs CI локально:

- `make docs-markdownlint`
- `make docs-links`
- `make docs-spellcheck`

## Документация

### Walking Warehouse

- [PRD — Ходячий склад](docs/PRD%20Ходячий%20склад.md)
- [ONE-PAGER — Рюкзак курьера](docs/ONE-PAGER-%D0%A5%D0%BE%D0%B4%D1%8F%D1%87%D0%B8%D0%B9%D0%A0%D1%8E%D0%BA%D0%B7%D0%B0%D0%BA.md)
- [Runbook: операционные логи](docs/runbooks/ww.md)

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
