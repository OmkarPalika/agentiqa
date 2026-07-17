# AgentiQA

**Can an AI agent actually buy from your store? Run one and find out.**

AI shopping agents are here (ChatGPT, Claude, Perplexity, agentic checkout). If an agent can't get through your funnel, that's revenue walking out the door — invisibly. AgentiQA sends a real AI agent (Claude + a headless browser) through your store like a customer — discover → product → cart → checkout — and reports **exactly where the agent gets stuck**, plus static agent-readiness checks. Stops before payment, always.

```
$ python -m agentiqa https://books.toscrape.com/ --goal "Buy any book"

Static checks: https://books.toscrape.com/
  [PASS] robots.txt allows agent user-agents
  [FAIL] JSON-LD structured data  — no Product/Offer; agents can't read your catalog
  [FAIL] OpenGraph tags           — present: none
  [FAIL] sitemap.xml              — 404

Running shopper agent (stops before payment)...
  step 2: click  "A Light in the Attic"
  milestone: product_found  ✓
  step 6: click  "add to basket"
  ...dead end.

VERDICT: Found the product (£51.77) but the funnel dead-ends. 'Add to basket'
buttons are non-functional — clicking reloads the listing with '?' appended, no
cart is created, no cart link exists anywhere, no checkout page. An AI agent
(or human) cannot transact. Fix: (1) make 'Add to basket' actually add + confirm,
(2) surface a persistent cart link with count, (3) put the button on the product
page, (4) ship a working cart + guest checkout.
```

## Why this exists

Static "agent-readiness" scanners tell you if your markup is clean. They **don't** tell you whether an agent can complete a purchase. That's a behavioral question, and the only way to answer it is to send an agent through the real flow. That's what this does.

## Quickstart

```
pip install -r requirements.txt
playwright install chromium

# free mode — static agent-readiness checks, no API key, no agent
python -m agentiqa https://your-store.com --no-agent
```

That's it for the free check. To run the live agent, add one of:

- **Claude Code subscription** (no extra cost): have the `claude` CLI on your PATH and logged in. Used automatically when no API key is set.
- **`ANTHROPIC_API_KEY`**: faster, ~$1–2 per audit. Used automatically when set.

```
# full run: static checks + live shopper agent + HTML report
python -m agentiqa https://your-store.com

# custom goal
python -m agentiqa https://your-store.com --goal "Buy a medium blue t-shirt"

# force a driver (default: api if ANTHROPIC_API_KEY set, else cli)
python -m agentiqa https://your-store.com --driver cli
```

Output: **`agentiqa-report.html`** — the conversion funnel (product found / added to cart / checkout reached), static check results, the agent's verdict, and the full step transcript.

> ⚠️ **Only run against stores you own or have written permission to test.**

## How it works

Two independent layers:

1. **Static checks** (stdlib only, no key) — robots.txt allows agent user-agents (`Claude-User`, `ChatGPT-User`, `OAI-SearchBot`, `PerplexityBot`), JSON-LD `Product`/`Offer`/`ItemList`, OpenGraph tags, `sitemap.xml`.
2. **Live shopper agent** — Claude reads a text snapshot of each page (interactive elements indexed by id) and drives the browser with `click` / `type_text` / `goto`, recording funnel milestones. No screenshots, no vision — pure DOM text, which is roughly what an agent shopper actually sees.

## Safety (enforced in code, not just the prompt)

- **Never enters payment data.** Payment-looking fields (card, CVV, expiry…) are refused by a code guard before any keystroke — not left to the model's judgment.
- **Never creates accounts or logs in.**
- **Never submits a final order.** Stops at the checkout page.

## Test

```
python test_checks.py
```

Offline, no key, no network — covers the static checks and the payment-field guard.

## License

MIT — see [LICENSE](LICENSE).
