#!/usr/bin/env python3
"""
Парсер пакета Roblox_English_Reworked_1_70_PACKAGE → curriculum.json + gap_report.md

Использование:
    python3 build_curriculum.py <path_to_package> [<output_dir>]
"""
import json
import re
import sys
from pathlib import Path
from datetime import datetime

# ── Конфиг ────────────────────────────────────────────────────────
EXPECTED_WORDS = 12
EXPECTED_GRAMMAR_IMAGES = 4
GRAMMAR_IMG_NAMES = [f"grammar-0{i}.jpg" for i in range(1, 5)]
CONV_IMG_NAME = "conversation.jpg"

LESSON_HEADER_RE = re.compile(r"^[^\w]*Урок\s+(\d+)\.?\s*(.*)$")
WORDS_LINE_RE = re.compile(r"^Слова\s*\(\s*\d+\s*\)\s*:\s*(.+)$")
GRAMMAR_HEADER_RE = re.compile(r"^Грамматика", re.IGNORECASE)
EXAMPLES_RE = re.compile(r"^Examples?\s*:\s*(.+)$", re.IGNORECASE)
CONVERSATION_HEADER_RE = re.compile(r"^Conversation\s*:?\s*$", re.IGNORECASE)


def parse_lesson_txt(text: str, lesson_num: int) -> dict:
    """Распарсить lesson.txt в структуру."""
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
    out = {
        "lesson": lesson_num,
        "title": None,
        "topic": None,
        "words": [],
        "grammar_patterns": [],
        "examples": [],
        "conversation": [],
    }

    if not lines:
        return out

    # Заголовок: "🔸 Урок N. Topic"
    m = LESSON_HEADER_RE.match(lines[0])
    if m:
        out["title"] = lines[0]
        out["topic"] = m.group(2).strip() or None

    # Машина состояний по остальным строкам
    state = "preamble"  # preamble | grammar | examples_done | conversation
    for ln in lines[1:]:
        # Слова
        wm = WORDS_LINE_RE.match(ln)
        if wm:
            raw = wm.group(1)
            words = [w.strip() for w in raw.split(",") if w.strip()]
            out["words"] = words
            continue

        # Заголовок грамматики
        if GRAMMAR_HEADER_RE.match(ln):
            state = "grammar"
            continue

        # Examples — отдельная строка с примерами
        em = EXAMPLES_RE.match(ln)
        if em:
            ex_raw = em.group(1).strip()
            # Разделяем по точке-пробелу-большая-буква, либо просто берём целиком
            parts = re.split(r"(?<=[.!?])\s+(?=[A-ZА-Я])", ex_raw)
            out["examples"] = [p.strip() for p in parts if p.strip()]
            state = "examples_done"
            continue

        # Conversation header
        if CONVERSATION_HEADER_RE.match(ln):
            state = "conversation"
            continue

        # По состоянию
        if state == "grammar":
            out["grammar_patterns"].append(ln)
        elif state == "conversation":
            # Реплики обычно начинаются с "—" или "-"
            cleaned = ln.lstrip("—-–").strip()
            if cleaned:
                out["conversation"].append(cleaned)

    return out


def collect_lesson_files(lesson_dir: Path, lesson_num: int, words: list) -> dict:
    """Собрать список ожидаемых медиафайлов и проверить их наличие."""
    words_img = lesson_dir / "Words" / "images"
    words_aud = lesson_dir / "Words" / "произношения"
    grammar_img = lesson_dir / "Grammar" / "images"
    conv_img = lesson_dir / "Conversation" / "images"

    issues = []
    word_assets = []

    for w in words:
        img = words_img / f"{w}.jpg"
        aud = words_aud / f"{w}.mp3"
        word_assets.append({
            "word": w,
            "image": str(img.relative_to(lesson_dir.parent.parent)) if img.exists() else None,
            "audio": str(aud.relative_to(lesson_dir.parent.parent)) if aud.exists() else None,
        })
        if not img.exists():
            issues.append(f"missing image: Lesson {lesson_num}/Words/images/{w}.jpg")
        if not aud.exists():
            issues.append(f"missing audio: Lesson {lesson_num}/Words/произношения/{w}.mp3")

    # Лишние файлы в Words/images, которых нет в списке слов
    if words_img.exists():
        actual_imgs = {p.stem for p in words_img.glob("*.jpg")}
        expected = set(words)
        extra = actual_imgs - expected
        for x in sorted(extra):
            issues.append(f"orphan image: Lesson {lesson_num}/Words/images/{x}.jpg (not in word list)")

    grammar_imgs = []
    for name in GRAMMAR_IMG_NAMES:
        p = grammar_img / name
        if p.exists():
            grammar_imgs.append(str(p.relative_to(lesson_dir.parent.parent)))
        else:
            issues.append(f"missing grammar image: Lesson {lesson_num}/Grammar/images/{name}")

    conv_path = conv_img / CONV_IMG_NAME
    conv_image = None
    if conv_path.exists():
        conv_image = str(conv_path.relative_to(lesson_dir.parent.parent))
    else:
        issues.append(f"missing conversation image: Lesson {lesson_num}/Conversation/images/{CONV_IMG_NAME}")

    return {
        "word_assets": word_assets,
        "grammar_images": grammar_imgs,
        "conversation_image": conv_image,
        "issues": issues,
    }


