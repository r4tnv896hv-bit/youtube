"""Publish the next unpublished episode: render -> upload -> record in published.json.

Without YouTube credentials it only renders (dry run) and records nothing, so
the same episode is retried once credentials exist.
"""
import datetime
import json
import os
import sys
from pathlib import Path

import make_video
import upload

HERE = Path(__file__).parent
EPISODES = HERE / "episodes.json"
PUBLISHED = HERE / "published.json"
LOW_QUEUE = 5


def main():
    episodes = json.loads(EPISODES.read_text(encoding="utf-8"))
    published = json.loads(PUBLISHED.read_text(encoding="utf-8"))
    done = {p["id"] for p in published}
    queue = [e for e in episodes if e["id"] not in done]
    if not queue:
        print("::warning::Episode queue is empty - add episodes to autotube/episodes.json")
        return 0
    if len(queue) <= LOW_QUEUE:
        print(f"::warning::Only {len(queue)} episodes left in autotube/episodes.json")

    ep = queue[0]
    out = HERE / "out" / f"{ep['id']}.mp4"
    duration, voice = make_video.render(ep, out)
    print(f"Rendered {out} ({duration:.1f}s, voice: {voice})")
    if duration > 60:
        print(f"::warning::Episode {ep['id']} is {duration:.0f}s; consider shortening it")

    if not upload.configured():
        print("::notice::YouTube secrets are not set - rendered only, nothing uploaded")
        return 0

    title = f"{ep['hook']} #Shorts #雑学 #科学"
    description = "\n".join([
        ep["hook"], "", *ep["lines"], "",
        f"毎日ひとつ、科学の雑学を短くお届けする「{make_video.CHANNEL}」です。",
        f"音声: {voice}",
        "この動画は自動生成された合成音声を使用しています。",
        "", "#Shorts #雑学 #科学 #豆知識",
    ])
    video_id = upload.upload(out, title, description,
                             ep.get("tags", []) + ["雑学", "科学", "豆知識", "Shorts"],
                             privacy=os.environ.get("YT_PRIVACY") or "public")
    print(f"Uploaded https://youtube.com/shorts/{video_id}")

    published.append({"id": ep["id"], "videoId": video_id,
                      "publishedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")})
    PUBLISHED.write_text(json.dumps(published, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
