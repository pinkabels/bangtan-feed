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

        if "file" in kwargs:
            path = kwargs["file"].fp.name
            new_kwargs["file"] = discord.File(path)

        elif "files" in kwargs:
            new_kwargs["files"] = [
                discord.File(path)
                for path in (
                    file.fp.name
                    for file in kwargs["files"]
                )
            ]

        webhook.send(**new_kwargs)

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
    video_path = None
    image_paths = []
    thumbnail_path = None

    if media:
        first = media[0]

        if first.get("is_video"):
            video_url = first.get("video_url")

            if video_url:
                response = requests.get(
                    video_url,
                    timeout=60
                )

                response.raise_for_status()

                with tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix=".mp4"
                ) as f:
                    f.write(response.content)
                    video_path = f.name

            description += "\n\n🎬 Video/Reel"

        else:
            for item in media[:10]:
                if item.get("is_video"):
                    continue

                image_url = item.get("url")
                if not image_url:
                    continue

                response = requests.get(
                    image_url,
                    timeout=60,
                )
                response.raise_for_status()

                with tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix=".jpg",
                ) as f:
                    f.write(response.content)
                    image_paths.append(f.name)

    link = f"\n\n{post['url']}"
    description = description[:4096 - len(link)] + link

    embed = discord.Embed(
        description=description,
        color=0xd58af4,
    )

    embed.set_author(
        name=f"{post['username']}",
        url=post["url"],
        icon_url="https://raw.githubusercontent.com/pinkabels/bangtan-feed/main/assets/logo-instagram.png"
    )

    if post.get("timestamp"):
        dt = datetime.fromtimestamp(
            post["timestamp"],
            tz=timezone.utc
        ).astimezone(KST)

        embed.set_footer(
            text=(
                f"Instagram • "
                f"{dt:%Y-%m-%d at %H:%M} "
                f"{dt.tzname()} • pinkabels 💗"
            )
        )

    try:
        if video_path:
            try:
                send_to_all(
                    embed=embed,
                    file=discord.File(video_path)
                )
            except discord.HTTPException as e:
                log(f"Discord upload failed: {e}")

                # Video too large: show the thumbnail instead.
                if media:
                    thumbnail_url = media[0]["url"]

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

                try:
                    if thumbnail_path:
                        send_to_all(
                            embed=embed,
                            files=[
                                discord.File(thumbnail_path),
                            ],
                        )
                    else:
                        send_to_all(embed=embed)

                    log("[INFO] Sent thumbnail fallback.")
                except Exception:
                    import traceback
                    log(traceback.format_exc())

        elif image_paths:
            send_to_all(
                embed=embed,
                files=[
                    discord.File(path)
                    for path in image_paths
                ],
            )
        else:
            send_to_all(embed=embed)                    

    finally:
        if video_path:
            os.remove(video_path)

        for path in image_paths:
            os.remove(path)

        if thumbnail_path:
            os.remove(thumbnail_path)
