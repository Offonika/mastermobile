# Локальная разработка
1) `make init` — venv и базовые инструменты
2) `make up` — поднимает db/redis/app
3) `make db-upgrade` — применяет миграции через корневой `./alembic.ini`
4) `make test` — прогоним тесты
5) Точки входа: `apps/mw/src/app.py` (uvicorn)

> Для ручного запуска Alembic используйте `.venv/bin/alembic -c ./alembic.ini upgrade head`.
