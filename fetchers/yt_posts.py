# ----------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 pinkabels
# ----------------------------
# fetchers/yt_posts.py
# ----------------------------
import json
import re
import subprocess
from services.logger import log


def _walk(obj):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from _walk(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk(item)


def fetch(handle):
    url = f"https://www.youtube.com/@{handle}/posts"

    cmd = [
        "curl",
        "-Ls",
        "-H", "User-Agent: Mozilla/5.0",
        url,
    ]

    try:
        html = subprocess.check_output(
            cmd,
            timeout=30,
            text=True,
        )
    except Exception as e:
        log(f"YouTube Posts error {handle}: {e}")
        return []

    m = re.search(
        r"var ytInitialData = (.*?);</script>",
        html,
        re.S,
    )

    if not m:
        log(f"Couldn't find ytInitialData for {handle}")
        return []

    try:
        data = json.loads(m.group(1))
    except Exception as e:
        log(f"Failed to parse ytInitialData: {e}")
        return []

    posts = []

    for node in _walk(data):
        renderer = node.get("backstagePostRenderer")

        if not renderer:
            continue

        post_id = renderer.get("postId")

        if not post_id:
            continue

        text = ""

        content = renderer.get(
            "contentText",
            {}
        )

        for run in content.get("runs", []):
            text += run.get("text", "")

        published = (
            renderer.get(
                "publishedTimeText",
                {}
            ).get(
                "simpleText",
                ""
            )
        )

        attachment_type = None
        video_url = None
        image_url = None

        attachment = renderer.get(
            "backstageAttachment",
            {}
        )

        # ----------------------------
        # Video attachment
        # ----------------------------
        video = attachment.get(
            "videoRenderer"
        )

        if video:
            video_id = video.get(
                "videoId"
            )

            if video_id:
                attachment_type = "video"
                video_url = (
                    f"https://youtu.be/{video_id}"
                )

        # ----------------------------
        # Image attachment
        # ----------------------------
        if not attachment_type:
            image = attachment.get(
                "backstageImageRenderer"
            )

            if image:
                thumbnails = (
                    image.get(
                        "image",
                        {}
                    )
                    .get(
                        "thumbnails",
                        []
                    )
                )

                if thumbnails:
                    attachment_type = "image"
                    image_url = thumbnails[-1].get(
                        "url"
                    )

        if video_url and f"({video_url})" not in text and video_url not in text:
            text += f"\n{video_url}"

        posts.append({
            "platform": "youtube_posts",
            "username": handle,
            "post_id": post_id,
            "url": f"https://www.youtube.com/post/{post_id}",
            "header": (f"📺 **BANGTANTV** just posted this:"),
            "caption": text,
            "video_url": video_url,
            "image_url": image_url,
            "attachment_type": attachment_type,
            "media": [],
            "timestamp": published,
        })

    return posts


def latest_post(handle):
    posts = fetch(handle)
    return posts[0] if posts else None
