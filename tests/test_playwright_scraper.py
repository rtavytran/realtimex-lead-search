from realtimex_lead_search.lead_search import playwright_scraper
from realtimex_lead_search.lead_search.models import StrategyStep


class FakeLink:
    def __init__(self, href):
        self.href = href

    def get_attribute(self, name):
        return self.href if name == "href" else None


class FakeEl:
    def __init__(self, text):
        self._text = text

    def inner_text(self):
        return self._text


class FakeCard:
    def __init__(self, name, text, href=None, website=None):
        self._name = name
        self._text = text
        self._href = href
        self._website = website

    def inner_text(self):
        return self._text

    def query_selector(self, selector):
        if selector in ["[role='heading']", "h1", "h2", "h3", "div.fontHeadlineSmall", "span.DkEaL"]:
            return FakeEl(self._name)
        if selector in ["a[data-value='Website']", "a[aria-label='Website']", "a:has-text('Website')"] and self._website:
            return FakeLink(self._website)
        if selector in ["a[href*='/maps/place/']", "a"] and self._href:
            return FakeLink(self._href)
        return None


class FakePage:
    def __init__(self, cards, html="body"):
        self.cards = cards
        self._html = html
        self.last_url = None
        self.screenshot_path = None

    def goto(self, url, timeout=None):
        self.last_url = url

    def wait_for_selector(self, selector, timeout=None):
        return None

    def wait_for_timeout(self, ms):
        return None

    def inner_text(self, selector):
        return self._html

    def content(self):
        return self._html

    def query_selector_all(self, selector):
        return self.cards

    def screenshot(self, path=None, full_page=None):
        self.screenshot_path = path


class FakeContext:
    def __init__(self, page):
        self.page = page
        self.headers = None
        self.viewport = None

    def new_page(self):
        return self.page

    def set_extra_http_headers(self, headers):
        self.headers = headers

    def set_viewport_size(self, viewport):
        self.viewport = viewport


class FakeBrowser:
    def __init__(self, page):
        self.page = page

    def new_context(self, *args, **kwargs):
        return FakeContext(self.page)

    def close(self):
        return None


def test_scrape_filters_sponsored_and_parses_phone():
    cards = [
        FakeCard("Sponsored", "Sponsored listing", href="https://maps.example/sponsored"),
        FakeCard(
            "Real Shop",
            "Real Shop\n4.9(10)\nCategory: Mobile Repair\nAddress: 123 Main St\nCall +1 555-111-2222",
            href="https://maps.example/real",
            website="https://realshop.example.com",
        ),
    ]
    page = FakePage(cards, html="<html>body</html>")
    browser_factory = lambda: FakeBrowser(page)
    steps = [StrategyStep(source="google_maps", query="q")]

    artifacts = playwright_scraper.scrape_steps(
        steps, anti_detection_config={"enabled": True}, browser_factory=browser_factory
    )

    assert len(artifacts) == 1
    art = artifacts[0]
    assert art.status == "ok"
    assert len(art.json_blob) == 1
    entry = art.json_blob[0]
    assert entry["name"] == "Real Shop"
    assert entry["phone"] == "+1 555-111-2222"
    assert entry["website"] == "https://realshop.example.com"
    assert entry["address"] == "123 Main St"
    assert entry["category"] == "Mobile Repair"
    assert "screenshot" not in (art.screenshot_path or "")


def test_scrape_captcha_detection_marks_error():
    page = FakePage(cards=[], html="Please solve the captcha to continue")
    browser_factory = lambda: FakeBrowser(page)
    steps = [StrategyStep(source="google_maps", query="q")]

    artifacts = playwright_scraper.scrape_steps(
        steps,
        anti_detection_config={"enabled": True, "max_retries": 1},
        browser_factory=browser_factory,
    )

    assert len(artifacts) == 1
    art = artifacts[0]
    assert art.status == "error"
    assert "captcha" in (art.error or "").lower()
