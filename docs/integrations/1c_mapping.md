# Маппинг интеграции с 1С:УТ

## Область действия
- Поддерживаются версии 1С:УТ 10.3 (источник) и 1С:УТ 11 (приёмник).
- Middleware выступает посредником: принимает REST/CommerceML события от 1С:УТ 10.3, нормализует данные и транслирует их в целевую 1С:УТ 11 и внутренние модели.
- Основные домены: НСИ, документы движения товаров, денежные операции и статусы задач доставки.

## НСИ
| Объект 1С | Таблица MW | Ключевые поля | Примечания |
| --- | --- | --- | --- |
| Номенклатура | `catalog.items` | `external_id`, `sku`, `barcode`, `vat_rate`, `uom_code`, `is_batch_tracked` | Поддерживаются партии и серийные номера; ссылка на категорию из `catalog.categories` |
| Контрагенты | `core.partners` | `external_id`, `inn`, `kpp`, `full_name`, `status` | Статусы маппятся: `Действует` → `active`, `Не обслуживается` → `inactive`, `Черный список` → `blocked` |
| Склады | `logistics.warehouses` | `external_id`, `name`, `type`, `address`, `geo_point`, `responsible_user_id` | При отсутствии координат запускается сервис геокодирования; поле `type` нормализуется (main, transit, courier) |
| Пользователи | `core.users` | `external_id`, `full_name`, `email`, `role` | Используется для привязки задач и ответственности |

## Документы
| Документ 1С | Модель MW | Поля | Особенности |
| --- | --- | --- | --- |
| Реализация товаров и услуг | `sales.shipments` | `document_number`, `document_date`, `customer_id`, `total_amount`, `currency_code`, `lines[]` | Каждая строка содержит `sku`, `qty`, `price`, `vat_rate`; суммы пересчитываются в RUB по курсу ЦБ |
| Поступление товаров | `inventory.incoming` | `supplier_id`, `contract_id`, `planned_receipt_at`, `lines[]` | После приёма создаётся задача в walking warehouse, статус `pending_quality_check` |
| Перемещение товаров | `inventory.transfers` | `source_warehouse_id`, `target_warehouse_id`, `reason_code`, `lines[]` | Поддерживаются межфилиальные перемещения; дополнительные уведомления для `reason_code = interbranch` |
| Возвраты от клиентов | `returns.requests` | `source_system`, `order_id`, `status` (`return_ready`\|`accepted`\|`return_rejected`), `items[]` (`quality` = `new`\|`defect`, `reason_id`?) | Синхронизируется с API `/api/v1/returns`; Idempotency-Key формируется как SHA256 от `document_number`; `reason_id` хранится как UUID, может отсутствовать |
| Денежные документы (ПКО/РКО) | `finance.cash_documents` | `document_number`, `document_date`, `amount`, `cashier_id`, `operation_type` | Используется для сверки наличных и задач курьеров |

## Статусы и справочники
- Единый словарь статусов хранится в `core.statuses`. Сопоставление выполняется при загрузке, непонятные статусы отправляются в очередь расхождений.
- Валюты приводятся к ISO-4217. В случае неизвестного кода документ блокируется и требует ручного вмешательства.
- Все даты конвертируются в UTC и хранятся в RFC-3339.

## Правила обмена
- Документы передаются пакетами ≤ 500 строк, сортировка по `document_date` ASC.
- Для REST-запросов 1С обязательно передаёт `Idempotency-Key`, `X-Request-Id`, `X-Api-Version`.
- Повторные запросы с другим телом → `409 Conflict` и запись в `integration_conflicts`.
- Ошибки `422` включают массив `errors[]` с указанием поля и причины; повторная отправка возможна после исправления.

## Ретраи и очереди
- 1С повторяет запросы 3 раза (1с, 5с, 30с) при сетевых ошибках.
- Middleware ставит документы в очередь повторной обработки (Redis) с шагами 5 мин → 30 мин → 2 ч; после 6 попыток задача попадает в DLQ.
- Все события фиксируются в `integration_log` с привязкой к `X-Request-Id` и `Idempotency-Key`.
