"""Static agent-readiness checks. Stdlib only — no API key, no browser."""

import json
import re
import urllib.request
import urllib.robotparser
from urllib.parse import urljoin, urlparse

AGENT_USER_AGENTS = ["Claude-User", "ChatGPT-User", "OAI-SearchBot", "PerplexityBot"]

FETCH_UA = "AgentiQA/0.1 (+agent-readiness scanner)"


def fetch(url: str, timeout: int = 15) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": FETCH_UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read(2_000_000).decode("utf-8", errors="replace")


def check_robots(robots_txt: str, base_url: str) -> dict:
    """Which known shopping-agent user-agents may crawl the site root."""
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(robots_txt.splitlines())
    allowed = {ua: rp.can_fetch(ua, base_url) for ua in AGENT_USER_AGENTS}
    return {
        "name": "robots.txt allows agent user-agents",
        "passed": all(allowed.values()),
        "detail": ", ".join(f"{ua}: {'allow' if ok else 'BLOCKED'}" for ua, ok in allowed.items()),
    }


def extract_jsonld(html: str) -> list:
    """All parseable JSON-LD blocks in the page."""
    blocks = []
    for m in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html, re.DOTALL | re.IGNORECASE,
    ):
        try:
            data = json.loads(m.group(1))
            blocks.extend(data if isinstance(data, list) else [data])
        except json.JSONDecodeError:
            pass
    return blocks


def _jsonld_types(blocks: list) -> set:
    types = set()
    for b in blocks:
        if not isinstance(b, dict):
            continue
        t = b.get("@type", "")
        types.update(t if isinstance(t, list) else [t])
        # @graph containers
        for g in b.get("@graph", []):
            if isinstance(g, dict):
                gt = g.get("@type", "")
                types.update(gt if isinstance(gt, list) else [gt])
    return types


def check_structured_data(html: str) -> dict:
    types = _jsonld_types(extract_jsonld(html))
    wanted = {"Product", "Offer", "ItemList", "WebSite", "Organization"}
    found = sorted(types & wanted)
    return {
        "name": "JSON-LD structured data",
        "passed": bool(types & {"Product", "Offer", "ItemList"}),
        "detail": f"found: {', '.join(found) or 'none'}"
        + ("" if types & {"Product", "Offer", "ItemList"} else " (no Product/Offer/ItemList — agents can't read your catalog)"),
    }


def check_opengraph(html: str) -> dict:
    tags = re.findall(r'<meta[^>]+property=["\']og:(\w+)["\']', html, re.IGNORECASE)
    have = set(tags)
    need = {"title", "description"}
    return {
        "name": "OpenGraph tags",
        "passed": need <= have,
        "detail": f"present: {', '.join(sorted(have)) or 'none'}",
    }


def check_sitemap(base_url: str) -> dict:
    url = urljoin(base_url, "/sitemap.xml")
    try:
        body = fetch(url)
        ok = "<urlset" in body or "<sitemapindex" in body
        return {"name": "sitemap.xml", "passed": ok, "detail": url if ok else "exists but not valid XML sitemap"}
    except Exception as e:
        return {"name": "sitemap.xml", "passed": False, "detail": f"not reachable ({e})"}


def run_static_checks(base_url: str) -> list:
    """Fetch homepage + robots.txt and run all checks. Returns list of result dicts."""
    parsed = urlparse(base_url)
    root = f"{parsed.scheme}://{parsed.netloc}/"
    results = []

    try:
        robots = fetch(urljoin(root, "/robots.txt"))
        results.append(check_robots(robots, root))
    except Exception:
        results.append({"name": "robots.txt allows agent user-agents", "passed": True,
                        "detail": "no robots.txt (everything allowed by default)"})

    try:
        html = fetch(base_url)
        results.append(check_structured_data(html))
        results.append(check_opengraph(html))
    except Exception as e:
        results.append({"name": "homepage reachable", "passed": False, "detail": str(e)})

    results.append(check_sitemap(root))
    return results
