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
    from agentiqa.shopper import PAYMENT_FIELD_RE
    for s in ("card_number", "cc-exp", "cvv", "security-code", "cardExpiry"):
        assert PAYMENT_FIELD_RE.search(s), s
    assert not PAYMENT_FIELD_RE.search("email_address")
    assert not PAYMENT_FIELD_RE.search("discount_code")
except ImportError:
    print("(skipped payment-guard test: playwright/anthropic not installed)")

print("all checks passed")
