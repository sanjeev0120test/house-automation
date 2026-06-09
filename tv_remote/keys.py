"""TV remote keys and app shortcuts for Mi TV."""

import time
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
    pkg = APPS.get(name.lower())
    if not pkg:
        raise ValueError(f"Unknown app: {name}")
    adb.ensure_connected()
    adb.shell(
        f"monkey -p {pkg} -c android.intent.category.LEANBACK_LAUNCHER 1",
        check=False,
    )


def screenshot(path: str = "tv_screenshot.png") -> str:
    """Capture what's on TV screen and save locally."""
    adb.ensure_connected()
    adb.shell("screencap -p /sdcard/tv_cap.png")
    adb.pull("/sdcard/tv_cap.png", path)
    return path


def youtube_search_play(query: str, wait: float = 6.0) -> str:
    """Search YouTube on TV and play the first result."""
    adb.ensure_connected()
    url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
    pkg = APPS["youtube"]
    adb.shell(
        f'am start -a android.intent.action.VIEW -d "{url}" {pkg}',
        check=False,
    )
    time.sleep(wait)
    adb.keyevent(DOWN)
    time.sleep(0.8)
    adb.keyevent(OK)
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
    """Return title of currently playing media, if any."""
    adb.ensure_connected()
    out = adb.shell("dumpsys media_session", check=False)
    for line in out.splitlines():
        if "description=" not in line:
            continue
        desc = line.split("description=", 1)[1].strip()
        if desc and desc != "null":
            title = desc.split(",")[0].strip()
            if title:
                return title
    return "Nothing playing right now"

