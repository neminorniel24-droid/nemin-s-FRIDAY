"""
Headlines. NewsData.io when a key is set, otherwise (or if it fails)
Google News RSS, which needs no key. So the news never comes back empty.
"""
import xml.etree.ElementTree as ET
from urllib.parse import quote_plus

import requests

import config


def _newsdata(topic: str | None, limit: int) -> list[dict]:
    params = {"apikey": config.NEWSDATA_KEY, "country": config.NEWS_COUNTRY, "language": "en"}
    if topic:
        params.pop("country")
        params["q"] = topic
    r = requests.get("https://newsdata.io/api/1/latest", params=params, timeout=8)
    data = r.json()
    if data.get("status") != "success":
        raise RuntimeError(str(data)[:150])
    out = []
    for it in data.get("results", []):
        if it.get("title"):
            out.append({"title": it["title"].strip(), "source": it.get("source_name") or it.get("source_id") or ""})
        if len(out) >= limit:
            break
    return out


def parse_rss(xml_text: str, limit: int) -> list[dict]:
    out = []
    root = ET.fromstring(xml_text)
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        if not title:
            continue
        source = (item.findtext("source") or "").strip()
        if " - " in title and not source:
            title, source = title.rsplit(" - ", 1)
        elif source and title.endswith(" - " + source):
            title = title[: -len(source) - 3]
        out.append({"title": title, "source": source})
        if len(out) >= limit:
            break
    return out


def _rss(topic: str | None, limit: int) -> list[dict]:
    region = f"hl=en-{config.NEWS_COUNTRY.upper()}&gl={config.NEWS_COUNTRY.upper()}&ceid={config.NEWS_COUNTRY.upper()}:en"
    url = (f"https://news.google.com/rss/search?q={quote_plus(topic)}&{region}" if topic
           else f"https://news.google.com/rss?{region}")
    r = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    return parse_rss(r.text, limit)


def headlines(topic: str | None = None, limit: int = 5) -> list[dict]:
    if config.NEWSDATA_KEY:
        try:
            items = _newsdata(topic, limit)
            if items:
                return items
        except Exception:
            pass
    return _rss(topic, limit)
