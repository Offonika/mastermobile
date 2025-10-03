<!-- docs/runbooks/call_export.md -->
# Runbook — выгрузка звонков Bitrix24 (`call_export`)

## Назначение
Пайплайн `call_export` отвечает за регулярную выгрузку аудиозаписей и транскриптов звонков из Bitrix24,
расчёт стоимости распознавания и публикацию отчётов. Документ предназначен для on-call инженеров,
эксплуатации и продуктовой команды, которые сопровождают выгрузки и инциденты по звонкам.

## Предпосылки
- Для всех обращений к ChatGPT/Whisper используйте прокси, настроенный через переменную `CHATGPT_PROXY_URL` в `.env` (пример: `http://proxy.example.com:8080`).

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

После запуска убедитесь, что создана запись в таблице `call_exports` со статусом `in_progress`. При ручном
старте указывайте `Idempotency-Key = hash(period + actor)` для избежания дублей.

## Мониторинг
- **Grafana:**
  - [Call Export Monitoring](https://grafana.example.com/d/mastermobile-call-export/call-export-overview?orgId=1) —
    панель в папке `MasterMobile / Integrations` с прогрессом, длительностью и статусами. Проверьте, что все виджеты с фильтрами по статусу используют `status="in_progress"` вместо устаревшего значения `running`.
  - [STT SLO & Alerts](https://grafana.example.com/d/mastermobile-stt/stt-alerts?orgId=1) —
    витрина `Speech-to-Text` для отслеживания SLO, burn rate и алертов `Alertmanager`.
- **Прометей:** ключевые запросы
  - Общее количество запусков: `sum by (status) (call_export_runs_total{environment="prod"})`
  - Стоимость транскрипций: `call_export_cost_total{environment="prod"}`
  - Дополнительно: `call_export_duration_seconds`, `call_transcripts_total`, `call_export_retry_total`.
  - SLO-метрика: `call_export_success_total{environment="prod"}` (см. раздел «SLO»).
- **Логи:** `docker compose logs -f app | jq 'select(.module=="call_export")'` — ищем `stage`, `call_id`, `error`.
- **Отчёты:** S3/объектное хранилище `exports/<period>/reports/summary_<period>.md` и CSV реестр
  `exports/<period>/registry/calls_<from>_<to>.csv`.
  - CSV cхема актуализирована до версии v0.2.0: добавлены столбцы `employee` и `text_preview`, а поля стоимости/языка переименованы в `transcription_cost`, `currency_code`, `language`. Детали — в [docs/specs/call_registry_schema.yaml](../specs/call_registry_schema.yaml).

### STT — SLO
- **Цель:** ≥ 95 % успешных завершений транскрипций за последние 24 часа (`success = status in {completed, skipped}`).
- **PromQL:**
  ```promql
  sum_over_time(call_export_success_total{environment="prod"}[24h])
    /
  sum_over_time(call_export_runs_total{environment="prod"}[24h])
  ```
- **Burn-rate контроль:**
  - 1h: `slo_error_budget_burn_rate(call_export_success_total, call_export_runs_total, window="1h", target=0.95)`
  - 6h: тот же запрос, но с окном `6h`.

## Алерты
| Правило | Порог | Действия |
| --- | --- | --- |
| `CallExportRunFailed` | `call_export_runs_total{status="error"} > 0` за 15 мин | Пейдж on-call, проверить логи и статус run. |
| `CallExportCostBudget` | `call_export_cost_total` > бюджет +20% (5 мин подряд) | Уведомить продакта, подтвердить тариф Whisper. |
| `CallExportRetryStorm` | `call_export_retry_total` > 50 за 15 мин | Проверить ошибки Bitrix24/Whisper, включить throttling. |
| `CallExport5xxGrowth` | `rate(call_export_transcribe_failures_total{code=~"5.."}[10m]) > 0.2` и рост на 50 % против `1h` среднего | Верифицировать статус Whisper/STT, переключить регион, включить деградационный режим. |
| `CallExportDLQSpike` | `increase(events_dlq_total{queue="call_export"}[15m]) > 10` | Проверить DLQ в Grafana, очистить/перепроиграть сообщения после анализа. |
| `CallExportJobLongRunning` | `max_over_time(call_export_duration_seconds{status="in_progress"}[30m]) > 1800` | Уточнить зависание в оркестраторе, оценить необходимость ручного завершения job. Обновите правило в Alertmanager/Grafana, если фильтр ещё использует `status="running"`. |
| `Bitrix24RateLimitWarn` | `integration.b24.rate_limited` события > 10/15 мин | Следовать playbook по лимитам Bitrix24. |

Алерты транслируются в `#ops-alerts` и PagerDuty (SEV-2 по умолчанию).

## Валидация и синтетические проверки
1. **Инжект алерта в Alertmanager Sandbox:**
   - В репозитории нет автоматизированных целей `make alerts-inject`/`make alerts-reset`. Для проверки используйте API Alertmanager Sandbox.
   - Подготовьте полезную нагрузку для теста `CallExportRunFailed`:
     ```bash
     export ALERTMANAGER_URL="https://alertmanager-sandbox.example.com"
     export ALERT_START="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
     export ALERT_END="$(date -u -d '+15 minutes' +"%Y-%m-%dT%H:%M:%SZ")"
     cat <<JSON >/tmp/call_export_run_failed.json
     [
       {
         "labels": {
           "alertname": "CallExportRunFailed",
           "service": "call_export",
           "severity": "critical",
           "environment": "sandbox",
           "source": "synthetic"
         },
         "annotations": {
           "summary": "Synthetic alert for call_export validation",
           "description": "Triggered manually from runbook validation"
         },
         "startsAt": "${ALERT_START}",
         "endsAt": "${ALERT_END}"
       }
     ]
     JSON
     ```
   - Отправьте алерт в Alertmanager Sandbox:
     ```bash
     curl -X POST "${ALERTMANAGER_URL}/api/v2/alerts" \
       -H 'Content-Type: application/json' \
       --data-binary @/tmp/call_export_run_failed.json
     ```
   - Для проверки других правил скорректируйте `alertname` и лейблы (`CallExport5xxGrowth`, `CallExportDLQSpike`, `CallExportJobLongRunning`).
2. **Проверить визуализацию:**
   - На дашборде [Call Export Monitoring](https://grafana.example.com/d/mastermobile-call-export/call-export-overview?orgId=1)
     убедиться, что панель «Active Alerts» отображает новое событие.
   - На дашборде [STT SLO & Alerts](https://grafana.example.com/d/mastermobile-stt/stt-alerts?orgId=1) проверить, что SLO-линии и burn-rate
     подсвечены в красном при тестовом нарушении.
3. **Прометей:** вручную выполнить запросы `call_export_transcribe_failures_total` и `events_dlq_total` через
   [Prometheus Expression Browser](https://prometheus.example.com/graph) для подтверждения инжекции.
4. **Post-check:** завершите синтетический алерт, отправив событие с истёкшим `endsAt`:
   ```bash
   export ALERT_RESOLVE_START="$(date -u -d '-10 minutes' +"%Y-%m-%dT%H:%M:%SZ")"
   export ALERT_RESOLVE_END="$(date -u -d '-1 minute' +"%Y-%m-%dT%H:%M:%SZ")"
   cat <<JSON >/tmp/call_export_run_failed_resolve.json
   [
     {
       "labels": {
         "alertname": "CallExportRunFailed",
         "service": "call_export",
         "severity": "critical",
         "environment": "sandbox",
         "source": "synthetic"
       },
       "annotations": {
         "summary": "Synthetic alert resolved",
         "description": "Manual resolution after validation"
       },
       "startsAt": "${ALERT_RESOLVE_START}",
       "endsAt": "${ALERT_RESOLVE_END}"
     }
   ]
   JSON
   curl -X POST "${ALERTMANAGER_URL}/api/v2/alerts" \
     -H 'Content-Type: application/json' \
     --data-binary @/tmp/call_export_run_failed_resolve.json
   ```
   Убедитесь, что алерт исчез из `Call Export Monitoring` и `STT SLO & Alerts`, и статус Alertmanager вернулся в `normal`.

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

## Changelog

- 03.10.2025 — Синхронизированы статусы `call_exports`/`call_records` с ER-диаграммой: обновлены мониторинг, алерт `CallExportJobLongRunning` и инструкции по дашбордам (переход с `running` на `in_progress`, уточнены успешные статусы SLO).
