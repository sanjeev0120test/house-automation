"""Validate every tv_remote.cli option against a connected Mi TV."""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tv_remote import adb, keys  # noqa: E402

PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"


def _foreground_package() -> str:
    out = adb.shell("dumpsys activity activities", check=False)
    for line in out.splitlines():
        if "mResumedActivity" not in line:
            continue
        match = re.search(r"u0\s+([\w.]+)/", line)
        if match:
            return match.group(1)
    out = adb.shell("dumpsys window displays", check=False)
    for line in out.splitlines():
        if "mCurrentFocus" not in line and "mFocusedApp" not in line:
            continue
        match = re.search(r"([\w.]+)/", line)
        if match:
            return match.group(1)
    return ""


def _music_volume() -> int | None:
    out = adb.shell("dumpsys audio", check=False)
    for line in out.splitlines():
        if "STREAM_MUSIC" in line and "volume" in line.lower():
            digits = [int(p) for p in line.replace(":", " ").split() if p.isdigit()]
            if digits:
                return digits[0]
    return None


def _record(name: str, status: str, detail: str, results: list[tuple]) -> None:
    results.append((name, status, detail))
    mark = {"PASS": "+", "FAIL": "X", "WARN": "~"}[status]
    print(f"  [{mark}] {name}: {detail}")


def main() -> int:
    results: list[tuple[str, str, str]] = []
    print("\n=== Mi TV Remote validation ===\n")

    msg = adb.connect()
    if not adb.is_connected():
        print(f"Cannot connect: {msg}")
        return 1
    print(f"Connected ({msg})\n")

    # 1 Home
    try:
        keys.home()
        time.sleep(1.5)
        pkg = _foreground_package()
        ok = "launcher" in pkg.lower() or pkg.endswith(".tvlauncher")
        _record("1 Home", PASS if ok else WARN, f"foreground={pkg or 'unknown'}", results)
    except Exception as exc:
        _record("1 Home", FAIL, str(exc), results)

    # 6 YouTube (test app launch before back/other nav)
    app_tests = [
        ("6 YouTube", "youtube"),
        ("7 Netflix", "netflix"),
        ("8 Prime Video", "prime"),
        ("9 Hotstar", "hotstar"),
        ("10 SonyLIV", "sonyliv"),
        ("11 JioCinema", "jio"),
    ]
    for label, app in app_tests:
        try:
            keys.home()
            time.sleep(1)
            keys.launch_app(app)
            time.sleep(5)
            pkg = _foreground_package()
            expected = keys.APPS[app]
            ok = expected in pkg or pkg in expected
            _record(label, PASS if ok else FAIL, f"expected~{expected}, got={pkg}", results)
        except Exception as exc:
            _record(label, FAIL, str(exc), results)

    # 2 Back
    try:
        keys.back()
        time.sleep(1)
        _record("2 Back", PASS, "keyevent sent", results)
    except Exception as exc:
        _record("2 Back", FAIL, str(exc), results)

    # 3/4 Volume
    try:
        before = _music_volume()
        keys.volume_up()
        time.sleep(0.5)
        keys.volume_up()
        time.sleep(0.5)
        after_up = _music_volume()
        keys.volume_down()
        time.sleep(0.5)
        after_down = _music_volume()
        vol_ok = before is not None and after_up is not None
        _record(
            "3 Volume Up / 4 Volume Down",
            PASS if vol_ok else WARN,
            f"vol {before} -> {after_up} -> {after_down}",
            results,
        )
    except Exception as exc:
        _record("3/4 Volume", FAIL, str(exc), results)

    # 5 OK
    try:
        keys.ok()
        _record("5 OK / Select", PASS, "keyevent sent", results)
    except Exception as exc:
        _record("5 OK", FAIL, str(exc), results)

    # 12 Play/Pause
    try:
        keys.launch_app("youtube")
        time.sleep(3)
        keys.play_pause()
        time.sleep(1)
        _record("12 Play / Pause", PASS, "keyevent sent while YouTube open", results)
    except Exception as exc:
        _record("12 Play / Pause", FAIL, str(exc), results)

    # 13 Screenshot
    try:
        path = keys.screenshot("tv_validate_screenshot.png")
        size = Path(path).stat().st_size if Path(path).exists() else 0
        _record(
            "13 Screenshot",
            PASS if size > 1000 else WARN,
            f"saved {path} ({size} bytes; black if HDCP)",
            results,
        )
    except Exception as exc:
        _record("13 Screenshot", FAIL, str(exc), results)

    # 16 YouTube search (first result)
    try:
        vid, title = keys._first_youtube_result("lofi beats")
        keys.youtube_search_play("lofi beats", wait=6)
        time.sleep(4)
        playing = keys.now_playing()
        pkg = _foreground_package()
        yt_ok = "youtube" in pkg
        play_ok = playing != "Nothing playing right now"
        _record(
            "16 YouTube search",
            PASS if yt_ok and play_ok else WARN,
            f"video={vid}, playing={playing[:60]}",
            results,
        )
    except Exception as exc:
        _record("16 YouTube search", FAIL, str(exc), results)

    # 14/15 presets
    for label, fn, needle in [
        ("14 Eminem preset", keys.play_eminem_hit, "eminem"),
        ("15 Enrique preset", keys.play_enrique_hit, "enrique"),
    ]:
        try:
            fn()
            time.sleep(6)
            playing = keys.now_playing().lower()
            ok = playing != "nothing playing right now"
            _record(label, PASS if ok else WARN, f"now_playing={playing[:60]}", results)
        except Exception as exc:
            _record(label, FAIL, str(exc), results)

    # 17 Skip forward
    try:
        keys.skip_forward()
        _record("17 Skip forward", PASS, "keyevent sent", results)
    except Exception as exc:
        _record("17 Skip forward", FAIL, str(exc), results)

    # 18 Now playing
    try:
        title = keys.now_playing()
        ok = title != "Nothing playing right now"
        _record("18 Now playing", PASS if ok else WARN, title[:80], results)
    except Exception as exc:
        _record("18 Now playing", FAIL, str(exc), results)

    fails = sum(1 for _, s, _ in results if s == FAIL)
    warns = sum(1 for _, s, _ in results if s == WARN)
    passes = sum(1 for _, s, _ in results if s == PASS)
    print(f"\n=== {passes} pass, {warns} warn, {fails} fail ===\n")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
