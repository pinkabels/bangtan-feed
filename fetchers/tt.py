# ----------------------------
# fetchers/tt.py
# ----------------------------

import json
import re
import subprocess

import requests

from services.logger import log


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/151.0.0.0 Safari/537.36"
)

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _extract_universal_data(html):
    """
    Extract TikTok's __UNIVERSAL_DATA_FOR_REHYDRATION__ JSON.
    """

    match = re.search(
        r'<script[^>]+id="__UNIVERSAL_DATA_FOR_REHYDRATION__"'
        r'[^>]*>(.*?)</script>',
        html,
        re.S,
    )

    if not match:
        raise ValueError(
            "TikTok page does not contain "
            "__UNIVERSAL_DATA_FOR_REHYDRATION__"
        )

    return json.loads(match.group(1))


def _get_video_item(data):
    """
    Extract the video item from TikTok's universal data.

    TikTok currently exposes video pages through:

        __DEFAULT_SCOPE__
          └── webapp.video-detail
                └── itemInfo
    """

    scope = data.get("__DEFAULT_SCOPE__", {})

    video_detail = scope.get("webapp.video-detail")

    if not isinstance(video_detail, dict):
        raise ValueError("TikTok video-detail data not found")

    item_info = video_detail.get("itemInfo")

    if not isinstance(item_info, dict):
        raise ValueError("TikTok itemInfo not found")

    # Usually:
    #
    # itemInfo:
    #   itemStruct: {...}
    #
    item = item_info.get("itemStruct")

    if isinstance(item, dict):
        return item

    # Be slightly defensive in case TikTok changes the nesting.
    for key, value in item_info.items():
        if isinstance(value, dict):
            if "id" in value:
                return value

    raise ValueError("TikTok video itemStruct not found")


def _make_post(item, username=None, fallback_url=None):
    """
    Convert TikTok's itemStruct into the format used by the bot.
    """

    video_id = str(item.get("id") or "")

    if not video_id:
        raise ValueError("TikTok video has no ID")

    author = item.get("author") or {}

    if not username:
        username = (
            author.get("uniqueId")
            or author.get("nickname")
            or ""
        )

    username = username.lstrip("@")

    video = item.get("video") or {}
    stats = item.get("stats") or {}
    music = item.get("music") or {}

    url = (
        fallback_url
        or item.get("shareUrl")
        or f"https://www.tiktok.com/@{username}/video/{video_id}"
    )

    # TikTok sometimes exposes downloadAddr/playAddr.
    video_url = (
        video.get("playAddr")
        or video.get("downloadAddr")
    )

    thumbnail = (
        video.get("cover")
        or video.get("originCover")
        or video.get("dynamicCover")
    )

    caption = (
        item.get("desc")
        or item.get("description")
        or ""
    )

    timestamp = item.get("createTime")

    if timestamp is not None:
        try:
            timestamp = int(timestamp)
        except (TypeError, ValueError):
            timestamp = None

    # Music title.
    music_name = (
        music.get("title")
        or ""
    )

    return {
        "post_id": video_id,
        "platform": "tiktok",
        "username": username,
        "caption": caption,
        "url": url,
        "thumbnail": thumbnail,
        "video_url": video_url,
        "views": (
            stats.get("playCount")
            or stats.get("viewCount")
            or 0
        ),
        "likes": (
            stats.get("diggCount")
            or stats.get("likeCount")
            or 0
        ),
        "comments": (
            stats.get("commentCount")
            or 0
        ),
        "shares": (
            stats.get("shareCount")
            or 0
        ),
        "saves": (
            stats.get("collectCount")
            or stats.get("saveCount")
            or 0
        ),
        "timestamp": timestamp,
        "music": music_name,
    }

def fetch_video(url):
    """
    Fetch a single TikTok video directly without yt-dlp.
    """
    video_id_match = re.search(r"/video/(\d+)", url)
    video_id = (
        video_id_match.group(1)
        if video_id_match
        else "unknown"
    )

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=30,
        )
        response.raise_for_status()

        data = _extract_universal_data(response.text)
        item = _get_video_item(data)

        post = _make_post(
            item,
            fallback_url=url,
        )

        log(
            f"TikTok direct video: "
            f"{post['post_id']} OK"
        )

        return post

    except requests.RequestException as e:
        log(
            f"TikTok direct video: "
            f"{video_id} request error: {e}"
        )
        return None

    except json.JSONDecodeError:
        log(
            f"TikTok direct video: "
            f"{video_id} invalid universal JSON"
        )
        return None

    except ValueError as e:
        log(
            f"TikTok direct video: "
            f"{video_id} {e}"
        )
        return None

    except Exception as e:
        log(
            f"TikTok direct video: "
            f"{video_id} unexpected error: {e}"
        )
        return None

def _get_video_ids_with_ytdlp(username):
    """
    Use yt-dlp ONLY as a video-ID discovery mechanism.

    We do not use yt-dlp to fetch the actual metadata.
    """

    url = f"https://www.tiktok.com/@{username}"

    try:
        result = subprocess.run(
            [
                "python",
                "-m",
                "yt_dlp",
                "-J",
                "--ignore-errors",
                "--playlist-end",
                "10",
                url,
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )

    except subprocess.TimeoutExpired:
        log(f"TikTok yt-dlp discovery timeout {username}")
        return []

    if not result.stdout.strip():
        log(f"TikTok yt-dlp returned no JSON for {username}")
        return []

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        log(f"TikTok yt-dlp returned invalid JSON for {username}")
        return []

    video_ids = []

    for entry in data.get("entries", []):
        if not entry:
            continue

        video_id = entry.get("id")

        if not video_id:
            continue

        video_ids.append(str(video_id))

    return video_ids


def fetch(username):
    """
    Fetch latest TikTok posts.

    yt-dlp is used only to discover recent video IDs.
    Each video is then fetched directly from TikTok.
    """

    username = username.lstrip("@")

    video_ids = _get_video_ids_with_ytdlp(username)

    if not video_ids:
        log(f"TikTok: no video IDs found for @{username}")
        return []

    log(
        f"TikTok @{username}: discovered "
        f"{len(video_ids)} video IDs: {', '.join(video_ids)}"
    )

    posts = []

    for video_id in video_ids:
        url = (
            f"https://www.tiktok.com/"
            f"@{username}/video/{video_id}"
        )

        post = fetch_video(url)

        if post:
            posts.append(post)

    return posts
