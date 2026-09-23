#!/usr/bin/env python3
"""
publish.py - upload or schedule a finished video to YouTube through Blotato.

The rest of this pack writes and hands you a block to copy. This is the one
script that touches your channel, and it never decides to: the skill that calls
it has already collected the literal word "publish" from you.

    python3 publish.py --title "..." --video short.mp4 --desc description.txt
    python3 publish.py --title "..." --video-url https://... --desc -
    python3 publish.py --title "..." --video short.mp4 --privacy public
    python3 publish.py --title "..." --video short.mp4 --schedule 2026-09-24T22:00:00Z
    python3 publish.py --title "..." --video short.mp4 --dry-run
    python3 publish.py --check                  # which channel is pinned, by name

Keys come from ~/.claude/youtube/.env (or --env PATH), falling back to the
process environment:

    BLOTATO_API_KEY=...
    BLOTATO_ACCOUNT_YOUTUBE=1234

PRIVATE BY DEFAULT, deliberately. One Blotato workspace can hold a dozen YouTube
channels and an account id is four digits that all look alike. A video that goes
to the wrong channel as private is invisible and you delete it in Studio; the
same mistake as public is a notification to every subscriber. Going live is an
explicit --privacy public and nothing less.

Only `requests` is needed beyond the standard library.
"""

import argparse
import datetime as dt
import json
import os
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("publish.py needs the requests package: pip install requests")

MCP_URL = "https://mcp.blotato.com/mcp"
DEFAULT_ENV = Path.home() / ".claude" / "youtube" / ".env"
LOG_PATH = Path.home() / ".claude" / "youtube" / "log.md"
TITLE_LIMIT = 100
DESC_LIMIT = 5000
PRIVACY = ("private", "unlisted", "public")
TERMINAL = ("published", "scheduled", "failed", "completed")


# ── env ───────────────────────────────────────────────────────────────────────

def load_env(path: Path):
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def require(key: str) -> str:
    val = os.environ.get(key, "").strip()
    if not val:
        sys.exit(f"{key} is not set. Put it in {DEFAULT_ENV} or pass --env.")
    return val


# ── Blotato MCP ───────────────────────────────────────────────────────────────

_rpc_id = 0


def _blotato_headers() -> dict:
    return {
        "blotato-api-key": require("BLOTATO_API_KEY"),
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }


def _parse_rpc_body(text: str) -> dict:
    text = text.strip()
    if text.startswith("{"):
        return json.loads(text)
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            payload = line[5:].strip()
            if payload and payload != "[DONE]":
                return json.loads(payload)
    raise RuntimeError(f"Unparseable MCP response: {text[:200]}")


def _rpc(tool: str, arguments: dict, timeout: int = 60):
    global _rpc_id
    _rpc_id += 1
    resp = requests.post(
        MCP_URL,
        headers=_blotato_headers(),
        json={
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": tool, "arguments": arguments},
            "id": _rpc_id,
        },
        timeout=timeout,
    )
    if not resp.ok:
        raise RuntimeError(f"Blotato MCP {tool} HTTP {resp.status_code}: {resp.text[:300]}")
    data = _parse_rpc_body(resp.text)
    if data.get("error"):
        raise RuntimeError(f"Blotato MCP {tool} error: {data['error']}")
    result = data.get("result", {})
    if result.get("isError"):
        raise RuntimeError(f"Blotato MCP {tool} tool error: {result}")
    content = result.get("content") or []
    if content and content[0].get("type") == "text":
        raw = content[0]["text"]
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw
    return result


def upload_media(path: Path) -> str:
    size_mb = path.stat().st_size / 1024 / 1024
    print(f"Uploading {path.name} ({size_mb:.1f} MB) to Blotato...")
    res = _rpc("blotato_create_presigned_upload_url", {"filename": path.name}, timeout=60)
    presigned = res.get("presignedUrl") or res.get("uploadUrl")
    public = res.get("publicUrl") or res.get("url")
    if not presigned or not public:
        sys.exit(f"Blotato presigned URL response missing expected fields: {res}")
    put = requests.put(presigned, data=path.read_bytes(), timeout=1800)
    if not put.ok:
        sys.exit(f"Upload PUT failed {put.status_code}: {put.text[:200]}")
    print("Upload complete.")
    return public


