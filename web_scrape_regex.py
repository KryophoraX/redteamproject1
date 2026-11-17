"""
Minimal demo: fetch a public page and pull a few fields with regex.

~1/4 of a full scraper — only title + same-site links.
You still need: robots.txt checks, rate limiting, pagination,
structured output, and a real HTML parser for anything serious.
"""

from __future__ import annotations

import re
import urllib.request

# Public page you are allowed to fetch — or leave as-is and use SAMPLE_HTML offline
URL = "https://example.com"

SAMPLE_HTML = """
<html>
  <head><title>Example Domain</title></head>
  <body>
    <h1>Example Domain</h1>
    <p><a href="https://www.iana.org/domains/example">More information...</a></p>
    <a href="/relative">ignored by this demo</a>
  </body>
</html>
"""

TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
# Very naive: only absolute http(s) hrefs — extend this yourself
HREF_RE = re.compile(
    r"""href\s*=\s*["'](https?://[^"']+)["']""",
    re.IGNORECASE,
)


def fetch(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "regex-scrape-demo/0.1 (internship project)"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8", errors="replace")


def extract(html: str) -> dict:
    title_match = TITLE_RE.search(html)
    title = title_match.group(1).strip() if title_match else None
    links = HREF_RE.findall(html)
    return {"title": title, "links": links}


def main() -> None:
    try:
        html = fetch(URL)
        source = URL
    except Exception as exc:  # network / DNS / TLS — still show regex path
        print(f"fetch failed ({exc}); using SAMPLE_HTML")
        html = SAMPLE_HTML
        source = "SAMPLE_HTML"

    data = extract(html)
    print("source:", source)
    print("title:", data["title"])
    print("links found:", len(data["links"]))
    for link in data["links"][:10]:
        print(" -", link)
    # TODO (rest of the project):
    # - parse more fields (headings, meta description) with extra regexes
    # - respect robots.txt + add delays
    # - write results to CSV/JSON
    # - prefer BeautifulSoup/lxml instead of regex for real HTML


if __name__ == "__main__":
    main()
