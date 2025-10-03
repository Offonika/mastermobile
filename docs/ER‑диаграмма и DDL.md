ER‑диаграмма и DDL (PostgreSQL) — v0.6.5 Unified
Проекты: «Ходячий склад» и Core Sync (единая БД Middleware)
 Основано на: v0.6.4; выровнено с 00‑Core v1.3.3 и API‑Contracts v1.1.0
 Дата: 22.09.2025
Что изменилось в v0.6.5 против v0.6.4
- Добавлены сущности `call_exports` и `call_records` для пайплайна Batch-Transcribe B24: фиксируют параметры периода, статус запуска, связь с инициатором (`core.users`) и детализированное состояние каждой записи звонка. (Синхронизация с API‑Contracts v1.1.0 подтверждена 26.09.2025.)
- Введён ссылочный контроль: `call_records.run_id` с каскадным удалением указывает на `call_exports.run_id`, `call_exports.actor_user_id` ссылается на `core.users.user_id` (nullable для системных запусков).
- Для наблюдаемости добавлены частичные индексы по статусам (`call_exports.status`, `call_records(status, run_id)`) и ограничения идемпотентности (`UNIQUE (run_id, call_id, coalesce(record_id,''))`).

Что изменилось в v0.6.4 против v0.6.3
- Добавлены поля валюты: orders.currency_code, instant_orders.currency_code (currency_code, по умолчанию RUB).
- Бизнес‑валидатор возвратов: reason_code обязателен (CHECK length(trim(reason_code)) > 0).
- Индексы очередей/наблюдаемости:
  - task_events(task_id_b24, ts desc) where type='status';
  - returns(status, updated_at desc) where status in ('pending','accepted').
- Дедуп фото: функциональный индекс по payload_json->>'checksum' для task_events с type='photo'.
- Уточнена опция DEFERRABLE‑FK для событий → заказа (документировано, по умолчанию выключено).


1) Схемы и разграничение (логическое)
schema core: orders, task_events, returns, return_lines, return_reason, integration_log, idempotency_key.


schema ww (Walking Warehouse): couriers, courier_stock, instant_orders, instant_order_lines, price_type, product (опц.).


schema b24 (Batch-Transcribe B24): call_exports, call_records.


Примечание: физически можно оставить в public, но разделение схем упрощает миграции и ответственность команд.
2) DDL‑дифф (миграции)
2.1 v0.6.1 → v0.6.2 (ранее внесено)
-- см. предыдущий раздел (идемпотентность (key, endpoint, actor_id) и др.)

2.2 v0.6.2 → v0.6.3 (новое)
-- Домены
create domain if not exists currency_code as char(3)
  check (value in ('RUB'));

-- Перевод временных полей в timestamptz (UTC)
-- orders
alter table if exists orders
  alter column created_at type timestamptz using created_at at time zone 'UTC',
  alter column updated_at type timestamptz using updated_at at time zone 'UTC';
-- task_events
alter table if exists task_events
  alter column ts type timestamptz using ts at time zone 'UTC';
-- instant_orders
alter table if exists instant_orders
  alter column created_at type timestamptz using created_at at time zone 'UTC',
  alter column updated_at type timestamptz using updated_at at time zone 'UTC';
-- returns
alter table if exists returns
  alter column created_at type timestamptz using created_at at time zone 'UTC',
  alter column updated_at type timestamptz using updated_at at time zone 'UTC';
-- couriers / courier_stock
alter table if exists couriers
  alter column updated_at type timestamptz using updated_at at time zone 'UTC';
alter table if exists courier_stock
  alter column updated_at type timestamptz using updated_at at time zone 'UTC';
-- integration_log
alter table if exists integration_log
  alter column ts type timestamptz using ts at time zone 'UTC';

-- Неотрицательные суммы/количества
alter table if exists orders
  add constraint if not exists chk_orders_nonneg check (
    coalesce(delivery_price,0) >= 0 and coalesce(cod_amount,0) >= 0
  );
alter table if exists instant_order_lines
  add constraint if not exists chk_iol_nonneg check (qty >= 0 and price >= 0);
alter table if exists return_lines
  add constraint if not exists chk_return_qty_positive check (qty > 0);

-- Индексы под онлайн‑пути
create index if not exists idx_orders_status_created on orders(status, created_at desc);
create index if not exists idx_returns_status_created on returns(status, created_at desc);
create index if not exists idx_io_courier_status_created on instant_orders(courier_id, status, created_at desc);

-- Уникальность: одна задача B24 → один IO от курьера
create unique index if not exists uq_io_task_courier on instant_orders(task_id_b24, courier_id);

-- Явное поведение FK (строки каскадно удаляются)
alter table if exists instant_order_lines
  drop constraint if exists instant_order_lines_instant_order_id_fkey,
  add constraint instant_order_lines_instant_order_id_fkey
    foreign key (instant_order_id) references instant_orders(id) on delete cascade;

