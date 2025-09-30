#!/usr/bin/env bash
set -euo pipefail

REPORT_DIR="build/reports"
mkdir -p "$REPORT_DIR"

# 1) Bootstrap
echo "== Bootstrap ==" | tee "$REPORT_DIR/WW_QA_Report.md"
(make init && make up && make test) 2>&1 | tee -a "$REPORT_DIR/WW_QA_Report.md" || true

# 2) Здоровье сервисов
echo -e "\n## Здоровье сервисов" >> "$REPORT_DIR/WW_QA_Report.md"
docker compose ps | tee "$REPORT_DIR/docker_ps.txt" | sed 's/^/    /' >> "$REPORT_DIR/WW_QA_Report.md" || true

# 3) Ping + Метрики
echo -e "\n## Ping & Метрики" >> "$REPORT_DIR/WW_QA_Report.md"
{ curl -sS http://localhost:8000/api/v1/system/ping || true; } \
 | sed 's/^/    /' >> "$REPORT_DIR/WW_QA_Report.md"
{ curl -sS http://localhost:8000/metrics | head -n 50 || true; } \
 | tee "$REPORT_DIR/metrics_head.txt" \
 | sed 's/^/    /' >> "$REPORT_DIR/WW_QA_Report.md"

# 4) CRUD сценарий (курьер + заказ)
echo -e "\n## CRUD WW" >> "$REPORT_DIR/WW_QA_Report.md"
C_HEADERS=(-H "Content-Type: application/json")
COURIER_JSON=$(curl -sS -X POST http://localhost:8000/api/v1/ww/couriers "${C_HEADERS[@]}" \
  -d '{"full_name":"Иван Курьер","phone":"+79990000000"}' || true)
echo "Courier: $COURIER_JSON" >> "$REPORT_DIR/WW_QA_Report.md"

ORDER_JSON=$(curl -sS -X POST http://localhost:8000/api/v1/ww/orders "${C_HEADERS[@]}" \
  -d '{"partner_name":"ООО Ромашка","address":"Москва, ул. Пушкина, 10","amount_rub":350}' || true)
echo "Order: $ORDER_JSON" >> "$REPORT_DIR/WW_QA_Report.md"

# Извлекаем id (падать не будем, это QA)
COURIER_ID=$(echo "$COURIER_JSON" | sed -n 's/.*"id":\s*\([0-9]\+\).*/\1/p' | head -n1 || true)
ORDER_ID=$(echo   "$ORDER_JSON"   | sed -n 's/.*"id":\s*\([0-9]\+\).*/\1/p' | head -n1 || true)

curl -sS -X POST "http://localhost:8000/api/v1/ww/orders/${ORDER_ID}/assign" "${C_HEADERS[@]}" \
  -d "{\"courier_id\":${COURIER_ID}}" >> "$REPORT_DIR/WW_QA_Report.md" || true
echo >> "$REPORT_DIR/WW_QA_Report.md"

curl -sS -X POST "http://localhost:8000/api/v1/ww/orders/${ORDER_ID}/status" "${C_HEADERS[@]}" \
  -d '{"status":"DONE"}' >> "$REPORT_DIR/WW_QA_Report.md" || true
echo >> "$REPORT_DIR/WW_QA_Report.md"

LOGS_JSON=$(curl -sS "http://localhost:8000/api/v1/ww/orders/${ORDER_ID}/logs" || true)
echo "Logs (truncated):" >> "$REPORT_DIR/WW_QA_Report.md"
echo "$LOGS_JSON" | head -n 50 | sed 's/^/    /' >> "$REPORT_DIR/WW_QA_Report.md"

# 5) Idempotency
echo -e "\n## Idempotency" >> "$REPORT_DIR/WW_QA_Report.md"
DUP1=$(curl -sS -X POST http://localhost:8000/api/v1/ww/orders \
  -H "Idempotency-Key: ww-order-abc123" "${C_HEADERS[@]}" \
  -d '{"partner_name":"ООО Ромашка","address":"Москва, ул. Пушкина, 10","amount_rub":350}' || true)
DUP2=$(curl -sS -X POST http://localhost:8000/api/v1/ww/orders \
  -H "Idempotency-Key: ww-order-abc123" "${C_HEADERS[@]}" \
  -d '{"partner_name":"ООО Ромашка","address":"Москва, ул. Пушкина, 10","amount_rub":350}' || true)
echo "dup#1: $DUP1" >> "$REPORT_DIR/WW_QA_Report.md"
echo "dup#2: $DUP2" >> "$REPORT_DIR/WW_QA_Report.md"

# 6) Метрики WW
echo -e "\n## WW Метрики" >> "$REPORT_DIR/WW_QA_Report.md"
curl -sS http://localhost:8000/metrics | grep -E 'ww_(orders_total|assignments_total|order_cycle_seconds|kmp4_exports_total)' -n \
  | sed 's/^/    /' >> "$REPORT_DIR/WW_QA_Report.md" || true

# 7) Отчёты
echo -e "\n## Отчёты" >> "$REPORT_DIR/WW_QA_Report.md"
curl -sS "http://localhost:8000/api/v1/ww/report/deliveries?from=$(date +%Y-%m-01)&to=$(date +%Y-%m-%d)&format=csv" \
  > "$REPORT_DIR/ww_report.csv" || true
curl -sS "http://localhost:8000/api/v1/ww/export/kmp4?from=$(date +%Y-%m-01)&to=$(date +%Y-%m-%d)&encoding=utf8&decimal=comma" \
  > "$REPORT_DIR/ww_kmp4.csv" || true
curl -sS "http://localhost:8000/api/v1/ww/export/kmp4?from=$(date +%Y-%m-01)&to=$(date +%Y-%m-%d)&encoding=utf8&decimal=comma" \
  > "$REPORT_DIR/ww_kmp4_repeat.csv" || true

{
  echo "ww_report.csv:  $(wc -l < "$REPORT_DIR/ww_report.csv" 2>/dev/null || echo 0) lines"
  echo "ww_report.csv md5: $(md5sum "$REPORT_DIR/ww_report.csv" 2>/dev/null || echo N/A)"
  echo "ww_kmp4.csv md5:   $(md5sum "$REPORT_DIR/ww_kmp4.csv" 2>/dev/null || echo N/A)"
  echo "repeat md5:        $(md5sum "$REPORT_DIR/ww_kmp4_repeat.csv" 2>/dev/null || echo N/A)"
  cmp -s "$REPORT_DIR/ww_kmp4.csv" "$REPORT_DIR/ww_kmp4_repeat.csv" && echo "KMP4 export is idempotent" || echo "KMP4 export differs"
} >> "$REPORT_DIR/WW_QA_Report.md" 2>/dev/null

echo -e "\n---\nГотово. Итоговый отчёт: $REPORT_DIR/WW_QA_Report.md"
