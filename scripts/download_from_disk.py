#!/usr/bin/env python3
# coding: utf-8
"""
scripts/download_from_disk.py

Скачивает последний файл (по дате изменения) из указанной папки на Bitrix24 Disk
и сохраняет в ./build/one_call/

Авторизация: через входящий вебхук (B24_WEBHOOK_USER_ID + B24_WEBHOOK_TOKEN).
Опции:
  --folder-id ID               прямой id папки на Диске (рекомендуется)
  --folder-path "A/B/2025-09"  путь по именам (начиная с корня общего диска)
  --name-pattern PATTERN       (опц.) фильтр по имени файла (регэксп)
  --dry-run                    не скачивает, только показывает найденный файл
  --limit N                    сколько элементов читать из папки (по умолчанию 200)
Пример:
  B24_BASE_URL=https://master-mobile.bitrix24.ru \
  B24_WEBHOOK_USER_ID=10979 B24_WEBHOOK_TOKEN=b0i4... \
  python scripts/download_from_disk.py --folder-path "Телефония - записи звонков/2025-09"
"""
from __future__ import annotations
import os, sys, re, json, argparse, time
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

# Настройки по умолчанию
BUILD_DIR = Path("./build/one_call")
BUILD_DIR.mkdir(parents=True, exist_ok=True)


def _env(name: str) -> str:
    v = os.getenv(name, "")
    return v


B24_BASE = _env("B24_BASE_URL")
B24_USER = _env("B24_WEBHOOK_USER_ID")
B24_TOKEN = _env("B24_WEBHOOK_TOKEN")

if B24_BASE.endswith("/rest/"):
    B24_BASE = B24_BASE[:-1]
def build_b24_url(method: str) -> str:
    base = B24_BASE.rstrip("/")
    if not base.endswith("/rest"):
        base = base + "/rest"
    return f"{base}/{B24_USER}/{B24_TOKEN}/{method}.json"

