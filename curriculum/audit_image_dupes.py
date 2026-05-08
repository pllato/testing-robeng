#!/usr/bin/env python3
"""
Audit image-vs-word visual similarity for the ELC Kids curriculum.

Algorithm (custom perceptual hash, no extra deps beyond PIL):
1. Download/cache each lesson's word images.
2. Crop top 25% (where text label is rendered) to remove "boy"/"girl"/etc text.
3. Resize to 16×16 grayscale.
4. Mean pixel value → 256-bit hash (1 bit per pixel: ≥mean → 1, else 0).
5. Compare hashes within a lesson via Hamming distance.
   <8  → visually identical
   8-25 → very similar
   >25  → different scenes
"""
import os, sys, json, urllib.request, hashlib
from PIL import Image
from io import BytesIO

BASE = "https://pub-4a4bf55405d74fe58e817b5fb86955d4.r2.dev"
UA   = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36"
CACHE_DIR = "/tmp/elc-img-real/cache"
os.makedirs(CACHE_DIR, exist_ok=True)

def fetch_curriculum():
    req = urllib.request.Request(BASE + "/curriculum.json", headers={"User-Agent": UA})
    with urllib.request.urlopen(req) as r:
        return json.load(r)

def fetch_image(rel_path):
    cache_key = hashlib.md5(rel_path.encode()).hexdigest() + ".jpg"
    cache_path = os.path.join(CACHE_DIR, cache_key)
    if os.path.exists(cache_path) and os.path.getsize(cache_path) > 1000:
        return open(cache_path, "rb").read()
    req = urllib.request.Request(BASE + "/" + rel_path, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = r.read()
        open(cache_path, "wb").write(data)
        return data
    except Exception as e:
        print(f"  ! fetch failed {rel_path}: {e}", file=sys.stderr)
        return None

def phash(img_bytes, size=16):
    if not img_bytes: return None
    im = Image.open(BytesIO(img_bytes)).convert("L")
    # Crop top 25% (where the text label is rendered)
    w, h = im.size
    im = im.crop((0, int(h * 0.25), w, h))
    im = im.resize((size, size), Image.LANCZOS)
    pixels = list(im.getdata())
    avg = sum(pixels) / len(pixels)
    return tuple(1 if p >= avg else 0 for p in pixels)

def hamming(a, b):
    return sum(1 for x, y in zip(a, b) if x != y)

def main():
    lessons_to_audit = list(range(1, 71))
    if len(sys.argv) > 1:
        # filter — e.g. "1,2,3,7"
        lessons_to_audit = [int(x) for x in sys.argv[1].split(",")]

    data = fetch_curriculum()
    by_lesson = {L["lesson"]: L for L in data["lessons"]}

    flagged = []  # (lesson_num, [groups of similar word names])
    print(f"Auditing {len(lessons_to_audit)} lessons (perceptual hash, top-cropped)...")
    print()

    for n in lessons_to_audit:
        L = by_lesson.get(n)
        if not L: continue
        wa = L.get("media", {}).get("word_assets", [])
        if not wa: continue
        # compute hashes
        items = []
        for w in wa:
            img = fetch_image(w["image"])
            h = phash(img)
            if h: items.append((w["word"], h))
        # group by similarity (DSU)
        n_items = len(items)
        parent = list(range(n_items))
        def find(x):
            while parent[x] != x: parent[x] = parent[parent[x]]; x = parent[x]
            return x
        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb: parent[ra] = rb
        for i in range(n_items):
            for j in range(i+1, n_items):
                d = hamming(items[i][1], items[j][1])
                if d < 8:           # ОЧЕНЬ похожие
                    union(i, j)
        # collect groups with >= 2 members
        groups = {}
        for i in range(n_items):
            r = find(i)
            groups.setdefault(r, []).append(items[i][0])
        dup_groups = [g for g in groups.values() if len(g) > 1]
        if dup_groups:
            flagged.append((n, dup_groups, L.get("topic","")))
            print(f"L{n:02d} ({L.get('topic','')}):")
            for g in dup_groups:
                print(f"   ⚠️ одинаковые: {g}")

    print()
    print(f"=== ИТОГ ===")
    print(f"уроков с дублями картинок: {len(flagged)} из {len(lessons_to_audit)}")
    total_words_in_dups = sum(sum(len(g) for g in groups) for _, groups, _ in flagged)
    print(f"слов, у которых картинка-дубль: ~{total_words_in_dups}")
    # save report
    rep = {
        "generated_for_lessons": lessons_to_audit,
        "flagged": [{"lesson": n, "topic": t, "duplicates": gs} for n, gs, t in flagged],
    }
    out = "/tmp/elc-img-real/duplicate_report.json"
    json.dump(rep, open(out, "w"), ensure_ascii=False, indent=2)
    print(f"отчёт сохранён: {out}")

if __name__ == "__main__":
    main()
