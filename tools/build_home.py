"""Regenerate the homepage trace data (RU, EN, IT) from the article lists.

Run from the repo root after adding an article:  python tools/build_home.py

Reads articles/index.html, en/articles/index.html and it/articles/index.html and
rewrites the <script type="application/json" id="trace-data"> block in index.html,
en/index.html and it/index.html. Order comes from the RU publication dates; titles,
dates and links come from each language's own list. Line endings are preserved.
Also rewrites sitemap.xml from all pages in the repo.
"""
import html
import json
import os
import posixpath
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LANE = {
    "C++": "cpp", "Курс · C++": "cpp", "Course · C++": "cpp", "Corso · C++": "cpp",
    "Инструменты": "cpp", "Tools": "cpp", "Strumenti": "cpp",
    "Ненормальное программирование": "abn", "Abnormal programming": "abn", "Programmazione anormale": "abn",
    "Производительность": "perf", "Performance": "perf", "Prestazioni": "perf",
    "Реверс-инжиниринг": "rev", "Reverse-engineering": "rev", "Reverse engineering": "rev",
    "Геймдизайн": "design", "Game design": "design",
    "Ремесло": "craft", "Craft": "craft", "Mestiere": "craft", "Блог": "craft", "Blog": "craft",
}
MONTHS_RU = ["январ", "феврал", "март", "апрел", "ма", "июн", "июл", "август", "сентябр", "октябр", "ноябр", "декабр"]
SHORT_RU = ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]
WPM = 243
SITE = "https://dalerank.github.io/"


def text(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def read(path):
    with open(path, encoding="utf-8", newline="") as f:
        return f.read()


def reading_min(page_path):
    page = read(page_path)
    m = re.search(r'<article class="prose">(.*?)</article>', page, re.S)
    body = re.sub(r"<pre.*?</pre>", "", m.group(1) if m else "", flags=re.S)
    return max(1, round(len(text(body).split()) / WPM))


def parse_list(lang_dir):
    """Entries of <lang>/articles/index.html: slug -> dict(href, lane, title, date, min)."""
    list_dir = posixpath.join(lang_dir, "articles") if lang_dir else "articles"
    src = read(os.path.join(ROOT, list_dir, "index.html"))
    out = {}
    for li in re.findall(r"<li>(.*?)</li>", src, re.S):
        m = re.search(r'<a href="([^"]+)">\s*<span class="tag[^"]*">(.*?)</span>\s*<h3>(.*?)</h3>', li, re.S)
        meta = re.search(r'class="pmeta">(.*?)</div>', li, re.S)
        if not m or not meta:
            continue
        href, tag, title = m.group(1), text(m.group(2)), text(m.group(3))
        spans = [text(s) for s in re.findall(r"<span>(.*?)</span>", meta.group(1))]
        target = posixpath.normpath(posixpath.join(list_dir, href))  # repo-relative
        mins = next((int(re.match(r"\d+", s).group()) for s in spans[1:] if re.match(r"\d+\s*min|\d+\s*мин", s)), None)
        if mins is None:
            mins = reading_min(os.path.join(ROOT, target))
        out[posixpath.basename(href)] = {
            "target": target, "lane": LANE.get(tag, "craft"),
            "title": title, "date": spans[0], "min": mins,
        }
    return out


def ru_key(date):
    parts = date.lower().split()
    if len(parts) == 2:  # "Апр 2025"
        return (int(parts[1]), SHORT_RU.index(parts[0][:3]), 1)
    d, mon, y = parts
    month = next(i for i, p in enumerate(MONTHS_RU) if mon.startswith(p) and not (p == "ма" and mon.startswith("март")))
    return (int(y), month, int(d))


def main():
    ru = parse_list("")
    order = sorted(reversed(list(ru)), key=lambda slug: ru_key(ru[slug]["date"]))  # list is newest-first; stable sort keeps add order within a day
    for lang_dir in ("", "en", "it"):
        items = ru if not lang_dir else parse_list(lang_dir)
        home = os.path.join(ROOT, lang_dir, "index.html")
        data = []
        for slug in order:
            a = items.get(slug, ru[slug])
            href = posixpath.relpath(a["target"], lang_dir or ".")
            data.append({
                "href": href, "lane": ru[slug]["lane"], "title": a["title"],
                "date": a["date"], "year": ru_key(ru[slug]["date"])[0], "min": a["min"],
            })
        page = read(home)
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
        new, n = re.subn(r'(<script type="application/json" id="trace-data">).*?(</script>)',
                         lambda m: m.group(1) + payload + m.group(2), page, flags=re.S)
        if n != 1:
            sys.exit(f"{home}: trace-data block not found")
        with open(home, "w", encoding="utf-8", newline="") as f:
            f.write(new)
        print(f"{lang_dir or 'ru'}: {len(data)} articles, {sum(d['min'] for d in data)} min")
    build_sitemap()


def build_sitemap():
    """sitemap.xml with every public page; robots.txt points to it."""
    urls = []
    for dirpath, dirs, files in os.walk(ROOT):
        rel_dir = os.path.relpath(dirpath, ROOT).replace("\\", "/")
        if rel_dir.split("/")[0] in (".git", ".claude", "assets", "tools"):
            dirs[:] = []
            continue
        for fn in files:
            if not fn.endswith(".html") or fn == "404.html":
                continue
            rel = fn if rel_dir == "." else f"{rel_dir}/{fn}"
            if 'name="robots" content="noindex' in read(os.path.join(ROOT, rel)):
                continue
            urls.append(SITE + (rel[: -len("index.html")] if fn == "index.html" else rel))
    urls.sort(key=lambda u: (u.count("/"), u))
    body = "\n".join(f"  <url><loc>{html.escape(u)}</loc></url>" for u in urls)
    with open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8", newline="\n") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + body + "\n</urlset>\n")
    print(f"sitemap: {len(urls)} pages")


if __name__ == "__main__":
    main()
