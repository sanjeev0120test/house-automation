"""One checked pass across the TV: home, volume, apps, then YouTube."""

from __future__ import annotations

import re
import time
from pathlib import Path

from tv_remote import adb, keys

SHOW_QUERY = "eminem not afraid official"
START_AT = 8
SEEK_TO = 40
APPS = (
    ("youtube", "YouTube"),
    ("netflix", "Netflix"),
    ("prime", "Prime Video"),
    ("hotstar", "Hotstar"),
    ("sonyliv", "SonyLIV"),
    ("jio", "JioCinema"),
)
STATE_NAMES = {2: "paused", 3: "playing", 6: "buffering"}


class _Run:
    last_package = ""
    video_id = ""
    expected_title = ""
    position_at_start = 0
    ads_skipped = 0


# Just long enough to see each change. The TV confirm is the real wait.
BEAT = 0.4


def _titles_agree(expected: str, actual: str) -> bool:
    actual_l = actual.casefold()
    words = [
        word
        for word in re.findall(r"[a-z0-9']+", expected.casefold())
        if len(word) > 3
    ]
    if not words:
        return expected.casefold()[:12] in actual_l
    return any(len(word) > 4 and word in actual_l for word in words)


def _wait_foreground(expected: str, timeout: float) -> str:
    deadline = time.time() + timeout
    seen = ""
    while time.time() < deadline:
        seen = keys.foreground_package()
        if expected in seen or (seen and seen in expected):
            return seen
        time.sleep(0.35)
    raise RuntimeError(f"expected {expected}, TV was showing {seen or 'nothing readable'}")


def _connect() -> str:
    message = adb.connect()
    if not adb.is_connected():
        raise RuntimeError(message or "ADB did not connect")
    model = adb.shell("getprop ro.product.model", check=False).strip() or "Android TV"
    return f"{model}, {message}"


def _home() -> str:
    keys.home()
    package = _wait_foreground("launcher", 10)
    _Run.last_package = package
    return f"launcher in front ({package})"


def _volume_roundtrip() -> str:
    original = keys.music_volume()
    if original is None:
        raise RuntimeError("the TV did not report music volume")
    if original >= 97:
        for _ in range(3):
            keys.volume_down()
            time.sleep(0.2)
        dipped = keys.music_volume()
        for _ in range(3):
            keys.volume_up()
            time.sleep(0.2)
        restored = keys.music_volume()
        if dipped is None or dipped >= original:
            raise RuntimeError(f"volume stayed at {original}")
        if restored != original:
            raise RuntimeError(f"volume did not return to {original} (now {restored})")
        return f"{original} -> {dipped} -> {restored}"

    for _ in range(3):
        keys.volume_up()
        time.sleep(0.2)
    raised = keys.music_volume()
    current = raised
    nudges = 0
    while current is not None and current > original and nudges < 8:
        keys.volume_down()
        time.sleep(0.2)
        current = keys.music_volume()
        nudges += 1
    if raised is None or raised <= original:
        raise RuntimeError(f"volume did not rise ({original} -> {raised})")
    if current != original:
        raise RuntimeError(f"volume did not return ({original} -> {raised} -> {current})")
    return f"{original} -> {raised} -> {current}"


def _open_app(name: str) -> str:
    expected = keys.APPS[name]
    keys.launch_app(name, settle=0.15)
    package = _wait_foreground(expected, 14)
    _Run.last_package = package
    return f"{package} is in front"


def _back_from_last_app() -> str:
    previous = _Run.last_package
    if not previous:
        raise RuntimeError("no app was opened to leave")
    for _ in range(2):
        keys.back()
        deadline = time.time() + 3.5
        while time.time() < deadline:
            package = keys.foreground_package()
            if package and package != previous:
                _Run.last_package = package
                return f"left {previous}, now {package}"
            time.sleep(0.35)
    raise RuntimeError(f"Back did not leave {previous}")


def _await_track(timeout: float) -> dict[str, object]:
    """Wait until the chosen video is playing, tapping Skip Ad when it appears."""
    title = _Run.expected_title
    deadline = time.time() + timeout
    next_dump = time.time() + 4.5
    info: dict[str, object] = {}
    while time.time() < deadline:
        info = keys.playback()
        actual = str(info.get("title") or "")
        if _titles_agree(title, actual) and info.get("state") in (3, 6):
            return info
        if time.time() >= next_dump:
            if keys.skip_ad_if_shown():
                _Run.ads_skipped += 1
                next_dump = time.time() + 2.0
            else:
                next_dump = time.time() + 3.5
        time.sleep(0.35)
    actual = str(info.get("title") or "nothing")
    raise RuntimeError(f"wanted \"{title}\", TV reported \"{actual}\"")


def _ad_note(before: int) -> str:
    skipped = _Run.ads_skipped - before
    if skipped <= 0:
        return ""
    word = "ad" if skipped == 1 else "ads"
    return f", skipped {skipped} {word}"


def _play_track() -> str:
    video_id, title = keys._first_youtube_result(SHOW_QUERY)
    _Run.video_id = video_id
    _Run.expected_title = title
    before = _Run.ads_skipped
    keys.open_youtube_video(video_id, START_AT)
    info = _await_track(40)
    position = info.get("position_ms")
    _Run.position_at_start = int(position) if isinstance(position, int) else 0
    actual = str(info.get("title") or title)
    return f"playing \"{actual}\" from about {START_AT}s{_ad_note(before)}"


