🎯 Назначение

Этот файл — «README для агентов и контрибьюторов» на стадии Docs-first (кода ещё нет).
Сейчас в репозитории только документация в docs/. Здесь зафиксированы:

источник истины и связи между документами,

единые конвенции (даты, деньги, статусы, ошибки),

правила синхронизации и контроля версий,

чек-лист PR для правок в документации,

план перехода к коду (скелет репо и первые задачи).

📚 Содержание

Карта документов и порядок влияния

Единые конвенции (00-Core)

Синхронизация и контроль версий

Version Map (сквозная таблица версий)

PR-чеклист (для правок в документации)

Docs-CI (проверки для .md)

Именование и структура файлов

Глоссарий и статусы

Модули/потоки (docs-phase)

UAT-чеклисты для ONE-PAGER

ADR (архитектурные решения)

Роли и владение (RACI)

Переход к коду: структура и стартовые задачи

.github шаблоны

Прямые ссылки на документы

🗺️ Карта документов и порядок влияния

Источник истины → производные
PRD/SRS → ER/DDL → API-Contracts → ONE-PAGER/UX

Текущее содержимое docs/:

00-Core — Синхронизация документации.md — общеобязательные конвенции.

Концепция проекта.md — контекст, цели и границы.

ER-диаграмма и DDL.md — единая ER (PostgreSQL 14+).

API-Contracts.md — единый контракт API v1.

Core Sync: PRD — Переход 1С: УТ 10.md, SRS — Core Sync 1С: УТ 10.md.

Walking Warehouse: PRD Ходячий склад.md, ONE-PAGER-ХодячийРюкзак.md, UX-скетчи-Рюкзак:Продажа.md.

Batch-Transcribe B24: ONE-PAGER — Тексты звонков Bitrix24.md.

Шаблонный SRS: Software Requirements Specification SRS.md (общая заготовка—уточнить связку с конкретными PRD/SRS).

Любые изменения «ниже по цепочке» не должны ломать «выше» без явного changelog.

📐 Единые конвенции (00-Core)

Дата/время: ISO-8601/RFC3339 с таймзоной.

Деньги: number (2 знака) + currency_code (ISO-4217).

Ошибки API: application/problem+json (type, title, status, detail, errors[]).

Статусы: словарь Status-Dictionary v1.

Версионирование API: префикс /api/v1 (breaking → /api/v2), заголовок X-Api-Version допустим.

Идемпотентность: Idempotency-Key обязателен на модифицирующих операциях; повтор с иным телом → 409.

ПДн/безопасность (docs-phase): флаги PII_MASKING_ENABLED, DISK_ENCRYPTION_FLAG (в dev можно false, в prod — true).

🔁 Синхронизация и контроль версий

Правило расхождений:

Поле есть в ER, нет в API → добавить в API или объявить вычисляемым (обосновать в changelog).

Поле есть в API, нет в ER → добавить в ER или пометить виртуальным.

Enum/статусы живут в 00-Core; из остальных файлов — ссылки на них.

Шапка каждого файла (обязательно):

Название: <…> · Версия: vX.Y · Дата: YYYY-MM-DD · Владелец: <роль/имя> · Статус: Draft/Approved
Связанные документы: <PRD/SRS/ER/API/ONE-PAGER ссылки>

Changelog (в конце файла):

### Changelog
- v1.2 — non-breaking: уточнены поля …; добавлена ссылка на …
- v1.1 — breaking: переименован status X→Y; обновить ER/API.

🧭 Version Map (сквозная таблица версий)

Хранится в docs/00-Core — Синхронизация документации.md.

Объект/поток    PRD/SRS    ER/DDL    API-Contracts    Примечания
Core Sync       PRD v1.x / SRS — Core Sync 1С: УТ 10.md    v0.6.x    v1.1.x    SoT=УТ 10.3
Walking Warehouse       PRD Ходячий склад.md / (SRS при наличии)    v0.6.x    v1.1.x    без нового типа «Возврат» в УТ 10.3
B24 Batch-Transcribe    ONE-PAGER — Тексты звонков Bitrix24.md    —    (опц.) v1.0    форматы calls.csv/txt зафиксированы
Общий шаблон SRS    Software Requirements Specification SRS.md    —    —    использовать как основу для новых SRS

✅ PR-чеклист (для правок в документации)

 Ссылки на затронутые файлы + обновление Version Map.

 В шапках обновлены версия/дата/владелец/статус.

 Changelog: breaking / non-breaking.

 Поля/статусы соответствуют 00-Core (нет дублей).

 Таблицы/диаграммы читаемы; внутренние ссылки рабочие (см. Docs-CI).

 Нет противоречий с «вышестоящими» документами.

🧪 Docs-CI (проверки для .md)

Запустить простые проверки в GitHub Actions:

markdownlint (заголовки/списки/таблицы),

link-checker (внутренние и внешние ссылки),

spellcheck/vale (RU/EN).

