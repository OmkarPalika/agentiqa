# AgentiQA — Design

## What

CLI tool: point at an e-commerce store URL, get an "agent conversion" report — can an AI shopping agent actually discover a product, add to cart, and reach checkout on this store?

Two layers:

1. **Static readiness checks** (no API key, stdlib only): robots.txt allows agent user-agents (Claude-User, ChatGPT-User, OAI-SearchBot, PerplexityBot), sitemap.xml exists, JSON-LD Product/Offer structured data, OpenGraph tags.
2. **Live shopper agent**: Claude drives a real Chromium browser via Playwright through a text-based page snapshot + click/type/goto tools. Records funnel milestones: `product_found` → `added_to_cart` → `checkout_reached`. **Hard stop before payment** — system-prompt rule plus a code-level guard in `type_text` that refuses card/CVV/expiry fields.

Output: self-contained HTML report (funnel, static check table, step transcript, failure notes).

## Architecture

- `agentiqa/checks.py` — static checks, pure functions over fetched text (urllib). Unit-testable offline.
- `agentiqa/shopper.py` — API driver: manual agentic loop (loop on `stop_reason == "tool_use"`, capped at 40 iterations). Tools: `read_page`, `click`, `type_text`, `goto`, `record_milestone`. Page snapshot = title/URL + indexed interactive elements + truncated visible text (no screenshots — cheaper, deterministic). Also exports `build_execute`, the shared browser-action executor.
- `agentiqa/shopper_cli.py` — CLI driver: same browser loop and safety guards, but the model speaks a one-JSON-object-per-turn protocol over the `claude` CLI (`-p --output-format json --resume`), so no API key is needed. Reuses `build_execute` from `shopper.py`.
- `agentiqa/report.py` — HTML string template, no deps.
- `agentiqa/__main__.py` — CLI: `python -m agentiqa <url> [--goal TEXT] [--no-agent] [--driver auto|api|cli] [-o out.html]`. Driver `auto` picks `api` when `ANTHROPIC_API_KEY` is set, else `cli`.

## Deliberate cuts (add later if demand)

- One agent persona, one run (no swarm/parallel personas)
- Homepage-only static checks (no product-page crawl)
- No screenshots/vision — text DOM snapshot only
- No auth/login flows, no account creation (also a safety rule)
- Manual loop with an explicit iteration cap (no tool-runner dependency)

## Safety rules (never cut)

- Never enter payment data, CVV, card numbers — enforced in code, not just prompt
- Never create accounts or submit final orders
- Only run against stores the user owns or has permission to test (README disclaimer)

## Verification

- `test_checks.py` — offline asserts over sample HTML/robots fixtures and the payment-field guard
- Live run requires a driver (API key or the `claude` CLI) + a target store; smoke test = static checks against any real site
