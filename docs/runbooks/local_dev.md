<!-- docs/runbooks/local_dev.md -->
# Локальная разработка

## Цель
Обеспечить разработчиков воспроизводимым окружением для Middleware, минимизируя время на
подготовку и исключая дрейф между локальной средой и CI/CD.

## Быстрый старт
1. Склонировать репозиторий и перейти в корень проекта.
2. Скопировать переменные окружения: `cp .env.example .env`.
3. Подготовить виртуальное окружение и зависимости: `make init`.
4. Запустить весь стек: `make up` (поднимает app, db, redis и собирает Docker-образ).
5. Применить миграции: `make db-upgrade`.
6. Прогнать проверки качества: `make lint && make typecheck && make test`.
7. Проверить здоровье API: `curl http://localhost:8000/health` → ожидаем `{ "status": "ok" }`.

## Требования
- Docker ≥ 24 c установленным плагином Compose (`docker compose version`).
- Python ≥ 3.11 и `make` на локальной машине для утилит из `Makefile`.
- Доступ к портам `8000`, `5432`, `6379` (по умолчанию). При конфликте измените значения в `.env`.

## Структура сервисов
| Сервис | Назначение | Порт контейнера | Порт хоста по умолчанию |
|--------|------------|------------------|-------------------------|
| `app`  | FastAPI MW (`apps/mw/src/app.py`) | `8000` | `${APP_PORT:-8000}` |
| `db`   | PostgreSQL 16 (данные MW)         | `5432` | `${DB_PORT:-5432}`  |
| `redis`| Кэш/очереди                       | `6379` | `${REDIS_PORT:-6379}` |

## Подробный сценарий
### 1. Подготовка окружения
- Создайте `.env` из примера и дополните секреты при необходимости.
- Проверьте новые переменные конфигурации: `JWT_SECRET`, `JWT_ISSUER`, `CORS_ORIGINS`,
  `MAX_PAGE_SIZE`, `REQUEST_TIMEOUT_S`, `ENABLE_TRACING`, а также флаги
  `PII_MASKING_ENABLED` и `DISK_ENCRYPTION_FLAG` для сценариев безопасности.
- Выполните `make init` — создаст `.venv`, установит `ruff`, `mypy`, `pytest`, Alembic и runtime-зависимости.
- Для чистого старта удалите контейнеры/volumes: `make down`.

### 2. Первый запуск стека
- `make up` — соберёт образ из `apps/mw/Dockerfile` и поднимет все сервисы.
- Проверить статусы: `docker compose ps` (сервис `app` должен быть в состоянии `healthy`).
- Логи приложения: `make logs`.

### 3. Работа в интерактивном режиме
- Код синхронизируется через volume `.:/app`; обновления подхватываются `uvicorn --reload`.
- Для миграций используйте `make db-upgrade`/`make db-downgrade` или Alembic напрямую:
  ```bash
  .venv/bin/alembic -c apps/mw/migrations/alembic.ini upgrade head
  ```
- Автоматические проверки перед коммитом: `make lint`, `make typecheck`, `make test`.

### 4. Smoke и контракт API
- Локальный health-check: `curl http://localhost:8000/health`.
- Сверка OpenAPI: `diff -u openapi.yaml <(curl -s http://localhost:8000/openapi.json)`.
- При расхождениях обновите `openapi.yaml` и задокументируйте изменения (см. `docs/testing/strategy.md`).

### 5. Завершение работы
- Остановить стек и удалить volumes: `make down`.
- Очистить виртуальное окружение при необходимости: `rm -rf .venv`.

## Troubleshooting
| Симптом | Действия |
|---------|----------|
| `app` падает с ошибкой подключения к БД | Проверьте `DB_*` переменные в `.env` и статус контейнера `db` (`docker compose logs db`). |
| Конфликт портов | Измените `APP_PORT`, `DB_PORT`, `REDIS_PORT` в `.env` и перезапустите `make up`. |
| Миграции не применяются | Убедитесь, что контейнер `db` в состоянии `healthy`, затем повторите `make db-upgrade`. |
| Тесты используют старый код | Очистите кэш pytest `rm -rf .pytest_cache` и перезапустите `make test`. |

## Связанные документы
- [Deploy runbook](deploy.md) — последовательность вывода изменений в окружения.
- [Incident response](incidents.md) — действия при сбоях в продакшене.
- [Testing strategy](../testing/strategy.md) — требования к автоматическим проверкам.
