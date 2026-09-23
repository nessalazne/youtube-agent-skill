#!/usr/bin/env python3
"""channel.py - read a channel's recent uploads off the YouTube Data API.

    python3 channel.py @handle                    # the last 15 uploads, readable
    python3 channel.py @handle --json             # the shape swipe.py eats
    python3 channel.py @me @rival1 @rival2 --json # several channels at once
    python3 channel.py @handle --max 30 --json > collected.json

This is the one thing the rest of the pack keeps asking you to do by hand: go and
get the titles. `--json` writes exactly the list `yt-viral/swipe.py` already
reads, so the two chain together and neither knows about the other:

    python3 channel.py @a @b @c --json > collected.json
    python3 ../skills/yt-viral/swipe.py collected.json --min 2.0

NEEDS A KEY, and it is free. Enable "YouTube Data API v3" at
console.cloud.google.com, make an API key, and put it in ~/.claude/youtube/.env:

    YOUTUBE_API_KEY=AIza...

QUOTA. You get 10,000 units a day. A `channels`, `playlistItems` or `videos` call
costs 1 unit; a `search` call costs 100. That is why a handle is looked up
directly and `search` is only the fallback - three channels by handle is 9 units,
the same three by name is 306. Use @handles.

READ, DO NOT SCRAPE. This is the official API with your own key. It never logs in
as you and never sees your password.
"""
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://www.googleapis.com/youtube/v3"
ENV_PATH = Path.home() / ".claude" / "youtube" / ".env"

_DURATION = re.compile(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")


def load_key():
    """YOUTUBE_API_KEY from the environment, else ~/.claude/youtube/.env."""
    key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if key:
        return key
    try:
        for line in ENV_PATH.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            if name.strip() == "YOUTUBE_API_KEY":
                return value.strip().strip('"').strip("'")
    except OSError:
        pass
    return ""


def get(endpoint, params, key):
    """One Data API call. Turns the API's own error text into a readable line."""
    params = dict(params, key=key)
    url = f"{API}/{endpoint}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        try:
            message = json.loads(body)["error"]["message"]
        except Exception:
            message = body[:200]
        if exc.code in (400, 403):
            die(f"YouTube rejected the request: {message}\n"
                f"  A 400 usually means the key is wrong. A 403 usually means the key is\n"
                f"  fine but 'YouTube Data API v3' is not enabled on that project, or you\n"
                f"  are out of quota for the day.")
        die(f"YouTube returned HTTP {exc.code}: {message}")
    except urllib.error.URLError as exc:
        die(f"Could not reach YouTube: {exc.reason}")


def die(message):
    print(message, file=sys.stderr)
    sys.exit(1)


def duration_seconds(iso):
    """PT10M13S -> 613. Returns None when the API omitted it (live streams)."""
    if not iso:
        return None
    m = _DURATION.match(iso)
    if not m:
        return None
    days, hours, minutes, seconds = (int(x) if x else 0 for x in m.groups())
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def opt_int(value):
    """Int, or None when YouTube omitted the stat - a creator can hide likes, and
    zero is a different claim from 'not shown'."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def resolve(name_or_handle, key):
    """A channel by @handle (1 unit) or, failing that, by name (100 units)."""
    query = (name_or_handle or "").strip()
    if not query:
        return None

    handle = query if query.startswith("@") else f"@{query}"
    data = get("channels", {"part": "snippet,statistics,contentDetails",
                            "forHandle": handle}, key)
    items = data.get("items", [])

    if not items:
        found = get("search", {"part": "snippet", "type": "channel",
                               "q": query, "maxResults": 1}, key)
        results = found.get("items", [])
        if not results:
            return None
        channel_id = results[0]["snippet"]["channelId"]
        data = get("channels", {"part": "snippet,statistics,contentDetails",
                                "id": channel_id}, key)
        items = data.get("items", [])
        if not items:
            return None

    item = items[0]
    try:
        return {
            "channel_id": item["id"],
            "name": item["snippet"]["title"],
            "handle": item["snippet"].get("customUrl", handle),
            "subs": opt_int(item.get("statistics", {}).get("subscriberCount")),
            "uploads": item["contentDetails"]["relatedPlaylists"]["uploads"],
        }
    except KeyError:
        return None


def recent(uploads_playlist, key, max_n=15):
    """The most recent uploads on a channel's uploads playlist."""
    playlist = get("playlistItems", {"part": "contentDetails",
                                     "playlistId": uploads_playlist,
                                     "maxResults": min(max_n, 50)}, key)
    ids = [it["contentDetails"]["videoId"] for it in playlist.get("items", [])
           if it.get("contentDetails", {}).get("videoId")]
    if not ids:
        return []

    details = get("videos", {"part": "statistics,snippet,contentDetails",
                             "id": ",".join(ids[:max_n])}, key)
    videos = []
    for item in details.get("items", []):
        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})
        videos.append({
            "youtube_id": item.get("id"),
            "title": snippet.get("title", ""),
            "views": int(stats.get("viewCount", 0) or 0),
            "likes": opt_int(stats.get("likeCount")),
            "comments": opt_int(stats.get("commentCount")),
            "duration": duration_seconds(item.get("contentDetails", {}).get("duration")),
            "published": snippet.get("publishedAt", ""),
        })
    return videos


