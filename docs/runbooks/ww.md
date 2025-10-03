<!-- docs/runbooks/ww.md -->
# Runbook — операционные логи Walking Warehouse

## Назначение
Этот runbook описывает, как сопровождать поток логирования Walking Warehouse: проверять доступность логов,
соблюдать требования по маскированию PII и расследовать инциденты.
Документ предназначен для on-call инженеров, SRE и продуктовой команды Walking Warehouse.

## Контур логирования
- **Сервисы-источники:** FastAPI (`apps.mw`), воркеры фоновых задач `ww_*`, интеграционные адаптеры 1С/Bitrix24.
- **Формат:** JSON (`application/json`), единый набор ключей (см. раздел «Формат записи»).
- **Транспорт:** stdout контейнеров → Loki (prod) / `docker compose logs` (stage/local).
- **Retention:** prod — 30 дней «горячие» + 180 дней архив; stage — 7 дней; локально — по логротейту Docker.
- **Alerting:** Alertmanager `WWLoggingGap` — триггерится при отсутствии записей >5 мин в prod.

## Метрики Walking Warehouse
- **Scrape:** `/metrics`, метки `operation={order_create|order_update|order_assign|order_status_update}`.
- **Основные:**
  - `ww_export_attempts_total`, `ww_export_success_total` — объём операций, видно провалы экспорта или API-обработчиков.
  - `ww_export_failure_total{reason="invalid_transition"}` — подсвечивает нарушения workflow (см. `ww_order_status_transitions_total`).
  - `ww_export_duration_seconds` — следим за SLA: `histogram_quantile(0.95, sum by (operation, le)(rate(ww_export_duration_seconds_bucket[5m])))`.
  - `ww_order_status_transitions_total{result="failure"}` — быстрый фильтр для проблемных переходов статусов.
- **Чек-лист при инциденте:**
  1. `sum by (operation)(increase(ww_export_attempts_total[5m]))` — есть ли вообще запросы.
  2. `sum by (reason)(increase(ww_export_failure_total[5m]))` — как распределены ошибки.
  3. `ww_order_status_transitions_total{result="failure"}` — какая пара статусов ломается.
  4. Сравнить `ww_export_duration_seconds` с SLO (порог 95-й перцентиль ≤ 400 мс для write-потоков).

## Формат записи
Каждая запись должна включать минимальный набор полей:

| Поле | Описание |
| --- | --- |
| `timestamp` | RFC-3339, UTC |
| `level` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `service` | `walking-warehouse-api` / `walking-warehouse-worker` |
| `environment` | `prod` / `stage` / `local` |
| `message` | Короткое описание события |
| `x_request_id` | Корреляция HTTP/фоновых вызовов |
| `idempotency_key` | Проставляется для вызовов, где требуется защита от дублей |
| `courier_id` | Идентификатор курьера, UUID/строка |
| `customer_phone` | Маскированный телефон клиента |
| `customer_email` | Маскированный email клиента |
| `extra` | Объект с деталями этапа (например, `stage`, `sku`, `qty`, `status`) |

### Пример записи (маскирование PII)
```json
{
  "timestamp": "2025-09-18T12:45:32.123Z",
  "level": "INFO",
  "service": "walking-warehouse-api",
  "environment": "prod",
  "message": "return_ready event accepted",
  "x_request_id": "1c1dbb56-02ae-4c6e-8a33-d45d9b07bd74",
  "idempotency_key": "return-ready-20250918-104532",
  "courier_id": "courier-ru-045",
  "customer_phone": "+7***-***-12-34",
  "customer_email": "a***@example.com",
  "extra": {
    "stage": "returns",
    "return_id": "ret-7b7f6f1c",
    "items": 2,
    "masked_total": "****.**",
    "pii_masked": true
  }
}
```

## Маскирование и соответствие требованиям
- Включайте `PII_MASKING_ENABLED=true` во всех prod/stage окружениях. Для dev допустимо отключать только временно.
- Телефоны выводим шаблоном `+7***-***-XX-XX`; email — `f***@domain`; суммы клиентов — `****.**`.
- Скрипт `scripts/check_pii_mask.py` (при появлении) должен запускаться в CI перед релизом.
- При нарушении маскировки:
  1. Зафиксировать окружение (`prod`/`stage` работают в Kubernetes, локальное окружение — `docker compose`).
  2. Для `prod`/`stage` остановить форвардинг в Loki:
     ```bash
     make logs-stop-forward \
       LOGS_FORWARD_CONTEXT=ww-prod \
       LOGS_FORWARD_NAMESPACE=observability \
       LOGS_FORWARD_DEPLOYMENT=ww-grafana-agent-logs
     ```
     > **Эффект:** Deployment `ww-grafana-agent-logs` масштабируется до `0` реплик; через 30–60 секунд новые записи перестают появляться в Loki (подтвердите `kubectl get deployment/ww-grafana-agent-logs -n observability`).
  3. Для локальной отладки (`docker compose`) — остановить сервисы `app`/`stt-worker`, чтобы прекратить генерацию логов: `docker compose stop app stt-worker`.
  4. Заэскалировать в `#security` и владельцам Walking Warehouse.
  5. Вырезать инцидентные записи (через `loki-adm tail --delete --ids ...`), задокументировать в postmortem.

## Доступ и диагностика
- **Prod:** Grafana Explore → `loki` → запрос `service="walking-warehouse-api"`.
- **Stage:** `kubectl logs deploy/ww-api -n walking-warehouse --since=1h | jq '.'`.
- **Local:** `docker compose logs -f app | jq 'select(.service=="walking-warehouse-api")'`.
- Для корреляции HTTP и фоновых событий используйте `x_request_id`.
- Проверяйте `idempotency_key`, если подозрение на дубли (`return_ready`, `courier_sale`).

## Типовые проверки при алертах
1. **`WWLoggingGap`:**
   - Убедиться, что сервисы живы: `kubectl get pods -n walking-warehouse`.
   - Проверить `stdout` контейнеров; при отсутствии записей → убедиться, что не отключён `structured-logging` флаг.
   - Сравнить с метрикой `http_requests_total{service="walking-warehouse-api"}` — есть ли трафик.
2. **Spike ошибок:**
   - Фильтровать `level="ERROR"` + `extra.stage`.
   - Извлечь `error` объект; при интеграционных ошибках свериться с [docs/observability.md](../observability.md).

## Постинцидентные действия
- Обновить этот runbook, если шаги диагностики расширились.
- Зафиксировать инцидент в [docs/runbooks/incidents.md](incidents.md).
- Синхронизировать изменения с PRD/ONE-PAGER (разделы об операционном контроле).

## Связанные материалы
- PRD: [«Ходячий склад»](../PRD%20Ходячий%20склад.md)
- ONE-PAGER: [«Рюкзак курьера»](../ONE-PAGER-%D0%A5%D0%BE%D0%B4%D1%8F%D1%87%D0%B8%D0%B9%D0%A0%D1%8E%D0%BA%D0%B7%D0%B0%D0%BA.md)
- Observability: [Обзор мониторинга](../observability.md)
- Инциденты: [Общий runbook](incidents.md)
