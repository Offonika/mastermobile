# Контрибьютинг

## Бранчинг
- trunk-based: `main` (protected), фичи — `feat/*`, фиксы — `fix/*`.

## Коммиты
- Conventional Commits: `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`.
- Один PR — одна логическая задача.

## Код-стайл
- ruff, mypy(strict), black (через ruff format).
- Перед пушем: `make lint && make typecheck && make test`.

## PR
- Чек-лист: OpenAPI обновлён? Тесты покрывают изменения? Миграции применяются?
