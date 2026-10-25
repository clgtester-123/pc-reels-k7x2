"""Top up the content sheet with new Reel rows written by Claude when unused rows run low."""
import csv
import json
import os
import re
import requests

MODEL = os.environ.get("CLAUDE_MODEL") or "claude-haiku-4-5"
BASE = (os.environ.get("ANTHROPIC_BASE_URL") or "https://api.anthropic.com").rstrip("/")
URL = BASE + ("/messages" if BASE.endswith("/v1") else "/v1/messages")
DISCLAIMER = "General fitness information, not medical advice."
TAGS = {
    "handstand": "#handstand #calisthenics #handstandprogression #bodyweighttraining #mobility",
    "pullup": "#pullup #calisthenics #pullupprogression #bodyweighttraining #homeworkout",
}
BANNED = re.compile(r"\b(guarantee|guaranteed|cure|cures|heal|heals|treat|treats|diagnos\w*|in \d+ (days|weeks)|fast results|"
                    r"lose weight|fat loss|injury[- ]proof|pain[- ]free)\b", re.I)

PROMPT = """You write short Instagram Reel scripts for "Progression Club", a calisthenics page that sells step-by-step PDF guides
(a handstand guide and a pull-up guide).

Write {n} NEW Reels for the product "{product}". Each is 3 to 5 short on-screen text slides, plain English, practical and beginner friendly.

Hard rules:
- No medical claims, no diagnosis or treatment language, no guaranteed results, no promised timelines or numbers of days/weeks.
- No weight-loss or body-image claims. Mention stopping if something hurts only as general safety, never as medical advice.
- Each slide at most 16 words. Hook at most 9 words.
- Do not repeat or closely mimic these existing hooks:
{existing}

Return ONLY a JSON array, no prose. Each item: {{"hook": str, "slides": [str, ...], "body": str}}
where body is one or two sentences for the caption (no hashtags, no link, no disclaimer)."""


def _call_claude(prompt):
    r = requests.post(
        URL,
        headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"], "Authorization": "Bearer " + os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json={"model": MODEL, "max_tokens": 4000, "messages": [{"role": "user", "content": prompt}]},
        timeout=120,
    )
    r.raise_for_status()
    text = "".join(b.get("text", "") for b in r.json()["content"])
    m = re.search(r"\[.*\]", text, re.S)
    return json.loads(m.group(0))


def refill(csv_path, enabled, minimum=5, batch=10):
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        fields = list(rows[0].keys())
    added = 0
    for product in enabled:
        unused = [r for r in rows if r["product"] == product and r["status"] == "unused"]
        if len(unused) >= minimum:
            continue
        existing = "\n".join("- " + r["hook"] for r in rows if r["product"] == product)
        items = _call_claude(PROMPT.format(n=batch, product=product, existing=existing))
        next_id = max(int(r["id"]) for r in rows) + 1
        for it in items:
            blob = " ".join([it["hook"], it["body"]] + it["slides"])
            if BANNED.search(blob) or not (3 <= len(it["slides"]) <= 5):
                continue  # skip anything that trips the compliance filter
            caption = f"{it['hook']}\n\n{it['body']}\n\nFull step-by-step guide: link in bio.\n\n{DISCLAIMER}"
            rows.append({"id": f"{next_id:03d}", "product": product, "hook": it["hook"], "slides": " | ".join(it["slides"]),
                         "caption": caption, "hashtags": TAGS[product], "status": "unused", "posted_at": "", "media_id": ""})
            next_id += 1
            added += 1
    if added:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
    return added
