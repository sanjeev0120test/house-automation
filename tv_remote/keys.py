"""TV remote keys and app shortcuts for Mi TV."""

import json
import re
import threading
import time
import urllib.request
from urllib.parse import quote_plus

from tv_remote import adb

HOME, BACK = 3, 4
VOL_UP, VOL_DOWN = 24, 25
UP, DOWN, LEFT, RIGHT = 19, 20, 21, 22
OK, POWER = 23, 26
PLAY_PAUSE, MUTE = 85, 164
SKIP_FORWARD, APP_SWITCH = 272, 187

# Verified on MiTV_AXSO2 — only apps that exist on the TV are listed
APPS = {
    "youtube": "com.google.android.youtube.tv",
    "netflix": "com.netflix.ninja",
    "prime": "com.amazon.amazonvideo.livingroom",
    "hotstar": "in.startv.hotstar",
    "sonyliv": "com.sonyliv",
    "jio": "com.jio.media.stb.ondemand",
    "settings": "com.android.tv.settings",
}

# Some leanback apps need an explicit activity (monkey alone is unreliable).
APP_ACTIVITIES = {
    "jio": "com.jio.media.stb.ondemand/com.v18.voot.ui.JVHomeActivity",
}


def _press(code: int) -> None:
    adb.ensure_connected()
    adb.keyevent(code)


def home() -> None:
    _press(HOME)


def back() -> None:
    _press(BACK)


def volume_up() -> None:
    _press(VOL_UP)


def volume_down() -> None:
    _press(VOL_DOWN)


def dpad_up() -> None:
    _press(UP)


def dpad_down() -> None:
    _press(DOWN)


def dpad_left() -> None:
    _press(LEFT)


def dpad_right() -> None:
    _press(RIGHT)


def ok() -> None:
    _press(OK)


def power() -> None:
    _press(POWER)


def play_pause() -> None:
    _press(PLAY_PAUSE)


def mute() -> None:
    _press(MUTE)


def launch_app(name: str, settle: float = 1.5) -> None:
    """Open a streaming app by short name (youtube, netflix, prime, etc.)."""
    key = name.lower()
    pkg = APPS.get(key)
    if not pkg:
        raise ValueError(f"Unknown app: {name}")
    adb.ensure_connected()
    activity = APP_ACTIVITIES.get(key)
    if activity:
        adb.shell(f"am start -n {activity}", check=False)
    else:
        adb.shell(
            f"monkey -p {pkg} -c android.intent.category.LEANBACK_LAUNCHER 1",
            check=False,
        )
    if settle > 0:
        time.sleep(settle)


def screenshot(path: str = "tv_screenshot.png") -> str:
    """Capture what's on TV screen and save locally."""
    adb.ensure_connected()
    adb.shell("screencap -p /sdcard/tv_cap.png")
    adb.pull("/sdcard/tv_cap.png", path)
    return path


def _extract_first_video_id(data: object) -> str | None:
    if isinstance(data, dict):
        renderer = data.get("videoRenderer")
        if isinstance(renderer, dict):
            video_id = renderer.get("videoId")
            if isinstance(video_id, str) and video_id:
                return video_id
        for value in data.values():
            found = _extract_first_video_id(value)
            if found:
                return found
    elif isinstance(data, list):
        for item in data:
            found = _extract_first_video_id(item)
            if found:
                return found
    return None


def _extract_first_video_title(data: object) -> str | None:
    if isinstance(data, dict):
        renderer = data.get("videoRenderer")
        if isinstance(renderer, dict):
            title = renderer.get("title")
            if isinstance(title, dict):
                text = title.get("simpleText") or title.get("accessibility", {}).get(
                    "accessibilityData", {}
                ).get("label")
                if isinstance(text, str) and text:
                    return text
        for value in data.values():
            found = _extract_first_video_title(value)
            if found:
                return found
    elif isinstance(data, list):
        for item in data:
            found = _extract_first_video_title(item)
            if found:
                return found
    return None


def _first_youtube_result(query: str) -> tuple[str, str]:
    """Resolve the first YouTube search hit to a video id and title."""
    search_url = (
        f"https://www.youtube.com/results?search_query={quote_plus(query)}"
    )
    request = urllib.request.Request(
        search_url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        },
    )
    html = urllib.request.urlopen(request, timeout=20).read().decode(
        "utf-8", errors="ignore"
    )

    video_id: str | None = None
    title: str | None = None
    match = re.search(r"var ytInitialData\s*=\s*(\{.*?\});", html)
    if match:
        payload = json.loads(match.group(1))
        video_id = _extract_first_video_id(payload)
        title = _extract_first_video_title(payload)

    if not video_id:
        fallback = re.search(r'"videoId"\s*:\s*"([a-zA-Z0-9_-]{11})"', html)
        if fallback:
            video_id = fallback.group(1)

    if not video_id:
        raise RuntimeError(f"No YouTube results for: {query}")

    return video_id, title or query


