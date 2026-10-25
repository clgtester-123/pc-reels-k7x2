"""Daily runner: pick next row -> render Reel -> publish to Instagram -> log -> refill -> keepalive.

Usage:
  python pipeline/run.py --dry-run     render only, change nothing, no publishing
  python pipeline/run.py               full run (used by GitHub Actions)
"""
import argparse
import csv
import datetime as dt
import os
import subprocess
import sys
import time

import requests

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
from make_reel import build  # noqa: E402
from publish import publish_reel, PublishError  # noqa: E402
from refill import refill  # noqa: E402

CSV_PATH = os.path.join(ROOT, "content", "reels.csv")
VIDEO_DIR = os.path.join(ROOT, "videos")
LOG_PATH = os.path.join(ROOT, "logs", "runs.log")
KEEP_VIDEOS = 7


def sh(*args, check=True):
    return subprocess.run(args, cwd=ROOT, check=check, capture_output=True, text=True)


DRY = False


def log(msg):
    line = f"{dt.datetime.utcnow().isoformat(timespec='seconds')}Z {msg}"
    if not DRY:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a") as f:
            f.write(line + "\n")
    print(line)


def read_rows():
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return rows, list(rows[0].keys())


def write_rows(rows, fields):
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def pick_next(rows, enabled):
    for r in rows:
        if r["status"] == "unused" and r["product"] in enabled:
            return r
    return None


def wait_for_url(url, tries=12):
    for _ in range(tries):
        try:
            if requests.head(url, timeout=20, allow_redirects=True).status_code == 200:
                return True
        except requests.RequestException:
            pass
        time.sleep(10)
    return False


def prune_videos():
    vids = sorted(f for f in os.listdir(VIDEO_DIR) if f.endswith(".mp4"))
    for f in vids[:-KEEP_VIDEOS]:
        os.remove(os.path.join(VIDEO_DIR, f))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    global DRY
    DRY = args.dry_run

    enabled = [p.strip() for p in os.environ.get("ENABLED_PRODUCTS", "handstand").split(",") if p.strip()]
    rows, fields = read_rows()
    row = pick_next(rows, enabled)
    os.makedirs(VIDEO_DIR, exist_ok=True)

    if row is None:
        log("No unused rows for enabled products; attempting refill")
        if not args.dry_run and os.environ.get("ANTHROPIC_API_KEY"):
            refill(CSV_PATH, enabled)
            rows, fields = read_rows()
            row = pick_next(rows, enabled)
        if row is None:
            log("Nothing to post. Exiting.")
            return 1

    out = os.path.join(VIDEO_DIR, f"{row['id']}.mp4") if not args.dry_run else f"/tmp/dryrun_{row['id']}.mp4"
    build(row, out)
    log(f"Rendered row {row['id']} ({row['product']}) -> {out}")
    if args.dry_run:
        print("Dry run complete. Nothing published or changed.")
        return 0

    # Publish the video file so Instagram can fetch it from a public URL.
    sh("git", "add", "videos")
    sh("git", "commit", "-m", f"video {row['id']}", check=False)
    sh("git", "push", "origin", "HEAD")
    repo = os.environ["GITHUB_REPOSITORY"]
    branch = os.environ.get("GITHUB_REF_NAME", "main")
    url = f"https://raw.githubusercontent.com/{repo}/{branch}/videos/{row['id']}.mp4"
    if not wait_for_url(url):
        log(f"Video URL never became reachable: {url}")
        return 2

    caption = row["caption"] + "\n\n" + row["hashtags"]
    try:
        media_id = publish_reel(url, caption)
    except PublishError as e:
        log(f"PUBLISH FAILED row {row['id']}: {e}")
        return 3

    row["status"] = "posted"
    row["posted_at"] = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    row["media_id"] = media_id
    write_rows(rows, fields)
    log(f"Posted row {row['id']} media_id={media_id}")

    # Self-refill when the queue is low.
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            added = refill(CSV_PATH, enabled)
            if added:
                log(f"Refilled sheet with {added} new rows")
        except Exception as e:  # never let refill break a successful post
            log(f"Refill failed (non-fatal): {e}")

    prune_videos()
    sh("git", "add", "-A")
    sh("git", "commit", "-m", f"posted {row['id']} + keepalive", check=False)
    sh("git", "push", "origin", "HEAD")
    return 0


if __name__ == "__main__":
    sys.exit(main())
