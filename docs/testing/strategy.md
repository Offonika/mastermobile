<!-- filename: docs/testing/strategy.md -->

<!-- docs/testing/strategy.md -->
# Тестовая стратегия MasterMobile

## Цели
- Поддерживать качество middleware на уровне требований PRD/SRS и API-контрактов.
- Гарантировать, что релизы, прошедшие CI/CD, воспроизводимы и предсказуемы.
- Обеспечить прозрачный процесс фикса и регрессии для команд разработки и эксплуатации.

## Пирамида тестирования
| Уровень | Покрытие | Инструменты | Частота |
|---------|----------|-------------|---------|
| Unit | Бизнес-логика, утилиты, валидация | `pytest`, `pytest-asyncio`, `factory_boy` | Каждый PR и локально |
| Contract/API | Соответствие OpenAPI и кодов ошибок | `schemathesis`, `httpx.AsyncClient`, `error_catalog.json` | Каждый PR и nightly |
| Integration | Работа с БД, Redis, миграциями | `pytest`, docker compose, Alembic | Каждый PR и перед релизом |
| E2E/Smoke | Ключевые пользовательские сценарии | `pytest -m smoke`, Postman/Insomnia | Staging/Prod после деплоя |
| Non-functional | Нагрузка и observability | `locust`, `k6`, Grafana alerts | По расписанию/по требованию |

## Политика PR и CI
- Каждый PR обязан проходить `make lint`, `make typecheck`, `make test` (см. `.github/workflows/ci.yml`).
- Для изменений OpenAPI обязателен workflow `OpenAPI validation`.
- Перед merge необходимо обновить связанный runbook/документацию, если меняется сценарий тестирования.
- Запрещено отключать тесты или использовать `xfail` без ADR/инцидента.

## Управление тестовыми данными
- Unit-тесты используют локальные фикстуры и фабрики, без подключения к внешним сервисам.
- Интеграционные тесты поднимают `docker-compose` стек (db, redis) с использованием `Makefile`
  (`make up`/`make down`). Каждое выполнение должно очищать состояние (`db-data` volume сбрасывается).
- Для smoke/E2E фиксировать тестовые аккаунты и ключи в защищённом сторе; переменные окружения
  хранить в `.env.example` с пометкой `# required for tests`.
- Ошибки и их ожидания синхронизируются через `docs/testing/error_catalog.json`.

## Автоматизация и покрытия
- **Линтеры:** `ruff` (PEP8, импорт, best practices).
- **Типы:** `mypy --strict`, обязательно для новых модулей.
- **Тесты:** `pytest` с плагинами `pytest-asyncio`, `pytest-cov` (целевое покрытие ≥ 80% линий).
- **Contract testing:** `schemathesis run openapi.yaml --checks all` (в pipeline по расписанию).
- **Регрессия:** ночные сборки запускают расширенный набор (`pytest -m "not slow"` днём, полный — ночью).

## Управление инцидентами
- Для каждого инцидента добавлять тест-кейс/регрессионный сценарий.
- Обновлять `error_catalog.json` и соответствующие фикстуры.
- Отражать шаги в [runbooks/incidents](../runbooks/incidents.md).

## Метрики качества
- Покрытие unit-тестами ≥ 80%, критические модули ≥ 90%.
- Время прохождения CI ≤ 10 минут; при превышении оптимизировать или параллелить тесты.
- Количество flaky-тестов = 0; обнаружение → обязательный фикс до релиза.

## Ответственность
| Зона | Владельцы | Обязанности |
|------|-----------|-------------|
| Unit/Integration | `@team-dev` | Поддержка тестов, фикстур и инфраструктуры PyTest |
| Contract/API | `@team-api` | Синхронизация OpenAPI, negative cases, schemathesis |
| E2E/Smoke | `@team-qa` | Сценарии end-to-end, тестовые данные |
| Нагрузочные | `@team-ops` + `@team-qa` | Планирование и выполнение нагрузочных прогонов |

## Связанные документы
- [Runbook: локальная разработка](../runbooks/local_dev.md)
- [Runbook: деплой](../runbooks/deploy.md)
- [Runbook: инциденты](../runbooks/incidents.md)
- [API Contracts](../API‑Contracts.md)
