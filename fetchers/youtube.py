# ----------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 pinkabels
# ----------------------------
# fetchers/youtube.py
# ----------------------------
import feedparser


def fetch(channel_id):
    feed = feedparser.parse(
        "https://www.youtube.com/feeds/videos.xml"
        f"?channel_id={channel_id}"
    )

    posts = []

    for entry in feed.entries[:5]:
        posts.append({
            "post_id": entry.yt_videoid,
            "url": entry.link,
            "channel": entry.author,
            "title": entry.title,
            "header": (
                f"📺 **{entry.author}** "
                f"just uploaded a new video!"
            ),
        })

    return posts


def latest_post(channel_id):
    posts = fetch(channel_id)
    return posts[0] if posts else None
