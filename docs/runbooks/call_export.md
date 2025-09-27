<!-- docs/runbooks/call_export.md -->
# Runbook — выгрузка звонков Bitrix24 (`call_export`)

## Назначение
Пайплайн `call_export` отвечает за регулярную выгрузку аудиозаписей и транскриптов звонков из Bitrix24,
расчёт стоимости распознавания и публикацию отчётов. Документ предназначен для on-call инженеров,
эксплуатации и продуктовой команды, которые сопровождают выгрузки и инциденты по звонкам.

## Предпосылки
- Для всех обращений к ChatGPT/Whisper используйте корпоративный прокси `http://user150107:dx4a5m@102.129.178.65:6517` (переменная `CHATGPT_PROXY_URL` в `.env`).

## Запуск и параметры
- **Плановый запуск:** cron/оркестратор инициирует run ежедневно в 02:00 UTC (можно изменить в scheduler).
- **Ручной запуск из контейнера:**
  ```bash
  docker compose run --rm app python -m jobs.call_export \
    --from "2025-08-01" \
    --to "2025-08-31" \
    --generate-summary=false
  ```
- **Параметры:**
  | Флаг | Обязателен | Значение по умолчанию | Описание |
  | --- | --- | --- | --- |
  | `--from` | да | `today-60d` | Начало периода выгрузки (UTC, ISO-8601). |
  | `--to` | нет | `today` | Конец периода выгрузки (UTC, ISO-8601, включительно). |
  | `--generate-summary` | нет | `false` | Создавать ли саммари/теги (увеличивает стоимость). |
  | `--dry-run` | нет | `false` | Только проверка доступа/квот, без скачивания аудио. |

После запуска убедитесь, что создана запись в таблице `call_exports` со статусом `running`. При ручном
старте указывайте `Idempotency-Key = hash(period + actor)` для избежания дублей.

## Мониторинг
- **Grafana:** [Call Export Monitoring](https://grafana.example.com/d/mastermobile-call-export/call-export-overview?orgId=1) —
  панель в папке `MasterMobile / Integrations` с прогрессом, длительностью и статусами.
- **Прометей:** ключевые запросы
  - Общее количество запусков: `sum by (status) (call_export_runs_total{environment="prod"})`
  - Стоимость транскрипций: `call_export_cost_total{environment="prod"}`
  - Дополнительно: `call_export_duration_seconds`, `call_transcripts_total`, `call_export_retry_total`.
- **Логи:** `docker compose logs -f app | jq 'select(.module=="call_export")'` — ищем `stage`, `call_id`, `error`.
- **Отчёты:** S3/объектное хранилище `exports/<period>/reports/summary_<period>.md` и CSV реестр
  `exports/<period>/registry/calls_<from>_<to>.csv`.

## Алерты
| Правило | Порог | Действия |
| --- | --- | --- |
| `CallExportRunFailed` | `call_export_runs_total{status="error"} > 0` за 15 мин | Пейдж on-call, проверить логи и статус run. |
| `CallExportCostBudget` | `call_export_cost_total` > бюджет +20% (5 мин подряд) | Уведомить продакта, подтвердить тариф Whisper. |
| `CallExportRetryStorm` | `call_export_retry_total` > 50 за 15 мин | Проверить ошибки Bitrix24/Whisper, включить throttling. |
| `Bitrix24RateLimitWarn` | `integration.b24.rate_limited` события > 10/15 мин | Следовать playbook по лимитам Bitrix24. |

Алерты транслируются в `#ops-alerts` и PagerDuty (SEV-2 по умолчанию).

## Инструкции по инцидентам
1. Зафиксировать инцидент в ротации (`INC-YYYYMMDD-XX`), классифицировать по `docs/runbooks/incidents.md`.
2. Проверить статус последнего run через `SELECT * FROM call_exports ORDER BY started_at DESC LIMIT 1;`.
3. Сравнить фактическое число транскрибированных звонков с ожидаемым (экспорт CSV vs Bitrix24 отчёт).
4. Анализировать логи с фильтром `correlation_id` → определить проблемные стадии (`fetch_calls`, `download`, `transcribe`).
5. Проверить интеграционные квоты по [playbook лимитов Bitrix24](../integrations/bitrix24_mapping.md#ограничения-и-квоты).
6. При недоступности Bitrix24 — включить режим `low_rate=true` (конфиг), развернуть очередь повторов, уведомить интеграции.
7. При проблемах стоимости — сверить тариф и количество минут, при необходимости отключить `--generate-summary`.
8. После стабилизации — обновить статус инцидента, приложить ссылки на Grafana и отчёты, создать postmortem при SEV-1/2.

## Ретраи
- **Авто-ретраи:** Bitrix24 (`429/5xx`) — 5 попыток с бэкоффом 5/15/30/60/120 секунд; Whisper — 3 попытки с 10/30/60 секунд.
- **Ручной перезапуск звонка:**
  ```sql
  UPDATE call_records
     SET status = 'pending', error_message = NULL, retry_count = retry_count + 1
   WHERE call_id = '<call_id>'
     AND run_id = '<run_id>';
  ```
  Затем выполнить `python -m jobs.call_export --resume --run-id <run_id>`.
- **Повторный запуск периода:** только после подтверждения отсутствия дублей в `call_exports`. Используйте `--dry-run` для
  предварительной оценки стоимости и времени.
- **DLQ:** если запись ушла в DLQ после 24 часов ретраев — вынести в отдельный тикет, обновить отчёт и уведомить заказчика.

## Связанные материалы
- PRD: [Тексты звонков Bitrix24](../PRD%20—%20Тексты%20звонков%20Bitrix24.md)
- Observability: [Метрики и дашборды](../observability.md)
- Инциденты: [Общий runbook](incidents.md)
- Playbook: [Лимиты Bitrix24](../integrations/bitrix24_mapping.md#ограничения-и-квоты)
