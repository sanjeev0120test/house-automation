# House Automation — TV Remote

Control an Android TV from your computer over WiFi using Python and ADB. Tested on Android TV with Network debugging enabled.

```bash
cp config/tv.json.example config/tv.json   # once: set YOUR_TV_IP
./scripts/check_connection.ps1             # verify network + ADB
python -m tv_remote.cli                    # run the numbered remote
python scripts/validate_remote.py          # optional: test all 18 options
```

**Requirements:** Python 3.10+, [Android platform-tools](https://developer.android.com/tools/releases/platform-tools) at `tools/platform-tools/adb`, TV and computer on the same WiFi, `config/tv.json` with your TV IP (gitignored).

---

## Table of contents

- [Overview](#overview)
- [One-time setup](#one-time-setup)
- [Remote menu](#remote-menu)
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

Expected: ping succeeds, TCP port open, `adb devices` shows `YOUR_TV_IP:5555    device`.

4. Start the remote:

```bash
python -m tv_remote.cli
```

Type **1–18** to act, **q** to quit.

---

## Remote menu

| Key | Action | ADB mechanism |
|-----|--------|---------------|
| 1 | Home | `input keyevent 3` |
| 2 | Back | `input keyevent 4` |
| 3 | Volume up | `input keyevent 24` |
| 4 | Volume down | `input keyevent 25` |
| 5 | OK / Select | `input keyevent 23` |
| 6 | Open YouTube | `monkey -p com.google.android.youtube.tv …` |
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
| 17 | Skip forward ~30 s | `input keyevent 272` (`KEYCODE_MEDIA_SKIP_FORWARD`) |
| 18 | Now playing | Parse `dumpsys media_session` for active playback |
| q | Quit | Exit CLI |

Options **14–16** print `Playing first result for: …` instead of `OK: …`.

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
  HTTP GET youtube.com/results  →  extract first videoId  →  open watch URL on TV
```

| Module | Responsibility |
|--------|----------------|
| `tv_remote/adb.py` | Load `config/tv.json`, run `adb`, connect, keyevent, shell, tap, pull |
| `tv_remote/keys.py` | Remote actions, app launch, YouTube resolve/play, ad-skip thread, now playing |
| `tv_remote/cli.py` | Numbered menu loop and error handling |
| `scripts/check_connection.ps1` | Ping, TCP port, `adb connect`, `adb devices` |
| `scripts/validate_remote.py` | Automated pass/fail test for all menu options |

---

## YouTube search and ad skip

### Search (options 14, 15, 16)

**Previous behaviour (broken):** open `youtube.com/results?search_query=…` on the TV, wait, send **DOWN**, then **OK**. On the test device focus was already on the first result; **DOWN** moved to the **second row**.

**Current behaviour (fixed):**

1. Computer fetches `https://www.youtube.com/results?search_query=…`
2. Parses `ytInitialData` JSON for the first `videoRenderer.videoId`
3. Opens `https://www.youtube.com/watch?v=VIDEO_ID` on the TV via `am start -a android.intent.action.VIEW`

This plays the same top result YouTube shows in a browser search, without DPAD navigation.

### Ad skip (background thread)

After playback starts, a daemon thread runs for **90 seconds** and every **2 seconds**:

1. Runs `uiautomator dump` and looks for an enabled node matching `skip ad` (case-insensitive)
2. If found, taps the button centre via `input tap X Y`
3. If not found, sends **RIGHT** once and re-checks
4. Falls back to title heuristics in the first 30 s (sponsored keywords or title mismatch vs expected)

**Limitation (observed on test device):** YouTube TV renders most UI in custom views. `uiautomator dump` often returns minimal nodes during playback, so ad skip works when the Skip Ad button is exposed in the accessibility tree. It does not skip unskippable ads.

---

## Validation

Run the full suite (takes ~3 minutes; switches apps and plays YouTube):

```bash
python scripts/validate_remote.py
```

Last verified run: **17 pass, 0 warn, 0 fail** — all menu options including six app launches, volume, YouTube search, presets, skip forward, and now playing.

The script checks foreground app via `dumpsys activity activities` (`mResumedActivity`), volume via `dumpsys audio`, and playback via `now_playing()`.

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
| Query foreground app | `dumpsys activity activities` |
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
- All traffic stays on your local network; no telemetry or external API except YouTube search HTTP from the computer during options 14–16.
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
| Ad not skipped | Skip button may not appear in UI dump on YouTube TV; unskippable ads cannot be bypassed |
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
│   └── cli.py               # numbered menu (options 1–18)
├── scripts/
│   ├── check_connection.ps1 # network + ADB smoke test
│   └── validate_remote.py   # automated test for all 18 options
└── tools/
    └── platform-tools/      # adb binary — gitignored, install locally
```

---

## License

See [LICENSE](LICENSE) in the repository root.
