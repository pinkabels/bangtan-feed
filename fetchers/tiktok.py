# ----------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 pinkabels
# ----------------------------
# fetchers/tiktok.py
# ----------------------------
import json
import subprocess

from services.logger import log


def fetch(username):
    """
    Fetch latest TikTok posts using yt-dlp JSON output.
    """

    url = f"https://www.tiktok.com/@{username}"

    try:
        result = subprocess.run(
            [
                "python",
                "-m",
                "yt_dlp",
                "-J",
                "--playlist-end",
                "5",
                url,
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=120,
        )

        data = json.loads(result.stdout)

    except subprocess.CalledProcessError as e:
        log(f"TikTok error {username}:")
        log(e.stderr or str(e))
        return []

    except subprocess.TimeoutExpired:
        log(f"TikTok timeout {username}")
        return []

    except json.JSONDecodeError:
        log(f"TikTok returned invalid JSON for {username}")
        return []

    entries = data.get("entries", [])

    posts = []

    for item in entries:
        video_id = item.get("id")

        if not video_id:
            continue

        posts.append(
            {
                "post_id": video_id,
                "platform": "tiktok",
                "username": username,
                "caption": (
                    item.get("title")
                    or item.get("description")
                    or ""
                ),
                "url": item.get(
                    "webpage_url",
                    f"https://www.tiktok.com/@{username}/video/{video_id}",
                ),
                "thumbnail": item.get("thumbnail"),
                "views": item.get(
                    "view_count",
                    0,
                ),
                "likes": item.get(
                    "like_count",
                    0,
                ),
                "comments": item.get(
                    "comment_count",
                    0,
                ),
                "shares": (
                    item.get("share_count")
                    or item.get("repost_count")
                    or 0
                ),
                "saves": item.get(
                    "save_count",
                    0,
                ),
                "timestamp": item.get(
                    "timestamp"
                ),
                "music": item.get(
                    "track"
                ),
            }
        )

    return posts