def _ui_dump() -> str:
    adb.shell("uiautomator dump /sdcard/ui.xml", check=False)
    return adb.shell("cat /sdcard/ui.xml", check=False)


def _skip_ad_label(node: str) -> bool:
    """True when this UI node is a YouTube Skip control, not a countdown."""
    if re.search(r"skip_ad", node, re.IGNORECASE):
        return True
    labels = re.findall(r'(?:text|content-desc)="([^"]*)"', node, re.IGNORECASE)
    for label in labels:
        norm = re.sub(r"\s+", " ", label).strip().lower()
        if norm in {"skip", "skip ad", "skip ads", "skip advertisement"}:
            return True
        if norm.startswith("skip ad"):
            return True
    return False


def _find_skip_ad_target(xml: str) -> tuple[int, int] | None:
    """Return tap coordinates for an enabled Skip Ad control, if visible."""
    for node in re.findall(r"<node\b[^>]*>", xml):
        if 'enabled="false"' in node or not _skip_ad_label(node):
            continue
        bounds = re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', node)
        if not bounds:
            continue
        x1, y1, x2, y2 = (int(v) for v in bounds.groups())
        width, height = x2 - x1, y2 - y1
        if width >= 40 and height >= 20:
            return (x1 + x2) // 2, (y1 + y2) // 2
    return None


def press_skip_ad() -> None:
    """Activate Skip. YouTube TV focuses that button when it enables, and OK presses it.

    The player draws Skip inside a custom view, so the accessibility dump has no label.
    """
    adb.ensure_connected()
    adb.keyevent(OK)


def skip_ad_if_shown() -> bool:
    """Tap a Skip label when the accessibility tree actually contains one."""
    target = _find_skip_ad_target(_ui_dump())
    if not target:
        return False
    adb.tap(*target)
    return True


_last_youtube_id: str | None = None
_ad_skip_stop = threading.Event()
_ad_skip_thread: threading.Thread | None = None


def _skip_youtube_ads(
    expected_title: str | None = None,
    max_seconds: float = 90.0,
    poll_interval: float = 2.0,
) -> None:
    """Poll for skippable ads and press Skip Ad when it becomes available."""
    started = time.time()
    deadline = started + max_seconds
    while time.time() < deadline and not _ad_skip_stop.is_set():
        age = time.time() - started
        playing = now_playing()
        expected = (expected_title or "").lower()[:24]
        matched = bool(expected) and expected in playing.lower()
        # Skip becomes pressable about five seconds into a preroll. OK is harmless
        # during the movie on this set, and it fires the focused Skip control.
        if not matched or age < 12:
            press_skip_ad()
            time.sleep(0.55)
            continue
        time.sleep(max(poll_interval, 1.5))


def _start_youtube_ad_skipper(
    expected_title: str | None = None,
    max_seconds: float = 90.0,
) -> None:
    """Watch for skippable ads in the background after playback starts."""
    global _ad_skip_thread
    stop_ad_skip(join_timeout=0.2)
    _ad_skip_stop.clear()
    _ad_skip_thread = threading.Thread(
        target=_skip_youtube_ads,
        kwargs={"expected_title": expected_title, "max_seconds": max_seconds},
        daemon=True,
    )
    _ad_skip_thread.start()


def stop_ad_skip(join_timeout: float = 12.0) -> None:
    """Stop the background ad skipper so later key events are ours."""
    _ad_skip_stop.set()
    thread = _ad_skip_thread
    if thread and thread.is_alive() and thread is not threading.current_thread():
        thread.join(join_timeout)


def open_youtube_video(video_id: str, start_seconds: int | None = None) -> None:
    """Open a YouTube video. A start time uses the youtu.be form this TV honors."""
    global _last_youtube_id
    adb.ensure_connected()
    _last_youtube_id = video_id
    if start_seconds is not None and int(start_seconds) > 0:
        url = f"https://youtu.be/{video_id}?t={int(start_seconds)}"
    else:
        url = f"https://www.youtube.com/watch?v={video_id}"
    adb.shell(
        f'am start -a android.intent.action.VIEW -d "{url}" {APPS["youtube"]}',
        check=False,
    )


