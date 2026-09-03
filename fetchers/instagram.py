# ----------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 pinkabels
# ----------------------------
# fetchers/instagram.py
# ----------------------------
import json
import subprocess
from services.logger import log


def best_image_url(media):
    candidates = (
        media.get("image_versions2", {})
        .get("candidates", [])
    )

    if not candidates:
        return media.get("display_uri")

    return max(
        candidates,
        key=lambda item: (
            item.get("width", 0) * item.get("height", 0)
        ),
    ).get("url")


def video_url(media):
    versions = media.get("video_versions", [])

    if not versions:
        return None

    # Instagram currently returns multiple encodings
    # at the same resolution. Use the first standard variant.
    return versions[0].get("url")


def make_media(media):
    videos = media.get("video_versions", [])

    if videos:
        return {
            "url": best_image_url(media),
            "video_url": video_url(media),
            "is_video": True,
        }

    return {
        "url": best_image_url(media),
        "video_url": None,
        "is_video": False,
    }


def fetch(username):
    url = (
        "https://www.instagram.com/api/v1/"
        f"feed/user/{username}/username/?count=10"
    )

    cmd = [
        "curl",
        "-s",
        "-H", "User-Agent: Mozilla/5.0",
        "-H", "X-IG-App-ID: 936619743392459",
        "-H", "Referer: https://www.instagram.com/",
        url,
    ]

    try:
        out = subprocess.check_output(
            cmd,
            timeout=30,
        )
        data = json.loads(out)

    except Exception as e:
        log(f"Instagram error {username}: {e}")
        return []

    if "items" not in data:
        log(f"Instagram returned an unexpected response for {username}:")
        log("Response:")
        log(json.dumps(data, indent=2)[:1000])
        return []

    posts = []

    for item in data.get("items", [])[:10]:
        shortcode = item.get("code")

        if not shortcode:
            continue

        caption_data = item.get("caption")
        caption = ""

        if isinstance(caption_data, dict):
            caption = caption_data.get("text", "")
        elif isinstance(caption_data, str):
            caption = caption_data

        carousel = item.get("carousel_media", [])

        if carousel:
            media = [
                make_media(child)
                for child in carousel
            ]
        else:
            media = [
                make_media(item)
            ]

        posts.append({
            "platform": "instagram",
            "username": username,
            "post_id": shortcode,
            "url": (
                f"https://www.instagram.com/p/"
                f"{shortcode}/"
            ),
            "caption": caption,
            "media": media,
            "timestamp": item.get("taken_at"),
        })

    return posts


def latest_post(username):
    posts = fetch(username)
    return posts[0] if posts else None
