"""Pure parsers for public news sources (no Flask, no database).

Shared by the app (app/news.py) and the public GitHub Pages board (board/build_board.py)."""
import html as htmllib
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime


def pick_quote(quotes, day):
    """Deterministic quote of the day."""
    return quotes[day.toordinal() % len(quotes)] if quotes else None


# ------------------------------------------------------------------ parsing
def _clean(s):
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def _date(s):
    for fmt in ("%b %d, %Y", "%d %b %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    return None


def parse_kpriet(page):
    """Return list of dicts (kind, title, url, published) from the KPRIET home page HTML."""
    items, seen = [], set()

    def add(kind, title, url, published=None):
        title, url = _clean(title)[:400], htmllib.unescape(url.strip())
        if len(title) < 6 or (kind, url, title) in seen or not url.startswith("http"):
            return
        seen.add((kind, url, title))
        items.append({"kind": kind, "title": title, "url": url.replace(" ", "%20"), "published": published})

    # 1. scrolling announcement marquee
    m = re.search(r'class="marquee-track"(.*?)</div>', page, re.S)
    if m:
        for href, text in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', m.group(1), re.S):
            add("kpriet_flash", text, href)
    # 2. stories (title from link target + date)
    for href, block in re.findall(r'<a href="(https?://[^"]*/stories/\d+/[^"]*)"[^>]*>(.*?)</a>', page, re.S):
        alt = re.search(r'alt="([^"]+)"', block)
        d = re.search(r'pl-card-date.*?<span>\s*([A-Za-z]{3,9} \d{1,2}, \d{4})\s*</span>', block, re.S)
        add("kpriet_story", alt.group(1) if alt else block, href, _date(d.group(1)) if d else None)
    # 3. upcoming happenings / events
    for href, block in re.findall(r'<a href="(https?://[^"]*/happenings/\d+/[^"]*)"[^>]*>(.*?)</a>', page, re.S):
        t = re.search(r'class="pl-event-title"[^>]*>(.*?)</p>', block, re.S)
        mon = re.search(r'pl-date-month">\s*(\w+)', block)
        day = re.search(r'pl-date-day">\s*(\d+)', block)
        yr = re.search(r'pl-date-year">\s*(\d{4})', block)
        pub = _date(f"{mon.group(1)} {day.group(1)}, {yr.group(1)}") if mon and day and yr else None
        if t:
            add("kpriet_event", t.group(1), href, pub)
    return items


def parse_rss(xml_text, source):
    out = []
    root = ET.fromstring(xml_text.encode("utf-8") if isinstance(xml_text, str) else xml_text)
    for it in root.iter("item"):
        title = _clean(it.findtext("title") or "")
        link = (it.findtext("link") or "").strip()
        pub = None
        try:
            pub = parsedate_to_datetime(it.findtext("pubDate") or "").date()
        except (TypeError, ValueError, IndexError):
            pass
        if title and link.startswith("http"):
            out.append({"kind": "city", "title": title[:400], "url": link, "published": pub, "source": source})
    return out


def score_city(title, cfg):
    t = title.lower()
    if any(k in t for k in cfg.get("exclude_keywords", [])):
        return -1
    return sum(1 for k in cfg.get("prefer_keywords", []) if k in t)
