"""Upload a video with the YouTube Data API v3 (resumable upload, refresh-token auth)."""
import os

import requests

TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
REQUIRED = ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN")


def configured():
    return all(os.environ.get(k) for k in REQUIRED)


def access_token():
    r = requests.post(TOKEN_URL, data={
        "client_id": os.environ["YT_CLIENT_ID"],
        "client_secret": os.environ["YT_CLIENT_SECRET"],
        "refresh_token": os.environ["YT_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    }, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"OAuth token refresh failed: {r.status_code} {r.text}")
    return r.json()["access_token"]


def upload(path, title, description, tags, privacy="public"):
    """Upload the file and return the new video id."""
    headers = {"Authorization": f"Bearer {access_token()}"}
    body = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "tags": tags,
            "categoryId": "27",  # Education
            "defaultLanguage": "ja",
            "defaultAudioLanguage": "ja",
        },
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
    }
    size = os.path.getsize(path)
    start = requests.post(
        UPLOAD_URL, params={"uploadType": "resumable", "part": "snippet,status"},
        headers={**headers, "X-Upload-Content-Type": "video/mp4",
                 "X-Upload-Content-Length": str(size)},
        json=body, timeout=60)
    if start.status_code != 200:
        raise RuntimeError(f"Upload init failed: {start.status_code} {start.text}")
    with open(path, "rb") as f:
        done = requests.put(start.headers["Location"], data=f,
                            headers={**headers, "Content-Type": "video/mp4",
                                     "Content-Length": str(size)}, timeout=1800)
    if done.status_code not in (200, 201):
        raise RuntimeError(f"Upload failed: {done.status_code} {done.text}")
    return done.json()["id"]