def b24_post(client: httpx.Client, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
    url = build_b24_url(method)
    r = client.post(url, data=data, timeout=60)
    try:
        return r.json()
    except Exception:
        return {"http_status": r.status_code, "text": r.text}

def find_folder_by_path(client: httpx.Client, path: str, limit: int = 200) -> Optional[int]:
    """
    Идём по уровням: для каждого сегмента вызываем disk.folder.getchildren(parentId=cur_id)
    Начинаем с корня каждого хранилища (disk.storage.getlist) и ищем первый совпадение.
    При успехе возвращаем ID папки.
    """
    # Получим storages
    storages = b24_post(client, "disk.storage.getlist", {}) or {}
    storages_list = storages.get("result") or []
    # segments
    parts = [p.strip() for p in path.split("/") if p.strip()]
    if not parts:
        return None
    # Попробуем пройти по всем хранилищам (обычно только одно "Общий диск")
    for s in storages_list:
        # root object id может лежать в разных ключах; проверим несколько
        root_id = s.get("ROOT_OBJECT_ID") or s.get("rootObjectId") or s.get("ROOT_ID") or s.get("ID")
        if not root_id:
            continue
        cur_id = root_id
        ok = True
        for part in parts:
            # перечисляем детей текущей папки и ищем child с NAME == part
            payload = {"id": cur_id, "ORDER[ID]": "ASC", "LIMIT": str(limit)}
            resp = b24_post(client, "disk.folder.getchildren", payload)
            items = resp.get("result", {}).get("items") or resp.get("result") or []
            found = None
            for it in items:
                name = it.get("NAME") or it.get("name") or it.get("TITLE") or ""
                typ = it.get("TYPE") or it.get("type") or ""
                # match by name
                if name == part and (str(typ).lower() in ("folder", "dir", "") or "folder" in str(typ).lower()):
                    found = it
                    break
            if not found:
                ok = False
                break
            # next level
            cur_id = found.get("ID") or found.get("id")
            if not cur_id:
                ok = False
                break
        if ok and cur_id:
            return int(cur_id)
    return None

def list_folder_children(client: httpx.Client, folder_id: int, limit: int = 500) -> List[Dict[str, Any]]:
    resp = b24_post(client, "disk.folder.getchildren", {"id": str(folder_id), "ORDER[=CREATED_TIME]": "DESC", "LIMIT": str(limit)})
    items = resp.get("result", {}).get("items") or resp.get("result") or []
    return items or []

def download_file_by_id(client: httpx.Client, file_id: int, dst: Path) -> Path:
    """
    Скачиваем через метод disk.file.download.json?id=FILE_ID
    Метод возвращает редирект на файл — httpx с follow_redirects=True загрузит контент.
    """
    url = build_b24_url("disk.file.download")
    params = {"id": str(file_id)}
    r = client.get(url, params=params, timeout=120, follow_redirects=True)
    r.raise_for_status()
    # попытка определить имя по Content-Disposition
    fn = None
    cd = r.headers.get("Content-Disposition") or r.headers.get("content-disposition", "")
    m = re.search(r'filename\*?=(?:UTF-8\'\'|")?([^;"\']+)', cd)
    if m:
        fn = m.group(1).strip().strip('"')
    if not fn:
        # fallback имя
        fn = f"call_recording_{file_id}.bin"
    out = dst / fn
    out.write_bytes(r.content)
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder-id", type=int, help="ID папки на Диске (если известен — лучший вариант)")
    ap.add_argument("--folder-path", type=str, help="Путь по именам, например 'Телефония - записи звонков/2025-09'")
    ap.add_argument("--month", type=str, help="Если указан, ищем подпапку с этим именем (например 2025-09)")
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--name-pattern", type=str, help="Regexp для фильтрации по имени файла")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not (B24_BASE and B24_USER and B24_TOKEN):
        print("Требуется установить B24_BASE_URL, B24_WEBHOOK_USER_ID, B24_WEBHOOK_TOKEN в окружении", file=sys.stderr)
        sys.exit(2)

    with httpx.Client() as client:
        folder_id = args.folder_id
        if not folder_id and args.folder_path:
            print(f"[info] Ищем папку по пути: {args.folder_path}")
            folder_id = find_folder_by_path(client, args.folder_path, limit=args.limit)
            print("[debug] resolved folder_id =", folder_id)
        if not folder_id and args.month:
            # попробуем найти папку месяца внутри default root path "Телефония - записи звонков"
            # Пользователь может указать только --month, тогда ожидаем что корневая папка называется так
            print("[info] Пытаемся найти корневую папку 'Телефония - записи звонков' и подпапку месяца", args.month)
            folder_id = find_folder_by_path(client, f"Телефония - записи звонков/{args.month}", limit=args.limit)
            print("[debug] resolved folder_id =", folder_id)

        if not folder_id:
            print("[warn] folder_id не указан и не найден. Укажи --folder-id или --folder-path.", file=sys.stderr)
            print("Подсказка: можно взять ID из URL Диска (открыть папку в UI).", file=sys.stderr)
            sys.exit(1)

        print(f"[info] Используем folder_id={folder_id}, читаем детей (limit={args.limit})")
        items = list_folder_children(client, folder_id, limit=args.limit)
        if not items:
            print("[warn] В папке нет элементов", file=sys.stderr)
            sys.exit(1)

        # Оставим только файлы и отсортируем по DATE_CREATE/CREATED_TIME/UPDATED
        files = []
        for it in items:
            # возможные ключи
            typ = it.get("TYPE") or it.get("type") or it.get("kind") or ""
            if str(typ).lower() in ("file", "f", "") or ("FILE" in it) or ("NAME" in it and it.get("ID")):
                # берем случаи как файл
                files.append(it)
            else:
                # иногда TYPE у папки == 'folder' — исключаем
                if not str(typ).lower().startswith("folder"):
                    files.append(it)

        if not files:
            print("[warn] Нет файлов в папке (посмотреть полный JSON ответа для диагностики)", file=sys.stderr)
            print(json.dumps(items[:10], ensure_ascii=False, indent=2))
            sys.exit(1)

        # сортировка: попробуем по полям DATE_CREATE / CREATED_TIME / TIMESTAMP_X
        def key_date(x):
            for k in ("CREATED_TIME", "DATE_CREATE", "TIMESTAMP_X", "UPDATE_TIME", "UPDATE_DATE"):
                v = x.get(k) or x.get(k.lower())
                if v:
                    return v
            # fallback: ID (не идеально)
            return str(x.get("ID") or x.get("id") or "")

        files_sorted = sorted(files, key=key_date, reverse=True)
        candidate = files_sorted[0]
        print("[info] Candidate file metadata (first):")
        print(json.dumps(candidate, ensure_ascii=False, indent=2))

        # Попробуем извлечь ID файла
        file_id = candidate.get("ID") or candidate.get("id") or candidate.get("FILE_ID") or candidate.get("fileId")
        if not file_id:
            # иногда структура вложена: candidate["FILE"]["ID"]
            file_id = (candidate.get("FILE") or {}).get("ID") or (candidate.get("FILE") or {}).get("id")
        if not file_id:
            print("[error] Не удалось определить id файла для скачивания. Смотри JSON выше.", file=sys.stderr)
            sys.exit(1)

        print(f"[info] Попытка скачать file_id={file_id}")
        if args.dry_run:
            print("[dry-run] не скачиваем — выход.")
            sys.exit(0)

        out_path = download_file_by_id(client, int(file_id), BUILD_DIR)
        print(f"[ok] Скачано: {out_path}")

if __name__ == "__main__":
    main()
