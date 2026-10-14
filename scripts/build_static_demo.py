"""Snapshot the showcase portfolio into static JSON for the GitHub Pages demo.

Seeds the fictional demo portfolio (app/demo.py) into a throw-away SQLite DB,
pulls real prices, then records every read endpoint the UI uses into
frontend/public/demo/. The frontend built with VITE_STATIC_DEMO=true reads
these files instead of calling a backend, so the demo needs no server and
no sign-in. Run from the repo root:

    python scripts/build_static_demo.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "public" / "demo"

tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{tmp}/demo.db"
os.environ.pop("DEMO_MODE", None)  # seed + warm synchronously below instead
os.chdir(ROOT / "backend")
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.demo import seed_showcase  # noqa: E402
from app.main import app  # noqa: E402
from app.services import market  # noqa: E402


def get(c: TestClient, path: str):
    r = c.get("/api" + path)
    r.raise_for_status()
    return r.json() if "json" in r.headers.get("content-type", "") else r.text


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    with TestClient(app) as c:  # runs migrations
        db = SessionLocal()
        try:
            seed_showcase(db)
            bf = market.backfill_history(db)
            rf = market.refresh_all(db, force=True)
        finally:
            db.close()
        print("backfill:", bf, "\nrefresh:", rf)

        data: dict = {}
        health = get(c, "/health")
        health["demo"] = True
        health["static"] = True
        data["/health"] = health
        for base in ("HKD", "USD", "CNY"):
            for method in ("wac", "fifo"):
                data[f"/portfolio/summary?base={base}&method={method}"] = get(
                    c, f"/portfolio/summary?base={base}&method={method}")
                data[f"/portfolio/history?base={base}&method={method}"] = get(
                    c, f"/portfolio/history?base={base}&method={method}")
        data["/instruments"] = get(c, "/instruments")
        data["/transactions"] = get(c, "/transactions?limit=1000")
        data["/cash"] = get(c, "/cash")
        data["/benchmarks"] = get(c, "/benchmarks")
        first = min((t["date"] for t in data["/transactions"]), default=date.today().isoformat())
        for b in data["/benchmarks"]:
            data[f"/benchmark?symbol={b['symbol']}"] = get(
                c, f"/benchmark?symbol={b['symbol']}&start={first}")
        for inst in data["/instruments"]:
            data[f"/instruments/{inst['id']}/prices"] = get(c, f"/instruments/{inst['id']}/prices")

        if not data["/portfolio/summary?base=HKD&method=wac"].get("holdings"):
            print("no holdings in snapshot", file=sys.stderr)
            return 1
        (OUT / "data.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
        (OUT / "backup.json").write_text(json.dumps(get(c, "/backup"), ensure_ascii=False, indent=2))
        (OUT / "transactions.csv").write_text(get(c, "/transactions/export.csv"), encoding="utf-8")
    print("wrote", OUT, f"{(OUT / 'data.json').stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
