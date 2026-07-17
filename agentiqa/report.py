"""Self-contained HTML report. No template deps."""

import html
from datetime import datetime, timezone

from . import CONTACT

STAGES = [("product_found", "Product found"), ("added_to_cart", "Added to cart"),
          ("checkout_reached", "Checkout reached")]


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
</style></head><body>
<h1>AgentiQA — Agent readiness report</h1>
<p><b>{html.escape(url)}</b> &middot; {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p>
<h2>Static readiness checks ({passed}/{len(checks)} passed)</h2>
<table><tr><th>Result</th><th>Check</th><th>Detail</th></tr>{check_rows}</table>
{agent_html}
{cta}
</body></html>"""
