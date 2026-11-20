"""
Demo: fetch a public page and extract a few fields with regex.

Still incomplete vs a real scraper — no pagination heuristics,
JS rendering, or a proper HTML parser.
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
USER_AGENT = "regex-scrape-demo/0.5 (internship project)"

SAMPLE_HTML = """
<html>
  <head>
    <title>Example Domain</title>
    <meta name="description" content="This domain is for use in illustrative examples." />
    <meta name="keywords" content="example, domain, demo" />
    <meta property="og:title" content="Example Domain (OG)" />
    <meta property="og:url" content="https://example.com/" />
    <link rel="canonical" href="https://example.com/" />
  </head>
  <body>
    <h1>Example Domain</h1>
    <h2>About</h2>
    <p>Contact: demo@example.com · Phone: 555-010-0199</p>
    <h2>Links</h2>
    <p><a href="https://www.iana.org/domains/example">More information...</a></p>
    <a href="/relative">relative link</a>
    <a href="https://example.com/again">duplicate absolute</a>
    <img src="/logo.png" alt="Logo" />
  </body>
</html>
"""

SAMPLE_HTML_RELATIVE = """
<html>
  <head>
    <title>Relative Page</title>
    <link rel="canonical" href="https://example.com/relative" />
  </head>
  <body>
    <h1>Relative Page</h1>
    <p>Offline crawl leaf. Back to <a href="/">home</a>.</p>
  </body>
