# Контрибьютинг

## Бранчинг
- trunk-based: `main` (protected), фичи — `feat/*`, фиксы — `fix/*`.

## Коммиты
- Conventional Commits: `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`.
- Один PR — одна логическая задача.

## Бинарные артефакты
- Перед началом работы установите [Git LFS](https://git-lfs.com/) и выполните `git lfs install`.
- Репозиторий хранит через LFS все `*.epf`, `*.erf` и дампы `1c/config_dump_txt/**/*.txt`.

## Код-стайл
- ruff, mypy(strict), black (через ruff format).
- Перед пушем: `make lint && make typecheck && make test`.

## PR
- Чек-лист: OpenAPI обновлён? Тесты покрывают изменения? Миграции применяются?
