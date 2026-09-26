# House Automation - TV

Control an Android TV from your computer over WiFi using Python and ADB. Tested on Android TV with Network debugging enabled.

```bash
cp config/tv.json.example config/tv.json   # once: set YOUR_TV_IP
./scripts/check_connection.ps1             # verify network + ADB
python -m tv_remote.cli                    # run the numbered remote
python -m tv_remote.cli showtime           # one checked pass across the TV
python scripts/validate_remote.py          # optional: test menu options 1–18
```

**Requirements:** Python 3.10+, [Android platform-tools](https://developer.android.com/tools/releases/platform-tools) at `tools/platform-tools/adb`, TV and computer on the same WiFi, `config/tv.json` with your TV IP (gitignored).

---

## Table of contents

- [Overview](#overview)
- [One-time setup](#one-time-setup)
- [Remote menu](#remote-menu)
- [Showtime](#showtime)
- [Architecture](#architecture)
- [YouTube search and ad skip](#youtube-search-and-ad-skip)
- [Validation](#validation)
- [Issues found and fixes](#issues-found-and-fixes)
- [What else ADB can automate](#what-else-adb-can-automate)
- [Wireless debugging (pairing)](#wireless-debugging-pairing)
- [Security](#security)
- [Troubleshooting](#troubleshooting)
- [Project layout](#project-layout)

---

## Overview

This project exposes a numbered CLI menu that sends ADB commands to the TV. No IR blaster, no cloud service, no third-party Python packages — only the standard library plus a local ADB binary.

On startup the CLI reads `config/tv.json`, runs `adb connect`, and waits for menu input. Each option maps to one function in `tv_remote/keys.py` that calls `adb shell`, `adb shell input keyevent`, or `adb shell am start`.

**Verified app packages on test device** (defined in `tv_remote/keys.py`):

| Short name | Package |
|------------|---------|
| youtube | `com.google.android.youtube.tv` |
| netflix | `com.netflix.ninja` |
| prime | `com.amazon.amazonvideo.livingroom` |
| hotstar | `in.startv.hotstar` |
| sonyliv | `com.sonyliv` |
| jio | `com.jio.media.stb.ondemand` |

Other Android TV models may have different package names. Confirm with:

```bash
adb shell pm list packages | grep -iE 'youtube|netflix|hotstar|jio|sony|amazon'
```

---

## One-time setup

### On the TV

| Step | Path |
|------|------|
| Enable Developer options | Settings → Device Preferences → About → click **Build** 7 times |
| USB debugging | Developer options → **ON** |
| Network debugging | Developer options → **ON** (default ADB port **5555**) |
| Authorize this computer | When prompted on TV, tap **Always allow** |

Read the TV IP: **Settings → Network → WiFi → [your network] → IP address**.

### On your computer

1. Install [Android platform-tools](https://developer.android.com/tools/releases/platform-tools) and place the `adb` binary under `tools/platform-tools/` (this path is gitignored).
2. Copy the config template and set your IP:

```bash
cp config/tv.json.example config/tv.json
# edit config/tv.json and set YOUR_TV_IP
```

```json
{"host": "YOUR_TV_IP", "port": 5555}
```

3. Confirm connectivity:

```bash
./scripts/check_connection.ps1
```

Expected: TCP port 5555 is open and `adb devices` shows `YOUR_TV_IP:5555    device`. Ping can fail even when that port is open.

4. Start the remote:

```bash
python -m tv_remote.cli
```

Type **1–19** to act, **q** to quit. Option **19** is the same sequence as `python -m tv_remote.cli showtime`.

---

## Remote menu

| Key | Action | ADB mechanism |
|-----|--------|---------------|
| 1 | Home | `input keyevent 3` |
| 2 | Back | `input keyevent 4` |
| 3 | Volume up | `input keyevent 24` |
| 4 | Volume down | `input keyevent 25` |
| 5 | OK / Select | `input keyevent 23` |
| 6 | Open YouTube | `monkey -p com.google.android.youtube.tv …` (can show the account picker) |
| 7 | Open Netflix | `monkey -p com.netflix.ninja …` |
| 8 | Open Prime Video | `monkey -p com.amazon.amazonvideo.livingroom …` |
| 9 | Open Hotstar | `monkey -p in.startv.hotstar …` |
| 10 | Open SonyLIV | `monkey -p com.sonyliv …` |
| 11 | Open JioCinema | `am start -n com.jio.media.stb.ondemand/com.v18.voot.ui.JVHomeActivity` |
| 12 | Play / Pause | `input keyevent 85` |
| 13 | Screenshot | `screencap` on device → `adb pull` to local file |
| 14 | Eminem on YouTube | YouTube search preset → first result |
| 15 | Enrique on YouTube | YouTube search preset → first result |
| 16 | YouTube search | Prompt for query → first result |
| 17 | Skip forward ~30 s | Reopen the video 30 s ahead (`youtu.be?t=`) when this process opened it and YouTube is in front. Otherwise key 272 |
| 18 | Now playing | Parse `dumpsys media_session` for active playback |
| 19 | Showtime | Cocomelon first, volume while that video plays, then the other kids clips and apps |
| q | Quit | Exit CLI |

Options **14–16** print `Playing first result for: …` instead of `OK: …`. That line names the search, not the row. The video opened is the first regular result, or the next one when the top hit is a mix, compilation, hour-long video, or playlist. Option **6** opens the YouTube app itself. Showtime does not; it opens a watch URL, so the account picker stays closed.

---

## Showtime

```bash
python -m tv_remote.cli showtime
```

Each step prints what it is about to do, runs it, then checks the TV before the next one. The pause between steps is under half a second. Kids videos come first. Each one is searched, Shorts are skipped, and the first regular result is opened — or the next result when that title is a mix, compilation, hour-long video, or playlist. It stays up until about 7.5 seconds after open and that title has been playing for about a second, then it is paused and sent back to the launcher.

The order is connect, home, then Cocomelon. That video is opened directly, and while it is playing the volume goes up and back down. If the level is already near the top, it goes down and back up instead. Then Shubh (We Rollin), Wheels on the Bus, the ABC song, and the Bath song. After those: Netflix, Prime Video, Hotstar, SonyLIV, JioCinema, back, a short Eminem clip, pause, home, screenshot, and now playing. The YouTube app home and account picker are not opened. OK / Select is left out: on the launcher it would open whichever tile is focused.

YouTube draws Skip inside its own player, not as a normal Android control, so a screen dump cannot see the label. When Skip turns on, YouTube focuses it. From about four seconds in, Showtime sends OK until the opened title has been playing for about a second, so the press lands as soon as that focus appears. An unskippable ad still has to finish. The wait stops at about 22 seconds if the title never appears. Cocomelon stays up a little longer than the other clips because volume is changed while that video is still playing. After the volume is back, it is paused and Home is opened.

---

## Architecture

```
┌─────────────┐     WiFi (TCP 5555)     ┌──────────────────┐
│  Computer   │ ◄──────────────────────►│   Android TV     │
│             │                         │                  │
│ tv_remote/  │   adb connect / shell   │  YouTube, Netflix│
│  cli.py     │   input keyevent        │  Prime, etc.     │
│  keys.py    │   am start (intents)    │                  │
│  adb.py     │   dumpsys / screencap   │                  │
└─────────────┘                         └──────────────────┘
       │
       │  YouTube search only:
       ▼
  HTTP GET youtube.com/results  →  first regular video, or the next if it is a mix  →  open watch URL on TV
```

| Module | Responsibility |
|--------|----------------|
| `tv_remote/adb.py` | Load `config/tv.json`, run `adb`, connect, keyevent, shell, tap, pull |
| `tv_remote/keys.py` | Remote actions, app launch, YouTube resolve/play, ad-skip thread, now playing |
| `tv_remote/cli.py` | Numbered menu loop and error handling |
| `tv_remote/showtime.py` | Kids clips first, volume during Cocomelon, then the other apps, then a short clip |
| `scripts/check_connection.ps1` | Ping, TCP port, `adb connect`, `adb devices` |
| `scripts/validate_remote.py` | Automated pass/fail test for menu options 1–18 |

---

## YouTube search and ad skip

### Search (options 14, 15, 16)

**Previous behaviour (broken):** open `youtube.com/results?search_query=…` on the TV, wait, send **DOWN**, then **OK**. On the test device focus was already on the first result; **DOWN** moved to the **second row**.

**Current behaviour (fixed):**

1. Computer fetches `https://www.youtube.com/results?search_query=…`
2. Parses `ytInitialData` JSON for `videoRenderer` entries, skipping Shorts and empty titles
3. Takes the first of those, or the next one when that title is a mix, compilation, hour-long video, or playlist. Showtime uses the same choice
4. Opens `https://www.youtube.com/watch?v=VIDEO_ID` on the TV via `am start -a android.intent.action.VIEW`

No DPAD navigation. The printed line still says `Playing first result for: …` even when step 3 moves to the next video.

### Ad skip

YouTube on this TV draws the Skip control inside the video player. `uiautomator dump` returns an empty player view, so there is no label to tap.

When Skip becomes available, YouTube focuses it. Sending OK (`keyevent 23`) activates that focused control. Options **14–16** start a background watcher that sends OK about every half second for the first 12 seconds, and keeps sending it until the media title matches, for at most 18 seconds. Showtime does not start that watcher. It sends OK itself from about four seconds in until the opened title has been playing for about a second.

**Limitation:** an unskippable ad has no Skip control, so OK cannot dismiss it. Showtime then pauses and opens the launcher. That can take up to about 22 seconds if the real title is slow to appear.

---

## Validation

Run the full suite (takes ~3 minutes; switches apps and plays YouTube):

```bash
python scripts/validate_remote.py
```

Last verified menu run: **17 pass, 0 warn, 0 fail**.

Showtime, checked on the TV:

```bash
python -m tv_remote.cli showtime
```

**18 ok, 0 failed, 170s.** Cocomelon opened result 1 directly (no account picker). While that video was playing, volume went 18 → 21 → 18 and the same title was still playing. Shubh (We Rollin), Wheels on the Bus, the ABC song, and the Bath song each opened result 1, matched on the TV, and were paused. Netflix, Prime Video, Hotstar, SonyLIV, and JioCinema came to the front. The YouTube app home is not opened.

The menu script records 17 checks for options 1–18 (volume up and down are one check). It reads the foreground app from `dumpsys activity activities` (`mResumedActivity`) and volume from `dumpsys audio`. Showtime reads the focused window from `dumpsys window` (`mCurrentFocus`) and music volume from `media volume --stream 3 --get`. Both use `now_playing()` for playback.

Quick connection check only:

```bash
./scripts/check_connection.ps1
```

Manual ADB check:

```bash
adb devices
adb shell dumpsys media_session
```

---

## Issues found and fixes

Each item below was reproduced on hardware, diagnosed with ADB, and fixed in code.

### 1. YouTube search played the second result

| | |
|---|---|
| **Symptom** | Searching for a song opened search results, then played the wrong (second) video |
| **Diagnosis** | Opened search URL + `keyevent DOWN` + `keyevent OK`. TV focus was already on row 1; DOWN selected row 2 |
| **Fix** | Resolve first `videoId` on the computer; open `watch?v=` URL directly. Removed DPAD navigation from search flow |
| **File** | `tv_remote/keys.py` — `_first_youtube_result()`, `youtube_search_play()` |

### 2. JioCinema did not come to foreground

| | |
|---|---|
| **Symptom** | Option 11 reported success but SonyLIV (previous app) stayed active |
| **Diagnosis** | `monkey -p com.jio.media.stb.ondemand …` injected events but did not reliably resume JioCinema. Package exists: confirmed via `pm list packages`. Launch activity resolved via `cmd package resolve-activity`: `com.v18.voot.ui.JVHomeActivity` |
| **Fix** | Use explicit `am start -n com.jio.media.stb.ondemand/com.v18.voot.ui.JVHomeActivity` for JioCinema; keep `monkey` for other apps |
| **File** | `tv_remote/keys.py` — `APP_ACTIVITIES`, `launch_app()` |

### 3. Now playing showed stale or wrong title

| | |
|---|---|
| **Symptom** | Option 18 returned the first `description=` line in `dumpsys media_session`, not the actively playing track |
| **Diagnosis** | Multiple apps register media sessions (YouTube, Netflix, Prime). Idle sessions still had metadata |
| **Fix** | Parse sessions by `package=`, read `state=` (prefer `state=3` = playing), then read `description=` |
| **File** | `tv_remote/keys.py` — `now_playing()` |

### 4. Crash on Unicode titles

| | |
|---|---|
| **Symptom** | `UnicodeDecodeError` / `AttributeError` when ad-skip thread called `now_playing()` during tracks with emoji titles |
| **Diagnosis** | `subprocess.run(..., text=True)` used the system default encoding; ADB output contained UTF-8 emoji |
| **Fix** | Set `encoding="utf-8", errors="replace"` on all ADB subprocess calls; guard `stdout` with `(result.stdout or "")` |
| **File** | `tv_remote/adb.py` |

### 5. Validation false failures for app launch

| | |
|---|---|
| **Symptom** | Test script reported wrong foreground package (e.g. `t8216` instead of package name) |
| **Diagnosis** | Parsed last token of `mResumedActivity` line; the task id (`t8216`) is last, not the package |
| **Fix** | Regex `u0\s+([\w.]+)/` on the `mResumedActivity` line. Added `home()` before each app launch test to avoid stale foreground |
| **File** | `scripts/validate_remote.py` |

### 6. Screenshots saved but appear black

| | |
|---|---|
| **Symptom** | Option 13 writes a PNG file; image is black during streaming |
| **Diagnosis** | HDCP-protected content blocks pixel capture in `screencap` — file is valid, pixels are blank |
| **Status** | Expected behaviour on protected content; not a code bug. Screenshots outside DRM apps may show content |

---

## What else ADB can automate

### Implemented in this repo

| Capability | How |
|------------|-----|
| D-pad and media keys | `adb shell input keyevent <code>` |
| Launch leanback apps | `monkey -p PACKAGE -c android.intent.category.LEANBACK_LAUNCHER 1` |
| Deep-link into content | `am start -a android.intent.action.VIEW -d "URL" PACKAGE` |
| Query playback state | `dumpsys media_session` |
| Query foreground app | `dumpsys window` (`mCurrentFocus`), then `dumpsys activity activities` |
| Screen capture | `screencap` + `adb pull` |
| UI inspection / tap | `uiautomator dump` + `input tap X Y` |
| Background polling | Python `threading` daemon for ad-skip watcher |

### Not implemented — same ADB pattern could support

These are **not** in the codebase today. They use the same `adb shell` / `input` / `am start` building blocks:

| Use case | Typical ADB approach |
|----------|---------------------|
| Scheduled playback | cron or systemd timer calling `python -c "from tv_remote import keys; keys.youtube_search_play('…')"` |
| Home Assistant / Node-RED | HTTP webhook → small Python script → `tv_remote.keys` functions |
| Wake TV before command | Wake-on-LAN magic packet to TV MAC, then `adb connect` (WoL not in this repo) |
| Text input / login flows | `adb shell input text '…'` or `input keyevent` per character |
| Install or sideload APKs | `adb install app.apk` |
| Logcat-triggered automation | `adb logcat` pipe → parse lines → call key functions on match |
| Multi-TV control | Multiple entries in config; pass host to `adb -s IP:PORT shell …` (would need code change) |
| Custom app shortcuts | Add package to `APPS` in `keys.py`; resolve activity with `cmd package resolve-activity --brief PACKAGE` |

To add a new streaming app: confirm the package name on your TV, add it to `APPS`, and if `monkey` fails, add an entry to `APP_ACTIVITIES` using the resolved activity name.

---

## Wireless debugging (pairing)

If your TV shows a **pairing code** instead of a plain port-5555 connect:

```bash
adb pair YOUR_TV_IP:PAIR_PORT
# enter the 6-digit code shown on TV when prompted

adb connect YOUR_TV_IP:DEBUG_PORT
```

Update `port` in `config/tv.json` to the **debug port** (not the pairing port).

---

## Security

- `config/tv.json` is **gitignored** — never commit your TV IP, pairing codes, or WiFi details.
- ADB access requires physical approval on the TV ("Always allow this computer").
- All traffic stays on your local network; no telemetry or external API except YouTube search HTTP from the computer during options 14–16 and during Showtime.
- `tools/platform-tools/` is gitignored; download platform-tools from the official Android developer site.

---

## Troubleshooting

| Problem | Steps |
|---------|-------|
| `Missing config/tv.json` | `cp config/tv.json.example config/tv.json` and set `host` |
| `Cannot connect` / timeout | Wake TV; same WiFi; confirm IP in TV Settings; enable Network debugging |
| `unauthorized` in `adb devices` | Accept the RSA prompt on the TV |
| `adb` not found | Install platform-tools to `tools/platform-tools/adb` |
| App launch fails | Run `adb shell pm list packages \| grep APPNAME`; update `APPS` in `keys.py` |
| JioCinema stuck | Confirm activity: `adb shell cmd package resolve-activity --brief com.jio.media.stb.ondemand` |
| YouTube plays wrong video | Should not occur with watch-URL flow; run `python scripts/validate_remote.py` |
| Ad not skipped | YouTube focuses Skip and OK presses it. A screen dump on this TV usually has no Skip label. An unskippable ad cannot be dismissed |
| Screenshot is black | HDCP on streaming apps — expected |
| Unicode decode error | Fixed in `adb.py`; pull latest code |

---

## Project layout

```
house-automation/
├── config/
│   ├── tv.json.example      # template (copy → tv.json)
│   └── tv.json              # your IP — gitignored
├── tv_remote/
│   ├── adb.py               # ADB wrapper (connect, shell, keyevent, tap)
│   ├── keys.py              # remote actions, YouTube logic, ad skip
│   ├── showtime.py          # one checked pass across the TV
│   └── cli.py               # numbered menu (options 1–19)
├── scripts/
│   ├── check_connection.ps1 # network + ADB smoke test
│   └── validate_remote.py   # automated test for all 18 options
└── tools/
    └── platform-tools/      # adb binary — gitignored, install locally
```

---

## License

See [LICENSE](LICENSE) in the repository root.
