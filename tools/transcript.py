#!/usr/bin/env python3
"""transcript.py - pull a video's caption track down as text or as an .srt.

    python3 transcript.py https://youtu.be/VIDEOID          # plain text
    python3 transcript.py https://youtu.be/VIDEOID --srt    # timestamped
    python3 transcript.py VIDEOID --srt -o transcript.srt
    python3 transcript.py URL --lang es                     # a specific language

Four skills in this pack want a timestamped transcript and all four currently ask
you to go and find one. `--srt` writes the format they already read, so this
chains straight into them and none of them needed changing:

    python3 transcript.py "$URL" --srt > t.srt
    python3 ../skills/yt-edit/deadair.py t.srt
    python3 ../skills/yt-chapters/chapters.py t.srt --target 8

NEEDS ONE PACKAGE, and only this tool does:

    pip3 install youtube-transcript-api

That is a deliberate exception to the rest of the pack running on a clean Python
with nothing installed. Fetching captions without it was tried and does not work:
the caption URLs on the watch page return an empty body now, whatever format you
ask for. Every other tool here still needs nothing.

NO CAPTIONS, NO TRANSCRIPT. This reads the track YouTube already has. It does not
transcribe audio. If a video has no captions the fallback is in the error.
"""
import json
import re
import sys

_ID_PATTERNS = [
    re.compile(r"(?:v=|/v/)([A-Za-z0-9_-]{11})"),
    re.compile(r"youtu\.be/([A-Za-z0-9_-]{11})"),
    re.compile(r"/shorts/([A-Za-z0-9_-]{11})"),
    re.compile(r"/embed/([A-Za-z0-9_-]{11})"),
    re.compile(r"/live/([A-Za-z0-9_-]{11})"),
]


def die(message):
    print(message, file=sys.stderr)
    sys.exit(1)


def video_id(text):
    """The 11-character id out of any of YouTube's URL shapes, or a bare id."""
    text = (text or "").strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", text):
        return text
    for pattern in _ID_PATTERNS:
        found = pattern.search(text)
        if found:
            return found.group(1)
    return None


def fetch(vid, lang=None):
    """[(start, duration, text)] from whichever caption track fits.

    Handles both the 1.x instance API and the 0.6.x static one, because which is
    installed is not something this tool gets to choose.
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        die("This tool needs one package that is not installed:\n\n"
            "    pip3 install youtube-transcript-api\n\n"
            "  It is the only tool in this pack that needs anything. If you would\n"
            "  rather not install it, every skill that wants a transcript still\n"
            "  takes one you supply yourself.")

    languages = [lang] if lang else ["en", "en-US", "en-GB"]
    try:
        if hasattr(YouTubeTranscriptApi, "fetch"):
            api = YouTubeTranscriptApi()
            try:
                fetched = api.fetch(vid, languages=languages)
            except Exception:
                fetched = api.fetch(vid)
            return [(float(getattr(s, "start", 0)), float(getattr(s, "duration", 0)),
                     (getattr(s, "text", "") or "").strip()) for s in fetched]
        try:
            raw = YouTubeTranscriptApi.get_transcript(vid, languages=languages)
        except Exception:
            raw = YouTubeTranscriptApi.get_transcript(vid)
        return [(float(s.get("start", 0)), float(s.get("duration", 0)),
                 (s.get("text") or "").strip()) for s in raw]
    except Exception as exc:
        name = type(exc).__name__
        if "Disabled" in name or "NoTranscript" in name or "NotFound" in name:
            die(f"That video has no caption track this tool can read ({name}).\n\n"
                "  The usual fix: upload your own video as unlisted, wait a few minutes\n"
                "  for YouTube to generate captions, and download the track from Studio.\n"
                "  Or run whisper over the file. Either way the skills take the result.")
        die(f"Could not read that transcript: {name}: {str(exc)[:200]}")


def stamp(seconds):
    """0.0 -> 00:00:00,000, the way SubRip wants it."""
    if seconds < 0:
        seconds = 0
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def to_srt(cues):
    out = []
    for i, (start, duration, text) in enumerate(cues, 1):
        if not text:
            continue
        # A zero-length cue produces an end before its start, which the SubRip
        # parsers in this pack read as a negative gap.
        end = start + (duration if duration > 0 else 1.5)
        out.append(f"{i}\n{stamp(start)} --> {stamp(end)}\n{text}\n")
    return "\n".join(out)


def main():
    args = sys.argv[1:]
    as_srt = "--srt" in args
    as_json = "--json" in args
    args = [a for a in args if a not in ("--srt", "--json")]

    lang = None
    if "--lang" in args:
        i = args.index("--lang")
        lang = args[i + 1]
        del args[i:i + 2]

    out_path = None
    for flag in ("-o", "--out"):
        if flag in args:
            i = args.index(flag)
            out_path = args[i + 1]
            del args[i:i + 2]
            break

    targets = [a for a in args if not a.startswith("--")]
    if not targets:
        print(__doc__)
        sys.exit(1)

    vid = video_id(targets[0])
    if not vid:
        die(f"Could not find a video id in {targets[0]!r}.\n"
            "  Give me a watch/share/shorts URL, or the 11-character id on its own.")

    cues = fetch(vid, lang)
    if not cues:
        die("That caption track came back empty.")

    if as_json:
        text = json.dumps([{"start": s, "duration": d, "text": t} for s, d, t in cues], indent=1)
    elif as_srt:
        text = to_srt(cues)
    else:
        text = " ".join(t for _, _, t in cues if t)

    if out_path:
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        words = sum(len(t.split()) for _, _, t in cues)
        print(f"{out_path}  -  {len(cues)} cues, {words:,} words, "
              f"{cues[-1][0] / 60:.1f} minutes", file=sys.stderr)
    else:
        print(text)


if __name__ == "__main__":
    main()
