"""
Demo: fetch a public page and extract a few fields with regex.

Still incomplete vs a real scraper — no crawl queue, pagination,
or a proper HTML parser.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from html import unescape
from pathlib import Path

DEFAULT_URL = "https://example.com"
USER_AGENT = "regex-scrape-demo/0.4 (internship project)"

SAMPLE_HTML = """
<html>
  <head>
    <title>Example Domain</title>
    <meta name="description" content="This domain is for use in illustrative examples." />
    <meta property="og:title" content="Example Domain (OG)" />
    <meta property="og:url" content="https://example.com/" />
  </head>
  <body>
    <h1>Example Domain</h1>
    <h2>About</h2>
    <p>Contact: demo@example.com</p>
    <h2>Links</h2>
    <p><a href="https://www.iana.org/domains/example">More information...</a></p>
    <a href="/relative">relative link</a>
    <a href="https://example.com/again">duplicate absolute</a>
    <img src="/logo.png" alt="Logo" />
  </body>
</html>
"""

TAG_RE = re.compile(r"<[^>]+>")
SCRIPT_STYLE_RE = re.compile(
    r"<(script|style)\b[^>]*>.*?</\1>",
    re.IGNORECASE | re.DOTALL,
)
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.IGNORECASE | re.DOTALL)
H2_RE = re.compile(r"<h2[^>]*>(.*?)</h2>", re.IGNORECASE | re.DOTALL)
META_DESC_RE = re.compile(
    r"""<meta\b(?=[^>]*\bname\s*=\s*["']description["'])[^>]*\bcontent\s*=\s*["']([^"']*)["']""",
    re.IGNORECASE,
)
OG_TITLE_RE = re.compile(
    r"""<meta\b(?=[^>]*\bproperty\s*=\s*["']og:title["'])[^>]*\bcontent\s*=\s*["']([^"']*)["']""",
    re.IGNORECASE,
)
OG_URL_RE = re.compile(
    r"""<meta\b(?=[^>]*\bproperty\s*=\s*["']og:url["'])[^>]*\bcontent\s*=\s*["']([^"']*)["']""",
    re.IGNORECASE,
)
HREF_RE = re.compile(r"""href\s*=\s*["']([^"'#]+)["']""", re.IGNORECASE)
IMG_SRC_RE = re.compile(r"""<img\b[^>]*\bsrc\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
DISALLOW_RE = re.compile(r"(?m)^\s*Disallow\s*:\s*(\S*)")
WORD_RE = re.compile(r"[A-Za-z0-9']+")


def strip_tags(text: str) -> str:
    return unescape(TAG_RE.sub("", text)).strip()


def unique_preserve(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def visible_text(html: str) -> str:
    cleaned = SCRIPT_STYLE_RE.sub(" ", html)
    return strip_tags(cleaned)


def fetch(url: str, timeout: float = 15.0) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


def robots_allows(url: str, timeout: float = 10.0) -> tuple[bool, str]:
    """Very small robots.txt check for this demo (User-agent: * only)."""
    parts = urllib.parse.urlsplit(url)
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    path = parts.path or "/"
    try:
        text = fetch(robots_url, timeout=timeout)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return True, "no robots.txt (404) — treating as allowed"
        return True, f"robots.txt HTTP {exc.code} — treating as allowed"
    except Exception as exc:
        return True, f"robots.txt unread ({exc}) — treating as allowed"

    disallows = DISALLOW_RE.findall(text)
    for rule in disallows:
        if rule == "":
            continue
        if path.startswith(rule):
            return False, f"Disallow: {rule} matches {path}"
    return True, "allowed under a naive User-agent: * read"


def same_host(url: str, base_url: str) -> bool:
    return urllib.parse.urlsplit(url).netloc.lower() == urllib.parse.urlsplit(base_url).netloc.lower()


def extract(
    html: str,
    base_url: str | None = None,
    *,
    max_links: int | None = None,
    same_host_only: bool = False,
) -> dict:
    title_m = TITLE_RE.search(html)
    h1_m = H1_RE.search(html)
    meta_m = META_DESC_RE.search(html)
    og_m = OG_TITLE_RE.search(html)
    og_url_m = OG_URL_RE.search(html)

    hrefs = unique_preserve(HREF_RE.findall(html))
    absolute = [h for h in hrefs if re.match(r"https?://", h, re.IGNORECASE)]
    relative = [h for h in hrefs if not re.match(r"https?://", h, re.IGNORECASE)]

    resolved: list[str] = []
    if base_url:
        resolved = unique_preserve([urllib.parse.urljoin(base_url, h) for h in hrefs])
        if same_host_only:
            resolved = [u for u in resolved if same_host(u, base_url)]

    images = unique_preserve(IMG_SRC_RE.findall(html))
    if base_url:
        images = unique_preserve([urllib.parse.urljoin(base_url, src) for src in images])

    if max_links is not None:
        absolute = absolute[:max_links]
        relative = relative[:max_links]
        resolved = resolved[:max_links]

    text = visible_text(html)
    words = WORD_RE.findall(text)

    return {
        "title": strip_tags(title_m.group(1)) if title_m else None,
        "h1": strip_tags(h1_m.group(1)) if h1_m else None,
        "h2": [strip_tags(m) for m in H2_RE.findall(html)],
        "meta_description": meta_m.group(1).strip() if meta_m else None,
        "og_title": og_m.group(1).strip() if og_m else None,
        "og_url": og_url_m.group(1).strip() if og_url_m else None,
        "emails": unique_preserve(EMAIL_RE.findall(html)),
        "images": images,
        "links": {
            "absolute": absolute,
            "relative": relative,
            "resolved": resolved,
        },
        "stats": {
            "char_count": len(text),
            "word_count": len(words),
            "link_count": len(hrefs),
            "image_count": len(images),
            "email_count": len(unique_preserve(EMAIL_RE.findall(html))),
        },
    }


def write_output(path: str, data: dict) -> None:
    out = Path(path)
    if out.suffix.lower() == ".csv":
        stats = data.get("stats") or {}
        row = {
            "source": data.get("source"),
            "title": data.get("title"),
            "h1": data.get("h1"),
            "h2": " | ".join(data.get("h2") or []),
            "meta_description": data.get("meta_description"),
            "og_title": data.get("og_title"),
            "og_url": data.get("og_url"),
            "emails": " | ".join(data.get("emails") or []),
            "images": " | ".join(data.get("images") or []),
            "absolute_links": " | ".join(data.get("links", {}).get("absolute") or []),
            "relative_links": " | ".join(data.get("links", {}).get("relative") or []),
            "resolved_links": " | ".join(data.get("links", {}).get("resolved") or []),
            "word_count": stats.get("word_count"),
            "char_count": stats.get("char_count"),
            "link_count": stats.get("link_count"),
            "image_count": stats.get("image_count"),
        }
        with out.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(row.keys()))
            writer.writeheader()
            writer.writerow(row)
    else:
        with out.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fetch a page and scrape a few fields with regex.")
    p.add_argument("--url", default=DEFAULT_URL, help="URL to fetch (default: example.com)")
    p.add_argument("--offline", action="store_true", help="Skip network; use SAMPLE_HTML")
    p.add_argument("--json", action="store_true", help="Print result as JSON")
    p.add_argument("-o", "--output", help="Write result to .json or .csv")
    p.add_argument("--delay", type=float, default=0.0, help="Seconds to wait before fetch")
    p.add_argument("--timeout", type=float, default=15.0, help="HTTP timeout in seconds")
    p.add_argument("--max-links", type=int, default=None, help="Cap each link list length")
    p.add_argument(
        "--same-host",
        action="store_true",
        help="Keep only resolved links on the same host as --url",
    )
    p.add_argument(
        "--check-robots",
        action="store_true",
        help="Naive robots.txt check before fetching (network only)",
    )
    p.add_argument("-q", "--quiet", action="store_true", help="Suppress human-readable stdout")
    return p.parse_args(argv)


def print_human(data: dict, link_preview: int = 15) -> None:
    print("source:", data["source"])
    print("title:", data["title"])
    print("h1:", data["h1"])
    print("h2:", ", ".join(data["h2"]) or "(none)")
    print("meta:", data["meta_description"])
    print("og:title:", data["og_title"])
    print("og:url:", data["og_url"])
    print("emails:", ", ".join(data["emails"]) or "(none)")
    print("images:", ", ".join(data["images"][:link_preview]) or "(none)")
    stats = data["stats"]
    print(
        "stats:",
        f"{stats['word_count']} words,",
        f"{stats['char_count']} chars,",
        f"{stats['link_count']} links,",
        f"{stats['image_count']} images",
    )
    for kind in ("absolute", "relative", "resolved"):
        links = data["links"][kind]
        print(f"{kind} links ({len(links)}):")
        for link in links[:link_preview]:
            print(" -", link)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.delay > 0 and not args.offline:
        time.sleep(args.delay)

    base_url = args.url
    if args.offline:
        html = SAMPLE_HTML
        source = "SAMPLE_HTML"
        base_url = DEFAULT_URL
    else:
        if args.check_robots:
            allowed, reason = robots_allows(args.url, timeout=args.timeout)
            print(f"robots: {reason}", file=sys.stderr)
            if not allowed:
                print("blocked by robots.txt — exiting", file=sys.stderr)
                return 2
        try:
            html = fetch(args.url, timeout=args.timeout)
            source = args.url
        except Exception as exc:
            print(f"fetch failed ({exc}); using SAMPLE_HTML", file=sys.stderr)
            html = SAMPLE_HTML
            source = "SAMPLE_HTML"
            base_url = DEFAULT_URL

    data = {
        "source": source,
        **extract(
            html,
            base_url=base_url,
            max_links=args.max_links,
            same_host_only=args.same_host,
        ),
    }

    if args.output:
        write_output(args.output, data)
        print(f"wrote {args.output}", file=sys.stderr)

    if args.json:
        print(json.dumps(data, indent=2))
    elif not args.quiet and not args.output:
        print_human(data)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
