"""Regenerate everything on the site that is derived from the article lists.

Run from the repo root after adding or translating an article:  python tools/build.py

Source of truth: articles/index.html, en/articles/index.html, it/articles/index.html
(order comes from the RU publication dates). Rewrites, for RU, EN and IT:
  - the homepage trace data (<script id="trace-data"> in index.html)
  - the "More on this topic" block at the end of every article (<!-- related --> markers)
  - the topic tag in each article head, as a link to the topic page that lists it
  - feed.xml (RSS of the newest local articles)
and sitemap.xml for the whole site. Line endings of edited pages are preserved.
"""
import html
import json
import os
import posixpath
import re
import sys
from email.utils import format_datetime
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://dalerank.github.io/"
LANGS = ("", "en", "it")
WPM = 243
RELATED_N = 3
FEED_N = 40

LANE = {
    "C++": "cpp", "Курс · C++": "cpp", "Course · C++": "cpp", "Corso · C++": "cpp",
    "Инструменты": "cpp", "Tools": "cpp", "Strumenti": "cpp",
    "Ненормальное программирование": "abn", "Abnormal programming": "abn", "Programmazione anormale": "abn",
    "Производительность": "perf", "Performance": "perf", "Prestazioni": "perf",
    "Реверс-инжиниринг": "rev", "Reverse-engineering": "rev", "Reverse engineering": "rev",
    "Геймдизайн": "design", "Game design": "design",
    "Ремесло": "craft", "Craft": "craft", "Mestiere": "craft", "Блог": "craft", "Blog": "craft",
}
# topic page preferred for each lane (an article links to whichever topic page lists it)
LANE_TOPIC = {"cpp": "cpp", "abn": "abnormal-programming", "perf": "performance",
              "rev": "reverse-engineering", "design": "game-design", "craft": "craft"}
STRINGS = {
    "": {"related": "Ещё по теме", "unit": "мин", "feed": "dalerank — заметки о коде и ремесле",
         "feed_desc": "Статьи о C++, производительности игровых движков и реверс-инжиниринге игр.", "lang": "ru"},
    "en": {"related": "More on this topic", "unit": "min", "feed": "dalerank — notes on code and craft",
           "feed_desc": "Articles on C++, game engine performance and reverse-engineering games.", "lang": "en"},
    "it": {"related": "Altro sull’argomento", "unit": "min", "feed": "dalerank — note su codice e mestiere",
           "feed_desc": "Articoli su C++, prestazioni dei motori di gioco e reverse engineering dei giochi.", "lang": "it"},
}
MONTHS_RU = ["январ", "феврал", "март", "апрел", "ма", "июн", "июл", "август", "сентябр", "октябр", "ноябр", "декабр"]
SHORT_RU = ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]


