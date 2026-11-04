# ----------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 pinkabels
# ----------------------------
# fetchers/instagram.py
# ----------------------------
import json
import re
import subprocess
import requests

from services.logger import log


def _decode_embedded(value):
    """Decode escaped slashes and Unicode in Instagram's embedded data."""
    if not isinstance(value, str):
        return value

    value = value.replace(r"\/", "/")

    # Decode Unicode escapes, including UTF-16 surrogate pairs.
    pattern = re.compile(
        r"\\u([0-9a-fA-F]{4})(?:\\u([0-9a-fA-F]{4}))?"
    )

    def replace_escape(match):
        first = int(match.group(1), 16)
        second_text = match.group(2)

        if (
            second_text
            and 0xD800 <= first <= 0xDBFF
        ):
            second = int(second_text, 16)
            if 0xDC00 <= second <= 0xDFFF:
                return chr(
                    0x10000
                    + ((first - 0xD800) << 10)
                    + (second - 0xDC00)
                )

        result = chr(first)

        if second_text:
            result += chr(int(second_text, 16))

        return result

    return pattern.sub(replace_escape, value)

def _parse_embed_html(html):
    """Extract recent post records from a public Instagram embed page."""
    marker = r'graphql_media\":['
    pos = html.find(marker)

    if pos < 0:
        raise ValueError("graphql_media data not found in embed HTML")

    script_start = html.rfind("<script", 0, pos)

    if script_start < 0:
        raise ValueError("Containing script not found")

    # Locate the JavaScript string containing graphql_media.
    in_string = False
    escaped = False
    quote_start = None

    for i in range(script_start, pos + len(marker)):
        char = html[i]

        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
            quote_start = i

    if not in_string or quote_start is None:
        raise ValueError("Containing JavaScript string not found")

    # Locate the end of that string.
    escaped = False
    quote_end = None

    for i in range(pos + len(marker), len(html)):
        char = html[i]

        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == '"':
            quote_end = i
            break

    if quote_end is None:
        raise ValueError("Containing JavaScript string is unterminated")

    # Decode the complete serialized payload.
    try:
        payload = json.loads(html[quote_start:quote_end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Could not decode Instagram payload: {exc}"
        ) from exc

    # graphql_media may be nested inside JSON-encoded context strings.
    def find_media(value, depth=0):
        if depth > 8:
            return None

        if isinstance(value, dict):
            entries = value.get("graphql_media")

            if isinstance(entries, list):
                return entries

            for child in value.values():
                result = find_media(child, depth + 1)
                if result is not None:
                    return result

        elif isinstance(value, list):
            for child in value:
                result = find_media(child, depth + 1)
                if result is not None:
                    return result

        elif isinstance(value, str):
            try:
                decoded = json.loads(value)
            except (ValueError, TypeError):
                return None

            if decoded == value:
                return None

            return find_media(decoded, depth + 1)

        return None

    entries = find_media(payload)

    if entries is None:
        raise ValueError("graphql_media not found in decoded Instagram payload")

    posts = []

    for entry in entries[:10]:
        if not isinstance(entry, dict):
            continue

        item = entry.get("shortcode_media", {})

        if not isinstance(item, dict):
            continue

        shortcode = item.get("shortcode")

        if not shortcode:
            continue

        caption_edges = (
            item.get("edge_media_to_caption", {})
            .get("edges", [])
        )
        caption = ""

        if caption_edges:
            caption = caption_edges[0].get("node", {}).get("text", "")

        caption = _decode_embedded(caption)
        caption = caption.replace(r"\n", "\n")

        children = (
            item.get("edge_sidecar_to_children", {})
            .get("edges", [])
        )

        media_items = (
            [child.get("node", {}) for child in children]
            if children
            else [item]
        )

        media = []

        for child in media_items:
            image_url = _decode_embedded(child.get("display_url"))
            raw_video_url = child.get("video_url")
            resolved_video_url = _decode_embedded(raw_video_url)

            media.append({
                "url": image_url,
                "video_url": resolved_video_url,
                "shortcode": child.get("shortcode"),
                "is_video": bool(child.get("is_video")),
            })

        posts.append({
            "platform": "instagram",
            "username": None,
            "post_id": shortcode,
            "url": f"https://www.instagram.com/p/{shortcode}/",
            "caption": caption,
            "media": media,
            "timestamp": item.get("taken_at_timestamp"),
        })

    return posts

def resolve_video_url(shortcode):
    """Resolve a video's MP4 URL from its individual Instagram embed."""
    if not shortcode:
        return None

    url = f"https://www.instagram.com/p/{shortcode}/embed/"

    try:
        response = requests.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://www.instagram.com/",
            },
            timeout=30,
        )
        response.raise_for_status()

        match = re.search(
            r'video_url\\":\\"(.*?)\\"',
            response.text,
        )
        if not match:
            log(f"Instagram video URL not found for {shortcode}")
            return None

        video_url = re.sub(r"\\+/", "/", match.group(1))

        if (
            not video_url.startswith("https://")
            or not video_url.split("?", 1)[0].endswith(".mp4")
        ):
            log(f"Invalid Instagram video URL for {shortcode}")
            return None

        return video_url

    except Exception as exc:
        log(f"Instagram video resolution failed for {shortcode}: {exc}")
        return None

def fetch(username):
    url = f"https://www.instagram.com/{username}/embed/"

    cmd = [
        "curl",
        "-4",
        "-fsS",
        "--max-time", "30",
        "-A", "Mozilla/5.0",
        "-H", "Referer: https://www.instagram.com/",
        url,
    ]

    try:
        out = subprocess.check_output(cmd, timeout=35)
        html = out.decode("utf-8", errors="replace")
        posts = _parse_embed_html(html)

    except Exception as exc:
        log(f"Instagram embed error {username}: {exc}")
        return []

    # Set the requested username on every normalized post.
    for post in posts:
        post["username"] = username

    if not posts:
        log(f"Instagram embed returned no usable posts for {username}")

    return posts


def latest_post(username):
    posts = fetch(username)
    return posts[0] if posts else None
