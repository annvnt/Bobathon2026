"""CLI entry point."""

from __future__ import annotations

import argparse
import sys

from radar.config import FIXTURE_FILE, load_dotenv


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Regulatory Radar — monitor, assess, alert")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("ingest", help="Pull live updates into feed/cache.json")
    ev = sub.add_parser("evaluate", help="Assess portfolio → output/gaps.json")
    ev.add_argument("--fixture", action="store_true", help="Use Dataset/regulatory_updates.json (offline demo)")
    sub.add_parser("alert", help="Send Twilio alerts for gaps")
    run_p = sub.add_parser("run", help="MCP -> evaluate -> alert (optional)")
    run_p.add_argument("--no-alert", action="store_true", help="Skip Twilio alerts")
    sub.add_parser("mcp", help="MCP: fetch via API keys -> embed -> route -> HIL")
    sub.add_parser("check", help="Self-check against organizer fixture data")
    serve = sub.add_parser("serve", help="Start web dashboard")
    serve.add_argument("--port", type=int, default=8000)

    args = parser.parse_args(argv)

    if args.command == "ingest":
        from radar import ingest as ing
        n = ing.ingest()
        print(f"Done - {n} new updates")
        return 0

    if args.command == "evaluate":
        from radar import evaluate as evm
        fixture = FIXTURE_FILE if args.fixture else None
        gaps = evm.evaluate(fixture=fixture)
        print(f"Done - {len(gaps)} gaps written to output/gaps.json")
        return 0

    if args.command == "alert":
        from radar import notify
        notify.alert_all()
        return 0

    if args.command == "mcp":
        from radar import mcp as mcp_mod
        stats = mcp_mod.run()
        print(f"Done - {stats}")
        return 0

    if args.command == "run":
        from radar import pipeline
        result = pipeline.run_pipeline(send_alerts=not args.no_alert)
        print(result)
        return 0 if result.get("status") == "completed" else 1

    if args.command == "check":
        return _self_check()

    if args.command == "serve":
        import uvicorn
        uvicorn.run("radar.web:app", host="0.0.0.0", port=args.port, reload=True)
        return 0

    return 1


def _self_check() -> int:
    """Runnable check using organizer fixture data only."""
    from radar import evaluate as evm
    from radar.config import PARTNERS_FILE
    import json

    gaps = evm.evaluate(fixture=FIXTURE_FILE)
    assert len(gaps) >= 1, "expected at least one gap from fixture"
    partners = json.loads(PARTNERS_FILE.read_text(encoding="utf-8"))
    seeded = {p["partner_id"] for p in partners["partners"] if p.get("compliance_status")}
    found = {g["partner_id"] for g in gaps}
    overlap = seeded & found
    assert overlap, f"expected gaps for seeded partners, got partners {found}"
    ridevolt = [g for g in gaps if g.get("partner_id") == "P013"]
    assert ridevolt, "expected RideVolt (P013) battery passport gap"
    print(f"OK - {len(gaps)} gaps, seeded overlap: {sorted(overlap)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
