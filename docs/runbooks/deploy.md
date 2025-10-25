<!-- docs/runbooks/deploy.md -->
# Деплой MasterMobile MW

## Область применения
Запуск и сопровождение выката middleware в средах `staging` и `production`. Runbook рассчитан
на инженеров, ответственных за release management и эксплуатацию.

## Подготовка
1. Убедиться, что все изменения смёржены в `main` и прошли CI (`make lint`, `make typecheck`,
   `make test`).
2. Проверить актуальность `openapi.yaml` (workflow `OpenAPI validation` должен быть зелёным).
3. Обновить `docs/` (changelog, версии runbook) и получить approve владельца области.
4. Зафиксировать версию артефакта: тег `vX.Y.Z` + запись в release notes.

## Автоматический pipeline
1. **Docker build** — собирается образ на базе `apps/mw/Dockerfile` и пушится в registry
   (`registry.example.com/mastermobile/mw:<tag>`).
2. **Database migrations** — выполняются через Alembic с флагом `--sql` для dry-run, затем
   применяется `alembic upgrade head` на staging.
3. **Smoke-tests** — запускается `pytest -m smoke` против staging (см. `docs/testing/strategy.md`).
4. **Manual approval** — проверяющий валидирует OpenAPI, миграции и smoke-отчёт.
5. **Prod deploy** — развёртывание helm/k8s чарта или docker compose (зависит от площадки).

## Чек-лист перед выкатом на прод
- [ ] Финальные миграции прогнаны на staging, данные валидны.
- [ ] Метрики health-check и latency в норме ≥ 30 минут.
- [ ] Feature flags/конфигурация подготовлены (см. архитектурную документацию, например `docs/architecture/overview.md`).
- [ ] Команда поддержки уведомлена в Slack/Teams за 30 минут до выката.

## Мониторинг во время выката
- API health (`/health`) — непрерывный мониторинг через Grafana/Prometheus.
- Ошибки приложения — `loguru`/Sentry или аналогичный агрегатор логов.
- База данных — задержка репликации, время выполнения долгих запросов.
- Redis — размер очередей, количество повторов задач.

## Прокси nginx
- Используйте конфигурацию из `infra/nginx/mastermobile.conf`.
- Локация `/api/` проброшена в unix-сокет приложения (`/var/run/mastermobile/mw.sock`),
  поэтому POST `https://master-mobile.ru/api/v1/chatkit/session` должен возвращать `200`.
- После выката перезапустите nginx и убедитесь в отсутствии 4xx/5xx в access-логах.

## Проверки после выката
1. Smoke-тесты против production (`pytest -m smoke --env=prod`).
2. Сверка версий: `curl https://prod.example.com/health` → `version` соответствует тегу.
3. Контроль ключевых бизнес-сценариев с продуктовой командой.
4. Обновить runbook/документацию, если выявлены отклонения.

## Rollback
- **Простая отмена:** `helm rollback mastermobile <previous-release>` или `docker compose
  pull && docker compose up -d` с предыдущим тегом.
- **База данных:** выполнить Alembic downgrade (`alembic downgrade -1`) и зафиксировать состояние.
- **Коммуникация:** уведомить заинтересованных лиц, завести инцидент (см. `incidents.md`).

## Контакты и эскалация
- `@team-arch` — владельцы архитектуры и миграций.
- `@team-ops` — эксплуатация и инфраструктура.
- `@team-product` — подтверждение бизнес-сценариев.

## Связанные документы
- [Локальная разработка](local_dev.md)
- [Incident response](incidents.md)
- [Testing strategy](../testing/strategy.md)
