# MasterMobile — Middleware & Integrations (FastAPI)

## Что это
Единый middleware-сервис: интеграция 1С (УТ 10.3/11), Bitrix24 и «Walking Warehouse».

## Быстрый старт (локально)
```bash
cp .env.example .env
make init
make up
make seed   # по мере появления
make test
```

## Архитектура (вкратце)
- FastAPI (apps/mw/src)
- Postgres (данные)
- Redis (кэш/очереди)
- OpenAPI: ./openapi.yaml
- CI: .github/workflows/ci.yml

## Полезное
- Документация: ./docs
- Контрибьютинг: ./CONTRIBUTING.md
- Лицензия: ./LICENSE
