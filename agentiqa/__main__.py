import argparse
import sys

from . import checks, report


def main():
    p = argparse.ArgumentParser(prog="agentiqa",
                                description="Test whether an AI shopping agent can buy from your store.")
    p.add_argument("url", help="Store URL (must be a store you own or have permission to test)")
    p.add_argument("--goal", default="Buy any in-stock product from this store.")
    p.add_argument("--no-agent", action="store_true", help="Static checks only (no API key needed)")
    p.add_argument("--driver", choices=["auto", "api", "cli"], default="auto",
                   help="api = Anthropic API key; cli = claude CLI subscription; auto = api if ANTHROPIC_API_KEY set, else cli")
    p.add_argument("-o", "--out", default="agentiqa-report.html")
    args = p.parse_args()

    print(f"Static checks: {args.url}")
    static = checks.run_static_checks(args.url)
    for c in static:
        print(f"  [{'PASS' if c['passed'] else 'FAIL'}] {c['name']}: {c['detail']}")

    agent = None
    if not args.no_agent:
        import os
        driver = args.driver
        if driver == "auto":
            driver = "api" if os.environ.get("ANTHROPIC_API_KEY") else "cli"
        # deferred imports: playwright/anthropic only needed for live run
        if driver == "cli":
            from . import shopper_cli as shopper
        else:
            from . import shopper
        print(f"Running shopper agent via {driver} driver (stops before payment)...")
        agent = shopper.run_shopper(args.url, args.goal)
        print(f"Milestones reached: {', '.join(agent['milestones']) or 'none'}")

    html = report.render(args.url, static, agent)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Report: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
