"""Offline self-check for agentiqa.checks. Run: python test_checks.py"""

from agentiqa import checks

SAMPLE_HTML = """<html><head>
<meta property="og:title" content="Test Store">
<meta property="og:description" content="Great stuff">
<script type="application/ld+json">
{"@context": "https://schema.org", "@type": "Product",
 "name": "Widget", "offers": {"@type": "Offer", "price": "9.99"}}
</script>
</head><body>hello</body></html>"""

BAD_HTML = "<html><head><title>nothing</title></head><body></body></html>"

ROBOTS_ALLOW = "User-agent: *\nAllow: /\n"
ROBOTS_BLOCK = "User-agent: ChatGPT-User\nDisallow: /\n\nUser-agent: *\nAllow: /\n"

# structured data
assert checks.check_structured_data(SAMPLE_HTML)["passed"]
assert not checks.check_structured_data(BAD_HTML)["passed"]

# @graph wrapper variant
graph_html = '<script type="application/ld+json">{"@graph": [{"@type": "Product"}]}</script>'
assert checks.check_structured_data(graph_html)["passed"]

# malformed JSON-LD doesn't crash
broken = '<script type="application/ld+json">{not json}</script>'
assert not checks.check_structured_data(broken)["passed"]

# opengraph
assert checks.check_opengraph(SAMPLE_HTML)["passed"]
assert not checks.check_opengraph(BAD_HTML)["passed"]

# robots
assert checks.check_robots(ROBOTS_ALLOW, "https://example.com/")["passed"]
r = checks.check_robots(ROBOTS_BLOCK, "https://example.com/")
assert not r["passed"] and "ChatGPT-User: BLOCKED" in r["detail"]

# payment field guard (import without playwright installed would fail — guard)
try:
    from agentiqa.shopper import PAYMENT_FIELD_RE, fingerprint
    for s in ("card_number", "cc-exp", "cvv", "security-code", "cardExpiry"):
        assert PAYMENT_FIELD_RE.search(s), s
    assert not PAYMENT_FIELD_RE.search("email_address")
    assert not PAYMENT_FIELD_RE.search("discount_code")

    # silent-failure detection: a click that changes nothing must produce an identical fingerprint
    class FakePage:
        def __init__(self, url, body):
            self.url, self._body = url, body

        def inner_text(self, _sel):
            return self._body

    same = fingerprint(FakePage("https://s/", "Cart (0)"))
    assert fingerprint(FakePage("https://s/", "Cart (0)")) == same       # nothing happened
    assert fingerprint(FakePage("https://s/", "Cart (1)")) != same       # cart badge updated
    assert fingerprint(FakePage("https://s/cart", "Cart (0)")) != same   # navigated
    # real case: a dead "add to basket" reloads the same page with a bare '?' appended
    assert fingerprint(FakePage("https://s/?", "Cart (0)")) == same
except ImportError:
    print("(skipped payment-guard test: playwright/anthropic not installed)")

# batch aggregate (pure, stdlib-only import)
from agentiqa import batch

_rows = [
    {"milestones": ["product_found", "added_to_cart", "checkout_reached"]},
    {"milestones": ["product_found"]},
    {"milestones": []},
    {"error": "boom"},  # excluded from percentages
]
_agg = batch.aggregate(_rows)
assert _agg["tested"] == 3 and _agg["errored"] == 1
assert _agg["reached_checkout"] == 1 and _agg["failed_checkout"] == 2
assert _agg["pct_failed"] == 67 and _agg["pct_reached"] == 33
assert _agg["pct_product"] == 67  # 2 of 3 reached a product
assert batch.furthest(["product_found", "added_to_cart"]) == "added_to_cart"
assert batch.furthest([]) == "none"
assert batch.aggregate([])["pct_failed"] == 0  # no divide-by-zero on empty

print("all checks passed")
