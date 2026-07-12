# ----------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 pinkabels
# ----------------------------
# fetchers/instagram.py
# ----------------------------
import json
import subprocess


def fetch(username):
    url = (
        "https://i.instagram.com/api/v1/"
        f"users/web_profile_info/?username={username}"
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
        print(
            f"Instagram error {username}: {e}"
        )
        return []

    if "data" not in data:
        print(
            f"\nInstagram returned an unexpected response for {username}:"
        )
        print(
            json.dumps(
                data,
                indent=2
            )[:1000]
        )
        return []

    user = data["data"].get("user")

    if not user:
        print(
            f"\nInstagram returned no user object for {username}:"
        )
        print(
            json.dumps(
                data,
                indent=2
            )[:1000]
        )
        return []

    edges = (
        user["edge_owner_to_timeline_media"]
        ["edges"]
    )

    posts = []

    for edge in edges[:5]:
        node = edge["node"]

        sidecar = (
            node.get(
                "edge_sidecar_to_children",
                {}
            ).get(
                "edges",
                []
            )
        )

        caption = ""

        caption_edges = (
            node.get(
                "edge_media_to_caption",
                {}
            ).get(
                "edges",
                []
            )
        )

        if caption_edges:
            caption = (
                caption_edges[0]
                ["node"]
                ["text"]
            )

        media = []

        if sidecar:
            for item in sidecar:
                child = item["node"]
                media.append({
                    "url": child.get("display_url"),
                    "video_url": child.get("video_url"),
                    "is_video": child.get(
                        "is_video",
                        False,
                    ),
                })
        else:
            media.append({
                "url": node.get("display_url"),
                "video_url": node.get("video_url"),
                "is_video": node.get(
                    "is_video",
                    False,
                ),
            })

        posts.append({
            "platform": "instagram",
            "username": username,
            "post_id": node["shortcode"],
            "url": (
                f"https://www.instagram.com/p/"
                f"{node['shortcode']}/"
            ),
            "caption": caption,
            "media": media,
            "timestamp": node.get(
                "taken_at_timestamp"
            ),
        })

    return posts


def latest_post(username):
    posts = fetch(username)
    return posts[0] if posts else None
