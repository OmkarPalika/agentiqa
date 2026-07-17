"""Shopper driven by `claude -p` (Claude Code subscription) — no API key needed.

Same browser loop and safety guards as shopper.py; the model speaks a JSON-action
protocol over the claude CLI instead of API tool calls.
"""

import json
import shutil
import subprocess

from playwright.sync_api import sync_playwright

from .shopper import MAX_STEPS, build_execute

PROMPT = """You are a realistic online shopper testing whether an e-commerce store works for AI agents.

Task: {goal}

I control a headless browser for you. Each of my messages shows the result of your last action (page snapshots list interactive elements as [id] <tag> label). Reply with EXACTLY ONE JSON object — no prose, no markdown fences, and do not use any of your own tools:

{{"action": "read_page"}}
{{"action": "click", "element_id": 12}}
{{"action": "type_text", "element_id": 3, "text": "...", "submit": false}}
{{"action": "goto", "url": "https://..."}}
{{"action": "record_milestone", "stage": "product_found"}}   (stages: product_found, added_to_cart, checkout_reached)
{{"action": "done", "summary": "what worked, where friction occurred, what the store should fix for AI shoppers"}}

Shop like a real customer: find a product, open its page, add it to cart, reach checkout. Send record_milestone the moment you hit each stage.

HARD RULES:
- NEVER enter payment details, card numbers, CVV, or expiry dates. Stop at the checkout page.
- NEVER create an account or log in. Guest checkout: obviously fake data (Test Shopper, test@example.com) is OK, but NEVER submit the final order.
- Stuck (broken flow, dead end)? Send done with WHERE and WHY.

The store is loaded at {url}. First action?"""

# One claude CLI process per step (~10-30s each); switch to the API driver when speed matters.
_DISALLOWED = "Bash,Read,Write,Edit,Glob,Grep,WebFetch,WebSearch,Task,TodoWrite,NotebookEdit"


def _claude(prompt: str, session: str | None) -> tuple[str, str | None]:
    exe = shutil.which("claude") or "claude"
    # --setting-sources project: skip user-level hooks/CLAUDE.md that pollute the protocol
    cmd = [exe, "-p", "--output-format", "json", "--setting-sources", "project",
           "--disallowedTools", _DISALLOWED]
    if session:
        cmd += ["--resume", session]
    r = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=600)
    if r.returncode != 0:
        raise RuntimeError(f"claude -p failed (exit {r.returncode}): {(r.stderr or r.stdout)[:500]}")
    data = json.loads(r.stdout)
    return data.get("result", ""), data.get("session_id")


def _parse_action(text: str) -> dict:
    start = text.find("{")
    if start < 0:
        return {}
    try:
        obj, _ = json.JSONDecoder().raw_decode(text[start:])
        return obj if isinstance(obj, dict) else {}
    except ValueError:
        return {}


def run_shopper(url: str, goal: str, log=print) -> dict:
    """Run the agent via `claude -p`. Returns {milestones, steps, summary}."""
    milestones, steps = [], []
    summary = ""

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.set_default_timeout(15000)
        page.goto(url, wait_until="domcontentloaded")
        execute = build_execute(page, milestones, log)

        text, session = _claude(PROMPT.format(goal=goal, url=url), None)
        for step in range(MAX_STEPS):
            action = _parse_action(text)
            name = action.get("action")
            if name == "done" or not name:
                summary = str(action.get("summary") or text).strip()
                break
            args = {k: v for k, v in action.items() if k != "action"}
            log(f"step {step + 1}: {name} {json.dumps(args)[:100]}")
            out = execute(name, args)
            steps.append({"tool": name, "input": args, "result": out[:200]})
            text, session = _claude(f"RESULT:\n{out}\n\nNext action (one JSON object only)?", session)
        else:
            summary = f"Stopped: hit {MAX_STEPS}-step limit before completing the flow."

        browser.close()

    return {"milestones": milestones, "steps": steps, "summary": summary}
