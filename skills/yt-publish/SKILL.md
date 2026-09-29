---
name: yt-publish
description: >-
  Upload or schedule a finished video to YouTube through Blotato, after the
  user has approved the title, the description and the file. Use when the
  user says "publish this", "upload it", "schedule this video", "send it to
  YouTube", or answers "publish" after /yt-package or /yt-seo. Requires an
  approved title and description and two explicit yeses. Never runs on its own.
---

# yt-publish

Every other skill in this pack writes and hands you a block to copy. This one
touches the channel. It is the only one that does, and it does not move until you
have said the word.

```bash
python3 publish.py --check                         # which channel is pinned, by name
python3 publish.py --title "..." --desc desc.txt --video short.mp4 --dry-run
python3 publish.py --title "..." --desc desc.txt --video short.mp4
python3 publish.py --title "..." --desc desc.txt --video short.mp4 --privacy public
python3 publish.py --title "..." --video-url https://... --schedule 2026-09-24T22:00:00Z
```

## Before you run anything

1. **The title and the description must have been approved in this
   conversation.** `/yt-package` writes and lints the title, `/yt-seo` writes the
   description. If neither has run, run them first. Do not invent a title here.
2. **The keys must already exist** in `~/.claude/youtube/.env`:

   ```
   BLOTATO_API_KEY=...
   BLOTATO_ACCOUNT_YOUTUBE=1234
   ```

   If they are missing, tell the user those two lines and stop. **Never ask them
   to paste a key into the chat.**
3. **Run `--check` first and read the channel name out loud.** A Blotato
   workspace can hold a dozen YouTube channels and the ids are four digits that
   all look alike. The id is not the confirmation; the name is.

## Private by default, and that is not a bug

`--privacy` is `private` unless the user asks otherwise. A video that lands on
the wrong channel as private is invisible and they delete it in Studio. The same
mistake as public is a notification to every subscriber and a video in the feed.

Going live takes an explicit `--privacy public`, and `--notify` is off unless
they ask for it. If they say "publish it" without saying public, that is a
private upload and you say so in the check block. Ask; do not assume.

## The check block

Print this, exactly, and then stop:

```
PUBLISH CHECK
channel:   Your Channel Name        (account 1234, verified YouTube)
title:     How I Fixed My Retention In 30 Days        (34 / 100 characters)
privacy:   PRIVATE                  (nothing goes live until you say public)
notify:    subscribers will NOT be notified
video:     short.mp4                (14.2 MB)
when:      now  |  2026-09-24 08:00 local (22:00 UTC)
description: 840 characters

<the first three lines of the description, exactly as they will go out>

Reply "publish" to send it, or tell me what to change.
```

Wait for the word **publish**. "yes", "ok", "looks good" and "send it" are not
enough for something that goes out under their name on their channel. Ask once
more if it is at all ambiguous.

## Running it

Run the command exactly as it appeared in the check block. Nothing changes
between what they approved and what goes out.

The script uploads the file, submits, and then polls every 20 seconds until
Blotato reaches a terminal state. YouTube transcodes, so this genuinely takes
minutes rather than seconds. **Do not end your turn while it is still polling.**
It prints exactly one of:

- `PUBLISHED <url>` — with a reminder of the privacy setting if it is not public
- `SCHEDULED <time>`
- `FAILED <reason>`

If it says `FAILED`, quote the reason and stop. Do not retry the same command;
work out what was wrong first. Every run is appended to
`~/.claude/youtube/log.md`.

## Never

- Never run the script without the word "publish" from the user in this
  conversation.
- Never publish to any account other than the one pinned in
  `BLOTATO_ACCOUNT_YOUTUBE`, even though the workspace has others and even if the
  user names a different channel. Change the env file instead, deliberately.
- Never pass `--privacy public` unless the user said public in this conversation.
- Never change the title, the description or the file between the check block and
  the command. What they approved is what goes out.