🗂️ Именование и структура файлов

Рекомендуемый формат имён (к переименованию позже, когда удобно):
one-pager_b24-transcribe.md, prd_core-sync.md, srs_core-sync.md, er_ddl.md, api-contracts.md, 00-core_sync.md.

Все документы — в docs/; подкаталоги допустимы: docs/adr/, docs/ux/, docs/core-sync/.

📖 Глоссарий и статусы

Вынести глоссарий и словарь статусов в docs/00-Core_glossary-status.md.

Краткие термины: SoT, Delta/Зеркало, MW, Batch-Transcribe.

🧩 Модули/потоки (docs-phase)

Модуль    Главные документы    Итоговые артефакты
Core Sync (УТ10.3↔УТ11)    PRD — Переход 1С: УТ 10.md, SRS — Core Sync 1С: УТ 10.md, ER-диаграмма и DDL.md, API-Contracts.md    перечень сущностей/статусов, ER v0.6.x
Walking Warehouse    PRD Ходячий склад.md, ONE-PAGER-ХодячийРюкзак.md, UX-скетчи-Рюкзак:Продажа.md    процессы задач/возвратов, UX-скрины
B24 Batch-Transcribe    ONE-PAGER — Тексты звонков Bitrix24.md (форматы calls.csv/txt как приложение)    calls.csv, transcripts/*.txt
Концепция    Концепция проекта.md    рамки/цели/не-цели
Общий шаблон SRS    Software Requirements Specification SRS.md    основа для новых SRS

✔️ UAT-чеклисты для ONE-PAGER

B24 Batch-Transcribe (пример):

100% звонков T-60…T0 в calls.csv.

≥ 98% звонков имеют call_<id>.txt.

Разница минут с Bitrix24 ≤ 1%.

Повторный запуск не создаёт дублей.

Итоговый отчёт: минуты и оценка стоимости.

(Добавляйте похожий блок в конец каждого ONE-PAGER.)

🧠 ADR (архитектурные решения)

Каталог: docs/adr/. Формат:

# ADR-0001: Возвраты без нового типа документа в УТ 10.3
Context → Decision → Consequences → Status

👥 Роли и владение (RACI)

Область    Owner    Reviewers
00-Core    Архитектура    Лиды потоков
Core Sync PRD/SRS    Продакт    Арх/Интеграции
ER/DDL    Арх/DB    Core Sync, WW
API-Contracts    Арх/API    Все потоки
WW PRD/UX    Продакт    Арх/Интеграция/UX
B24 Transcribe    Интеграции    Арх/Аналитика

🏁 Переход к коду: структура и стартовые задачи

Когда начнём разработку — целевая структура:

/apps/mw/      # FastAPI
/contracts/    # OpenAPI/JSON Schema
/db/migrations/# SQL-миграции (ER v0.6.x → …)
/scripts/      # утилиты (в т.ч. batch-transcribe)
/docs/         # источник истины
/.github/      # PR template, CODEOWNERS, workflows

Стартовые задачи:

Скелет pyproject.toml, Makefile (venv, ci, test, typecheck, lint, check-openapi).

Сгенерировать пустой OpenAPI v1 из schemas/ по API-Contracts.md (валидатор зелёный).

Первые SQL-миграции по ER-диаграмма и DDL.md.

Зафиксировать CLI интерфейс scripts/b24_transcribe (параметры/форматы).

Docs-CI (markdownlint + link-checker + spellcheck).

Добавить .github/pull_request_template.md, .github/CODEOWNERS.

📁 .github шаблоны

PR template (.github/pull_request_template.md)

## Что изменили
- …

## Ссылки/версии
- Обновлён Version Map
- Связанные: …

## Проверки
- [ ] Шапки обновлены (версия/дата/владелец/статус)
- [ ] Changelog (breaking/non-breaking)
- [ ] Линки валидны (Docs-CI)

CODEOWNERS (.github/CODEOWNERS)

docs/00*                     @team-arch
docs/API*                    @team-api
docs/ER*                     @team-db
docs/PRD*                    @team-product
docs/SRS*                    @team-product
docs/Software Requirements Specification SRS.md @team-product
docs/ONE-PAGER*              @team-ww
docs/UX*                     @team-ww

🔗 Прямые ссылки на документы

00-Core: docs/00-Core — Синхронизация документации.md

Концепция: docs/Концепция проекта.md

ER/DDL: docs/ER-диаграмма и DDL.md

API: docs/API-Contracts.md

Core Sync: docs/PRD — Переход 1С: УТ 10.md, docs/SRS — Core Sync 1С: УТ 10.md

Walking Warehouse: docs/PRD Ходячий склад.md, docs/ONE-PAGER-ХодячийРюкзак.md, docs/UX-скетчи-Рюкзак:Продажа.md

Batch-Transcribe: docs/ONE-PAGER — Тексты звонков Bitrix24.md

Шаблон SRS: docs/Software Requirements Specification SRS.md
