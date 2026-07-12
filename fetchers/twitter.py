# ----------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 pinkabels
# ----------------------------
# fetchers/twitter.py
# ----------------------------
import re
import feedparser


def fetch(username):
    feed = feedparser.parse(
        f"https://fxtwitter.com/{username}/feed.xml"
    )

    posts = []

    for entry in feed.entries[:5]:
        media = []

        for link in entry.get("links", []):
            if link.get("rel") == "enclosure":
                media.append({
                    "url": link["href"],
                    "type": link.get("type"),
                })

        for url in re.findall(
            r'https://pbs\.twimg\.com/media/[^"]+\?name=orig',
            entry.summary,
        ):
            if not any(
                m["url"] == url
                for m in media
            ):
                media.append({
                    "url": url,
                    "type": "image/jpeg",
                })

        tweet_id = entry.link.rsplit("/", 1)[-1]

        posts.append({
            "post_id": tweet_id,
            "url": (
                f"https://fxtwitter.com/"
                f"{username}/status/{tweet_id}"
            ),
        })

    return posts


def latest_post(username):
    posts = fetch(username)
    return posts[0] if posts else None