def text(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def read(path):
    with open(path, encoding="utf-8", newline="") as f:
        return f.read()


def write_if_changed(path, old, new):
    if new != old:
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(new)
        return True
    return False


def reading_min(page_path):
    page = read(page_path)
    m = re.search(r'<article class="prose">(.*?)</article>', page, re.S)
    body = re.sub(r"<pre.*?</pre>", "", m.group(1) if m else "", flags=re.S)
    return max(1, round(len(text(body).split()) / WPM))


def parse_list(lang_dir):
    """Entries of <lang>/articles/index.html, keyed by file name, in list order."""
    list_dir = posixpath.join(lang_dir, "articles") if lang_dir else "articles"
    src = read(os.path.join(ROOT, list_dir, "index.html"))
    out = {}
    for li in re.findall(r"<li>(.*?)</li>", src, re.S):
        m = re.search(r'<a href="([^"]+)">\s*<span class="tag[^"]*">(.*?)</span>\s*<h3>(.*?)</h3>\s*(?:<p>(.*?)</p>)?', li, re.S)
        meta = re.search(r'class="pmeta">(.*?)</div>', li, re.S)
        if not m or not meta:
            continue
        href, tag, title, desc = m.group(1), text(m.group(2)), text(m.group(3)), text(m.group(4) or "")
        spans = [text(s) for s in re.findall(r"<span>(.*?)</span>", meta.group(1))]
        target = posixpath.normpath(posixpath.join(list_dir, href))  # repo-relative
        mins = next((int(re.match(r"\d+", s).group()) for s in spans[1:] if re.match(r"\d+\s*min|\d+\s*мин", s)), None)
        if mins is None:
            mins = reading_min(os.path.join(ROOT, target))
        out[posixpath.basename(href)] = {
            "target": target, "local": target.startswith(list_dir + "/"),
            "lane": LANE.get(tag, "craft"), "tag": tag,
            "title": title, "desc": desc, "date": spans[0], "min": mins,
        }
    return out


def ru_key(date):
    parts = date.lower().split()
    if len(parts) == 2:  # "Апр 2025"
        return (int(parts[1]), SHORT_RU.index(parts[0][:3]), 1)
    d, mon, y = parts
    month = next(i for i, p in enumerate(MONTHS_RU) if mon.startswith(p))
    return (int(y), month, int(d))


def rel(from_dir, target):
    return posixpath.relpath(target, from_dir or ".")


def topic_index(lang_dir):
    """file name -> list of topic slugs whose page lists it."""
    tdir = os.path.join(ROOT, lang_dir, "topics")
    out = {}
    for fn in sorted(os.listdir(tdir)):
        if fn.endswith(".html"):
            for href in re.findall(r'<li><a href="([^"]+)"', read(os.path.join(tdir, fn))):
                out.setdefault(posixpath.basename(href), []).append(fn[:-5])
    return out


# ---------------------------------------------------------------- trace
def build_trace(lang_dir, items, ru, order):
    data = []
    for slug in order:
        a = items.get(slug, ru[slug])
        data.append({"href": rel(lang_dir, a["target"]), "lane": ru[slug]["lane"], "title": a["title"],
                     "date": a["date"], "year": ru_key(ru[slug]["date"])[0], "min": a["min"]})
    home = os.path.join(ROOT, lang_dir, "index.html")
    page = read(home)
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    new, n = re.subn(r'(<script type="application/json" id="trace-data">).*?(</script>)',
                     lambda m: m.group(1) + payload + m.group(2), page, flags=re.S)
    if n != 1:
        sys.exit(f"{home}: trace-data block not found")
    write_if_changed(home, page, new)
    return len(data)


# ---------------------------------------------------------------- article pages
def build_articles(lang_dir, items, ru, order):
    s = STRINGS[lang_dir]
    topics = topic_index(lang_dir)
    pos = {slug: i for i, slug in enumerate(order)}
    changed = 0
    for slug, a in items.items():
        if not a["local"]:
            continue
        path = os.path.join(ROOT, a["target"])
        page = read(path)
        eol = "\r\n" if "\r\n" in page else "\n"
        art_dir = posixpath.dirname(a["target"])
        lane = ru[slug]["lane"]

        # related: nearest articles of the same lane by publication order
        same = [o for o in items if o != slug and ru.get(o, {}).get("lane") == lane and o in pos]
        same.sort(key=lambda o: (abs(pos[o] - pos[slug]), -pos[o]))
        rows = []
        for o in same[:RELATED_N]:
            b = items[o]
            rows.append(f'      <li class="lane-{lane}"><a href="{html.escape(rel(art_dir, b["target"]))}">{html.escape(b["title"], quote=False)}</a>'
                        f'<div class="pmeta"><span>{html.escape(b["date"], quote=False)}</span><span>{b["min"]} {s["unit"]}</span></div></li>')
        block = eol.join(["<!-- related -->", f'    <nav class="related" aria-label="{s["related"]}">',
                          f'      <h2>{s["related"]}</h2>', "      <ul>", *rows, "      </ul>", "    </nav>",
                          "    <!-- /related -->"]) if rows else "<!-- related --><!-- /related -->"
        if "<!-- related -->" in page:
            new = re.sub(r"<!-- related -->.*?<!-- /related -->", lambda m: block, page, count=1, flags=re.S)
        else:
            idx = page.rfind('<a class="backlink" href="index.html">')
            if idx < 0:
                print(f"  skip related (no backlink): {a['target']}")
                new = page
            else:
                new = page[:idx] + block + eol + "    " + page[idx:]

        # topic tag in the article head links to its topic page
        pages = topics.get(slug, [])
        topic = LANE_TOPIC[lane] if LANE_TOPIC[lane] in pages else (pages[0] if pages else None)
        if topic:
            href = rel(art_dir, posixpath.join(lang_dir, "topics", topic + ".html") if lang_dir else "topics/" + topic + ".html")
            new = re.sub(r'(<div class="article-head">\s*)<(?:span|a) class="tag (lane-[a-z]+)"(?: href="[^"]*")?>([^<]*)</(?:span|a)>',
                         lambda m: f'{m.group(1)}<a class="tag {m.group(2)}" href="{href}">{m.group(3)}</a>', new, count=1)
        changed += write_if_changed(path, page, new)
    return changed


# ---------------------------------------------------------------- feeds
def build_feed(lang_dir, items, ru, order):
    s = STRINGS[lang_dir]
    base = SITE + (lang_dir + "/" if lang_dir else "")
    entries = [o for o in reversed(order) if o in items and items[o]["local"]][:FEED_N]
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">', "<channel>",
           f"  <title>{html.escape(s['feed'])}</title>", f"  <link>{base}</link>",
           f"  <description>{html.escape(s['feed_desc'])}</description>", f"  <language>{s['lang']}</language>",
           f'  <atom:link href="{base}feed.xml" rel="self" type="application/rss+xml" />']
    for o in entries:
        a = items[o]
        y, mth, d = ru_key(ru[o]["date"])
        when = format_datetime(datetime(y, mth + 1, d, 9, 0, tzinfo=timezone.utc))
        url = SITE + a["target"]
        out += ["  <item>", f"    <title>{html.escape(a['title'])}</title>", f"    <link>{url}</link>",
                f'    <guid isPermaLink="true">{url}</guid>', f"    <pubDate>{when}</pubDate>",
                f"    <category>{html.escape(a['tag'])}</category>",
                f"    <description>{html.escape(a['desc'])}</description>", "  </item>"]
    out += ["</channel>", "</rss>", ""]
    path = os.path.join(ROOT, lang_dir, "feed.xml")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out))
    return len(entries)


