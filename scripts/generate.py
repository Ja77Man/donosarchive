# scripts/generate.py
from __future__ import annotations

from pathlib import Path
from datetime import datetime
from typing import Optional, List

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except Exception:
    ZoneInfo = None

CHAN_URL = "https://ayup.cc/chans/callumfromthecorner/chan.html"
BASE_URL = "https://ayup.cc/chans/callumfromthecorner/"
DONO_VIDS_BASE = "https://ayup.cc/chans/callumfromthecorner/dono-vids/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Nightly-Static-Bot/1.0; +https://vercel.com/)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def fetch_html(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=30)
    if r.status_code == 404:
        raise FileNotFoundError(f"404 Not Found: {url}")
    r.raise_for_status()
    return r.text


def extract_css(soup: BeautifulSoup) -> str:
    head = soup.find("head")
    if not isinstance(head, Tag):
        return ""
    parts: List[str] = []
    for tag in head.find_all(["style", "link"]):
        if isinstance(tag, Tag):
            parts.append(str(tag))
    return "\n".join(parts)


def parse_date(date_str: str) -> Optional[datetime]:
    try:
        return datetime.strptime(date_str, "%A %d/%m/%Y %H:%M:%S")
    except Exception:
        return None


def extract_donos_links_with_dates(chan_soup: BeautifulSoup) -> list[dict]:
    results: list[dict] = []

    for table in chan_soup.find_all("table"):
        if not isinstance(table, Tag):
            continue

        # Find the donos.html link
        donos_a = None
        for a in table.find_all("a"):
            if not isinstance(a, Tag):
                continue
            href = a.get("href")
            if isinstance(href, str) and href.endswith("donos.html"):
                donos_a = a
                break

        if not donos_a:
            continue

        # Find a "Date:" cell and its next sibling
        date_val: Optional[str] = None
        for td in table.find_all("td"):
            if not isinstance(td, Tag):
                continue
            if "Date:" in td.get_text():
                sib = td.find_next_sibling("td")
                if isinstance(sib, Tag):
                    date_val = sib.get_text(strip=True)
                break

        if date_val:
            results.append(
                {
                    "href": donos_a.get("href"),
                    "date": date_val,
                    "parsed": parse_date(date_val),
                }
            )

    return [item for item in results if isinstance(item.get("href"), str)]


def fix_dono_links(table: Tag) -> Tag:
    for a in table.find_all("a"):
        if not isinstance(a, Tag):
            continue
        href = a.get("href")
        if isinstance(href, str) and "dono-vids/" in href:
            fname = href.split("dono-vids/")[-1]
            a["href"] = DONO_VIDS_BASE + fname
    return table


def get_table_from_donos_soup(soup: BeautifulSoup) -> Optional[Tag]:
    el = soup.find("table")
    if isinstance(el, Tag):
        return fix_dono_links(el)
    return None


def build_full_html() -> str:
    # 1) Fetch the channel index
    chan_html = fetch_html(CHAN_URL)
    chan_soup = BeautifulSoup(chan_html, "html.parser")
    css = extract_css(chan_soup)

    # 2) Gather donos pages
    links = extract_donos_links_with_dates(chan_soup)

    # 3) Fetch each donos page and extract its first table
    sections: list[dict] = []
    for item in links:
        href = item.get("href")
        date = item.get("date")
        parsed = item.get("parsed")

        if not isinstance(href, str):
            continue
        url = href if href.startswith("http") else BASE_URL + href.lstrip("/")

        try:
            html = fetch_html(url)
        except FileNotFoundError:
            continue

        soup = BeautifulSoup(html, "html.parser")
        table = get_table_from_donos_soup(soup)
        if isinstance(table, Tag):
            sections.append(
                {
                    "date": str(date),
                    "date_parsed": parsed if isinstance(parsed, datetime) else None,
                    "table_html": str(table),
                }
            )

    # 4) Sort newest → oldest
    sections.sort(
        key=lambda x: x["date_parsed"] or datetime.min,
        reverse=True,
    )

    # 5) Build the HTML page
    if ZoneInfo:
        ts = datetime.now(ZoneInfo("Europe/Malta")).strftime("%Y-%m-%d %H:%M:%S %Z")
    else:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    head = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Ayup.cc Donos Archive</title>
{css}
<style>
  body {{ margin: 1.25rem; font-family: system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; }}
  h1 {{ margin-bottom: .25rem; }}
  .subtitle {{ color: #555; margin-bottom: 1rem; font-size: .95rem; }}
  h2 {{ margin-top: 1.5rem; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: .5rem; }}
  table, th, td {{ border: 1px solid #ddd; }}
  th, td {{ padding: .5rem; vertical-align: top; }}
  a {{ text-decoration: none; }}
</style>
</head>
<body>
<h1>Ayup.cc Donos Archive</h1>
<p class="subtitle">Updated daily • Last update: {ts}</p>
<p class="subtitle">Created by Ja77_Man on twitch</p>
"""

    parts = [head]
    for sec in sections:
        parts.append(f"<h2>{sec['date']}</h2>\n{sec['table_html']}\n")
    parts.append("</body>\n</html>")
    return "".join(parts)


def main() -> None:
    html = build_full_html()
    out_dir = Path("public")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "index.html"
    out_file.write_text(html, encoding="utf-8")
    print(f"Wrote {out_file} ({len(html):,} bytes)")


if __name__ == "__main__":
    main()