def _poll_until_terminal(submission_id: str, max_wait: int = 900) -> dict:
    """YouTube transcodes, so this waits longer than the text platforms do."""
    deadline = time.time() + max_wait
    last = {}
    while time.time() < deadline:
        time.sleep(20)
        try:
            data = _rpc("blotato_get_post_status", {"postSubmissionId": str(submission_id)})
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        last = data
        status = str(data.get("status", "")).lower()
        if status in TERMINAL:
            return data
        print(f"  status: {status or 'in-progress'} ...", flush=True)
    last.setdefault("status", "timeout")
    return last


# ── account check ─────────────────────────────────────────────────────────────

def _accounts() -> list:
    res = _rpc("blotato_list_accounts", {}, timeout=30)
    if isinstance(res, dict):
        for key in ("accounts", "items", "data"):
            if isinstance(res.get(key), list):
                return res[key]
    return res if isinstance(res, list) else []


def find_account(account_id: str) -> dict:
    for acc in _accounts():
        if str(acc.get("id")) == str(account_id):
            return acc
    return {}


def account_name(acc: dict) -> str:
    return acc.get("fullname") or acc.get("displayName") or acc.get("username") or "?"


def verify_youtube(account_id: str) -> dict:
    """The pinned id must exist and must be YouTube. Returns the account.

    An id on its own proves nothing here - a workspace can hold many YouTube
    channels and the ids are four digits apart. Everything downstream prints the
    name this returns, so the human sees a channel and not a number.
    """
    acc = find_account(account_id)
    if not acc:
        sys.exit(f"Account {account_id} is not in this Blotato workspace.")
    platform = str(acc.get("platform", "")).lower()
    if platform != "youtube":
        sys.exit(f"Account {account_id} is {platform or 'unknown'}, not YouTube "
                 f"({account_name(acc)}). Refusing to post.")
    return acc


# ── helpers ───────────────────────────────────────────────────────────────────

def read_text(source: str) -> str:
    if not source:
        return ""
    text = sys.stdin.read() if source == "-" else Path(source).read_text()
    return text.strip("\n")


def guard(text: str, limit: int, label: str) -> str:
    if len(text) <= limit:
        return text
    sys.exit(f"The {label} is {len(text):,} characters and YouTube allows {limit:,}. "
             f"Shorten it and run again - this is not truncated for you, because a "
             f"{label} cut mid-sentence is worse than an error.")


def build_payload(account_id, title, desc, privacy, notify, schedule, media_url):
    args = {
        "accountId": account_id,
        "platform": "youtube",
        "text": desc,
        "title": title,
        "privacyStatus": privacy,
        "shouldNotifySubscribers": bool(notify),
    }
    if media_url:
        args["mediaUrls"] = [media_url]
    if schedule and schedule != "now":
        try:
            dt.datetime.fromisoformat(schedule.replace("Z", "+00:00"))
        except ValueError:
            sys.exit(f"--schedule must be now or an ISO 8601 UTC time, got {schedule!r}")
        args["scheduledTime"] = schedule
    return args


