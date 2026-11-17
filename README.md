# Web scrape (regex demo)

Small internship demo: fetch a public page and pull a few fields with regular expressions.

## Run

```bash
python3 web_scrape_regex.py
```

If the network fetch fails, the script uses built-in sample HTML so the regex path still runs.

## What it does

- Requests `https://example.com` (change `URL` in the script if needed)
- Extracts the page `<title>`
- Collects absolute `http(s)` `href` links

## Notes

- Regex is fragile for real HTML; prefer a parser (e.g. BeautifulSoup) for production use
- Only scrape sites you are allowed to access; respect `robots.txt` and rate limits
