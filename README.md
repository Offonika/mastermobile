# MasterMobile — Middleware & Integrations (FastAPI)

[![CI](https://github.com/Offonika/mastermobile/actions/workflows/ci.yml/badge.svg)](https://github.com/Offonika/mastermobile/actions/workflows/ci.yml)
[![Docs CI](https://github.com/Offonika/mastermobile/actions/workflows/docs-ci.yml/badge.svg)](https://github.com/Offonika/mastermobile/actions/workflows/docs-ci.yml)

## Что это
Единый middleware-сервис: интеграция актуальных конфигураций 1С, Bitrix24 и «Walking Warehouse».

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
- `make docs-links` — сканирование ссылок через `lychee` с конфигом `.lychee.toml` (контейнер `lycheeverse/lychee`).
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
| `CORS_ORIGINS`  | `http://localhost:3000,https://master-mobile.ru,https://mastermobile.bitrix24.ru` | Разрешённые источники CORS (через запятую) |
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
- Golden set NLU: [docs/NLU/golden_set.csv](docs/NLU/golden_set.csv) — 100 запросов (текст/голос) с разметкой по слотам, структура описана в [PRD «Ассистент мастера»](docs/PRD%20%E2%80%94%20%C2%AB%D0%90%D1%81%D1%81%D0%B8%D1%81%D1%82%D0%B5%D0%BD%D1%82%20%D0%BC%D0%B0%D1%81%D1%82%D0%B5%D1%80%D0%B0%C2%BB.md#e-golden-set-%D0%B4%D0%BB%D1%8F-nlu%D0%BF%D0%BE%D0%B8%D1%81%D0%BA%D0%B0).
- Контрибьютинг: ./CONTRIBUTING.md
- Лицензия: ./LICENSE
- Артефакты 1С для SRS КМП4: `1c/config_dump_txt/` хранит выборку ключевых объектов поддерживаемой конфигурации «1С:Управление торговлей» (модули возвратов, перемещений, регистров), а внешняя обработка лежит в `1c/external/kmp4_delivery_report/` (распакованный код в `src/`, рядом — собранный XML). Выгрузка фиксирует текущее поведение обмена/форм и служит источником требований при подготовке нового SRS по потоку КМП4.

## Walking Warehouse

«Ходячий склад» (Walking Warehouse) закрывает сквозной процесс доставки и возвратов между ERP 1С, middleware и мобильным виджетом Bitrix24: менеджер запускает доставку и допродажи из 1С, курьер ведёт маршрут и «рюкзак» в веб-приложении, а сервис фиксирует фото, геометки, наличные и возвраты без новых типов документов. Стратегические договорённости и UX собраны в профильных документах:

- [PRD «Ходячий склад»](docs/PRD%20Ходячий%20склад.md) — цель, роли и процессы «рюкзака», доставки и возвратов.
- [ONE-PAGER «Ходячий рюкзак»](docs/ONE-PAGER-%D0%A5%D0%BE%D0%B4%D1%8F%D1%87%D0%B8%D0%B9%D0%A0%D1%8E%D0%BA%D0%B7%D0%B0%D0%BA.md) — сценарии по шагам и ключевые договорённости по деньгам, штрихкодам и геометкам.
- [SRS «Курьерская доставка с “Ходячим складом”»](docs/Software%20Requirements%20Specification%20SRS.md) — требования к API, логике «рюкзака», ролям и идемпотентности.
- [UX-скетчи «Рюкзак/Продажа»](docs/UX-%D1%81%D0%BA%D0%B5%D1%82%D1%87%D0%B8-%D0%A0%D1%8E%D0%BA%D0%B7%D0%B0%D0%BA:%D0%9F%D1%80%D0%BE%D0%B4%D0%B0%D0%B6%D0%B0.md) — интерфейс курьера, оффлайн-поведение и правила доступности.
- [00-Core — Синхронизация документации](docs/00%E2%80%91Core%20%E2%80%94%20%D0%A1%D0%B8%D0%BD%D1%85%D1%80%D0%BE%D0%BD%D0%B8%D0%B7%D0%B0%D1%86%D0%B8%D1%8F%20%D0%B4%D0%BE%D0%BA%D1%83%D0%BC%D0%B5%D0%BD%D1%82%D0%B0%D1%86%D0%B8%D0%B8.md) — единые статусы, SoT и style-guide для всех документов.

### Setup & verification

1. Скопируйте `.env.example` в `.env`, задайте доступы 1С/Bitrix24 и флаги Walking Warehouse (например, включение кнопки «Положить в рюкзак» и уведомлений).
2. Поднимите окружение: `make init && make up`. Метрики FastAPI проверяются на `http://localhost:8000/metrics`; health-пинг — `http://localhost:8000/health`.
3. Проверьте REST-контракт возвратов: подготовьте JWT с ролью `1c` или `admin` (см. `JWT_SECRET`/`JWT_ISSUER` в `.env`). Выполните `curl -H "Authorization: Bearer $JWT_TOKEN" -H "X-Request-Id: doc-readme" http://localhost:8000/api/v1/returns` и убедитесь, что возвращается пагинированный список. Для CRUD сценариев используйте `tests/test_returns_api.py`.
4. Запустите профильные тесты Walking Warehouse: `pytest tests/test_returns_api.py tests/test_db_models_returns.py` (или общий `make test`). Они подтверждают идемпотентность `/api/v1/returns`, ORM-схему и ограничения по причинам возврата.

### Docs linting

Перед релизом изменений по Walking Warehouse обязательно прогоняйте Docs CI локально:

- `make docs-markdownlint`
- `make docs-links`
- `make docs-spellcheck`

## Assistant

### Структура ассистента

- `apps/mw/src/api/routers/chatkit.py` — REST-контракт для ChatKit (`/api/v1/chatkit/session`, `/api/v1/chatkit/widget-action`) и rate limiting. 【F:apps/mw/src/api/routers/chatkit.py†L22-L211】
- `apps/mw/src/services/chatkit.py` — HTTP-клиент OpenAI, выдаёт `client_secret` для виджета; `apps/mw/src/services/chatkit_state.py` хранит флаги ожидания запроса. 【F:apps/mw/src/services/chatkit.py†L10-L74】【F:apps/mw/src/services/chatkit_state.py†L1-L39】
- `apps/mw/src/integrations/openai/workflows.py` — проксирует события виджета в workflow Agent Builder и обогащает метаданными. 【F:apps/mw/src/integrations/openai/workflows.py†L1-L125】
- `apps/mw/src/web/static/assistant/index.html` — статическая демо-страница, раздаётся по `/assistant`. 【F:apps/mw/src/app.py†L75-L106】【F:apps/mw/src/web/static/assistant/index.html†L1-L122】
- `apps/mw/src/web/static/assistant/vendor/chatkit.js` — компактная версия виджета без React, подключается на демо-странице. 【F:apps/mw/src/web/static/assistant/vendor/chatkit.js†L1-L209】
- `frontend/src/components/B24Assistant.tsx` — основная интеграция ассистента в Bitrix24 через `@openai/chatkit-react`. 【F:frontend/src/components/B24Assistant.tsx†L1-L156】
- `scripts/smoke_chatkit.sh` — shell-smoke, проверяет `/health`, выдачу `client_secret` и подтверждение `widget-action`. 【F:scripts/smoke_chatkit.sh†L1-L89】
- Тесты: `tests/api/test_chatkit.py`, `tests/services/test_chatkit.py`, `tests/test_chatkit_widget_action.py` — покрывают ручки, сервис и обработку действий виджета. 【F:tests/api/test_chatkit.py†L1-L125】【F:tests/services/test_chatkit.py†L1-L154】【F:tests/test_chatkit_widget_action.py†L1-L80】

### Как обновить `chatkit.js`

`apps/mw/src/web/static/assistant/vendor/chatkit.js` — артефакт, который хранится в репозитории, чтобы показать работу ассистента без React. При смене API нужно держать его в актуальном состоянии:

1. Обновите зависимости фронтенда до нужной версии ChatKit: скорректируйте `@openai/chatkit-react` в `frontend/package.json` и выполните `npm install`. 【F:frontend/package.json†L8-L23】
2. Проверьте основную интеграцию в Bitrix24: `npm run build` в `frontend/` должен пройти без ошибок и собрать production-бандл в `dist/`. 【F:frontend/package.json†L5-L11】
3. Синхронизируйте поведение статического виджета:
   - Сверьтесь с актуальной логикой получения `client_secret` и отправки `widget-action` в `B24Assistant.tsx` и `chatkit.py`.
   - Обновите функции `requestSession`, `sendWidgetAction` и разметку внутри `ChatKitWidget` в `vendor/chatkit.js`, чтобы поля и заголовки совпадали с API. 【F:apps/mw/src/web/static/assistant/vendor/chatkit.js†L1-L209】【F:frontend/src/components/B24Assistant.tsx†L25-L122】【F:apps/mw/src/api/routers/chatkit.py†L124-L211】
   - Убедитесь, что файл по-прежнему экспортирует глобальный `ChatKitWidget` (в конце файла). 【F:apps/mw/src/web/static/assistant/vendor/chatkit.js†L189-L209】
4. Откройте `http://localhost:8000/assistant/` после запуска стека и убедитесь, что виджет инициализируется (при необходимости — с реальным `OPENAI_API_KEY`). 【F:apps/mw/src/app.py†L82-L88】

### Команды деплоя

1. Скопируйте `.env.example` → `.env` и заполните `OPENAI_API_KEY`, `OPENAI_WORKFLOW_ID`, `OPENAI_VECTOR_STORE_ID`, параметры Bitrix24. 【F:.env.example†L25-L36】【F:apps/mw/src/config/settings.py†L40-L57】
2. Соберите Python-зависимости и инфраструктуру: `make init && make up`. Команда поднимет `app`, `db`, `redis` и пробросит `/assistant`. 【F:Makefile†L24-L40】【F:docker-compose.yml†L1-L73】
3. Для фронтенда выполните `npm install && npm run build` в `frontend/`, затем опубликуйте `dist/` в хостинге Bitrix24 или подключите через reverse-proxy. 【F:frontend/package.json†L5-L23】
4. При выкладке в стоящую среду используйте `docker compose build app && docker compose up -d app` (или пайплайн из `docs/runbooks/deploy.md`) и следите за health-check `http://<host>:8000/health`. 【F:docs/runbooks/deploy.md†L9-L43】【F:docker-compose.yml†L5-L36】
5. После деплоя прогоните smoke-скрипт: `./scripts/smoke_chatkit.sh --base-url http://<host>:8000`. Он проверит health, выдачу сессии и подтверждение действия. 【F:scripts/smoke_chatkit.sh†L1-L89】

### Smoke-тест OpenAI workflow

Для проверки доступности Agent Builder workflow можно воспользоваться вспомогательным скриптом:

```bash
./scripts/openai_workflow_smoke.sh --env-file .env "ping"
```

Скрипт берёт `OPENAI_API_KEY`, `OPENAI_WORKFLOW_ID`, `OPENAI_PROJECT`, `OPENAI_ORG` и `OPENAI_BASE_URL` либо из текущих переменных окружения, либо из указанного `.env`. В ответ ожидается JSON с результатами выполнения workflow. Если нужно отправить запрос вручную через `curl`, следите за тем, чтобы не заключать идентификатор в кавычки и передавать корректный заголовок `Content-Type`:

```bash
curl "https://api.openai.com/v1/workflows/${OPENAI_WORKFLOW_ID}/runs" \
  -H "Authorization: Bearer ${OPENAI_API_KEY}" \
  -H "Content-Type: application/json" \
  ${OPENAI_PROJECT:+-H "OpenAI-Project: ${OPENAI_PROJECT}"} \
  ${OPENAI_ORG:+-H "OpenAI-Organization: ${OPENAI_ORG}"} \
  -d '{"input":{"message":"ping"}}'
```

> Типичная ошибка: если в ответ приходит `{ "error": { "message": "Invalid URL (POST /v1/workflows/runs)" } }`,
> значит, идентификатор workflow не попал в путь запроса. Убедитесь, что вызываете
> `https://api.openai.com/v1/workflows/${OPENAI_WORKFLOW_ID}/runs` и **не** передаёте поле
> `workflow_id` в теле запроса.
>
> Обратите внимание: `source .env` не подойдёт для загрузки переменных с пробелами. Используйте вспомогательный скрипт или экспортируйте только нужные `OPENAI_*` значения вручную.

### Чек-лист тестов

- `make lint` — статический анализ Python. 【F:Makefile†L42-L46】
- `make typecheck` — mypy по `apps/`. 【F:Makefile†L48-L49】
- `make test` или `pytest tests/api/test_chatkit.py tests/services/test_chatkit.py tests/test_chatkit_widget_action.py` — функциональные проверки ассистента. 【F:Makefile†L51-L52】【F:tests/api/test_chatkit.py†L1-L125】【F:tests/services/test_chatkit.py†L1-L154】【F:tests/test_chatkit_widget_action.py†L1-L80】
- `npm run build` в `frontend/` — сборка React-виджета. 【F:frontend/package.json†L5-L11】
- `./scripts/smoke_chatkit.sh --base-url http://localhost:8000` — end-to-end smoke. 【F:scripts/smoke_chatkit.sh†L1-L89】

## Документация

### Walking Warehouse

- [PRD — Ходячий склад](docs/PRD%20Ходячий%20склад.md)
- [ONE-PAGER — Рюкзак курьера](docs/ONE-PAGER-%D0%A5%D0%BE%D0%B4%D1%8F%D1%87%D0%B8%D0%B9%D0%A0%D1%8E%D0%BA%D0%B7%D0%B0%D0%BA.md)
- [Runbook: операционные логи](docs/runbooks/ww.md)

## API v1 — быстрые вызовы

- `GET /api/v1/system/ping` — пинг сервисного слоя; заголовок `X-Request-Id` опционален (будет сгенерирован, если не передан).
- `GET /api/v1/returns` — пагинированный список возвратов. Требует `Authorization: Bearer <JWT>` с ролью `1c` или `admin`; необязательные query-параметры: `page`, `page_size`.
- `POST /api/v1/returns` — создание возврата. Требует `Idempotency-Key` (уникальный ≤128 символов) и желательно `X-Request-Id`.
- `GET /api/v1/returns/{return_id}` — просмотр конкретного возврата.
- `PUT /api/v1/returns/{return_id}` — полная замена возврата. Требует `Idempotency-Key` и рекомендуемый `X-Request-Id`.
- `DELETE /api/v1/returns/{return_id}` — удаление возврата. Требует `Idempotency-Key`.

Пример запроса на создание возврата:

```bash
curl -X POST http://localhost:8000/api/v1/returns \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT_TOKEN" \
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
