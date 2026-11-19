# Web scrape (regex demo)

Internship demo: fetch a public page and pull a few fields with regular expressions.

## Run

```bash
python3 web_scrape_regex.py
python3 web_scrape_regex.py --offline
python3 web_scrape_regex.py --url https://example.com --json
python3 web_scrape_regex.py --offline -o result.json
python3 web_scrape_regex.py --offline -o result.csv
python3 web_scrape_regex.py --url https://example.com --delay 1 --check-robots --timeout 10
python3 web_scrape_regex.py --offline --same-host --max-links 5 --json
python3 -m unittest test_web_scrape_regex.py
```

If the network fetch fails, the script falls back to built-in sample HTML.

See [UPDATES-2026-11-18.md](UPDATES-2026-11-18.md) for today’s changes.

## What it extracts

- `<title>`, first `<h1>`, all `<h2>`s
- meta `description`, `og:title`, `og:url`
- email-looking strings and `<img src>` (resolved when a base URL is known)
- absolute / relative `href`s, plus URLs resolved against the page base (deduped)
- basic page stats (word/char/link/image counts)

## Extras in this demo

- `--delay` / `--timeout` for polite fetching
- `--check-robots` naive `robots.txt` read (`User-agent: *` / `Disallow` only)
- `--same-host` and `--max-links` to trim link lists
- `-o` writes `.json` or `.csv`; `-q` keeps stdout quiet when writing files
- `--json` for structured stdout

## Notes

- Regex is fragile for real HTML; prefer BeautifulSoup/lxml for anything serious
- Only scrape sites you are allowed to access
- Still missing vs a full scraper: crawl queue, pagination, per-bot robots parsing
- Stdlib only (no third-party packages)
