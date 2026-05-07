#!/usr/bin/env python3
"""
Готовим медиа к загрузке в R2:
- структура: lessons/lesson-01/words/<slug>.jpg, audio/<slug>.mp3,
            grammar/01.jpg..04.jpg, conversation.jpg
- jpg-картинки оптимизируем через sips (resize 1024 + quality 75)
- mp3 копируем как есть (5.7 MB на всё, не имеет смысла трогать)
- финальный curriculum.json пишем со slug-путями, без префикса домена

Использование:
    python3 build_media_staging.py <package_dir> <staging_dir>
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

JPG_MAX_SIDE = 1024
JPG_QUALITY = 75


def slugify(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"[^a-z0-9\-]", "", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s


def optimize_jpg(src: Path, dst: Path):
    """sips: resize до JPG_MAX_SIDE по большей стороне + JPEG quality."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    # sips -Z resize если больше N
    subprocess.run(
        ["sips", "-Z", str(JPG_MAX_SIDE),
         "-s", "format", "jpeg",
         "-s", "formatOptions", str(JPG_QUALITY),
         str(src), "--out", str(dst)],
        check=True, capture_output=True
    )


def copy_file(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def process_lesson(curr_lesson: dict, package_dir: Path, staging_root: Path) -> dict:
    """Для одного урока: копирует/оптимизирует файлы, возвращает обновлённый dict."""
    n = curr_lesson["lesson"]
    lesson_slug = f"lesson-{n:02d}"
    base = staging_root / "lessons" / lesson_slug
    base.mkdir(parents=True, exist_ok=True)

    # Слова: image + audio
    new_word_assets = []
    for wa in curr_lesson["media"]["word_assets"]:
        word = wa["word"]
        slug = slugify(word)
        if not slug:
            slug = f"word-{len(new_word_assets)+1:02d}"

        new_img_rel = f"lessons/{lesson_slug}/words/{slug}.jpg"
        new_aud_rel = f"lessons/{lesson_slug}/audio/{slug}.mp3"

        if wa["image"]:
            src = package_dir / wa["image"]
            dst = staging_root / new_img_rel
            optimize_jpg(src, dst)

        if wa["audio"]:
            src = package_dir / wa["audio"]
            dst = staging_root / new_aud_rel
            copy_file(src, dst)

        new_word_assets.append({
            "word": word,
            "slug": slug,
            "image": new_img_rel,
            "audio": new_aud_rel,
        })

    # Grammar: 01..04
    new_grammar = []
    for i, g in enumerate(curr_lesson["media"]["grammar_images"], start=1):
        new_rel = f"lessons/{lesson_slug}/grammar/{i:02d}.jpg"
        if g:
            src = package_dir / g
            dst = staging_root / new_rel
            optimize_jpg(src, dst)
        new_grammar.append(new_rel)

    # Conversation
    new_conv = None
    if curr_lesson["media"]["conversation_image"]:
        new_conv = f"lessons/{lesson_slug}/conversation.jpg"
        src = package_dir / curr_lesson["media"]["conversation_image"]
        dst = staging_root / new_conv
        optimize_jpg(src, dst)

    new_lesson = {
        **curr_lesson,
        "slug": lesson_slug,
        "media": {
            "word_assets": new_word_assets,
            "grammar_images": new_grammar,
            "conversation_image": new_conv,
        },
    }
    return new_lesson


def main(package_dir: Path, staging_dir: Path):
    if not package_dir.is_dir():
        sys.exit(f"Не найден package: {package_dir}")
    staging_dir.mkdir(parents=True, exist_ok=True)

    # читаем уже распарсенный curriculum.json
    curriculum_path = Path(__file__).parent / "curriculum.json"
    if not curriculum_path.exists():
        sys.exit(f"Сначала запусти build_curriculum.py чтобы получить {curriculum_path}")

    curriculum = json.loads(curriculum_path.read_text(encoding="utf-8"))

    # параллельная обработка по урокам
    new_lessons = [None] * len(curriculum["lessons"])
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            pool.submit(process_lesson, l, package_dir, staging_dir): i
            for i, l in enumerate(curriculum["lessons"])
        }
        done = 0
        for fut in as_completed(futures):
            i = futures[fut]
            new_lessons[i] = fut.result()
            done += 1
            print(f"  [{done:>2}/70] lesson-{new_lessons[i]['lesson']:02d}")

    new_curriculum = {
        **curriculum,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "media_base_path": "lessons/",
        "lessons": new_lessons,
    }

    out_json = Path(__file__).parent / "curriculum.r2.json"
    out_json.write_text(
        json.dumps(new_curriculum, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # размер staging
    total = subprocess.run(
        ["du", "-sh", str(staging_dir)], capture_output=True, text=True
    ).stdout.strip()
    print(f"\nStaging size: {total}")
    print(f"R2-ready JSON: {out_json}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("Usage: build_media_staging.py <package_dir> <staging_dir>")
    main(Path(sys.argv[1]).expanduser().resolve(),
         Path(sys.argv[2]).expanduser().resolve())
