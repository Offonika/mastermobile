# AGENTS.md

## 🧑‍💻 Инструкция для Codex и контрибьюторов

Этот репозиторий — общий для двух потоков: **«Ходячий склад (Walking Warehouse)»** и **Core Sync (1С: УТ 10.3 ↔ УТ 11)**. Здесь живут Middleware (FastAPI), контракты API v1, интеграция с Bitrix24 и вспомогательные сервисы.  
В файле описано, как агент Codex (и любой разработчик) должен работать с кодовой базой: запуск, тесты, линтинг, проверки контрактов, миграции БД и где искать основное.

**Нормативные ссылки** (актуальные версии):  
- **API‑Contracts v1.1.3 — Unified**  
- **SRS Core Sync v1.0.1** / **PRD Core Sync v1.1.1**  
- **SRS «Курьерская доставка» v0.3** / **PRD «Ходячий склад» v1.3.1**  
- **ER + DDL v0.6.4 — Unified (PostgreSQL 14+)**  
- **00‑Core v1.3** (Core‑API‑Style, Status‑Dictionary, Metrics/Alerts, Retention, Envs/Flags)

---

## 📐 Правила Codex (обязательно)

### Покрытие и тесты
- Покрытие не ниже **85 %** (`pytest --cov`, `--cov-fail-under=85`).
- Каждый новый публичный endpoint/handler/use‑case имеет unit‑тест и контрактный тест.
- Тесты лежат в `tests/` зеркально структуре пакетов; используем `pytest`, `pytest-asyncio`, `httpx.AsyncClient`, `respx`/`pytest-respx` для моков HTTP (Bitrix24/1С), `fakeredis` для очередей.
- Крайние случаи: идемпотентность (повтор с иным телом → 409), лимиты (429), таймауты (504), offline‑реплей, расчёты сумм/НДС/округлений.

### Типизация
- Запускаем `mypy --strict` для всего Python‑кода.
- Публичные функции и тестовые функции аннотированы полностью (включая `-> None`).
- `Any` не использовать (кроме обоснованных мест с `# type: ignore[...]/# noqa: ANN401`).

### Стиль
- Форматирование: **Black** (строки ≤ 88), линтер: **ruff** (`ruff check .`).
- Импорты: stdlib → сторонние → внутренние; неиспользуемые импорты запрещены.
- Логгер в модулях: `logger = logging.getLogger(__name__)`.

### Контракты API
- **Единый контракт**: API‑Contracts v1.1.3.  
- Проверка схем и совместимости: `make check-openapi` (генерация/валидация OpenAPI, привязка status/enum, problem+json).  
- Для всех модифицирующих запросов тестируйте `Idempotency-Key` (TTL 72ч, `(key, endpoint, actor_id)`), заголовки `X-Correlation-Id`, `X-Api-Version`.

### Наблюдаемость/логирование
- Логи JSON с `correlation_id`; ПДн (телефон/адрес/суммы) — маскировать.
- Метрики/алерты — по 00‑Core: задержка дельт, %5xx/%4xx, размер очередей, дубликаты/1000 POST.

### Безопасность
- JWT (access 15 мин, refresh 7 дней), JWKS‑ротация ≤90 дн, clock‑skew ≤30с.
- **Никогда** не сохраняем фото/файлы в БД — только ID Bitrix24 Disk.
- Webhooks подписываются `X-Webhook-Signature: sha256=HMAC_SHA256(body, secret)`, окно ±5 мин.

### Управление ресурсами
- HTTP‑клиенты, БД‑сессии и файловые дескрипторы закрывать (`async with`/`with`).
- В тестах — закрывайте клиентов/фикстуры; никаких утечек соединений.

### Локальный CI перед коммитом
- `make ci` или: `pytest -q --cov && mypy --strict . && ruff check . && make check-openapi`  
Код возврата обязан быть `0`.

---

## 📁 Структура репозитория

