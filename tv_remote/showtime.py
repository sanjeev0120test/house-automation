"""One checked pass across the TV: home, volume, apps, then YouTube."""

from __future__ import annotations

import re
import time
from pathlib import Path

from tv_remote import adb, keys

SHOW_QUERY = "eminem not afraid official"
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
    skip_presses = 0
    clip_started = 0.0


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


def _guard_clip() -> None:
    if _Run.clip_started and time.time() - _Run.clip_started > 10:
        raise RuntimeError("the YouTube clip ran longer than 10 seconds")


def _play_track() -> str:
    """Open the track, press OK while Skip can be focused, then leave it up briefly."""
    video_id, title = keys._first_youtube_result(SHOW_QUERY)
    _Run.video_id = video_id
    _Run.expected_title = title
    keys.open_youtube_video(video_id)
    opened = time.time()
    matched_at: float | None = None
    saw_other = False
    presses = 0
    info: dict[str, object] = {}
    while time.time() - opened < 22:
        age = time.time() - opened
        # Skip usually enables at 5s. Keep sending OK through 9s even if the
        # media title already shows the song, because YouTube often reports
        # that title while the ad is still on screen.
        if age >= 4:
            keys.press_skip_ad()
            presses += 1
        info = keys.playback()
        actual = str(info.get("title") or "")
        matched = _titles_agree(title, actual) and info.get("state") in (3, 6)
        if actual and actual.lower() not in {"null", "none"} and not _titles_agree(title, actual):
            saw_other = True
        if _titles_agree(title, actual) and info.get("state") == 2:
            keys.media_play()
            info = keys.playback()
            actual = str(info.get("title") or "")
            matched = _titles_agree(title, actual) and info.get("state") in (3, 6)
        if age >= 4 and (age < 9 or not matched):
            keys.press_skip_ad()
            presses += 1
        if matched:
            if matched_at is None:
                matched_at = time.time()
            if age >= 8.5 and time.time() - matched_at >= 1.2:
                break
        else:
            matched_at = None
        time.sleep(0.3)
    else:
        actual = str(info.get("title") or "nothing")
        raise RuntimeError(f"wanted \"{title}\", TV reported \"{actual}\"")
    _Run.skip_presses = presses
    _Run.clip_started = time.time()
    if saw_other:
        _Run.ads_skipped += 1
    _guard_clip()
    actual = str(info.get("title") or title)
    ad_bit = ", ad title cleared after OK" if saw_other else ", OK armed for Skip"
    return f"\"{actual}\" for a few seconds ({presses} OK presses{ad_bit})"


def _pause() -> str:
    _guard_clip()
    keys.media_pause()
    return _wait_state(2, "paused")


def _stop_and_home() -> str:
    """Leave the clip so it does not keep playing."""
    _guard_clip()
    keys.media_pause()
    keys.home()
    package = _wait_foreground("launcher", 8)
    info = keys.playback()
    if info.get("state") == 3:
        keys.media_pause()
        time.sleep(0.4)
        info = keys.playback()
    if info.get("state") == 3:
        raise RuntimeError("video was still playing after Home")
    state = STATE_NAMES.get(info.get("state"), "stopped")
    return f"launcher {package}, playback {state}"


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
    if info.get("state") == 3:
        raise RuntimeError("the clip is still playing")
    title = str(info.get("title") or "nothing")
    state = STATE_NAMES.get(info.get("state"), "stopped")
    return f"{state}: {title}"


def run() -> int:
    """Run the showtime sequence. Returns 0 when every TV check passes."""
    _Run.last_package = ""
    _Run.video_id = ""
    _Run.expected_title = ""
    _Run.position_at_start = 0
    _Run.ads_skipped = 0
    _Run.skip_presses = 0
    _Run.clip_started = 0.0

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
                "YouTube clip",
                f"Play the first result for \"{SHOW_QUERY}\" for a few seconds. OK presses Skip as soon as YouTube focuses that button.",
                _play_track,
            ),
            ("Pause", "Pause that clip and confirm the TV reports paused.", _pause),
            (
                "Stop",
                "Go Home and confirm the clip is not still playing.",
                _stop_and_home,
            ),
            (
                "Screenshot",
                "Capture the TV after the clip has stopped and confirm a real PNG was saved.",
                _screenshot,
            ),
            (
                "Now playing",
                "Read the media session and confirm the clip was not left running.",
                _now_playing,
            ),
        ]
    )

    _Run.ads_skipped = 0
    _Run.skip_presses = 0
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
    presses = _Run.skip_presses
    if _Run.ads_skipped:
        ad_line = f"An ad title cleared after {presses} OK presses."
    else:
        ad_line = (
            f"{presses} OK presses while Skip can be focused. "
            "No separate ad title showed on this run."
        )
    print(f"=== Showtime: {passed} ok, {failures} failed, {elapsed:.0f}s ===", flush=True)
    print(ad_line, flush=True)
    if failures == 0:
        print("The clip was stopped and the TV is back on the launcher.\n", flush=True)
    return 1 if failures else 0
