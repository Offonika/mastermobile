# Обсервабилити

## Цели
- Возможность восстановить полный путь запроса от Bitrix24/1С до БД и очередей.
- Мониторинг SLA: p95 латентности API, задержки очередей, частота ошибок интеграций.
- Аудит действий: корреляция `X-Request-Id`, `Idempotency-Key`, `user_id/role`.

## Логи
- Формат: JSON (`application/json`). Каждая запись — валидный объект.
- Обязательные поля: `timestamp` (RFC-3339, UTC), `level`, `service`, `environment`, `message`, `x_request_id`, `idempotency_key`, `user_role`.
- Дополнительные поля: `module`, `function`, `line`, `duration_ms`, `error` (структура `{type, message, stack}`), `extra` (dict).
- Логирование персональных данных запрещено. Включаем маскирование для телефонов, email, адресов; используем флаг `PII_MASKING_ENABLED`.
- Хранение: Loki/ELK ≥ 30 дней, архив ≥ 180 дней для расследований.
- Walking Warehouse: пошаговый runbook по логам — [docs/runbooks/ww.md](runbooks/ww.md).

## Метрики
| Метрика | Тип | Labels | Цель |
| --- | --- | --- | --- |
| `http_request_duration_seconds` | Histogram | `method`, `status_code`, `path` | p95 ≤ 250 мс (чтение), p95 ≤ 400 мс (запись) |
| `http_requests_total` | Counter | `method`, `status_code`, `path` | Контроль объёма вызовов, rate limit |
| `background_tasks_duration_seconds` | Histogram | `task_name`, `status` | SLA фоновых процессов |
| `integration_failures_total` | Counter | `system`, `reason`, `retry_stage` | Алерты при росте ошибок внешних систем |
| `queue_lag_seconds` | Gauge | `queue_name` | Контроль задержек Redis/Kafka (порог 60 сек) |
| `events_dlq_total` | Counter | `event_type` | Триггер для ручного разбора |
| `ww_export_attempts_total` / `ww_export_success_total` | Counter | `operation` | Запуски и успехи WW-обработчиков экспорта/ордеров |
| `ww_export_failure_total` | Counter | `operation`, `reason` | Контроль отказов WW-операций с расшифровкой причины |
| `ww_export_duration_seconds` | Histogram | `operation`, `outcome` | Длительность WW-операций (сравнение с SLO) |
| `ww_order_status_transitions_total` | Counter | `from_status`, `to_status`, `result` | Диагностика переходов статусов заказов WW |

- Экспортер: Prometheus `/metrics`, scrape interval 15с.
- Alertmanager правила: p95 > SLO 5 мин подряд, `integration_failures_total` +50% за 10 мин, `queue_lag_seconds` > 60с.

WW-метрики используют метку `operation` (`order_create`, `order_update`, `order_assign`, `order_status_update`) и позволяют собрать полный путь: попытка → успех/ошибка → длительность. Для поиска проблемных переходов статусов фильтруйте `ww_order_status_transitions_total{result="failure"}` и уточняйте пары `from_status`, `to_status` (например, `NEW→DONE`).

### Рекомендуемые PromQL запросы

- Ошибка по статусам: ``sum by (status_code)(rate(http_requests_total[5m]))``
- p95 латентности по маршруту: ``histogram_quantile(0.95, sum by (method, path, le)(rate(http_request_duration_seconds_bucket[5m])))``

## Трассировки
- OpenTelemetry SDK. Спаны: `http.server`, `http.client`, `redis.command`, `db.query`, `event.publish`, `event.consume`.
- Трейсы связываются по `X-Request-Id` и W3C `traceparent`/`tracestate`.
- Минимальный набор атрибутов: `service.name`, `service.version`, `deployment.environment`, `user.role`, `http.route`, `db.statement` (только шаблон), `queue.name`.
- Экспортер: Tempo/Jaeger. Retention 7 дней, для инцидентов — экспорт в архив.

## Дашборды
- **API Overview**: RPS, p95, error rate, распределение ролей.
- **Integration Health**: успех/ошибки по 1С и Bitrix24, количество ретраев, DLQ.
- **Queue Lag**: задержка по каждому топику/очереди, глубина, длительность ретраев.
- **SLO Tracking**: бюджет ошибок, burn rate (1h/6h), прогноз исчерпания.

> Подробные инструкции по реакциям, SLO и синтетическим проверкам для `call_export` см. в [runbook-е выгрузки звонков](runbooks/call_export.md).

## Инцидентная реакция
- PagerDuty/Telegram уведомления при `critical` алертах.
- Runbook содержит шаги проверки (`make logs`, запросы к `/health`, `/metrics`, анализ DLQ`).
- По завершении инцидента: постмортем, обновление NFR/ADR при необходимости, добавление тестов и метрик.