alter table if exists return_lines
  drop constraint if exists return_lines_return_id_fkey,
  add constraint return_lines_return_id_fkey
    foreign key (return_id) references returns(return_id) on delete cascade;

-- Подсказки для планировщика (опциональные GIN для JSONB)
create index if not exists idx_integration_log_req_gin on integration_log using gin (request jsonb_path_ops);
create index if not exists idx_integration_log_resp_gin on integration_log using gin (response jsonb_path_ops);

2.3 v0.6.3 → v0.6.4 (новое)
-- Валюта в денежных сущностях
alter table if exists orders
  add column if not exists currency_code currency_code not null default 'RUB';

alter table if exists instant_orders
  add column if not exists currency_code currency_code not null default 'RUB';

-- Бизнес‑правило: при браке причина обязательна
alter table if exists return_lines
  add constraint if not exists chk_return_reason_code_not_blank
    check (length(trim(reason_code)) > 0);

-- Индексы очередей/наблюдаемости
create index if not exists idx_task_events_status_ts
  on task_events(task_id_b24, ts desc) where type='status';

create index if not exists idx_returns_status_uat
  on returns(status, updated_at desc) where status in ('pending','accepted');

-- Дедуп фото по контрольной сумме
create index if not exists idx_task_events_photo_checksum
  on task_events ((payload_json->>'checksum')) where type='photo';

-- (Опция) DEFERRABLE‑FK событий к заказу — включать при гарантии порядка доставки данных
-- alter table if exists task_events
--   add constraint fk_task_event_order
--   foreign key (task_id_b24) references orders(task_id_b24) deferrable initially deferred;

-- 2.1 Идемпотентность: новая модель ключа (UNIQUE (key, endpoint, actor_id), TTL 72h)
create table if not exists idempotency_key_new (
  key               uuid not null,
  endpoint          text not null,
  actor_id          text not null,
  scope             text not null,
  resource_ref      text,
  response_snapshot jsonb,
  created_at        timestamptz not null default now(),
  expires_at        timestamptz not null,
  constraint pk_idem primary key (key, endpoint, actor_id),
  constraint chk_idem_ttl check (expires_at > created_at)
);

-- перенос данных (best‑effort): actor_id/endpoint потребуют заполнения скриптом миграции
-- пример: endpoint из лога/контекста, actor_id = courier_id|user_id|"1c"
insert into idempotency_key_new (key, endpoint, actor_id, scope, resource_ref, response_snapshot, created_at, expires_at)
select key::uuid, coalesce(scope,'/unknown'), coalesce(resource_ref,'system'), scope, resource_ref, response_snapshot, created_at,
       (created_at + interval '72 hours')
from idempotency_key
on conflict do nothing;

drop table idempotency_key;
alter table idempotency_key_new rename to idempotency_key;
create index if not exists idx_idem_expires on idempotency_key(expires_at) where expires_at > now();

-- 2.2 События: жёсткий UQ на correlation_id (если приходит)
create unique index if not exists uq_task_events_corr on task_events(correlation_id) where correlation_id is not null;

-- 2.3 Очереди возвратов (уточнение)
create index if not exists idx_returns_pending on returns(return_id) where status='pending';

-- Обязательные телефоны (уже были), оставляем как есть
-- orders.phone ru_phone not null; instant_orders.client_phone ru_phone not null

2.4 v0.6.4 → v0.6.5 (новое)
-- Пакетная выгрузка звонков Bitrix24
create table if not exists call_exports (
  run_id          uuid primary key,
  period_from     timestamptz not null,
  period_to       timestamptz not null,
  status          text not null check (status in ('pending','in_progress','completed','error','cancelled')),
  started_at      timestamptz not null default now(),
  finished_at     timestamptz,
  actor_user_id   uuid references core.users(user_id) on delete set null,
  options         jsonb,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  constraint chk_call_exports_period check (period_to >= period_from)
);

create index if not exists idx_call_exports_status_active
  on call_exports(status)
  where status in ('pending','in_progress','error');

create table if not exists call_records (
  id                bigserial primary key,
  run_id            uuid not null references call_exports(run_id) on delete cascade,
  call_id           text not null,
  record_id         text,
  call_started_at   timestamptz,
  duration_sec      integer not null check (duration_sec >= 0),
  recording_url     text,
  storage_path      text,
  transcript_path   text,
  summary_path      text,
  text_preview      text,
  language          text,
  employee_id       text,
  checksum          text,
  transcription_cost numeric(12,2),
  currency_code     currency_code default 'RUB',
  status            text not null check (status in ('pending','downloading','downloaded','transcribing','completed','skipped','error')),
  error_code        text,
  error_message     text,
  attempts          integer not null default 0 check (attempts >= 0),
  last_attempt_at   timestamptz,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);

create index if not exists idx_call_records_status_run
  on call_records(status, run_id)
  where status in ('pending','downloading','transcribing','error');

create index if not exists idx_call_records_checksum
  on call_records((checksum))
  where checksum is not null;

