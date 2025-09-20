# Локальная разработка
0) `cp .env.example .env` — скопируйте переменные окружения перед стартом Compose
1) `make init` — venv и базовые инструменты
2) `docker compose up -d db redis` — поднимает только Postgres и Redis (по необходимости)
3) `make up` — собирает образ приложения и стартует app/db/redis
4) `make db-upgrade` — применяет миграции через `./apps/mw/migrations/alembic.ini`
5) `make test` — прогоним тесты
6) Точки входа: `apps/mw/src/app.py` (uvicorn)

> Для ручного запуска Alembic используйте `.venv/bin/alembic -c ./apps/mw/migrations/alembic.ini upgrade head`.
