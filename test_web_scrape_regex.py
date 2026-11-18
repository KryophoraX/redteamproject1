import unittest

from web_scrape_regex import SAMPLE_HTML, extract


class ExtractTests(unittest.TestCase):
    def test_sample_html(self):
        data = extract(SAMPLE_HTML, base_url="https://example.com")
        self.assertEqual(data["title"], "Example Domain")
        self.assertEqual(data["h1"], "Example Domain")
        self.assertEqual(data["h2"], ["About", "Links"])
        self.assertIn("illustrative examples", data["meta_description"])
        self.assertEqual(data["og_title"], "Example Domain (OG)")
        self.assertEqual(data["emails"], ["demo@example.com"])
        self.assertIn("https://example.com/relative", data["links"]["resolved"])
        self.assertIn("/relative", data["links"]["relative"])


if __name__ == "__main__":
    unittest.main()