create unique index if not exists uq_call_records_run_call_record
  on call_records(run_id, call_id, coalesce(record_id, ''));

Основные положения:
- `call_exports` фиксирует один запуск выгрузки: период (`period_from`/`period_to`), статус (pending/in_progress/completed/error/cancelled), ссылку на инициатора (`actor_user_id` → `core.users.user_id`, nullable для системных джобов), тайминги (`started_at`, `finished_at`) и JSON‑опции запуска (флаги `generate_summary`, `language_override` и др.).
- `call_records` хранит каждую запись звонка в рамках запуска: бизнес-ключ `(run_id, call_id, coalesce(record_id,''))`, длительность (`duration_sec`), локации хранения (`recording_url`, `storage_path`, `transcript_path`, `summary_path`), текстовый предпросмотр (`text_preview`), язык (`language`), идентификатор оператора (`employee_id`), контрольные суммы (`checksum`), стоимость (`transcription_cost`, `currency_code`), текущий статус (pending/downloading/downloaded/transcribing/completed/skipped/error) и информацию об ошибках/повторах (`attempts`, `last_attempt_at`, `error_code`, `error_message`).
- Идемпотентность запуска реализована через общую таблицу `idempotency_key`: POST `/tasks/call_export` требует заголовок `Idempotency-Key` (UUID по 00‑Core §2.1), ключ хранится 72 часа и предотвращает создание повторного run при идентичном payload.
- `delivery_logs` фиксирует каждое событие по заказу или назначению: ссылка на заказ (`order_id`) и назначение (`assignment_id`), идентификатор курьера (`courier_id`), статус сообщения (info/success/warning/error), тип события (`event_type`), текст (`message`) и JSON‑payload. В payload всегда есть флаг `kmp4_exported:boolean`, по умолчанию `false`, который переворачивается при фактическом экспорте отчёта КМП4.
- Внешние ключи: `call_records.run_id` с каскадным удалением → `call_exports.run_id`; `call_exports.actor_user_id` → `core.users.user_id` (`ON DELETE SET NULL`).
- Индексация рассчитана на мониторинг прогрессии и дедупликацию: частичный индекс по активным статусам, GIN/GiST не требуется; хэш по `checksum` обеспечивает быстрый поиск дублей при ретраях.

-- 2.5 Комментарии‑подсказки по статусам (привязка к Status‑Dictionary v1)
comment on column orders.status is 'Status‑Dictionary v1 (полный список см. 00‑Core §3.1: READY|PICKED_UP|...); изменения — через приложение, не DDL';
comment on column instant_orders.status is 'Status‑Dictionary v1 (полный список: DRAFT|PENDING_APPROVAL|APPROVED|DELIVERED|CANCELLED|REJECTED|TIMEOUT_ESCALATED; см. 00‑Core §3.2)';
comment on column returns.status is 'Status‑Dictionary v1 (полный список: pending|accepted|rejected|cancelled); фиксация статусов возвратов';

-- 2.6 Ретенции (операторские заметки)
comment on table integration_log is 'Retention: 90d';
comment on table task_events is 'Retention: 180d (geo внутри), см. Core §9';
comment on table idempotency_key is 'TTL: 72h';

3) Полный DDL (инвариантные части)
Базовые блоки остаются как в v0.6.2. В новых средах сразу создавайте таблицы с timestamptztz и добавленными CHECK/индексами; на уже развёрнутых — применяйте миграции §2.2.
 Не изменены относительно v0.6.1 за исключением блока идемпотентности и комментариев — см. исходный документ.
4) Совместимость и политика статус‑энумов
В БД оставлены CHECK‑ограничения для статусов v1; используем полный список из Status‑Dictionary v1 (см. 00‑Core §3). При additive‑изменениях расширяем списки через миграцию.
Для instant_orders.status проверьте, что CHECK/enum уже включает DELIVERED; окружения со старым набором статусов требуют отдельной миграции.


Ломающие изменения статусов запрещены в v1 (см. API‑Contracts §12).


(Опция) DEFERRABLE‑FK task_events.task_id_b24 → orders.task_id_b24 включается только если пайплайн гарантирует порядок вставок; по умолчанию FK выключен (отражено в миграционном блоке §2.3).


5) Ретенции и ПДн
integration_log: ≥90 дн; task_events: ≥180 дн; idempotency_key: 72 ч.


call_exports / call_records: ≥365 дн (для аудита выгрузок и повторного запуска пайплайна; см. PRD B24 §8).


Телефоны — домен ru_phone; фото/файлы не храним, только ID (B24 Disk).


6) To‑Do для v0.6.3
Заполнить исторически endpoint/actor_id для существующих записей idempotency_key (миграционный скрипт из логов).


Ввести справочник delivery_pay_method и заменить временный CHECK в orders.


Решить по FK product.sku (включить при переходе на локальный каталог).


Опционально: вынести сущности по схемам core и ww физически.