def append_log(title: str, status: str, url: str, schedule: str, privacy: str):
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
        with LOG_PATH.open("a") as fh:
            fh.write(f"- {stamp} | yt-publish | {status} | {privacy} | {schedule} | "
                     f"{url or '-'} | {title[:120]}\n")
    except OSError as exc:
        print(f"(could not write {LOG_PATH}: {exc})", file=sys.stderr)


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Upload or schedule a video to YouTube through Blotato.")
    ap.add_argument("--title", help="the video title (required, 100 characters max)")
    ap.add_argument("--desc", default="", help="path to the description, or - for stdin")
    ap.add_argument("--video", type=Path, help="video file to upload")
    ap.add_argument("--video-url", help="an already-hosted video URL, used instead of --video")
    ap.add_argument("--privacy", default="private", choices=PRIVACY,
                    help="private (default), unlisted or public")
    ap.add_argument("--notify", action="store_true",
                    help="notify subscribers (off unless asked for)")
    ap.add_argument("--schedule", default="now", help="now (default) or an ISO 8601 UTC time")
    ap.add_argument("--env", type=Path, default=DEFAULT_ENV, help=f"env file (default {DEFAULT_ENV})")
    ap.add_argument("--dry-run", action="store_true", help="print the payload and exit, no network")
    ap.add_argument("--check", action="store_true", help="name the pinned channel and exit")
    ap.add_argument("--max-wait", type=int, default=900, help="seconds to poll for a terminal status")
    args = ap.parse_args()

    load_env(args.env)

    if args.check:
        account_id = require("BLOTATO_ACCOUNT_YOUTUBE")
        acc = verify_youtube(account_id)
        print(f"OK: account {account_id} is YouTube - {account_name(acc)}")
        required = acc.get("requiredFields")
        if required:
            print(f"    Blotato requires: {json.dumps(required)}")
        return

    if not args.title:
        ap.error("--title is required unless --check is given")
    if not args.video and not args.video_url and not args.dry_run:
        ap.error("give me --video or --video-url")

    title = guard(args.title.strip(), TITLE_LIMIT, "title")
    desc = guard(read_text(args.desc), DESC_LIMIT, "description")

    account_id = os.environ.get("BLOTATO_ACCOUNT_YOUTUBE", "").strip() or (
        "<BLOTATO_ACCOUNT_YOUTUBE>" if args.dry_run else require("BLOTATO_ACCOUNT_YOUTUBE"))

    if args.dry_run:
        media = args.video_url or (f"<upload of {args.video}>" if args.video else None)
        print(json.dumps(build_payload(account_id, title, desc, args.privacy,
                                       args.notify, args.schedule, media),
                         indent=2, ensure_ascii=False))
        return

    acc = verify_youtube(account_id)
    print(f"Channel: {account_name(acc)}  (account {account_id})")

    media_url = args.video_url
    if not media_url:
        if not args.video.exists():
            sys.exit(f"Video not found: {args.video}")
        media_url = upload_media(args.video)

    payload = build_payload(account_id, title, desc, args.privacy,
                            args.notify, args.schedule, media_url)
    print(f"Submitting to YouTube ({args.privacy}, schedule={args.schedule})...")
    try:
        res = _rpc("blotato_create_post", payload, timeout=120)
    except Exception as exc:
        append_log(title, "failed", "", args.schedule, args.privacy)
        sys.exit(f"FAILED {exc}")

    sub_id = None
    if isinstance(res, dict):
        sub_id = res.get("postSubmissionId") or res.get("submissionId") or res.get("id")
    if not sub_id:
        append_log(title, "submitted", "", args.schedule, args.privacy)
        print(f"SUBMITTED (no submission id returned): {str(res)[:300]}")
        return

    print(f"Submission {sub_id}, polling (YouTube transcodes, this takes minutes)...")
    final = _poll_until_terminal(sub_id, max_wait=args.max_wait)
    status = str(final.get("status", "")).lower()
    url = final.get("publicUrl") or final.get("url") or ""
    append_log(title, status, url, args.schedule, args.privacy)

    if status in ("published", "completed"):
        print(f"PUBLISHED {url or '(no public URL returned yet, check Blotato)'}")
        if args.privacy != "public":
            print(f"  It is {args.privacy}. Flip it in Studio when you are ready.")
    elif status == "scheduled":
        when = final.get("scheduledTime") or payload.get("scheduledTime") or "the scheduled time"
        print(f"SCHEDULED {when}")
    else:
        err = final.get("errorMessage") or final.get("error") or json.dumps(final)[:300]
        sys.exit(f"FAILED {status}: {err}")


if __name__ == "__main__":
    main()
