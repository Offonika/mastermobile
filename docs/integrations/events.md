<!-- filename: docs/integrations/events.md -->

# События интеграций

## Формат
- Используется CloudEvents v1.0 в представлении `application/cloudevents+json`.
- Обязательные атрибуты: `id` (UUID v4), `source` (`urn:mastermobile:<system>`), `type`, `specversion`, `time` (RFC-3339 UTC), `subject`, `data_content_type`, `data`, `data_schema`.
- Заголовки транспорта: `X-Request-Id`, `X-Correlation-Id`, `Idempotency-Key`, `X-Signature` (для HMAC-подписей вебхуков).
- Payload версионируется полем `data_version`. Клиенты обязаны обрабатывать только известные версии и публиковать обратную совместимость в ADR.

## Категории событий
| Категория | Типы (`type`) | Назначение |
| --- | --- | --- |
| **НСИ** | `integration.1c.masterdata.upserted`, `integration.1c.masterdata.deleted` | Репликация справочников между 1С и MW |
| **Логистика** | `integration.task.created`, `integration.task.status_changed`, `integration.return.created` | Управление задачами курьеров, возвратами и мгновенными заказами |
| **Финансы** | `integration.cash.registered`, `integration.cash.reconciled` | Контроль наличных операций и сверок |
| **Инциденты** | `integration.anomaly.detected`, `integration.conflict.detected` | Уведомление о расхождениях, блокировках и инцидентах SLA |
| **Аудит** | `integration.audit.logged` | Технический аудит запросов, подписей, идемпотентности |

## Пример события возврата
```json
{
  "specversion": "1.0",
  "id": "8a65f0c1-00f4-4f9d-8b3d-3cfa628dc034",
  "source": "urn:mastermobile:integration:bitrix24",
  "type": "integration.return.created",
  "subject": "returns/ret_501",
  "time": "2024-02-01T10:15:30Z",
  "data_content_type": "application/json",
  "data_schema": "https://api.mastermobile.app/schemas/returns-event.json",
  "data_version": "1.0",
  "data": {
    "return_id": "ret_501",
    "order_id": "order_1001",
    "courier_id": "cour_123",
    "status": "pending",
    "items": [
      {"sku": "SKU-1001", "qty": 1, "quality": "defect"}
    ]
  }
}
```

## Гарантии доставки
- Транспорт по умолчанию — Redis Streams. Для продовых окружений допускается Kafka с сохранением semantics.
- Паттерн outbox: события пишутся в таблицу `events.outbox`, воркер публикует и помечает offset. При ошибке публикации запись остаётся и уходит в ретрай.
- Повторные доставки допускаются. Клиенты обязаны использовать `Idempotency-Key` и хранить последние обработанные `id`.
- DLQ активируется после 5 неудачных попыток (5м → 30м → 2ч → 6ч → 24ч). Обработчик DLQ отправляет уведомление в канал `#integrations-alerts`.

## Безопасность и наблюдаемость
- Все события подписываются HMAC (SHA-256). Ключи хранятся в Secret Manager, ротация минимум раз в 90 дней.
- Логи публикации содержат `id`, `type`, `Idempotency-Key`, `status_code` потребителя.
- Метрики: `events_published_total`, `events_retry_total`, `events_latency_seconds` (p95 ≤ 2с), `events_dlq_total`.
- Трассировки: спаны `event.publish` и `event.consume` объединяются по `traceparent` и `X-Request-Id`.
