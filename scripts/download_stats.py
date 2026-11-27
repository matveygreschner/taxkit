"""How many people use TaxKit: release downloads (all time) and repo traffic (views, clones, last 14 days).

GitHub keeps download counts forever but traffic for only 14 days, so this script also appends a dated
snapshot to stats/downloads.csv and stats/traffic.csv. Run it locally or let .github/workflows/stats.yml
run it daily.

    python scripts/download_stats.py                  # print a summary
    python scripts/download_stats.py --record         # also append to stats/*.csv
    GH_TOKEN=$(gh auth token) python scripts/download_stats.py --record   # include traffic

Download counts are public. Traffic needs a token with push access to the repo (your own `gh` login,
or a TRAFFIC_TOKEN secret in Actions); without one, traffic is skipped.
Standard library only.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

REPO = os.environ.get("TAXKIT_REPO", "matveygreschner/taxkit")
STATS = Path(__file__).resolve().parents[1] / "stats"


def _get(path: str, token: str | None):
    req = urllib.request.Request(f"https://api.github.com/repos/{REPO}{path}",
                                 headers={"Accept": "application/vnd.github+json", "User-Agent": "taxkit-stats"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def downloads(token: str | None) -> list[dict]:
    rows = []
    for rel in _get("/releases?per_page=100", token):
        for a in rel.get("assets", []):
            rows.append({"release": rel["tag_name"], "asset": a["name"], "downloads": a["download_count"]})
    return rows


def traffic(token: str | None) -> dict | None:
    if not token:
        return None
    try:
        views = _get("/traffic/views", token)
        clones = _get("/traffic/clones", token)
    except urllib.error.HTTPError as e:      # 403: token lacks push access
        print(f"(traffic skipped: HTTP {e.code})")
        return None
    days = {}
    for v in views.get("views", []):
        days.setdefault(v["timestamp"][:10], {}).update(views=v["count"], unique_visitors=v["uniques"])
    for c in clones.get("clones", []):
        days.setdefault(c["timestamp"][:10], {}).update(clones=c["count"], unique_cloners=c["uniques"])
    return days


def _skill(asset: str) -> str:
    return asset.rsplit(".", 1)[0]


def record(rows: list[dict], days: dict | None, today: str) -> None:
    STATS.mkdir(exist_ok=True)
    f = STATS / "downloads.csv"
    new = not f.exists()
    with f.open("a", newline="") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["date", "release", "asset", "downloads_to_date"])
        for r in rows:
            w.writerow([today, r["release"], r["asset"], r["downloads"]])
    if days:
        # Traffic is per day; keep one row per day, newest value wins (GitHub revises the last day).
        t = STATS / "traffic.csv"
        old = {}
        if t.exists():
            with t.open() as fh:
                old = {r["date"]: r for r in csv.DictReader(fh)}
        for d, v in days.items():
            old[d] = {"date": d, **{k: v.get(k, 0) for k in ("views", "unique_visitors", "clones", "unique_cloners")}}
        with t.open("w", newline="") as fh:
            w = csv.DictWriter(fh, ["date", "views", "unique_visitors", "clones", "unique_cloners"])
            w.writeheader()
            for d in sorted(old):
                w.writerow(old[d])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--record", action="store_true", help="append a snapshot to stats/*.csv")
    a = ap.parse_args()
    token = os.environ.get("TRAFFIC_TOKEN") or os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    rows = downloads(token)
    by_skill: dict[str, int] = {}
    for r in rows:
        by_skill[_skill(r["asset"])] = by_skill.get(_skill(r["asset"]), 0) + r["downloads"]
    print(f"Downloads for {REPO} (all releases, .zip + .skill combined):")
    for name, n in sorted(by_skill.items(), key=lambda kv: -kv[1]):
        print(f"  {name:28s} {n:6d}")
    print(f"  {'TOTAL':28s} {sum(by_skill.values()):6d}")
    days = traffic(token)
    if days:
        v = sum(d.get("views", 0) for d in days.values())
        c = sum(d.get("clones", 0) for d in days.values())
        print(f"Last 14 days: {v} page views, {c} clones")
    if a.record:
        record(rows, days, dt.date.today().isoformat())
        print(f"Recorded to {STATS}")


if __name__ == "__main__":
    main()
