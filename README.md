# TV - ADB WiFi 

Control your Mi Android TV from this laptop over the same WiFi network.

## Quick start

1. Copy `config/tv.json.example` → `config/tv.json` and set **your TV IP** (from TV Settings → Network).
2. On the TV: enable **Developer options**, **USB debugging**, and **Network debugging**.
3. Run:

```powershell
cd c:\dev\house-automation
python -m tv_remote.cli
```

Type **1–5** to control the TV. Type **q** to quit.

## TV setup (one time)

| Step | On Mi TV |
|------|----------|
| Developer options | Settings → Device Preferences → About → click **Build** 7× |
| USB debugging | Developer options → **ON** |
| Network debugging | Developer options → **ON** (opens ADB port 5555) |
| Allow prompt | When asked, tap **Always allow** |

Find your TV IP: **Settings → Network → WiFi → [your network] → IP address**

Put that IP in `config/tv.json` (local file, not in git):

```json
{"host": "YOUR_TV_IP", "port": 5555}
```

## CLI menu

| Key | Action |
|-----|--------|
| 1 | Home |
| 2 | Back |
| 3 | Volume Up |
| 4 | Volume Down |
| 5 | OK / Select |
| q | Quit |

Connects automatically when you start the CLI.

## Check connection

```powershell
.\scripts\check_connection.ps1
```

## Wireless debugging (if no “Network debugging” toggle)

Use the IP, pairing port, and code shown on the TV:

```powershell
.\tools\platform-tools\adb.exe pair YOUR_TV_IP:PAIR_PORT
.\tools\platform-tools\adb.exe connect YOUR_TV_IP:DEBUG_PORT
```

Update `port` in `config/tv.json` to the debug port.

## Security

- **`config/tv.json` is gitignored** — your TV IP stays on this machine only.
- Do not commit WiFi names, IPs, pairing codes, or router details.
- Use `config/tv.json.example` as a template with placeholders only.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Cannot connect | Wake TV; confirm IP in TV Settings; enable Network debugging |
| Unauthorized | Accept the debug prompt on the TV |
| Timeout | Same WiFi as laptop; TV not in deep sleep |
