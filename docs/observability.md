# Обсервабилити

## JSON-логи
- Формат `application/json`; каждая строка — валидный JSON-объект без завершающей запятой.
- Обязательные поля: `timestamp` (RFC-3339, UTC), `level`, `message`, `service`, `environment`, `x_request_id`.
- Дополнительные контекстные поля: `module`, `function`, `line`, `extra` (произвольный словарь ключ-значение), `error` (структура с `type`, `message`, `stack`).
- Пример записи:
  ```json
  {"timestamp": "2024-01-15T12:34:56.789Z", "level": "INFO", "service": "mw-core", "environment": "production", "x_request_id": "5cf7848a-1c42-4dc4-8a8e-2f1a6c006eb0", "message": "Request handled", "module": "apps.mw.api.handlers.orders", "function": "create_order", "line": 128, "extra": {"customer_id": "cst_123", "payload_size": 512}}
  ```
- Вспомогательные поля (`extra`, `error`) должны сериализоваться в JSON (строки, числа, булевы флаги, вложенные объекты).
- Запрещено логировать персональные данные без маскирования; используем флаги `PII_MASKING_ENABLED` и политики из 00-Core.

## Метрики
- `http_server_requests_duration_seconds` — гистограмма длительности обработки HTTP ручек; собираем p50/p90/p95/p99, алерты по p95.
- `http_server_requests_total` — счётчик запросов с лейблами `method`, `path_template`, `status_code`.
- `http_server_errors_total` — счётчик 5xx с лейблами `service`, `endpoint`.
- `db_query_duration_seconds` — гистограмма времени SQL-запросов; мониторим p95 и p99.
- `db_query_exceptions_total` — счётчик исключений по типам ошибок (timeout, deadlock, integrity).
- `external_api_latency_seconds` — гистограмма времени интеграций; отдельные лейблы для сторонних систем (b24, 1c_ut, warehouse).
- `external_api_failures_total` — счётчик неуспешных обращений к внешним сервисам с лейблами `system`, `reason`.
- `background_task_duration_seconds` — гистограмма длительности фоновых задач; собираем p95 и алерты на превышение SLA.
- Все метрики экспортируются в Prometheus-совместимом формате по `/metrics` и снабжаются единицами измерения.

## Трассировка запросов
- Каждому входящему запросу присваиваем `X-Request-Id`; если заголовок уже пришёл — переиспользуем, иначе генерируем UUID v4.
- Значение `X-Request-Id` сохраняется в контекст логирования (`x_request_id`) и проксируется во все исходящие HTTP-запросы.
- Для асинхронных задач и ретраев переносим `X-Request-Id` вручную, чтобы восстановить цепочку событий.
- Трассировки экспортируются в формате W3C Trace Context (`traceparent`/`tracestate`) поверх базового `X-Request-Id`.
- Интеграции с APM (Jaeger/Tempo/Zipkin) используют общее пространство имён `mw-core`; спаны помечаются лейблами `component`, `status`.
- В отчётах инцидентов `X-Request-Id` обязателен для быстрой корреляции логов, метрик и трассировок.
