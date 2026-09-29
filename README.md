# The YouTube agent skill (Ness edition)

Twelve Claude skills that run a YouTube channel. Eleven of them write. The
twelfth uploads, through Blotato, and only after you have said "publish".

One of them writes your script off 21 hook formulas and scores the hook before
you waste a take on it. One lints the title and the thumbnail as a single
pairing, because writing them separately is why half of your click surface says
the same thing twice. One reads your audience-retention export and tells you the
exact second people left and what you were saying when they did. One turns a
transcript into an edit decision list. One finds the Shorts already hiding inside
a long video. One goes and finds what is working in your niche and ranks it by
how far each video beat its own channel, not by how big the channel is.

And two of them just fetch. The original pack asks you to paste in your own
titles, collect a competitor's videos yourself, and go and find a transcript
from somewhere. These go and get all three.

**Nothing reaches your channel until you say publish.** The eleven writing skills
never touch YouTube. `/yt-publish` does, once, after you approve the exact title,
description and file — and it uploads private unless you say otherwise.

## Install

Paste this into Claude:

```
https://github.com/nessalazne/youtube-agent-skill

Install this skill, then confirm /yt-script works.
```

Or do it yourself, in Claude Code:

```bash
git clone https://github.com/nessalazne/youtube-agent-skill.git
cp -r youtube-agent-skill/skills/yt-* ~/.claude/skills/
```

Or as a plugin:

```
/plugin marketplace add nessalazne/youtube-agent-skill
/plugin install youtube-agent
```

Project-local instead of global: copy the same folders into your repo's
`.claude/skills/`. No Claude Code at all? Paste any single `SKILL.md` at the top
of a chat and it runs as a mode. You lose the Python tools, which is most of the
point of `/yt-script`, `/yt-retention` and `/yt-edit`, but the rest works.

Then spend ten minutes on [`templates/voice.md`](templates/voice.md). Copy it to
`~/.claude/youtube/voice.md` and fill it in, or send Claude three of your own
videos and say "write my voice.md from these". Every skill reads that file. It
matters more here than anywhere else, because you have to say the words out loud.

## The twelve

| command | what it does |
| --- | --- |
| `/yt-script` | One idea into a script. Five hooks off [21 formulas](skills/yt-script/hooks.json), scored, then the spoken script with the retention beats marked. |
| `/yt-package` | Title and thumbnail as one pairing, linted for truncation, duplication and vagueness. |
| `/yt-edit` | A transcript into an edit decision list: dead air, filler cues, retakes, with timecodes. |
| `/yt-comment` | The comment section triaged into four piles, then replies in your voice. Says which one to pin. |
| `/yt-plan` | A week that fits the hours you actually have. One anchor, one cheap one, three Shorts. |
| `/yt-viral` | What is working in your niche, ranked by multiple over each channel's own median. |
| `/yt-retention` | Your retention export read properly: hook leak, the cliffs, the slide, and what to change. |
| `/yt-shorts` | The Shorts already inside a long video, with a new first line written for each. |
| `/yt-seo` | The description, the tags that are worth having, and the three queries this should win. |
| `/yt-chapters` | Chapters from a transcript, validated against YouTube's own rules so they render. |
| `/yt-audit` | The whole channel, ending in ONE fix rather than twenty. |
| `/yt-publish` | Uploads or schedules the finished video through Blotato. Private by default. Two yeses. |

## The fetchers

The original pack is honest about what it asks of you: collect the videos
"however the user prefers", transcribe the first fifteen seconds yourself, go and
export the file. That is a lot of manual work between you and an answer.

```bash
python3 tools/channel.py @handle                       # the last 15 uploads, readable
python3 tools/channel.py @me @rival1 @rival2 --json    # the shape swipe.py eats
python3 tools/transcript.py "$URL" --srt -o t.srt      # the shape deadair and chapters eat
```

They were built to feed the tools that were already here, so **not one of the six
original tools changed**:

```bash
python3 tools/channel.py @a @b @c --json > collected.json
python3 skills/yt-viral/swipe.py collected.json --min 2.0

python3 tools/transcript.py "$URL" --srt > t.srt
python3 skills/yt-edit/deadair.py t.srt
python3 skills/yt-chapters/chapters.py t.srt --target 8
python3 skills/yt-retention/retention.py retention.csv --transcript t.srt
```

That last one is the one worth having. With a transcript, the retention report
stops saying "they left at 442 seconds" and starts saying what you were in the
middle of saying when they did.

`channel.py` needs a free YouTube Data API key and runs on a clean Python with
nothing installed. `transcript.py` needs `pip install youtube-transcript-api` and
is the only tool in the pack that needs anything — fetching captions without it
was tried, and the caption URLs return an empty body now whatever you ask for.

**Every skill still works without either of them.** The fetchers are a shortcut,
never a requirement. Paste your data in and nothing is lost but typing.

```
# ~/.claude/youtube/.env
YOUTUBE_API_KEY=AIza...
```

