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


def launch_app(name: str) -> None:
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
    time.sleep(1.5)


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


def _find_skip_ad_target(xml: str) -> tuple[int, int] | None:
    """Return tap coordinates for an enabled Skip Ad control, if visible."""
    for node in re.findall(r"<node[^>]+/?>", xml):
        if not re.search(r"skip\s*ad", node, re.IGNORECASE):
            continue
        if 'enabled="false"' in node or 'clickable="false"' in node:
            continue
        bounds = re.search(
            r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', node
        )
        if not bounds:
            continue
        x1, y1, x2, y2 = (int(v) for v in bounds.groups())
        width, height = x2 - x1, y2 - y1
        if width >= 40 and height >= 20:
            return (x1 + x2) // 2, (y1 + y2) // 2
    return None


def _try_skip_ad() -> bool:
    """Skip a YouTube ad when the on-screen button is enabled."""
    target = _find_skip_ad_target(_ui_dump())
    if target:
        adb.tap(*target)
        return True

    adb.keyevent(RIGHT)
    time.sleep(0.25)
    target = _find_skip_ad_target(_ui_dump())
    if target:
        adb.tap(*target)
        return True

    return False


def _skip_youtube_ads(
    expected_title: str | None = None,
    max_seconds: float = 90.0,
    poll_interval: float = 2.0,
) -> None:
    """Poll for skippable ads and press Skip Ad when it becomes available."""
    deadline = time.time() + max_seconds
    while time.time() < deadline:
        if _find_skip_ad_target(_ui_dump()):
            _try_skip_ad()
            time.sleep(1.0)
            continue

        playing = now_playing()
        if playing != "Nothing playing right now":
            lower = playing.lower()
            ad_hint = any(
                token in lower
                for token in (" sponsored", " advertisement", " visit site")
            )
            title_mismatch = (
                expected_title
                and expected_title.lower()[:24] not in lower
                and time.time() < deadline - max_seconds + 30
            )
            if ad_hint or title_mismatch:
                _try_skip_ad()

        time.sleep(poll_interval)


def _start_youtube_ad_skipper(
    expected_title: str | None = None,
    max_seconds: float = 90.0,
) -> None:
    """Watch for skippable ads in the background after playback starts."""
    thread = threading.Thread(
        target=_skip_youtube_ads,
        kwargs={"expected_title": expected_title, "max_seconds": max_seconds},
        daemon=True,
    )
    thread.start()


def youtube_search_play(query: str, wait: float = 5.0) -> str:
    """Search YouTube and play the first result, skipping ads when possible."""
    adb.ensure_connected()
    video_id, title = _first_youtube_result(query)
    watch_url = f"https://www.youtube.com/watch?v={video_id}"
    pkg = APPS["youtube"]
    adb.shell(
        f'am start -a android.intent.action.VIEW -d "{watch_url}" {pkg}',
        check=False,
    )
    time.sleep(wait)
    _start_youtube_ad_skipper(expected_title=title)
    return query


def play_eminem_hit() -> str:
    return youtube_search_play("eminem not afraid official")


def play_enrique_hit() -> str:
    return youtube_search_play("enrique iglesias hero official")


def skip_forward() -> None:
    _press(SKIP_FORWARD)


def show_recent_apps() -> None:
    _press(APP_SWITCH)


def now_playing() -> str:
    """Return title of the active playback session, if any."""
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
            match = re.search(r"state=(\d+)", stripped)
            if match:
                current["state"] = int(match.group(1))
            continue
        if stripped.startswith("metadata:") and "description=" in stripped:
            desc = stripped.split("description=", 1)[1].strip()
            if desc and desc != "null":
                current["description"] = desc
    if current:
        sessions.append(current)

    def _title(session: dict[str, object]) -> str | None:
        desc = session.get("description")
        if not isinstance(desc, str):
            return None
        title = desc.split(",")[0].strip()
        return title or None

    active = [
        s for s in sessions if s.get("state") == 3 and _title(s)
    ]
    if not active:
        active = [s for s in sessions if _title(s)]

    if active:
        title = _title(active[0])
        if title:
            return title
    return "Nothing playing right now"

