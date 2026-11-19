import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from web_scrape_regex import SAMPLE_HTML, extract, main, write_output


class ExtractTests(unittest.TestCase):
    def test_sample_html(self):
        data = extract(SAMPLE_HTML, base_url="https://example.com")
        self.assertEqual(data["title"], "Example Domain")
        self.assertEqual(data["h1"], "Example Domain")
        self.assertEqual(data["h2"], ["About", "Links"])
        self.assertIn("illustrative examples", data["meta_description"])
        self.assertEqual(data["og_title"], "Example Domain (OG)")
        self.assertEqual(data["og_url"], "https://example.com/")
        self.assertEqual(data["emails"], ["demo@example.com"])
        self.assertIn("https://example.com/relative", data["links"]["resolved"])
        self.assertIn("/relative", data["links"]["relative"])
        self.assertIn("https://example.com/logo.png", data["images"])
        self.assertGreater(data["stats"]["word_count"], 0)

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


class OutputTests(unittest.TestCase):
    def test_write_json_and_csv(self):
        data = {"source": "SAMPLE_HTML", **extract(SAMPLE_HTML, base_url="https://example.com")}
        with TemporaryDirectory() as tmp:
            json_path = Path(tmp) / "out.json"
            csv_path = Path(tmp) / "out.csv"
            write_output(str(json_path), data)
            write_output(str(csv_path), data)
            loaded = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(loaded["title"], "Example Domain")
            csv_text = csv_path.read_text(encoding="utf-8")
            self.assertIn("word_count", csv_text)
            self.assertIn("Example Domain", csv_text)

    def test_cli_offline_json(self):
        code = main(["--offline", "--json", "--same-host", "--max-links", "2"])
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