Enable "YouTube Data API v3" in the
[Google Cloud console](https://console.cloud.google.com/apis/library/youtube.googleapis.com)
and make a key. It is free, with a daily quota of 10,000 units. Looking up three
channels by `@handle` costs 9 of them; looking the same three up by name costs
306, which is why you should use handles.

## Publishing

The original pack does not publish, and says so plainly. This edition does,
through [Blotato](https://blotato.com/?ref=ness), which handles the upload so
there is no OAuth dance and no browser automation.

```bash
python3 skills/yt-publish/publish.py --check        # which channel is pinned, by name
python3 skills/yt-publish/publish.py --title "..." --desc desc.txt --video short.mp4 --dry-run
python3 skills/yt-publish/publish.py --title "..." --desc desc.txt --video short.mp4
```

```
# ~/.claude/youtube/.env
BLOTATO_API_KEY=...
BLOTATO_ACCOUNT_YOUTUBE=1234
```

Three things it does that are worth knowing about before you trust it with your
channel:

**It is private by default.** `--privacy public` is an explicit choice every
time. A video that lands on the wrong channel as private is invisible and you
delete it in Studio; the same mistake as public is a notification to every
subscriber.

**It names the channel, not the id.** One Blotato workspace can hold a dozen
YouTube channels and the account ids are four digits that all look alike, so
`--check` prints the channel's actual name and refuses outright if the pinned id
turns out to be some other platform.

**It waits.** After submitting it polls every 20 seconds until Blotato reports
published, scheduled or failed, and prints the URL. YouTube transcodes, so this
takes minutes. A failure is quoted, not retried. Every run is appended to
`~/.claude/youtube/log.md`.

## The six tools

Every one of these runs on a clean Python 3 with no dependencies, and all six are
exactly as their author wrote them. They are the reason the skills are not just
prompts.

```bash
python3 skills/yt-script/hookscore.py --hook "one line"        # 5-property hook panel
python3 skills/yt-package/title.py --title "..." --thumb "..." # title + thumbnail linter
python3 skills/yt-edit/deadair.py transcript.srt               # edit decision list
python3 skills/yt-chapters/chapters.py transcript.srt          # validated chapters
python3 skills/yt-retention/retention.py retention.csv         # where they left, and why
python3 skills/yt-viral/swipe.py collected.json --min 2.0      # outliers by own-channel multiple
```

## The fine print, which is the honest part

**`hookscore.py` is a heuristic, not a predictor.** The panel was built and
calibrated against 74 real short-form hooks (the first 15 seconds of
auto-captions, top-8 and bottom-8 by views across five channels). It separates
deliberately bad hooks from real ones well. It separates a given creator's hits
from their own misses barely at all. A low score is a reason to look again; a
high score is not a promise.

**The formula classifier is about the words, not the result.** When `/yt-viral`
says a title used The Statistic, that is a judgement about the title you can see,
not a claim about why the video got its views.

**It reads, it does not scrape.** `channel.py` is the official YouTube Data API
with your own key. It never logs in as you and never sees your password.

**It publishes, and that is the thing to read carefully.** Publishing is the one
capability the original pack deliberately left out, and adding it is the main
reason this fork exists. It is deliberately hard to fire by accident: it uploads
to one pinned channel, private unless you say public, subscribers unnotified
unless you ask, and only after Claude has printed the exact title, description
and file and you have typed the word "publish". Anything that claims to run your
channel unattended should still be read with suspicion. This does not.

**Tags barely matter** and this pack says so instead of selling you a tag
generator.

**Nothing invents a number.** If a skill wants a figure it does not have, it asks
you for it or writes the line without it.

## Files

```
tools/channel.py             a channel's recent uploads, off the Data API (stdlib only)
tools/transcript.py          a video's caption track as text or .srt
skills/yt-script/hooks.json  the 21 hook formulas, shared with the classifier
skills/yt-script/hookscore.py    the five-property hook panel
skills/yt-package/title.py       title + thumbnail linter
skills/yt-edit/deadair.py        edit decision list
skills/yt-chapters/chapters.py   chapter boundaries, validated
skills/yt-retention/retention.py hook leak, cliffs, slide
skills/yt-viral/swipe.py         outliers by own-channel median
skills/yt-publish/publish.py     the Blotato upload
templates/voice.md               the profile every skill reads
```

## What changed in the Ness edition

- **`tools/channel.py` and `tools/transcript.py`** — the fetch layer. They write
  exactly the formats the existing tools already read, so none of the six needed
  changing, and six of the eleven skills stopped asking you to paste data in.
- **`/yt-publish`** — a twelfth skill, and the only one that touches YouTube.
  Uploads through Blotato, private by default, two explicit yeses.
- **Every skill's gate block was rewritten**, because "nothing here publishes"
  stopped being true of the pack as a whole the moment `/yt-publish` existed.
- Rebranded metadata, and the MIT licence carries both copyright lines.

The six Python tools, `hooks.json` and `templates/voice.md` are byte-identical to
upstream.

## Go deeper

Want to go further, like building these skills into your own app or
customizing them for how your business works? Join the hub:
[hub.digicuratoragency.com/join](https://hub.digicuratoragency.com/join).

For more on AI automation, watch the
[Learn With Ness](https://www.youtube.com/@nessalazne) YouTube channel.

## Credit

Original pack by Jake Schincariol, [opusjake.ai](https://opusjake.ai). This
edition is maintained by Ness Alazne,
[builds.digicuratoragency.com](https://builds.digicuratoragency.com).

## License

MIT. Take it, change it, ship it.
