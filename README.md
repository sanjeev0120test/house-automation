# House Automation — Mi TV Remote

Your laptop becomes a smart remote for a Mi Android TV over WiFi. No IR blaster, no extra hardware — just Python, ADB, and the same network your TV already uses.

Type a number. The TV responds.

## What makes this different

Most “TV remotes” stop at volume and home. This one goes further:

- **Instant app launch** — YouTube, Netflix, Prime, Hotstar, SonyLIV, JioCinema open with one keypress.
- **Smart YouTube search** — Type any song or topic; the tool resolves the **top YouTube search result** on your PC and opens it directly on the TV (no fragile arrow-key navigation through result rows).
- **Ad skip watcher** — After a video starts, a background thread watches for an enabled **Skip ad** button and taps it automatically when it appears.
- **Now playing** — Reads the active media session from the TV so you always know what’s on.

Everything runs locally. Your TV IP never leaves your machine.

## Quick start

```powershell
cd c:\dev\house-automation
copy config\tv.json.example config\tv.json   # then edit with your TV IP
python -m tv_remote.cli
```

Type **1–18** to control the TV. Type **q** to quit.

## One-time TV setup

| Step | On Mi TV |
|------|----------|
| Developer options | Settings → Device Preferences → About → click **Build** 7× |
| USB debugging | Developer options → **ON** |
| Network debugging | Developer options → **ON** (opens ADB port 5555) |
| Allow prompt | When asked, tap **Always allow** |

Find your TV IP under **Settings → Network → WiFi → [your network] → IP address**, then put it in `config/tv.json`:

```json
{"host": "YOUR_TV_IP", "port": 5555}
```

Use `config/tv.json.example` as a template — the real file is gitignored.

## Remote menu

| Key | What it does |
|-----|----------------|
| 1 | Home |
| 2 | Back |
| 3 | Volume up |
| 4 | Volume down |
| 5 | OK / Select |
| 6 | Open YouTube |
| 7 | Open Netflix |
| 8 | Open Prime Video |
| 9 | Open Hotstar |
| 10 | Open SonyLIV |
| 11 | Open JioCinema |
| 12 | Play / Pause |
| 13 | Screenshot (saved locally) |
| 14 | Play Eminem on YouTube (first search result) |
| 15 | Play Enrique on YouTube (first search result) |
| 16 | YouTube search — type anything, plays #1 result |
| 17 | Skip forward ~30 s |
| 18 | Show now playing title |
| q | Quit |

The CLI connects automatically on startup.

## How YouTube search works

```
You type "cocomelon"
        ↓
Laptop fetches youtube.com search results (first video ID)
        ↓
ADB opens youtube.com/watch?v=… directly on the TV
        ↓
Background thread polls for "Skip ad" and taps when ready
```

No more landing on the second row of search results — the top hit plays every time.

## Validate everything

Run the full test suite against your connected TV:

```powershell
python scripts\validate_remote.py
```

Checks all 18 options: app launches, volume, YouTube search, presets, skip forward, and now playing.

Or just ping the connection:

```powershell
.\scripts\check_connection.ps1
```

## Wireless debugging (no “Network debugging” toggle)

Use the IP, pairing port, and code shown on the TV:

```powershell
.\tools\platform-tools\adb.exe pair YOUR_TV_IP:PAIR_PORT
.\tools\platform-tools\adb.exe connect YOUR_TV_IP:DEBUG_PORT
```

Update `port` in `config/tv.json` to the debug port.

## Project layout

```
house-automation/
├── config/tv.json.example   # template (copy → tv.json)
├── tv_remote/
│   ├── adb.py               # ADB connection + shell/keyevents
│   ├── keys.py              # remote actions + YouTube logic
│   └── cli.py               # numbered menu
└── scripts/
    ├── check_connection.ps1
    └── validate_remote.py
```

## Security

- **`config/tv.json` is gitignored** — your TV IP stays on this machine only.
- Do not commit WiFi names, IPs, pairing codes, or router details.
- ADB access is limited to devices you explicitly authorize on the TV.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Cannot connect | Wake TV; confirm IP in TV Settings; enable Network debugging |
| Unauthorized | Accept the debug prompt on the TV |
| Timeout | Same WiFi as laptop; TV not in deep sleep |
| Screenshot is black | HDCP-protected content — normal on streaming apps |
| JioCinema won’t open | Re-run validation; app uses an explicit launch activity |
