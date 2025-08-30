# api/generate.py
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from http.server import BaseHTTPRequestHandler

CHAN_URL = "https://ayup.cc/chans/callumfromthecorner/chan.html"
BASE_URL = "https://ayup.cc/chans/callumfromthecorner/"
DONO_VIDS_BASE = "https://ayup.cc/chans/callumfromthecorner/dono-vids/"

def fetch_html(url):
    r = requests.get(url, timeout=30)
    if r.status_code == 404:
        raise FileNotFoundError(f"404 Not Found: {url}")
    r.raise_for_status()
    return r.text

def extract_css(soup):
    head = soup.find("head")
    return "".join(str(tag) for tag in (head.find_all(["style", "link"]) if head else []))

def parse_date(date_str):
    try:
        return datetime.strptime(date_str, "%A %d/%m/%Y %H:%M:%S")
    except Exception:
        return None

def extract_donos_links_with_dates(chan_soup):
    links_with_dates = []
    for table in chan_soup.find_all("table"):
        donos_a = table.find("a", href=True, string=lambda t: t and t.endswith("donos.html"))
        if not donos_a:
            for a in table.find_all("a", href=True):
                if a["href"].endswith("donos.html"):
                    donos_a = a
                    break
        if donos_a:
            date_val = None
            for td in table.find_all("td"):
                if "Date:" in td.get_text():
                    sib = td.find_next_sibling("td")
                    if sib:
                        date_val = sib.get_text(strip=True)
                    break
            if date_val:
                links_with_dates.append({
                    "href": donos_a["href"],
                    "date": date_val,
                    "parsed": parse_date(date_val),
                })
    return links_with_dates

def fix_dono_links(table):
    for a in table.find_all("a", href=True):
        href = a["href"]
        if "dono-vids/" in href:
            fname = href.split("dono-vids/")[-1]
            a["href"] = DONO_VIDS_BASE + fname
    return table

def get_table_from_donos_soup(soup):
    table = soup.find("table")
    return fix_dono_links(table) if table else None

def generate_html_document():
    # 1) Fetch channel index
    chan_html = fetch_html(CHAN_URL)
    chan_soup = BeautifulSoup(chan_html, "html.parser")
    css = extract_css(chan_soup)

    # 2) Find all dono pages and sort by parsed date (newest first)
    all_links = extract_donos_links_with_dates(chan_soup)
    all_links.sort(key=lambda x: x["parsed"] or datetime.min, reverse=True)

    # 3) Build sections (date + table)
    sections = []
    for item in all_links:
        href = item["href"]
        date = item["date"]
        url = href if href.startswith("http") else BASE_URL + href.lstrip("/")
        try:
            html = fetch_html(url)
        except FileNotFoundError:
            continue
        soup = BeautifulSoup(html, "html.parser")
        table = get_table_from_donos_soup(soup)
        if table:
            sections.append({"date": date, "table_html": str(table)})

    # 4) Return a full HTML page (no file saved)
    parts = [
        '<!DOCTYPE html>',
        '<html>',
        '<head>',
        '<meta charset="UTF-8">',
        css,
        '<title>Ayup.cc Donos Archive</title>',
        '</head>',
        '<body>',
        '<h1>Ayup.cc Donos</h1>',
    ]
    for sec in sections:
        parts.append(f"<h2>{sec['date']}</h2>")
        parts.append(sec["table_html"])
    parts.append("</body></html>")
    return "".join(parts)

# Vercel Python serverless handler
class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            html = generate_html_document()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            # Cache the response for 24h in Vercel’s cache/CDN
            self.send_header("Cache-Control", "public, s-maxage=86400, stale-while-revalidate=3600")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(f"Error: {e}".encode("utf-8"))
