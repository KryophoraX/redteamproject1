# Web scrape (regex demo)

Internship demo: fetch a public page and pull a few fields with regular expressions.

## Run

```bash
python3 web_scrape_regex.py
python3 web_scrape_regex.py --offline
python3 web_scrape_regex.py --url https://example.com --json
python3 web_scrape_regex.py --offline -o result.json
python3 web_scrape_regex.py --offline -o result.csv
python3 web_scrape_regex.py --url https://example.com --delay 1 --check-robots
python3 -m unittest test_web_scrape_regex.py
```

If the network fetch fails, the script falls back to built-in sample HTML.

## What it extracts

- `<title>`, first `<h1>`, all `<h2>`s
- meta `description` and `og:title`
- email-looking strings
- absolute / relative `href`s, plus URLs resolved against the page base (deduped)

## Extras in this demo

- `--delay` before fetch
- `--check-robots` naive `robots.txt` read (`User-agent: *` / `Disallow` only)
- `-o` writes `.json` or `.csv`

## Notes

- Regex is fragile for real HTML; prefer BeautifulSoup/lxml for anything serious
- Only scrape sites you are allowed to access
- Still missing vs a full scraper: crawl queue, pagination, per-bot robots parsing
