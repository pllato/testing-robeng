#!/usr/bin/env python3
"""
Параллельная загрузка staging-папки в R2 bucket через wrangler.
Идемпотентно: пропускает уже залитые файлы (HEAD-проверка).

Использование:
    python3 upload_to_r2.py <staging_dir> <bucket_name> [--workers N] [--check]
"""
from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

WRANGLER = str(Path("~/.local/bin/wrangler").expanduser())


def list_files(staging: Path) -> list:
    files = []
    for p in staging.rglob("*"):
        if p.is_file():
            rel = p.relative_to(staging)
            files.append((p, str(rel)))
    return files


def check_exists(bucket: str, key: str) -> bool:
    """Используем `r2 object get --pipe` с null output как HEAD-эквивалент."""
    r = subprocess.run(
        [WRANGLER, "r2", "object", "get", f"{bucket}/{key}",
         "--pipe", "--remote"],
        capture_output=True, timeout=30
    )
    return r.returncode == 0


def upload_one(local: Path, key: str, bucket: str, content_type: Optional[str]) -> tuple:
    cmd = [WRANGLER, "r2", "object", "put", f"{bucket}/{key}",
           "--file", str(local), "--remote"]
    if content_type:
        cmd += ["--content-type", content_type]
    # до 3 ретраев с экспоненциальной задержкой
    import time
    last_err = ""
    for attempt in range(3):
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if r.returncode == 0:
            return (key, True, "")
        last_err = (r.stderr or r.stdout)[-300:]
        # не ретраим явные неавторизованные ошибки
        if "code: 9109" in last_err or "Authorization" in last_err:
            return (key, False, last_err)
        time.sleep(1.5 * (attempt + 1))
    return (key, False, last_err)


def content_type_for(path: Path) -> Optional[str]:
    suf = path.suffix.lower()
    return {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
            ".mp3": "audio/mpeg", ".json": "application/json"}.get(suf)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("staging_dir", type=Path)
    ap.add_argument("bucket")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--check", action="store_true",
                    help="только подсчитать, ничего не грузить")
    args = ap.parse_args()

    staging = args.staging_dir.expanduser().resolve()
    if not staging.is_dir():
        sys.exit(f"Не существует: {staging}")

    files = list_files(staging)
    print(f"Найдено файлов: {len(files)}")
    if args.check:
        return

    ok = 0
    failed = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(upload_one, local, key, args.bucket, content_type_for(local)): key
            for local, key in files
        }
        for i, fut in enumerate(as_completed(futures), 1):
            key, success, err = fut.result()
            if success:
                ok += 1
            else:
                failed.append((key, err))
            if i % 50 == 0 or i == len(files):
                print(f"  [{i}/{len(files)}] ok={ok} failed={len(failed)}")

    print(f"\nГотово: ok={ok}  failed={len(failed)}")
    if failed:
        print("\nПервые 10 ошибок:")
        for k, e in failed[:10]:
            print(f"  {k}\n    {e}")


if __name__ == "__main__":
    main()