def _seek_ahead() -> str:
    if not _Run.video_id:
        raise RuntimeError("no video was started")
    before = _Run.ads_skipped
    keys.open_youtube_video(_Run.video_id, SEEK_TO)
    deadline = time.time() + 16
    next_dump = time.time() + 4.5
    info: dict[str, object] = {}
    while time.time() < deadline:
        info = keys.playback()
        actual = str(info.get("title") or "")
        position = info.get("position_ms")
        title_ok = _titles_agree(_Run.expected_title, actual)
        if title_ok and isinstance(position, int):
            near_target = 30_000 <= position <= 90_000
            moved = (
                _Run.position_at_start >= 50_000
                and position + 15_000 < _Run.position_at_start
            )
            if near_target or moved:
                return (
                    f"playback is at {position // 1000}s "
                    f"(jumped to {SEEK_TO}s){_ad_note(before)}"
                )
        elif time.time() >= next_dump:
            if keys.skip_ad_if_shown():
                _Run.ads_skipped += 1
                next_dump = time.time() + 2.0
            else:
                next_dump = time.time() + 3.5
        time.sleep(0.35)
    position = info.get("position_ms")
    raise RuntimeError(f"seek to {SEEK_TO}s did not land (position={position})")


def _pause() -> str:
    keys.media_pause()
    return _wait_state(2, "paused")


def _resume() -> str:
    keys.media_play()
    return _wait_state(3, "playing")


def _wait_state(wanted: int, label: str) -> str:
    deadline = time.time() + 8
    state: object = None
    while time.time() < deadline:
        info = keys.playback()
        state = info.get("state")
        actual = str(info.get("title") or "")
        if state == wanted and _titles_agree(_Run.expected_title, actual):
            return f"{label}, still \"{actual}\""
        time.sleep(0.35)
    raise RuntimeError(f"expected {label}, media state was {state}")


def _screenshot() -> str:
    path = Path(keys.screenshot("tv_screenshot_showtime.png"))
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise RuntimeError(f"{path} is not a PNG")
    if len(data) < 5000:
        raise RuntimeError(f"{path} is only {len(data)} bytes")
    return f"saved {path.name} ({len(data)} bytes)"


def _now_playing() -> str:
    info = keys.playback()
    title = str(info.get("title") or "")
    if not _titles_agree(_Run.expected_title, title):
        raise RuntimeError(f"expected the showtime track, TV said \"{title or 'nothing'}\"")
    state = STATE_NAMES.get(info.get("state"), str(info.get("state")))
    position = info.get("position_ms")
    seconds = f"{int(position) // 1000}s" if isinstance(position, int) else "an unknown time"
    return f"{state} at {seconds}: {title}"


def run() -> int:
    """Run the showtime sequence. Returns 0 when every TV check passes."""
    _Run.last_package = ""
    _Run.video_id = ""
    _Run.expected_title = ""
    _Run.position_at_start = 0

    steps: list[tuple[str, str, object]] = [
        ("Connect", "Join the TV over ADB and read its model.", _connect),
        ("Home", "Open the launcher and confirm it is the screen in front.", _home),
        (
            "Volume",
            "Raise music volume, confirm the TV reports the change, then put it back.",
            _volume_roundtrip,
        ),
    ]
    for name, label in APPS:
        steps.append(
            (
                label,
                f"Open {label} and confirm that package is the focused window.",
                lambda name=name: _open_app(name),
            )
        )
    steps.extend(
        [
            (
                "Back",
                "Leave the last app and confirm the focused window changed.",
                _back_from_last_app,
            ),
            (
                "YouTube track",
                f"Search \"{SHOW_QUERY}\", play the first result near {START_AT}s, skip an ad if one is on screen, and confirm the title.",
                _play_track,
            ),
            (
                "Jump ahead",
                f"Re-open that same video at {SEEK_TO}s and confirm playback moved there.",
                _seek_ahead,
            ),
            ("Pause", "Pause the track and confirm the TV reports paused.", _pause),
            ("Resume", "Start it again and confirm the TV reports playing.", _resume),
            (
                "Screenshot",
                "Capture the TV screen and confirm a real PNG was saved here.",
                _screenshot,
            ),
            (
                "Now playing",
                "Read the active media session and confirm it is still this track.",
                _now_playing,
            ),
        ]
    )

    _Run.ads_skipped = 0
    started = time.time()
    print("\n=== Showtime ===", flush=True)
    print("Each step runs on the TV, then the TV's own state is checked.\n", flush=True)
    failures = 0
    total = len(steps)
    for index, (name, blurb, action) in enumerate(steps, start=1):
        print(f"[{index}/{total}] {name}", flush=True)
        print(f"       {blurb}", flush=True)
        try:
            detail = action()
            print(f"       OK: {detail}\n", flush=True)
        except Exception as exc:
            failures += 1
            print(f"       FAIL: {exc}\n", flush=True)
        time.sleep(BEAT)

    passed = total - failures
    elapsed = time.time() - started
    ads = _Run.ads_skipped
    ad_line = (
        f"Skipped {ads} ad{'s' if ads != 1 else ''}."
        if ads
        else "No ad button appeared on this run."
    )
    print(f"=== Showtime: {passed} ok, {failures} failed, {elapsed:.0f}s ===", flush=True)
    print(ad_line, flush=True)
    if failures == 0:
        print("The TV should be playing the YouTube track from this run.\n", flush=True)
    return 1 if failures else 0
