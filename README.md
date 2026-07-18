# 💜 bangtan-feed

A lightweight Python bot that monitors BTS members' official social media accounts and sends new posts to Discord using a webhook.

## Currently supported platforms

- Instagram
- X (via fxtwitter RSS)
- YouTube videos
- YouTube Community posts
- TikTok (with native video uploads)

The bot remembers previously seen posts using SQLite so duplicate notifications are never sent.

## Features

- Monitor multiple Instagram accounts
- Monitor multiple X accounts
- Monitor multiple YouTube channels
- Monitor multiple TikTok accounts
- Send rich Discord webhook notifications
- Rich embeds for Instagram and TikTok posts
- Automatically falls back to thumbnails when Instagram/TikTok videos exceed Discord's upload limit
- Prevent duplicate notifications with SQLite
- Randomize polling order to reduce rate limiting
- Configurable polling interval
- Simple YAML configuration

## Requirements

- Python 3.11 or newer
- SQLite
- yt-dlp (for TikTok)
- A Discord webhook

## Installation

Clone the repository:

```bash
git clone git@github.com:pinkabels/bangtan-feed.git
cd bangtan-feed
mkdir data
```

Create a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r req.txt
```

Copy the example file:

```bash
cp .env.example .env
```
Edit `.env` and define your Discord webhooks.

Logger:
```bash
mkdir logs
```

## Running

```bash
chmod +x bangtan.sh
```
```bash
./bangtan.sh
```

## Project Structure

```text
bangtan-feed/
├── data/
│   └── social.db
├── fetchers/
│   ├── instagram.py
│   ├── tiktok.py
│   ├── twitter.py
│   ├── youtube.py
│   └── yt_posts.py
├── logs/
│   └── BTS.log
├── services/
│   ├── db.py
│   ├── logger.py
│   └── webhook.py
├── .env.example
├── .gitignore
├── bangtan.sh
├── config.yaml
├── jin.py
├── LICENSE
├── README.md
└── req.txt
```

## Notes

- Instagram requests may be rate-limited if polled too aggressively.
- TikTok support uses yt-dlp to retrieve metadata and download videos for Discord uploads.
- The bot randomizes account polling order and supports configurable delays between requests.
- Oversized Instagram videos automatically fall back to sending the post thumbnail instead of failing.

## License

This project is licensed under the MIT License.
