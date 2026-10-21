"""Canonical, strictly allowlisted link providers for LinkScribe.

Never feed arbitrary user-provided addresses to yt-dlp. We reconstruct recognized
public video URLs and pass only those to the extractor. This does not authorize
retrieving otherwise restricted content or bypassing a site's terms.
"""
from __future__ import annotations
from dataclasses import dataclass
import re
from urllib.parse import parse_qs, urlsplit

VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
VIMEO_ID_RE = re.compile(r"^[0-9]{1,18}$")
DAILYMOTION_ID_RE = re.compile(r"^[a-zA-Z0-9]{4,30}$")


@dataclass(frozen=True)
class Source:
    provider: str
    video_id: str
    url: str


def parse_source(raw: str) -> Source:
    raw = raw.strip()
    if not raw or len(raw) > 2048 or any(ord(c) < 32 for c in raw):
        raise ValueError("Enter one valid video link (2048 characters or fewer).")
    if raw.startswith(("youtu.be/", "youtube.com/", "www.youtube.com/", "m.youtube.com/", "vimeo.com/", "www.vimeo.com/", "dailymotion.com/", "www.dailymotion.com/", "dai.ly/")):
        raw = "https://" + raw
    try:
        url = urlsplit(raw)
        if (url.scheme not in {"https", "http"} or not url.hostname or url.username or url.password
                or url.port is not None or url.fragment and len(url.fragment) > 1024):
            raise ValueError
        host = url.hostname.lower().rstrip(".")
    except (ValueError, TypeError):
        raise ValueError("Use a valid YouTube, Vimeo, or Dailymotion video link.") from None
    path = url.path.strip("/")
    parts = path.split("/") if path else []
    if host == "youtu.be":
        video_id = path if len(parts) == 1 else ""
    elif host in {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}:
        if path == "watch":
            video_id = parse_qs(url.query).get("v", [""])[0]
        elif len(parts) == 2 and parts[0] in {"shorts", "live", "embed"}:
            video_id = parts[1]
        else:
            video_id = ""
    elif host == "www.youtube-nocookie.com" and len(parts) == 2 and parts[0] == "embed":
        video_id = parts[1]
    else:
        video_id = ""
    if VIDEO_ID_RE.fullmatch(video_id):
        return Source("youtube", video_id, f"https://www.youtube.com/watch?v={video_id}")
    if host in {"vimeo.com", "www.vimeo.com", "player.vimeo.com"}:
        if host == "player.vimeo.com":
            video_id = parts[1] if len(parts) == 2 and parts[0] == "video" else ""
        else:
            video_id = parts[0] if len(parts) == 1 else ""
        if VIMEO_ID_RE.fullmatch(video_id):
            return Source("vimeo", video_id, f"https://vimeo.com/{video_id}")
    if host in {"dailymotion.com", "www.dailymotion.com", "dai.ly"}:
        video_id = parts[0] if host == "dai.ly" and len(parts) == 1 else (parts[1] if len(parts) == 2 and parts[0] == "video" else "")
        if DAILYMOTION_ID_RE.fullmatch(video_id):
            return Source("dailymotion", video_id, f"https://www.dailymotion.com/video/{video_id}")
    raise ValueError("Only individual YouTube, Vimeo and Dailymotion video links are supported. Playlists, private links and arbitrary URLs are not accepted.")
