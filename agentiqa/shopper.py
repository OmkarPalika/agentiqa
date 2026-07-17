"""Live shopper agent: Claude drives a Chromium browser through a purchase flow.

Stops before payment — enforced in code (PAYMENT_FIELD_RE guard), not just prompt.
"""

import json
import re

import anthropic
from playwright.sync_api import sync_playwright

MODEL = "claude-opus-4-8"
MAX_STEPS = 40
MILESTONES = ["product_found", "added_to_cart", "checkout_reached"]

# Heuristic match for payment fields; swap for a field-classifier if merchants report misses.
PAYMENT_FIELD_RE = re.compile(r"card|cvv|cvc|cc-|expir|security.?code|pan\b", re.IGNORECASE)

SYSTEM = """You are a realistic online shopper testing whether an e-commerce store works for AI agents.

Your task: {goal}

Work through the store like a real customer: find a product, open its page, add it to cart, and proceed to checkout. Use read_page to see the current page, click/type_text/goto to act.

Call record_milestone the moment you achieve each stage: product_found (viewing a product page), added_to_cart (item is in the cart), checkout_reached (you are on the checkout page).

HARD RULES:
- NEVER enter payment details, card numbers, CVV, or expiry dates. Stop at the checkout page.
- NEVER create an account or log in. If checkout offers guest checkout, you may fill name/email with obviously fake test data (Test Shopper, test@example.com) but do NOT submit the final order.
- If you are stuck (cookie walls you can dismiss, do so; broken flows, dead ends), note precisely WHERE and WHY you got stuck, then stop.

When done (checkout reached, or stuck), end with a plain-text summary: what worked, where friction occurred, and what the store should fix for AI shoppers."""

TOOLS = [
    {"name": "read_page", "description": "Get a text snapshot of the current page: URL, title, interactive elements with numeric ids, and visible text.",
     "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "click", "description": "Click an interactive element by the numeric id from read_page.",
     "input_schema": {"type": "object", "properties": {"element_id": {"type": "integer"}}, "required": ["element_id"], "additionalProperties": False}},
    {"name": "type_text", "description": "Type text into an input element by numeric id (presses Enter if submit=true).",
     "input_schema": {"type": "object", "properties": {"element_id": {"type": "integer"}, "text": {"type": "string"}, "submit": {"type": "boolean"}}, "required": ["element_id", "text"], "additionalProperties": False}},
    {"name": "goto", "description": "Navigate to a URL on the same site.",
     "input_schema": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"], "additionalProperties": False}},
    {"name": "record_milestone", "description": "Record reaching a funnel stage: product_found, added_to_cart, or checkout_reached.",
     "input_schema": {"type": "object", "properties": {"stage": {"type": "string", "enum": MILESTONES}}, "required": ["stage"], "additionalProperties": False}},
]


def snapshot(page) -> tuple[str, list]:
    """Text snapshot of the page + list of live element handles, indexed."""
    els = page.query_selector_all("a[href], button, input, select, textarea, [role=button]")
    lines, handles = [], []
    for el in els:
        if len(handles) >= 120:
            break
        try:
            if not el.is_visible():
                continue
            tag = el.evaluate("e => e.tagName.toLowerCase()")
            label = (el.inner_text() or el.get_attribute("aria-label")
                     or el.get_attribute("placeholder") or el.get_attribute("value") or "")[:80].strip()
            extra = ""
            if tag == "a":
                extra = f" href={el.get_attribute('href') or ''}"[:120]
            elif tag == "input":
                extra = f" type={el.get_attribute('type') or 'text'} name={el.get_attribute('name') or ''}"
            lines.append(f"[{len(handles)}] <{tag}{extra}> {label}")
            handles.append(el)
        except Exception:
            continue
    text = page.inner_text("body")[:3000]
    snap = (f"URL: {page.url}\nTITLE: {page.title()}\n\nINTERACTIVE ELEMENTS:\n"
            + "\n".join(lines) + f"\n\nVISIBLE TEXT (truncated):\n{text}")
    return snap, handles


def is_payment_field(el) -> bool:
    for attr in ("name", "id", "autocomplete", "placeholder", "aria-label"):
        v = el.get_attribute(attr)
        if v and PAYMENT_FIELD_RE.search(v):
            return True
    return False


def build_execute(page, milestones: list, log):
    """Shared action executor: maps agent actions onto the live page. Used by API and CLI drivers."""
    state = {"handles": []}

    def execute(name: str, args: dict) -> str:
        if name == "read_page":
            snap, state["handles"] = snapshot(page)
            return snap
        if name == "record_milestone":
            stage = args.get("stage")
            if stage not in MILESTONES:
                return f"Error: stage must be one of {MILESTONES}"
            if stage not in milestones:
                milestones.append(stage)
            log(f"  milestone: {stage}")
            return f"recorded {stage}"
        if name == "goto":
            page.goto(args["url"], wait_until="domcontentloaded")
            return f"navigated to {page.url}"
        # element ops
        i = args.get("element_id", -1)
        handles = state["handles"]
        if not (isinstance(i, int) and 0 <= i < len(handles)):
            return "Error: stale or invalid element_id — call read_page again."
        el = handles[i]
        try:
            if name == "click":
                el.click()
                page.wait_for_load_state("domcontentloaded")
                return f"clicked; now at {page.url}"
            if name == "type_text":
                if is_payment_field(el):
                    return "REFUSED: this looks like a payment field. Never enter payment data. Stop here and summarize."
                el.fill(args["text"])
                if args.get("submit"):
                    el.press("Enter")
                    page.wait_for_load_state("domcontentloaded")
                return "typed"
        except Exception as e:
            return f"Error: {e}"
        return f"unknown tool {name}"

    return execute


def run_shopper(url: str, goal: str, log=print) -> dict:
    """Run the agent via the Anthropic API. Returns {milestones, steps, summary}."""
    client = anthropic.Anthropic()
    milestones, steps = [], []
    summary = ""

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.set_default_timeout(15000)
        page.goto(url, wait_until="domcontentloaded")
        execute = build_execute(page, milestones, log)

        messages = [{"role": "user", "content": f"The store is loaded at {url}. Begin. Call read_page first."}]
        for step in range(MAX_STEPS):
            response = client.messages.create(
                model=MODEL, max_tokens=4096,
                thinking={"type": "adaptive"},
                system=SYSTEM.format(goal=goal),
                tools=TOOLS, messages=messages,
            )
            messages.append({"role": "assistant", "content": response.content})
            tool_uses = [b for b in response.content if b.type == "tool_use"]
            for b in response.content:
                if b.type == "text" and b.text.strip():
                    summary = b.text.strip()
            if response.stop_reason != "tool_use" or not tool_uses:
                break
            results = []
            for tu in tool_uses:
                log(f"step {step + 1}: {tu.name} {json.dumps(tu.input)[:100]}")
                out = execute(tu.name, tu.input)
                steps.append({"tool": tu.name, "input": tu.input, "result": out[:200]})
                results.append({"type": "tool_result", "tool_use_id": tu.id, "content": out})
            messages.append({"role": "user", "content": results})
        else:
            summary = summary or f"Stopped: hit {MAX_STEPS}-step limit before completing the flow."

        browser.close()

    return {"milestones": milestones, "steps": steps, "summary": summary}