def collect(names, key, max_n):
    """[{channel, title, views, url, duration}] - swipe.py's input, exactly."""
    rows, missing = [], []
    for name in names:
        channel = resolve(name, key)
        if not channel:
            missing.append(name)
            continue
        for video in recent(channel["uploads"], key, max_n):
            rows.append({
                "channel": channel["name"],
                "title": video["title"],
                "views": video["views"],
                "url": f"https://www.youtube.com/watch?v={video['youtube_id']}",
                "duration": video["duration"],
                "published": video["published"],
            })
    return rows, missing


def show(names, key, max_n):
    for name in names:
        channel = resolve(name, key)
        if not channel:
            print(f"\n  {name}  - not found")
            continue
        subs = f"{channel['subs']:,}" if channel["subs"] is not None else "hidden"
        print(f"\n  {channel['name']}   {subs} subscribers   {channel['handle']}")
        videos = recent(channel["uploads"], key, max_n)
        if not videos:
            print("    no readable uploads")
            continue
        views = sorted(v["views"] for v in videos)
        median = views[len(views) // 2]
        print(f"  {'-' * 72}")
        for v in videos:
            multiple = (v["views"] / median) if median else 0
            # Shorts are the reason this is not just minutes: a 45-second video
            # reading as "0m" hides the one thing that makes it a different format.
            secs = v["duration"]
            length = "   -" if not secs else (f"{secs}s" if secs < 60 else f"{secs // 60}m")
            print(f"    {v['views']:>11,}  {multiple:5.1f}x  {length:>4}  {v['title'][:52]}")
        print(f"\n    {len(videos)} videos, median {median:,} views")
        if len(videos) < 4:
            print("    under four videos - a median off this few is not a median")


def main():
    args = sys.argv[1:]
    as_json = "--json" in args
    args = [a for a in args if a != "--json"]
    max_n = 15
    if "--max" in args:
        i = args.index("--max")
        max_n = int(args[i + 1])
        del args[i:i + 2]
    names = [a for a in args if not a.startswith("--")]
    if not names:
        print(__doc__)
        sys.exit(1)

    key = load_key()
    if not key:
        die("No YouTube API key.\n"
            "  Enable 'YouTube Data API v3' at console.cloud.google.com, make a key,\n"
            f"  and put this line in {ENV_PATH}:\n\n"
            "    YOUTUBE_API_KEY=AIza...\n\n"
            "  Everything else in this pack works without it. This tool does not.")

    if as_json:
        rows, missing = collect(names, key, max_n)
        if missing:
            print(f"not found: {', '.join(missing)}", file=sys.stderr)
        if not rows:
            die("nothing collected")
        print(json.dumps(rows, indent=1))
    else:
        show(names, key, max_n)
        print()


if __name__ == "__main__":
    main()
