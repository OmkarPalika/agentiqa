"""Self-contained HTML report. No template deps."""

import html
from datetime import datetime, timezone

from . import CONTACT

STAGES = [("product_found", "Product found"), ("added_to_cart", "Added to cart"),
          ("checkout_reached", "Checkout reached")]

# Failed static check -> the concrete action a store owner should take. Matched by keyword.
FIX_HINTS = {
    "robots": "Allow AI agent user-agents (Claude-User, ChatGPT-User, OAI-SearchBot, PerplexityBot) in robots.txt so agents can browse your store.",
    "JSON-LD": "Add JSON-LD Product/Offer structured data to product pages so agents can read price, availability, and variants.",
    "OpenGraph": "Add OpenGraph tags (og:title, og:description, og:image) so agents and link previews understand your pages.",
    "sitemap": "Publish a reachable sitemap.xml so agents can discover your full catalog.",
}


def _furthest(milestones: list) -> str:
    reached = [label for key, label in STAGES if key in milestones]
    return reached[-1] if reached else "the store never loaded / no product reached"


def _fix_list(checks: list, agent: dict | None) -> str:
    items = []
    if agent and "checkout_reached" not in agent["milestones"]:
        items.append("<li><b>Highest priority:</b> the agent could not reach checkout. See the verdict below for exactly where the funnel broke.</li>")
    for c in checks:
        if c["passed"]:
            continue
        hint = next((v for k, v in FIX_HINTS.items() if k.lower() in c["name"].lower()), None)
        if hint:
            items.append(f"<li>{html.escape(hint)}</li>")
    if not items:
        return "<p>No blocking issues found — this store is in good shape for AI shoppers.</p>"
    return f"<ul>{''.join(items)}</ul>"


def render(url: str, checks: list, agent: dict | None) -> str:
    check_rows = "\n".join(
        f"<tr><td>{'PASS' if c['passed'] else 'FAIL'}</td>"
        f"<td>{html.escape(c['name'])}</td><td>{html.escape(c['detail'])}</td></tr>"
        for c in checks
    )

    if agent:
        reached = agent["milestones"]
        funnel = "\n".join(
            f"<div class='stage {'ok' if key in reached else 'miss'}'>{label}"
            f" {'&#10003;' if key in reached else '&#10007;'}</div>"
            for key, label in STAGES
        )
        step_rows = "\n".join(
            f"<tr><td>{i + 1}</td><td>{html.escape(s['tool'])}</td>"
            f"<td>{html.escape(str(s['input'])[:120])}</td><td>{html.escape(s['result'])}</td></tr>"
            for i, s in enumerate(agent["steps"])
        )
        agent_html = f"""
<h2>Agent purchase funnel</h2>
<div class="funnel">{funnel}</div>
<h2>Agent verdict</h2>
<pre class="summary">{html.escape(agent['summary'])}</pre>
<h2>Step transcript ({len(agent['steps'])} actions)</h2>
<table><tr><th>#</th><th>Action</th><th>Input</th><th>Result</th></tr>{step_rows}</table>"""
    else:
        agent_html = "<h2>Agent run</h2><p>Skipped (static checks only).</p>"

    if agent:
        won = "checkout_reached" in agent["milestones"]
        cls = "verdict ok" if won else "verdict miss"
        msg = ("An AI shopping agent completed the purchase flow on this store (stopping before payment)."
               if won else
               f"An AI shopping agent could NOT complete checkout. It got as far as: {html.escape(_furthest(agent['milestones']))}.")
        banner = f'<div class="{cls}">{msg}</div>'
    else:
        banner = '<div class="verdict neutral">Static readiness checks only — run the live agent for a full purchase-flow verdict.</div>'

    fixes = f'<h2>Recommended fixes</h2>{_fix_list(checks, agent)}'

    cta = ""
    if CONTACT and CONTACT != "your-email@example.com":
        cta = (f'<p class="cta">Want these issues fixed for you? '
               f'<a href="mailto:{html.escape(CONTACT)}">{html.escape(CONTACT)}</a></p>')

    passed = sum(1 for c in checks if c["passed"])
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>AgentiQA report — {html.escape(url)}</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:960px;margin:2rem auto;padding:0 1rem;color:#1a1a2e}}
h1{{font-size:1.4rem}} table{{border-collapse:collapse;width:100%;font-size:.9rem}}
td,th{{border:1px solid #ddd;padding:.4rem .6rem;text-align:left;vertical-align:top}}
.funnel{{display:flex;gap:.5rem;margin:1rem 0}}
.stage{{padding:.6rem 1rem;border-radius:6px;font-weight:600}}
.ok{{background:#d4f7dc;color:#116329}} .miss{{background:#ffe0e0;color:#a11}}
.summary{{background:#f6f6f8;padding:1rem;border-radius:6px;white-space:pre-wrap}}
.cta{{margin-top:2rem;padding:1rem;background:#eef;border-radius:6px;font-weight:600}}
.verdict{{padding:1rem 1.2rem;border-radius:8px;font-size:1.1rem;font-weight:600;margin:1rem 0}}
.verdict.ok{{background:#d4f7dc;color:#116329}} .verdict.miss{{background:#ffe0e0;color:#a11}}
.verdict.neutral{{background:#eef;color:#334}}
h2{{font-size:1.1rem;margin-top:2rem}} ul{{line-height:1.6}}
</style></head><body>
<h1>AgentiQA — Agent readiness report</h1>
<p><b>{html.escape(url)}</b> &middot; {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p>
{banner}
{fixes}
<h2>Static readiness checks ({passed}/{len(checks)} passed)</h2>
<table><tr><th>Result</th><th>Check</th><th>Detail</th></tr>{check_rows}</table>
{agent_html}
{cta}
</body></html>"""
