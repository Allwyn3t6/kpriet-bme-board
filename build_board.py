"""Builds the PUBLIC department board (GitHub Pages).

Public information only: a daily quote, KPRIET website announcements/stories/events and Coimbatore
headlines from public RSS feeds. No internal or personal data from the department app is used.

Usage:  python build_board.py [--out site]
Runs hourly in GitHub Actions (see .github/workflows/board.yml)."""
import argparse
import html
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
try:
    from feed_parsers import parse_kpriet, parse_rss, pick_quote, score_city   # board repo layout
except ImportError:  # running inside the private app repo
    sys.path.insert(0, str(HERE.parent / "app"))
    from feed_parsers import parse_kpriet, parse_rss, pick_quote, score_city

IST = timezone(timedelta(hours=5, minutes=30))
UA = "KPRIET-BME-Public-Board/1.0 (GitHub Pages; read-only)"


def load_config():
    for p in (HERE / "home_feeds.json", HERE.parent / "config" / "home_feeds.json"):
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    raise FileNotFoundError("home_feeds.json not found")


def fetch(url):
    import requests
    r = requests.get(url, headers={"User-Agent": UA}, timeout=20)
    r.raise_for_status()
    return r.text


def collect(cfg, fetcher=fetch, previous=None):
    """Gather public items. On a source failure, keep that source's items from the previous build."""
    previous = previous or {}
    status, data = {}, {"flash": [], "stories": [], "events": [], "city": []}
    try:
        items = parse_kpriet(fetcher(cfg["kpriet"]["home_url"]))
        data["flash"] = [i for i in items if i["kind"] == "kpriet_flash"]
        data["stories"] = [i for i in items if i["kind"] == "kpriet_story"]
        data["events"] = [i for i in items if i["kind"] == "kpriet_event"]
        status["KPRIET"] = "ok"
        if not items:
            raise ValueError("no items parsed")
    except Exception as e:
        status["KPRIET"] = f"kept previous ({type(e).__name__})"
        for k in ("flash", "stories", "events"):
            data[k] = data[k] or previous.get(k, [])
    city_cfg = cfg.get("city", {})
    for feed in city_cfg.get("feeds", []):
        try:
            rows = parse_rss(fetcher(feed["url"]), feed["name"])
            for r in rows:
                r["score"] = score_city(r["title"], city_cfg)
            data["city"] += [r for r in rows if r["score"] >= 0]
            status[feed["name"]] = "ok"
        except Exception as e:
            status[feed["name"]] = f"failed ({type(e).__name__})"
    if not data["city"]:
        data["city"] = previous.get("city", [])
    seen, city = set(), []
    for r in sorted(data["city"], key=lambda r: (-r.get("score", 0), str(r.get("published") or "")), reverse=False):
        key = r["title"].lower()[:80]
        if key not in seen:
            seen.add(key)
            city.append(r)
    data["city"] = sorted(city, key=lambda r: (-r.get("score", 0), str(r.get("published") or "")[::-1]))[: city_cfg.get("show", 6) + 3]
    return data, status


def _jsonable(data):
    def conv(v):
        return v.isoformat() if isinstance(v, (date, datetime)) else v
    return {k: [{kk: conv(vv) for kk, vv in i.items()} for i in v] for k, v in data.items()}


def e(s):
    return html.escape(str(s or ""), quote=True)


def fmt_day(d):
    if isinstance(d, str):
        try:
            d = date.fromisoformat(d)
        except ValueError:
            return None
    return d


def render(cfg, data, now):
    tpl = (HERE / "template.html").read_text(encoding="utf-8")
    q = pick_quote(cfg.get("quotes", []), now.date()) or {"text": "", "author": ""}
    today = now.date()

    ticker = "".join(
        f'<a href="{e(i["url"])}" target="_blank" rel="noopener"><span class="dot"></span>{e(i["title"])}</a>'
        for i in (data["flash"] + data["stories"]))
    stories = "".join(
        f'<a class="story reveal" href="{e(s["url"])}" target="_blank" rel="noopener">'
        f'<span class="chip">{e(fmt_day(s.get("published")).strftime("%d %b") if fmt_day(s.get("published")) else "Story")}</span>'
        f'<span class="story-title">{e(s["title"])}</span><span class="arrow">↗</span></a>'
        for s in data["stories"][:6]) or '<p class="muted">No stories right now.</p>'
    events = []
    for ev in data["events"][:6]:
        d = fmt_day(ev.get("published"))
        if d and d < today:
            continue
        days = (d - today).days if d else None
        when = "today" if days == 0 else (f"in {days} days" if days else "")
        events.append(
            f'<a class="event reveal" href="{e(ev["url"])}" target="_blank" rel="noopener" '
            f'data-date="{d.isoformat() if d else ""}">'
            f'<span class="cal"><b>{d.strftime("%d") if d else "–"}</b><i>{d.strftime("%b %Y") if d else ""}</i></span>'
            f'<span><span class="event-title">{e(ev["title"])}</span><span class="countdown">{e(when)}</span></span></a>')
    events_html = "".join(events) or '<p class="muted">No upcoming events listed on kpriet.ac.in right now.</p>'
    city = "".join(
        f'<a class="headline reveal" href="{e(c["url"])}" target="_blank" rel="noopener">'
        f'<span class="src">{e(c.get("source", ""))}</span><span class="headline-title">{e(c["title"])}</span>'
        f'<span class="muted small">{e(fmt_day(c.get("published")).strftime("%d %b") if fmt_day(c.get("published")) else "")}</span></a>'
        for c in data["city"][: cfg.get("city", {}).get("show", 6)]) or '<p class="muted">Headlines will appear after the next update.</p>'

    repl = {
        "{{QUOTE_TEXT}}": e(q["text"]), "{{QUOTE_AUTHOR}}": e(q["author"]),
        "{{TICKER}}": ticker, "{{STORIES}}": stories, "{{EVENTS}}": events_html, "{{CITY}}": city,
        "{{UPDATED}}": now.strftime("%d %b %Y, %I:%M %p IST"), "{{UPDATED_ISO}}": now.isoformat(),
        "{{TODAY}}": now.strftime("%A, %d %B %Y"), "{{TICKER_SECONDS}}": str(max(35, 7 * (len(data["flash"]) + len(data["stories"])))),
        "{{CITY_LABEL}}": e(cfg.get("city", {}).get("label", "Coimbatore")),
    }
    for k, v in repl.items():
        tpl = tpl.replace(k, v)
    return tpl


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE / "site"))
    args = ap.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cfg = load_config()
    prev_file = out / "data.json"
    previous = {}
    for p in (prev_file, HERE / "data.json"):
        if p.exists():
            try:
                previous = json.loads(p.read_text(encoding="utf-8")).get("items", {})
                break
            except ValueError:
                pass
    data, status = collect(cfg, previous=previous)
    now = datetime.now(IST)
    (out / "index.html").write_text(render(cfg, data, now), encoding="utf-8")
    payload = {"updated": now.isoformat(), "status": status, "items": _jsonable(data),
               "quote": pick_quote(cfg.get("quotes", []), now.date())}
    (out / "data.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / ".nojekyll").write_text("", encoding="utf-8")
    print(json.dumps(status))


if __name__ == "__main__":
    main()
