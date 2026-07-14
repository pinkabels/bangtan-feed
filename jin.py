# ----------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 pinkabels
# ----------------------------
# jin.py (entry point)
# ----------------------------
import yaml
import time
import random
from datetime import datetime
from services.webhook import notify
from services.db import (
    init,
    add_account,
    get_accounts,
    get_last_post,
    set_last_post,
    has_seen_post,
    mark_seen_post,
)
from fetchers.instagram import fetch as fetch_instagram
from fetchers.twitter import fetch as fetch_twitter
from fetchers.youtube import fetch as fetch_youtube


def log(message):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] {message}")

def check_accounts():
    init()

    with open("config.yaml") as f:
        config = yaml.safe_load(f)

    log("=== Poll started ===")

    accounts = []

    for user in config.get("instagram", []):
        accounts.append(
            ("instagram", user)
        )

    for user in config.get("twitter", []):
        accounts.append(
            ("twitter", user)
        )

    for channel in config.get("youtube", []):
        accounts.append(
            ("youtube", channel)
        )

    random.shuffle(accounts)

    for platform, username in accounts:
        add_account(
            f"{platform}:{username}"
        )

    log("Configured accounts:")

    for platform, username in accounts:
        log(f" • {platform:<10} {username}")

    log("Database contents:")

    for row in get_accounts():
        log(str(row))

    for platform, username in accounts:

        if platform == "instagram":
            posts = fetch_instagram(username)
            time.sleep(random.randint(8, 15))

        elif platform == "twitter":
            posts = fetch_twitter(username)

        elif platform == "youtube":
            posts = fetch_youtube(username)

        else:
            continue

        if not posts:
            continue

        key = f"{platform}:{username}"

        previous = get_last_post(key)
        new_found = False

        for post in reversed(posts):

            if has_seen_post(key, post["post_id"]):
                continue

            new_found = True

            if previous is None:
                log(
                    f"[INIT] {username}: "
                    f"{post['post_id']}"
                )
            else:
                log(f"[NEW] {username}")
                log(post["url"])
                notify(post)

            mark_seen_post(
                key,
                post["post_id"],
            )

        set_last_post(
            key,
            posts[0]["post_id"],
        )

        if not new_found:
            log(f"[OK] {username} unchanged")

    log("=== Poll finished ===")
    log("=" * 60)

if __name__ == "__main__":
    with open("config.yaml") as f:
        config = yaml.safe_load(f)

    interval = config.get("poll_interval", 600)

    while True:
        check_accounts()
        time.sleep(interval)