- **apps/mw/** — Middleware (FastAPI, бизнес‑логика)
  - `api/` — роутеры v1 (`/nsi`, `/docs`, `/cash`, `/sync`, `/tasks`, `/returns`)
  - `domain/` — use‑cases, валидаторы, идемпотентность
  - `infra/` — клиенты Bitrix24/1C, очереди (Redis), БД (SQLAlchemy)
  - `schemas/` — Pydantic‑схемы, OpenAPI источники
  - `settings.py` — конфиг
- **db/** — SQL‑миграции (`v0.6.1` → `v0.6.4`), скрипты инициализации
- **contracts/** — OpenAPI/JSON Schema, генераторы и проверки
- **infra/docker/** — контейнеры (mw, postgres, redis), `docker-compose.yml`
- **scripts/** — утилиты (генерация ключей, загрузка UF‑полей B24)
- **tests/** — автотесты (юнит/контракт/интеграционные)

---

## 🚀 Запуск (локально / Docker / Codex)

### Локально
```bash
python -V  # >=3.11
make venv && source .venv/bin/activate
cp infra/env/.env.example .env  # заполните значения
make run  # запускает FastAPI на http://localhost:8000
```

### Docker / Compose
```bash
docker compose up -d postgres redis
docker compose up mw  # билд и запуск middleware
```

### Полезные Make‑цели
```bash
make ci             # тесты+линтеры+контракты
make test           # pytest с покрытием
make lint           # ruff + black --check
make typecheck      # mypy --strict
make check-openapi  # валидатор контрактов/схем
make load-devdata   # опционально: начальные справочники/UF поля
```

---

## 🧪 Тесты и качество

- **Юнит/Async:** `pytest -q --cov` (+ `pytest-asyncio`).
- **HTTP‑моки:** `respx` + `httpx.AsyncClient` для Bitrix24/1С.
- **Очереди:** `fakeredis` для ретраев/backoff.
- **Контракты:** схематесты на схемы из `contracts/` (евалидатор OpenAPI, problem+json, статус‑маппинг).
- **Негативные сценарии:** 409 идемпотентности (повтор с иным телом), 429 rate limit, 504 upstream timeout, 413 upload‑limit, 401/403.

Пример запуска:
```bash
pytest -q --cov --cov-fail-under=85
mypy --strict apps/mw
ruff check apps/mw tests
```

---

## 🛠️ Переменные окружения (.env)

Минимум для dev:
```
DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/mw
REDIS_URL=redis://localhost:6379/0
JWT_SECRET=change_me
B24_BASE_URL=https://example.bitrix24.ru/rest
B24_TOKEN=xxx
ALLOWLIST_IPS=127.0.0.1/32
API_RATE_LIMIT_RPM=600
API_RATE_LIMIT_RPS=30
```
**Важно:** секреты не коммитим. Для Codex используйте секреты окружения.

---

## 🗄️ База данных и миграции

- Целевая СУБД: **PostgreSQL 14+**. Схема — согласно **ER + DDL v0.6.4 Unified**.
- Миграции — SQL‑файлы в `db/migrations/` (порядок по версии).  
- Применение: `make migrate` (psql). Откат — `make rollback` (если предусмотрен).
- Инварианты: `timestamptz (UTC)`, домены `ru_phone`/`currency_code`, **нехранение** фото/файлов.

---

## 🔐 Безопасность и ПДн

- ПДн (телефон/адрес/фото) в БД не храним (только ссылки/ID).  
- Маскирование ПДн в логах.  
- HTTPS везде; токены в Secret Manager (локально — в `.env`).

---

## 💬 Статусы, идемпотентность и ретраи (обязательные правила)

- **Статусы**: по **Status‑Dictionary v1**; PATCH `/tasks/{id}` — основной; `POST /tasks/{id}/status` — deprecated.  
- **Идемпотентность**: `Idempotency-Key` обязателен для всех модификаций; TTL 72ч; уникальность `(key, endpoint, actor_id)`; повтор с иным телом → 409.  
- **Ретраи в Bitrix24**: backoff 5s→15s→30s→… до 15мин; максимум 20 попыток/24ч; при 429 — `Retry-After`.

---

## 🧭 Git‑практики

- Ветки: `main` (stable), `develop` (интеграция), `feature/<ticket>`, `fix/<ticket>`.
- Коммиты: `[scope] кратко` (напр. `[api] add /returns reject`), описание что/зачем.
- PR: чек‑лист — тесты зелёные, линтеры пройдены, контракт не ломается, покрытие ≥85%.

---

## ⚡ Примеры задач для Codex/разработки

- **Контракты:** _Сгенерировать OpenAPI по Pydantic‑схемам, запустить `make check-openapi`, устранить несовпадения с API‑Contracts v1.1.3._
- **Идемпотентность:** _Добавить storage `(key, endpoint, actor_id)` и middleware, покрыть тестами повтор 200/201 и 409._
- **Bitrix24:** _Имплементировать `tasks.task.add/update` с ретраями/лимитами и problem+json‑обработкой ошибок._
- **Возвраты:** _Эндпоинт `/api/v1/returns/{id}/reject` + юнит‑тесты статусов/уведомлений._
- **Рюкзак:** _`/api/v1/couriers/{id}/stock` GET+POST, ETag/If‑None‑Match, кэширование._
- **Наблюдаемость:** _Прометей‑метрики: задержки дельт, ретраи, дубликаты/1000 POST; алерты по 00‑Core._
- **Безопасность:** _Подпись вебхуков, проверка окна ±5 мин, примеры для тестов._

---

## 📄 Дополнительно

- Дополняйте этот файл по мере развития. Любые изменения, влияющие на контракт/БД, должны ссылаться на актуальные версии документов (см. «Нормативные ссылки»).
- Вопросы по архитектуре/интеграциям — в Issues/PR или через Codex «Ask».  

— Конец —
