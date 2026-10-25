"""Publish a Reel through the Instagram API with Instagram Login.

Needs two secrets: IG_USER_ID and IG_ACCESS_TOKEN (an Instagram User access token
with the instagram_business_basic and instagram_business_content_publish permissions).
The video must be reachable at a public HTTPS URL.
"""
import os
import time
import requests

GRAPH = "https://graph.instagram.com/v21.0"


class PublishError(RuntimeError):
    pass


def _check(r):
    try:
        data = r.json()
    except Exception:
        raise PublishError(f"Non-JSON response {r.status_code}: {r.text[:300]}")
    if r.status_code >= 400 or "error" in data:
        raise PublishError(f"Instagram API error {r.status_code}: {data}")
    return data


def publish_reel(video_url, caption, user_id=None, token=None, timeout_s=300):
    user_id = user_id or os.environ["IG_USER_ID"]
    token = token or os.environ["IG_ACCESS_TOKEN"]

    # 1. create container
    r = requests.post(
        f"{GRAPH}/{user_id}/media",
        data={"media_type": "REELS", "video_url": video_url, "caption": caption, "share_to_feed": "true",
              "access_token": token},
        timeout=60,
    )
    container = _check(r)["id"]

    # 2. wait until processing finishes
    start = time.time()
    while True:
        r = requests.get(f"{GRAPH}/{container}", params={"fields": "status_code,status", "access_token": token}, timeout=60)
        st = _check(r)
        code = st.get("status_code")
        if code == "FINISHED":
            break
        if code in ("ERROR", "EXPIRED"):
            raise PublishError(f"Container failed: {st}")
        if time.time() - start > timeout_s:
            raise PublishError(f"Timed out waiting for processing: {st}")
        time.sleep(10)

    # 3. publish
    r = requests.post(f"{GRAPH}/{user_id}/media_publish", data={"creation_id": container, "access_token": token}, timeout=60)
    return _check(r)["id"]


def refresh_token(token):
    """Long-lived Instagram tokens last 60 days; this returns a fresh one (valid to refresh after 24h)."""
    r = requests.get("https://graph.instagram.com/refresh_access_token",
                     params={"grant_type": "ig_refresh_token", "access_token": token}, timeout=60)
    return _check(r)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "refresh":
        out = refresh_token(os.environ["IG_ACCESS_TOKEN"])
        print("New token expires in", out.get("expires_in"), "seconds")
        print(out["access_token"])
