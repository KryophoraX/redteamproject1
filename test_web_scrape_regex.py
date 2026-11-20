import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scrape_gui import build_crawl_kwargs, format_result
from web_scrape_regex import SAMPLE_HTML, crawl, extract, main, write_output


class ExtractTests(unittest.TestCase):
    def test_sample_html(self):
        data = extract(SAMPLE_HTML, base_url="https://example.com")
        self.assertEqual(data["title"], "Example Domain")
        self.assertEqual(data["h1"], "Example Domain")
        self.assertEqual(data["h2"], ["About", "Links"])
        self.assertIn("illustrative examples", data["meta_description"])
        self.assertEqual(data["keywords"], ["example", "domain", "demo"])
        self.assertEqual(data["canonical"], "https://example.com/")
        self.assertEqual(data["og_title"], "Example Domain (OG)")
        self.assertEqual(data["og_url"], "https://example.com/")
        self.assertEqual(data["emails"], ["demo@example.com"])
        self.assertTrue(any("555" in p for p in data["phones"]))
        self.assertIn("https://example.com/relative", data["links"]["resolved"])
        self.assertIn("/relative", data["links"]["relative"])
        self.assertIn("https://example.com/logo.png", data["images"])
        self.assertGreater(data["stats"]["word_count"], 0)
        self.assertGreaterEqual(data["stats"]["phone_count"], 1)

    def test_same_host_and_max_links(self):
        data = extract(
            SAMPLE_HTML,
            base_url="https://example.com",
            max_links=1,
            same_host_only=True,
        )
        self.assertEqual(len(data["links"]["resolved"]), 1)
        self.assertTrue(
            data["links"]["resolved"][0].startswith("https://example.com")
        )


class CrawlTests(unittest.TestCase):
    def test_offline_multi_page(self):
        data = crawl(
            "https://example.com",
            offline=True,
            max_pages=2,
            delay=0,
            timeout=5,
            user_agent="test",
            check_robots=False,
            max_links=None,
            same_host_only=True,
        )
        self.assertIn("pages", data)
        self.assertEqual(data["crawl"]["fetched"], 2)
        titles = {p["title"] for p in data["pages"]}
        self.assertIn("Example Domain", titles)
        self.assertIn("Relative Page", titles)


class OutputTests(unittest.TestCase):
    def test_write_json_csv_md(self):
        data = {"source": "SAMPLE_HTML", **extract(SAMPLE_HTML, base_url="https://example.com")}
        with TemporaryDirectory() as tmp:
            json_path = Path(tmp) / "out.json"
            csv_path = Path(tmp) / "out.csv"
            md_path = Path(tmp) / "out.md"
            write_output(str(json_path), data)
            write_output(str(csv_path), data)
            write_output(str(md_path), data)
            loaded = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(loaded["title"], "Example Domain")
            csv_text = csv_path.read_text(encoding="utf-8")
            self.assertIn("word_count", csv_text)
            self.assertIn("canonical", csv_text)
            self.assertIn("Example Domain", csv_text)
            md_text = md_path.read_text(encoding="utf-8")
            self.assertIn("# Scrape report", md_text)
            self.assertIn("Example Domain", md_text)

    def test_cli_offline_json(self):
        code = main(["--offline", "--json", "--same-host", "--max-links", "2"])
        self.assertEqual(code, 0)

    def test_cli_offline_crawl(self):
        code = main(["--offline", "--json", "--max-pages", "2", "-q"])
        self.assertEqual(code, 0)


class GuiHelperTests(unittest.TestCase):
    def test_build_crawl_kwargs(self):
        kwargs = build_crawl_kwargs(
            url="https://example.com",
            offline=True,
            same_host=True,
            check_robots=True,
            delay="0.5",
            timeout="10",
            max_pages="2",
            max_links="",
            user_agent="",
        )
        self.assertEqual(kwargs["max_pages"], 2)
        self.assertTrue(kwargs["offline"])
        self.assertFalse(kwargs["check_robots"])  # ignored while offline
        self.assertIsNone(kwargs["max_links"])
        data = crawl(**kwargs)
        self.assertEqual(data["crawl"]["fetched"], 2)

    def test_build_crawl_kwargs_bad_number(self):
        with self.assertRaises(ValueError):
            build_crawl_kwargs(
                url="https://example.com",
                offline=True,
                same_host=False,
                check_robots=False,
                delay="nope",
                timeout="15",
                max_pages="1",
                max_links="",
                user_agent="x",
            )

    def test_format_result(self):
        data = crawl(
            "https://example.com",
            offline=True,
            max_pages=1,
            delay=0,
            timeout=5,
            user_agent="test",
            check_robots=False,
            max_links=None,
            same_host_only=False,
        )
        text = format_result(data)
        self.assertIn("Example Domain", text)
        self.assertIn("title:", text)


if __name__ == "__main__":
    unittest.main()
