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

## Метрики
| Метрика | Тип | Labels | Цель |
| --- | --- | --- | --- |
| `http_requests_duration_seconds` | Histogram | `method`, `path_template`, `status_code`, `role` | p95 ≤ 250 мс (чтение), p95 ≤ 400 мс (запись) |
| `http_requests_total` | Counter | `method`, `path_template`, `status_code`, `role` | Контроль объёма вызовов, rate limit |
| `background_tasks_duration_seconds` | Histogram | `task_name`, `status` | SLA фоновых процессов |
| `integration_failures_total` | Counter | `system`, `reason`, `retry_stage` | Алерты при росте ошибок внешних систем |
| `queue_lag_seconds` | Gauge | `queue_name` | Контроль задержек Redis/Kafka (порог 60 сек) |
| `events_dlq_total` | Counter | `event_type` | Триггер для ручного разбора |

- Экспортер: Prometheus `/metrics`, scrape interval 15с.
- Alertmanager правила: p95 > SLO 5 мин подряд, `integration_failures_total` +50% за 10 мин, `queue_lag_seconds` > 60с.

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

## Инцидентная реакция
- PagerDuty/Telegram уведомления при `critical` алертах.
- Runbook содержит шаги проверки (`make logs`, запросы к `/health`, `/metrics`, анализ DLQ`).
- По завершении инцидента: постмортем, обновление NFR/ADR при необходимости, добавление тестов и метрик.