def build(package_dir: Path, out_dir: Path):
    lessons_root = package_dir / "Lessons"
    if not lessons_root.is_dir():
        sys.exit(f"Не найдена папка: {lessons_root}")

    out_dir.mkdir(parents=True, exist_ok=True)

    curriculum = {
        "version": "1.0",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "source_package": package_dir.name,
        "lesson_count": 0,
        "lessons": [],
    }
    all_issues = []

    for lesson_num in range(1, 71):
        ldir = lessons_root / f"Lesson {lesson_num}"
        if not ldir.is_dir():
            all_issues.append(f"missing lesson folder: Lesson {lesson_num}")
            continue

        lesson_txt = ldir / "lesson.txt"
        if not lesson_txt.exists():
            all_issues.append(f"missing lesson.txt: Lesson {lesson_num}")
            continue

        text = lesson_txt.read_text(encoding="utf-8")
        parsed = parse_lesson_txt(text, lesson_num)

        # Проверки структуры
        if not parsed["title"]:
            all_issues.append(f"Lesson {lesson_num}: не удалось распарсить заголовок")
        if len(parsed["words"]) != EXPECTED_WORDS:
            all_issues.append(
                f"Lesson {lesson_num}: ожидалось {EXPECTED_WORDS} слов, получено {len(parsed['words'])}"
            )
        if not parsed["grammar_patterns"]:
            all_issues.append(f"Lesson {lesson_num}: пустые grammar_patterns")
        if not parsed["conversation"]:
            all_issues.append(f"Lesson {lesson_num}: пустой conversation")

        # Медиа
        media = collect_lesson_files(ldir, lesson_num, parsed["words"])
        all_issues.extend(media["issues"])

        lesson_obj = {
            **parsed,
            "media": {
                "word_assets": media["word_assets"],
                "grammar_images": media["grammar_images"],
                "conversation_image": media["conversation_image"],
            },
        }
        curriculum["lessons"].append(lesson_obj)

    curriculum["lesson_count"] = len(curriculum["lessons"])

    # Записать JSON
    out_json = out_dir / "curriculum.json"
    out_json.write_text(
        json.dumps(curriculum, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Отчёт о пробелах
    gap_path = out_dir / "gap_report.md"
    grouped = {
        "missing_lesson": [],
        "missing_lesson_txt": [],
        "title_parse": [],
        "word_count": [],
        "empty_grammar": [],
        "empty_conversation": [],
        "missing_image": [],
        "missing_audio": [],
        "missing_grammar_image": [],
        "missing_conv_image": [],
        "orphan_image": [],
        "other": [],
    }
    for issue in all_issues:
        if issue.startswith("missing lesson folder"):
            grouped["missing_lesson"].append(issue)
        elif issue.startswith("missing lesson.txt"):
            grouped["missing_lesson_txt"].append(issue)
        elif "не удалось распарсить заголовок" in issue:
            grouped["title_parse"].append(issue)
        elif "ожидалось" in issue and "слов" in issue:
            grouped["word_count"].append(issue)
        elif "пустые grammar_patterns" in issue:
            grouped["empty_grammar"].append(issue)
        elif "пустой conversation" in issue:
            grouped["empty_conversation"].append(issue)
        elif issue.startswith("missing image:"):
            grouped["missing_image"].append(issue)
        elif issue.startswith("missing audio:"):
            grouped["missing_audio"].append(issue)
        elif issue.startswith("missing grammar image"):
            grouped["missing_grammar_image"].append(issue)
        elif issue.startswith("missing conversation image"):
            grouped["missing_conv_image"].append(issue)
        elif issue.startswith("orphan image"):
            grouped["orphan_image"].append(issue)
        else:
            grouped["other"].append(issue)

    md = []
    md.append(f"# Gap report — {package_dir.name}")
    md.append(f"\nСгенерировано: {curriculum['generated_at']}")
    md.append(f"\nУроков обработано: **{curriculum['lesson_count']} / 70**")
    md.append(f"\nВсего замечаний: **{len(all_issues)}**\n")

    titles = {
        "missing_lesson": "Отсутствующие папки уроков",
        "missing_lesson_txt": "Отсутствующие lesson.txt",
        "title_parse": "Не распарсен заголовок",
        "word_count": "Неверное число слов",
        "empty_grammar": "Пустой раздел грамматики",
        "empty_conversation": "Пустой диалог",
        "missing_image": "Отсутствующие картинки слов",
        "missing_audio": "Отсутствующие аудио слов",
        "missing_grammar_image": "Отсутствующие картинки грамматики",
        "missing_conv_image": "Отсутствующие картинки диалога",
        "orphan_image": "Лишние картинки (не в списке слов)",
        "other": "Прочее",
    }
    for key, items in grouped.items():
        if not items:
            continue
        md.append(f"\n## {titles[key]} ({len(items)})\n")
        for it in items[:200]:
            md.append(f"- {it}")
        if len(items) > 200:
            md.append(f"- ... и ещё {len(items) - 200}")

    if not all_issues:
        md.append("\n✅ Замечаний не обнаружено.")

    gap_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    # Stdout summary
    print(f"OK")
    print(f"  curriculum.json: {out_json}  ({out_json.stat().st_size:,} bytes)")
    print(f"  gap_report.md:   {gap_path}")
    print(f"  lessons:         {curriculum['lesson_count']}/70")
    print(f"  issues:          {len(all_issues)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("Usage: build_curriculum.py <package_dir> [<output_dir>]")
    pkg = Path(sys.argv[1]).expanduser().resolve()
    out = Path(sys.argv[2]).expanduser().resolve() if len(sys.argv) > 2 else Path.cwd()
    build(pkg, out)
