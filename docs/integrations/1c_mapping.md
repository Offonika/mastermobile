# Маппинг интеграции с 1С:УТ

## Область действия
- Поддерживаемая конфигурация: 1С:Управление торговлей 10.3 (источник данных) ⇄ MasterMobile middleware.
- На стороне MW в эксплуатации только поток возвратов, смежные сущности описаны миграцией `apps/mw/migrations/versions/0001_init.py`.
- Бизнес-цель: зафиксировать заявки на возврат, строки возврата и связанные события курьерских задач, сохраняя трассировку обмена с 1С.

## Сущности MW
| Объект 1С | Таблица MW | Ключевые поля | Комментарии |
| --- | --- | --- | --- |
| Возврат товаров от покупателя | `returns` | `return_id` (UUID MW), `order_id_1c`, `courier_id`, `status`, `source` | `status` ∈ {`return_ready`, `accepted`, `return_rejected`}; `source` ∈ {`widget`, `call_center`, `warehouse`}. Таймстемпы `created_at`/`updated_at` проставляются СУБД. |
| Строки возврата | `return_lines` | `id`, `return_id`, `line_id`, `sku`, `qty`, `quality` | `quality` ∈ {`new`, `defect`}. Колонка `photos` хранит массив URL/идентификаторов, `reason_id` — UUID внешнего справочника причин возвратов. |
| Журнал интеграций | `integration_log` | `direction`, `external_system`, `endpoint`, `correlation_id` | `direction` ∈ {`inbound`, `outbound`}; `external_system` ∈ {`1c`, `b24`, `warehouse`}. Поля `request`/`response` содержат JSONB-дампы, `retry_count` ведётся для исходящих вызовов. |
| События задач | `task_event` | `task_id_b24`, `type`, `actor_id`, `payload_json` | `type` ∈ {`status`, `photo`, `geo`, `comment`}. `correlation_id` уникален и используется для дедупликации событий Bitrix24. `return_id` связывается с `returns.return_id` (ON DELETE SET NULL). |

### Статусы и справочники
- Статус возврата `return_ready` ставит 1С после регистрации документа; `accepted` и `return_rejected` — результат обработки склада/курьера.
- `return_lines.reason_id` резервируется под справочник причин в 1С, `reason_note` — свободное поле для операторов.
- `task_event.payload_json` хранит оригинальный payload виджета/Bitrix24 (например, координаты или ссылку на фото).

## Потоки обмена
### Регистрация возврата
1. 1С формирует документ «Возврат товаров от покупателя» и вызывает `POST /api/v1/returns`.
2. Middleware записывает строку в `returns`, дочерние записи в `return_lines`, а также журналирует запрос/ответ в `integration_log` (`direction = 'inbound'`, `external_system = '1c'`).
3. Ответ включает созданный `return_id` и текущий статус (`return_ready` по умолчанию).

### Обновление решения по возврату
1. После проверки склада/курьера 1С вызывает `PUT /api/v1/returns/{returnId}` с обновлёнными полями и статусом `accepted` или `return_rejected`.
2. MW обновляет запись, фиксируя изменения в `returns.updated_at`. Для каждой строки допускается корректировка `quality`, `reason_id`, `photos`.
3. Все модификации протоколируются в `integration_log` и помечаются `correlation_id` из заголовка `Idempotency-Key`.

### Отмена возврата
- `DELETE /api/v1/returns/{returnId}` доступен администраторам MW. При успешном удалении строка из `returns` удаляется, связанные `return_lines` каскадно удаляются, а связанные `task_event` теряют ссылку (становятся `NULL`).

### События задач
- Курьерский виджет и Bitrix24 публикуют изменения (фото, гео, статусы) в MW, записи попадают в `task_event` с уникальным `correlation_id`.
- Для событий, привязанных к возврату, заполняется `return_id`, что позволяет 1С отслеживать прогресс курьера. Отдельный поток экспорта в 1С использует эти данные для актуализации задач.

## Заголовки и идемпотентность
- `Idempotency-Key` обязателен для `POST`, `PUT` и `DELETE` `/api/v1/returns*` и записывается в `integration_log.correlation_id`. Повтор с тем же ключом возвращает исходный ответ, расхождение payload → `409 Conflict`.
- `X-Request-Id` необязателен: если 1С его не передаёт, MW генерирует значение и возвращает в заголовке ответа (см. `openapi.yaml`).
- `Authorization: Bearer <JWT>` требуется для всех защищённых эндпоинтов; роли `1c`, `courier`, `admin` см. `openapi.yaml`.
- Заголовок `X-Api-Version` не используется; версионирование обеспечивается префиксом пути `/api/v1`.

## Ретраи и наблюдаемость
- 1С инициирует повтор через 1с → 5с → 30с при сетевых ошибках/5xx. MW использует `integration_log.retry_count` только для исходящих запросов; для входящих повторов опорным остаётся `Idempotency-Key`.
- Все ответы MW содержат `X-Request-Id` и поле `request_id` в теле ошибки (формат RFC 7807), что позволяет сопоставить записи логов и журнал `integration_log`.
- Для статистики доступен индекс `ix_integration_log_resource_ref`, позволяющий фильтровать журнал по идентификатору ресурса (`returns/{return_id}`).

## Версионные примечания
- 2024-05-09: документ синхронизирован с миграцией `0001_init` (таблицы `returns`, `return_lines`, `integration_log`, `task_event`) и актуальными требованиями к заголовкам/идемпотентности из `openapi.yaml`.