# ---------------------------------------------------------------- sitemap
def build_sitemap():
    urls = []
    for dirpath, dirs, files in os.walk(ROOT):
        rel_dir = os.path.relpath(dirpath, ROOT).replace("\\", "/")
        if rel_dir.split("/")[0] in (".git", ".claude", "assets", "tools"):
            dirs[:] = []
            continue
        for fn in files:
            if not fn.endswith(".html") or fn == "404.html":
                continue
            r = fn if rel_dir == "." else f"{rel_dir}/{fn}"
            if 'name="robots" content="noindex' in read(os.path.join(ROOT, r)):
                continue
            urls.append(SITE + (r[: -len("index.html")] if fn == "index.html" else r))
    urls.sort(key=lambda u: (u.count("/"), u))
    body = "\n".join(f"  <url><loc>{html.escape(u)}</loc></url>" for u in urls)
    with open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8", newline="\n") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + body + "\n</urlset>\n")
    return len(urls)


def main():
    ru = parse_list("")
    # list is newest-first; a stable sort keeps add order within a day
    order = sorted(reversed(list(ru)), key=lambda slug: ru_key(ru[slug]["date"]))
    for lang_dir in LANGS:
        items = ru if not lang_dir else parse_list(lang_dir)
        n = build_trace(lang_dir, items, ru, order)
        c = build_articles(lang_dir, items, ru, order)
        f = build_feed(lang_dir, items, ru, order)
        print(f"{lang_dir or 'ru'}: trace {n} articles, {c} article pages updated, feed {f} items")
    print(f"sitemap: {build_sitemap()} pages")


if __name__ == "__main__":
    main()