</html>
"""

# Tiny offline graph so --max-pages can be demoed without the network.
SAMPLE_PAGES = {
    "https://example.com": SAMPLE_HTML,
    "https://example.com/": SAMPLE_HTML,
    "https://example.com/relative": SAMPLE_HTML_RELATIVE,
    "https://example.com/again": SAMPLE_HTML,
}

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
META_KEYWORDS_RE = re.compile(
    r"""<meta\b(?=[^>]*\bname\s*=\s*["']keywords["'])[^>]*\bcontent\s*=\s*["']([^"']*)["']""",
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
CANONICAL_RE = re.compile(
    r"""<link\b(?=[^>]*\brel\s*=\s*["']canonical["'])[^>]*\bhref\s*=\s*["']([^"']+)["']""",
    re.IGNORECASE,
)
HREF_RE = re.compile(r"""href\s*=\s*["']([^"'#]+)["']""", re.IGNORECASE)
IMG_SRC_RE = re.compile(r"""<img\b[^>]*\bsrc\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_RE = re.compile(
    r"(?<!\w)(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}(?!\w)"
)
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


def normalize_url(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    path = parts.path or "/"
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc.lower(), path, parts.query, ""))


def fetch(url: str, timeout: float = 15.0, user_agent: str = USER_AGENT) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


def robots_allows(
    url: str, timeout: float = 10.0, user_agent: str = USER_AGENT
) -> tuple[bool, str]:
    """Very small robots.txt check for this demo (User-agent: * only)."""
    parts = urllib.parse.urlsplit(url)
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    path = parts.path or "/"
    try:
        text = fetch(robots_url, timeout=timeout, user_agent=user_agent)
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
    keywords_m = META_KEYWORDS_RE.search(html)
    og_m = OG_TITLE_RE.search(html)
    og_url_m = OG_URL_RE.search(html)
    canonical_m = CANONICAL_RE.search(html)

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

    emails = unique_preserve(EMAIL_RE.findall(html))
    phones = unique_preserve(PHONE_RE.findall(html))
    text = visible_text(html)
    words = WORD_RE.findall(text)
    keywords_raw = keywords_m.group(1).strip() if keywords_m else None
    keywords = (
        [k.strip() for k in keywords_raw.split(",") if k.strip()] if keywords_raw else []
    )

    return {
        "title": strip_tags(title_m.group(1)) if title_m else None,
        "h1": strip_tags(h1_m.group(1)) if h1_m else None,
        "h2": [strip_tags(m) for m in H2_RE.findall(html)],
        "meta_description": meta_m.group(1).strip() if meta_m else None,
        "keywords": keywords,
        "canonical": canonical_m.group(1).strip() if canonical_m else None,
        "og_title": og_m.group(1).strip() if og_m else None,
        "og_url": og_url_m.group(1).strip() if og_url_m else None,
        "emails": emails,
        "phones": phones,
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
            "email_count": len(emails),
            "phone_count": len(phones),
        },
    }


def page_row(data: dict) -> dict:
    stats = data.get("stats") or {}
    return {
        "source": data.get("source"),
        "title": data.get("title"),
        "h1": data.get("h1"),
        "h2": " | ".join(data.get("h2") or []),
        "meta_description": data.get("meta_description"),
        "keywords": " | ".join(data.get("keywords") or []),
        "canonical": data.get("canonical"),
        "og_title": data.get("og_title"),
        "og_url": data.get("og_url"),
        "emails": " | ".join(data.get("emails") or []),
        "phones": " | ".join(data.get("phones") or []),
        "images": " | ".join(data.get("images") or []),
        "absolute_links": " | ".join(data.get("links", {}).get("absolute") or []),
        "relative_links": " | ".join(data.get("links", {}).get("relative") or []),
        "resolved_links": " | ".join(data.get("links", {}).get("resolved") or []),
        "word_count": stats.get("word_count"),
        "char_count": stats.get("char_count"),
        "link_count": stats.get("link_count"),
        "image_count": stats.get("image_count"),
        "phone_count": stats.get("phone_count"),
    }


def pages_from_result(data: dict) -> list[dict]:
    if "pages" in data:
        return list(data["pages"])
    return [data]


def write_markdown(path: Path, data: dict) -> None:
    lines = ["# Scrape report", ""]
    crawl = data.get("crawl")
    if crawl:
        lines.append(
            f"Crawled **{crawl.get('fetched', 0)}** page(s)"
            f" (max {crawl.get('max_pages')})."
        )
        lines.append("")
    for page in pages_from_result(data):
        lines.append(f"## {page.get('title') or '(no title)'}")
        lines.append("")
        lines.append(f"- source: `{page.get('source')}`")
        if page.get("canonical"):
            lines.append(f"- canonical: `{page['canonical']}`")
        if page.get("h1"):
            lines.append(f"- h1: {page['h1']}")
        if page.get("meta_description"):
            lines.append(f"- meta: {page['meta_description']}")
        if page.get("keywords"):
            lines.append(f"- keywords: {', '.join(page['keywords'])}")
        if page.get("emails"):
            lines.append(f"- emails: {', '.join(page['emails'])}")
        if page.get("phones"):
            lines.append(f"- phones: {', '.join(page['phones'])}")
        stats = page.get("stats") or {}
        if stats:
            lines.append(
                f"- stats: {stats.get('word_count', 0)} words, "
                f"{stats.get('link_count', 0)} links, "
                f"{stats.get('image_count', 0)} images"
            )
        resolved = (page.get("links") or {}).get("resolved") or []
        if resolved:
            lines.append("- resolved links:")
            for link in resolved[:20]:
                lines.append(f"  - {link}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_output(path: str, data: dict) -> None:
    out = Path(path)
    suffix = out.suffix.lower()
    if suffix == ".csv":
        rows = [page_row(p) for p in pages_from_result(data)]
        with out.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
    elif suffix == ".md":
        write_markdown(out, data)
    else:
        with out.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fetch a page and scrape a few fields with regex.")
    p.add_argument("--url", default=DEFAULT_URL, help="URL to fetch (default: example.com)")
    p.add_argument("--offline", action="store_true", help="Skip network; use SAMPLE_HTML")
    p.add_argument("--json", action="store_true", help="Print result as JSON")
    p.add_argument("-o", "--output", help="Write result to .json, .csv, or .md")
    p.add_argument("--delay", type=float, default=0.0, help="Seconds to wait before each fetch")
    p.add_argument("--timeout", type=float, default=15.0, help="HTTP timeout in seconds")
    p.add_argument("--max-links", type=int, default=None, help="Cap each link list length")
    p.add_argument(
        "--max-pages",
        type=int,
        default=1,
        help="Tiny same-host BFS crawl depth budget (default: 1 = single page)",
    )
    p.add_argument(
        "--same-host",
        action="store_true",
        help="Keep only resolved links on the same host as --url",
    )
    p.add_argument(
        "--user-agent",
        default=USER_AGENT,
        help="HTTP User-Agent string",
    )
    p.add_argument(
        "--check-robots",
        action="store_true",
        help="Naive robots.txt check before fetching (network only)",
    )
    p.add_argument("-q", "--quiet", action="store_true", help="Suppress human-readable stdout")
    return p.parse_args(argv)


def print_human(data: dict, link_preview: int = 15) -> None:
    pages = pages_from_result(data)
    crawl = data.get("crawl")
    if crawl and len(pages) > 1:
        print(f"crawl: fetched {crawl['fetched']} / max {crawl['max_pages']}")
        print()
    for i, page in enumerate(pages):
        if len(pages) > 1:
            print(f"--- page {i + 1}/{len(pages)} ---")
        print("source:", page["source"])
        print("title:", page["title"])
        print("h1:", page["h1"])
        print("h2:", ", ".join(page["h2"]) or "(none)")
        print("meta:", page["meta_description"])
        print("keywords:", ", ".join(page.get("keywords") or []) or "(none)")
        print("canonical:", page.get("canonical"))
        print("og:title:", page["og_title"])
        print("og:url:", page["og_url"])
        print("emails:", ", ".join(page["emails"]) or "(none)")
        print("phones:", ", ".join(page.get("phones") or []) or "(none)")
        print("images:", ", ".join(page["images"][:link_preview]) or "(none)")
        stats = page["stats"]
        print(
            "stats:",
            f"{stats['word_count']} words,",
            f"{stats['char_count']} chars,",
            f"{stats['link_count']} links,",
            f"{stats['image_count']} images,",
            f"{stats.get('phone_count', 0)} phones",
        )
        for kind in ("absolute", "relative", "resolved"):
            links = page["links"][kind]
            print(f"{kind} links ({len(links)}):")
            for link in links[:link_preview]:
                print(" -", link)
        if i < len(pages) - 1:
            print()


def load_html(
    url: str,
    *,
    offline: bool,
    timeout: float,
    user_agent: str,
    check_robots: bool,
) -> tuple[str, str]:
    """Return (html, source_label)."""
    if offline:
        key = normalize_url(url)
        # Also try without trailing-slash variants already covered in SAMPLE_PAGES.
        html = SAMPLE_PAGES.get(key) or SAMPLE_PAGES.get(url) or SAMPLE_HTML
        return html, "SAMPLE_HTML" if html is SAMPLE_HTML and key not in SAMPLE_PAGES else key

    if check_robots:
        allowed, reason = robots_allows(url, timeout=timeout, user_agent=user_agent)
        print(f"robots ({url}): {reason}", file=sys.stderr)
        if not allowed:
            raise PermissionError(reason)
    try:
        return fetch(url, timeout=timeout, user_agent=user_agent), url
    except Exception as exc:
        print(f"fetch failed for {url} ({exc})", file=sys.stderr)
        raise


def crawl(
    start_url: str,
    *,
    offline: bool,
    max_pages: int,
    delay: float,
    timeout: float,
    user_agent: str,
    check_robots: bool,
    max_links: int | None,
    same_host_only: bool,
) -> dict:
    """BFS same-host crawl capped by max_pages (demo-sized)."""
    seed = normalize_url(start_url)
    queue = [seed]
    seen: set[str] = set()
    pages: list[dict] = []

    while queue and len(pages) < max_pages:
        url = queue.pop(0)
        key = normalize_url(url)
        if key in seen:
            continue
        seen.add(key)

        if delay > 0 and not offline and pages:
            time.sleep(delay)
        elif delay > 0 and not offline and not pages:
            time.sleep(delay)

        try:
            html, source = load_html(
                url,
                offline=offline,
                timeout=timeout,
                user_agent=user_agent,
                check_robots=check_robots and not offline,
            )
        except PermissionError:
            return {"error": "blocked by robots.txt", "source": url}
        except Exception:
            if not pages:
                # First page fallback keeps the offline demo usable.
                html, source = SAMPLE_HTML, "SAMPLE_HTML"
                key = normalize_url(DEFAULT_URL)
            else:
                continue

        base = DEFAULT_URL if source == "SAMPLE_HTML" else url
        page = {
            "source": source,
            **extract(
                html,
                base_url=base,
                max_links=max_links,
                same_host_only=same_host_only or max_pages > 1,
            ),
        }
        pages.append(page)

        for link in page["links"]["resolved"]:
            n = normalize_url(link)
            if n in seen:
                continue
            if same_host(n, seed):
                queue.append(n)

    if len(pages) == 1 and max_pages == 1:
        return pages[0]

    return {
        "crawl": {
            "seed": seed,
            "fetched": len(pages),
            "max_pages": max_pages,
            "queued_remaining": len(queue),
        },
        "pages": pages,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.max_pages < 1:
        print("--max-pages must be >= 1", file=sys.stderr)
        return 2

    data = crawl(
        args.url,
        offline=args.offline,
        max_pages=args.max_pages,
        delay=args.delay,
        timeout=args.timeout,
        user_agent=args.user_agent,
        check_robots=args.check_robots,
        max_links=args.max_links,
        same_host_only=args.same_host,
    )

    if data.get("error"):
        print(data["error"], file=sys.stderr)
        return 2

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
