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
        if "file" in kwargs:
            path = kwargs["file"].fp.name

            new_kwargs = kwargs.copy()
            new_kwargs["file"] = discord.File(path)

            webhook.send(**new_kwargs)
        else:
            webhook.send(**kwargs)


def notify(post):
    if "caption" not in post:
        content = post.get("url")

        if "header" in post:
            content = f"{post['header']}\n{post['url']}"

        send_to_all(content=content)
        return

    embed = discord.Embed(
        title=f"@{post['username']}",
        url=post["url"],
        description=post["caption"][:4000],
        color=0xd58af4,
    )

    media = post.get("media", [])
    video_path = None

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

            embed.description += (
                "\n\n🎬 Video/Reel"
            )

        else:
            embed.set_image(
                url=first["url"]
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
                f"{dt.tzname()}"
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
                print(f"Discord upload failed: {e}")

                # Video too large: show the thumbnail instead.
                if media:
                    embed.set_image(url=media[0]["url"])
                try:
                    send_to_all(embed=embed)
                    print("[INFO] Sent thumbnail fallback.")
                except Exception:
                    import traceback
                    traceback.print_exc()
        else:
            send_to_all(embed=embed)

    finally:
        if video_path:
            os.remove(video_path)
