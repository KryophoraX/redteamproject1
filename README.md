# Web scrape (regex demo)

Internship demo: fetch a public page and pull a few fields with regular expressions.

## Run

```bash
python3 web_scrape_regex.py
python3 web_scrape_regex.py --offline
python3 web_scrape_regex.py --url https://example.com --json
python3 web_scrape_regex.py --offline -o result.json
python3 web_scrape_regex.py --offline -o result.csv
python3 web_scrape_regex.py --offline -o report.md
python3 web_scrape_regex.py --url https://example.com --delay 1 --check-robots --timeout 10
python3 web_scrape_regex.py --offline --same-host --max-links 5 --json
python3 web_scrape_regex.py --offline --max-pages 2 --json
python3 scrape_gui.py
# if Homebrew Python lacks Tk:
/usr/bin/python3 scrape_gui.py
python3 -m unittest test_web_scrape_regex.py
```

If the network fetch fails, the script falls back to built-in sample HTML.

GUI (`scrape_gui.py`) is a thin Tkinter wrapper: options form, Run/Clear/Save, human or JSON results. Still stdlib-only. If `python3` has no `_tkinter`, use `/usr/bin/python3` on macOS.

See [UPDATES-2026-11-19.md](UPDATES-2026-11-19.md) for today’s changes.

## What it extracts

- `<title>`, first `<h1>`, all `<h2>`s
- meta `description`, `keywords`, `og:title`, `og:url`, `link rel=canonical`
- email- and phone-looking strings and `<img src>` (resolved when a base URL is known)
- absolute / relative `href`s, plus URLs resolved against the page base (deduped)
- basic page stats (word/char/link/image/email/phone counts)

## Extras in this demo

- `--delay` / `--timeout` / `--user-agent` for polite fetching
- `--check-robots` naive `robots.txt` read (`User-agent: *` / `Disallow` only)
- `--same-host` and `--max-links` to trim link lists
- `--max-pages` tiny same-host BFS crawl (offline uses a 2-page sample graph)
- `-o` writes `.json`, `.csv`, or `.md`; `-q` keeps stdout quiet when writing files
- `--json` for structured stdout
- `scrape_gui.py` — Tkinter UI over the same scrape helpers

## Notes

- Regex is fragile for real HTML; prefer BeautifulSoup/lxml for anything serious
- Only scrape sites you are allowed to access
- Still missing vs a full scraper: pagination detection, per-bot robots parsing, JS rendering
- Stdlib only (no third-party packages)
