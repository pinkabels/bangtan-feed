# ----------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 pinkabels
# ----------------------------
# services/webhook.py
# ----------------------------
import os
import tempfile
import requests
import discord
import subprocess
from services.logger import log
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

KST = timezone(
    timedelta(hours=9),
    "UTC+9"
)

WEBHOOKS = [
    discord.SyncWebhook.from_url(url.strip())
    for url in os.getenv("WEBHOOKS", "").split(",")
    if url.strip()
]

if not WEBHOOKS:
    raise RuntimeError("WEBHOOKS is not configured.")


def send_to_all(**kwargs):
    for webhook in WEBHOOKS:
        new_kwargs = kwargs.copy()
        files_to_close = []

        if "file" in kwargs:
            path = kwargs["file"].fp.name
            new_kwargs["file"] = discord.File(path)
            files_to_close.append(new_kwargs["file"])

        elif "files" in kwargs:
            new_kwargs["files"] = [
                discord.File(file.fp.name)
                for file in kwargs["files"]
            ]
            files_to_close.extend(new_kwargs["files"])

        try:
            webhook.send(**new_kwargs)
        finally:
            for discord_file in files_to_close:
                discord_file.close()

def notify(post):
    if "caption" not in post:
        content = post.get("url")

        if "header" in post:
            content = f"{post['header']}\n{post['url']}"

        send_to_all(content=content)
        return

    if post.get("platform") == "youtube_posts":
        content = (
            f"{post['header']}\n\n"
            f"{post['caption']}"
        )

        if post.get("timestamp"):
            content += (
                "\n────────────────\n"
                f"{post['timestamp']}"
            )

        if post.get("image_url") and content:
            embed = discord.Embed(
                color=0xd58af4,
            )
            embed.set_image(
                url=post["image_url"]
            )
            send_to_all(content=content, embed=embed)
        else:
            send_to_all(content=content)

        return

    if post.get("platform") == "tiktok":
        link = f"\n\n{post['url']}"
        embed = discord.Embed(
            description=(
                f"{post['caption'][:4096 - len(link)]}"
                f"{link}"
            ),
            color=0x25F4EE,
        )

        embed.set_author(
            name=f"@{post['username']}",
            url=post["url"],
            icon_url="https://raw.githubusercontent.com/pinkabels/bangtan-feed/main/assets/logo-tiktok.png"
        )

        if post.get("timestamp"):
            dt = datetime.fromtimestamp(
                post["timestamp"],
                tz=timezone.utc
            ).astimezone(KST)

            embed.set_footer(
                text=(
                    f"TikTok • "
                    f"{dt:%Y-%m-%d at %H:%M} "
                    f"{dt.tzname()} • pinkabels 💗"
                )
            )

        video_path = None
        thumbnail_path = None

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                subprocess.run(
                    [
                        "python",
                        "-m",
                        "yt_dlp",
                        "--quiet",
                        "--no-warnings",
                        "-o",
                        f"{tmpdir}/%(id)s.%(ext)s",
                        post["url"],
                    ],
                    check=True,
                    timeout=120,
                    capture_output=True,
                    text=True,
                )

                downloaded = next(
                    os.path.join(tmpdir, f)
                    for f in os.listdir(tmpdir)
                    if f.endswith(".mp4")
                )

                with tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix=".mp4",
                ) as f:
                    video_path = f.name

                os.replace(
                    downloaded,
                    video_path,
                )
            try:
                send_to_all(
                    embed=embed,
                    file=discord.File(video_path),
                )

            except discord.HTTPException as e:
                log(f"Discord upload failed: {e}")
                # Discord upload failed, fallback thumbnail
                if post.get("thumbnail"):
                    response = requests.get(
                        post["thumbnail"],
                        timeout=60,
                    )
                    response.raise_for_status()

                    with tempfile.NamedTemporaryFile(
                        delete=False,
                        suffix=".jpg",
                    ) as f:
                        f.write(response.content)
                        thumbnail_path = f.name

                if thumbnail_path:
                    send_to_all(
                        embed=embed,
                        file=discord.File(thumbnail_path),
                    )
                    log("[INFO] Sent thumbnail fallback.")
                else:
                    send_to_all(embed=embed)

        finally:
            if video_path:
                os.remove(video_path)
            if thumbnail_path:
                os.remove(thumbnail_path)

        return

    description = post["caption"]
    media = post.get("media", [])
    media_paths = []
    fallback_thumbnail_paths = []
    downloaded_media = []

    from fetchers.instagram import resolve_video_url

    try:
        # Download up to 10 items, preserving carousel order.
        for item in media[:10]:
            is_video = item.get("is_video", False)
            media_url = (
                item.get("video_url")
                if is_video
                else item.get("url")
            )

            if is_video and not media_url:
                media_url = resolve_video_url(
                    item.get("shortcode")
                )

            if not media_url:
                log(
                    "Instagram media skipped: "
                    f"no usable URL for {item.get('shortcode')}"
                )
                continue

            try:
                response = requests.get(
                    media_url,
                    timeout=60,
                )
                response.raise_for_status()

                suffix = ".mp4" if is_video else ".jpg"
                with tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix=suffix,
                ) as f:
                    f.write(response.content)
                    path = f.name

                media_paths.append(path)
                downloaded_media.append((item, path, is_video))

            except Exception as exc:
                log(
                    "Instagram media download failed "
                    f"for {item.get('shortcode')}: {exc}"
                )

        if any(is_video for _, _, is_video in downloaded_media):
            description += "\n\n🎬 Video/Reel"

        # Preserve the existing embed formatting.
        link = f"\n\n{post['url']}"
        description = description[:4096 - len(link)] + link

        embed = discord.Embed(
            description=description,
            color=0xd58af4,
        )
        embed.set_author(
            name=f"{post['username']}",
            url=post["url"],
            icon_url=(
                "https://raw.githubusercontent.com/pinkabels/"
                "bangtan-feed/main/assets/logo-instagram.png"
            ),
        )

        if post.get("timestamp"):
            dt = datetime.fromtimestamp(
                post["timestamp"],
                tz=timezone.utc,
            ).astimezone(KST)

            embed.set_footer(
                text=(
                    f"Instagram • "
                    f"{dt:%Y-%m-%d at %H:%M} "
                    f"{dt.tzname()} • pinkabels 💗"
                )
            )

        if not downloaded_media:
            send_to_all(embed=embed)
        else:
            discord_files = []
            try:
                discord_files = [
                    discord.File(path)
                    for _, path, _ in downloaded_media
                ]
                send_to_all(
                    embed=embed,
                    files=discord_files,
                )

            except discord.HTTPException as exc:
                log(f"Discord carousel upload failed: {exc}")

                # Retry with images and video thumbnails in carousel order.
                fallback_paths = []

                for item, path, is_video in downloaded_media:
                    if not is_video:
                        fallback_paths.append(path)
                        continue

                    thumbnail_url = item.get("url")
                    if not thumbnail_url:
                        continue

                    try:
                        response = requests.get(
                            thumbnail_url,
                            timeout=60,
                        )
                        response.raise_for_status()

                        with tempfile.NamedTemporaryFile(
                            delete=False,
                            suffix=".jpg",
                        ) as f:
                            f.write(response.content)
                            thumbnail_path = f.name

                        fallback_thumbnail_paths.append(thumbnail_path)
                        fallback_paths.append(thumbnail_path)

                    except Exception as fallback_exc:
                        log(
                            "Instagram video thumbnail download failed: "
                            f"{fallback_exc}"
                        )

                fallback_files = []
                try:
                    if fallback_paths:
                        fallback_files = [
                            discord.File(path)
                            for path in fallback_paths
                        ]
                        send_to_all(
                            embed=embed,
                            files=fallback_files,
                        )
                        log("[INFO] Sent Instagram media fallback.")
                    else:
                        send_to_all(embed=embed)

                except Exception as fallback_exc:
                    log(
                        "Instagram media fallback failed: "
                        f"{fallback_exc}"
                    )

                finally:
                    for discord_file in fallback_files:
                        discord_file.close()

            finally:
                for discord_file in discord_files:
                    discord_file.close()

    finally:
        for path in media_paths + fallback_thumbnail_paths:
            if os.path.exists(path):
                os.remove(path)