def youtube_search_play(query: str, wait: float = 5.0) -> str:
    """Search YouTube and play the first result, skipping ads when possible."""
    video_id, title = _first_youtube_result(query)
    open_youtube_video(video_id)
    _start_youtube_ad_skipper(expected_title=title, max_seconds=18)
    time.sleep(wait)
    return query


def play_eminem_hit() -> str:
    return youtube_search_play("eminem not afraid official")


def play_enrique_hit() -> str:
    return youtube_search_play("enrique iglesias hero official")


def skip_forward(seconds: int = 30) -> None:
    """Jump ahead in the YouTube video we opened, or send the media skip key."""
    adb.ensure_connected()
    if not _last_youtube_id or "youtube" not in foreground_package():
        _press(SKIP_FORWARD)
        return
    media_pause()
    time.sleep(0.8)
    info = playback()
    position_ms = info.get("position_ms")
    base = int(position_ms) // 1000 if isinstance(position_ms, int) and position_ms > 0 else 0
    open_youtube_video(_last_youtube_id, base + seconds)


def show_recent_apps() -> None:
    _press(APP_SWITCH)


def music_volume() -> int | None:
    """Current media volume as reported by the TV audio service."""
    adb.ensure_connected()
    out = adb.shell("media volume --stream 3 --get", check=False)
    match = re.search(r"volume is (\d+)", out)
    if match:
        return int(match.group(1))
    speaker = adb.shell("settings get system volume_music_speaker", check=False).strip()
    if speaker.isdigit():
        return int(speaker)
    return None


def foreground_package() -> str:
    """Package name of the window currently in front on the TV."""
    adb.ensure_connected()
    focused = adb.shell("dumpsys window | grep mCurrentFocus", check=False)
    if "not found" in focused.lower():
        focused = adb.shell("dumpsys window", check=False)
    for line in focused.splitlines():
        if "mCurrentFocus" not in line:
            continue
        match = re.search(r"\s([\w.]+)/", line)
        if match:
            return match.group(1)
    out = adb.shell("dumpsys activity activities", check=False)
    for line in out.splitlines():
        if "mResumedActivity" not in line:
            continue
        match = re.search(r"u0\s+([\w.]+)/", line)
        if match:
            return match.group(1)
    return ""


def media_pause() -> None:
    adb.ensure_connected()
    adb.keyevent(127)


def media_play() -> None:
    adb.ensure_connected()
    adb.keyevent(126)


def _session_title(session: dict[str, object]) -> str | None:
    desc = session.get("description")
    if not isinstance(desc, str):
        return None
    title = desc.split(",")[0].strip()
    return title or None


def playback() -> dict[str, object]:
    """Best media session: package, state, position_ms, speed, title."""
    adb.ensure_connected()
    out = adb.shell("dumpsys media_session", check=False)
    sessions: list[dict[str, object]] = []
    current: dict[str, object] = {}
    for line in out.splitlines():
        stripped = line.strip()
        if stripped.startswith("package="):
            if current:
                sessions.append(current)
            current = {"package": stripped.split("=", 1)[1]}
            continue
        if "state=PlaybackState" in stripped:
            match = re.search(
                r"state=(\d+), position=(-?\d+).*?speed=([0-9.]+)",
                stripped,
            )
            if match:
                current["state"] = int(match.group(1))
                current["position_ms"] = int(match.group(2))
                current["speed"] = float(match.group(3))
            continue
        if stripped.startswith("metadata:") and "description=" in stripped:
            desc = stripped.split("description=", 1)[1].strip()
            if desc and desc != "null":
                current["description"] = desc
    if current:
        sessions.append(current)

    def rank(session: dict[str, object]) -> tuple[int, int, int]:
        playing = 1 if session.get("state") == 3 else 0
        titled = 1 if _session_title(session) else 0
        youtube = 1 if "youtube" in str(session.get("package", "")) else 0
        return (playing, titled, youtube)

    best = max(sessions, key=rank) if sessions else {}
    return {
        "package": best.get("package"),
        "state": best.get("state"),
        "position_ms": best.get("position_ms"),
        "speed": best.get("speed"),
        "title": _session_title(best) if best else None,
    }


def now_playing() -> str:
    """Return title of the active playback session, if any."""
    title = playback().get("title")
    if isinstance(title, str) and title:
        return title
    return "Nothing playing right now"

