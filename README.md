# TV - ADB WiFi 

Control your Mi Android TV from this laptop over the same WiFi network.

## Mi TV setup (do this on the TV remote)

### Step 1 — Enable Developer Options (done if you clicked Build 7×)

1. **Settings → Device Preferences → About**
2. Click **Build** 7 times → “You are now a developer”

### Step 2 — Turn on debugging (required)

1. **Settings → Device Preferences → Developer options**
2. Turn **ON** these toggles:
   - **USB debugging**
   - **Network debugging** OR **ADB over network** OR **Wireless debugging**
     - *Network debugging* → uses port **5555** (simplest; use this if you see it)
     - *Wireless debugging* → shows IP + **pairing port** + 6-digit code (see below)

3. When the TV shows **Allow USB debugging?** → check **Always allow** → **OK**

### Step 3 — Confirm live IP (on the TV, not only Mi Home app)

1. **Settings → Network & Internet → WiFi → [your network]**
2. Note the **IP address** (e.g. `192.168.1.128`)
3. Copy [`config/tv.json.example`](config/tv.json.example) to `config/tv.json` and set your IP:

```json
{"host": "192.168.1.128", "port": 5555}
```

> Mi Home app may show a *configured* static IP. Always verify the **live IP on the TV** while the TV is **awake**.

### Step 4 — If you only have “Wireless debugging”

On the TV screen you will see something like:

- IP: `192.168.1.128`
- Pairing port: `37123`
- Pairing code: `123456`
- Debug port: `45678` (after pairing)

On the laptop:

```powershell
.\tools\platform-tools\adb.exe pair 192.168.1.128:37123
# enter the 6-digit code when prompted
.\tools\platform-tools\adb.exe connect 192.168.1.128:45678
```

Update `port` in `config/tv.json` to the **debug port**.

### Step 5 — Connect from laptop

```powershell
cd c:\dev\house-automation
.\scripts\check_connection.ps1
```

Or manually:

```powershell
.\tools\platform-tools\adb.exe connect 192.168.1.128:5555
.\tools\platform-tools\adb.exe devices
```

Success:

```
192.168.1.128:5555    device
```

Quick test:

```powershell
.\tools\platform-tools\adb.exe shell input keyevent 3
```

(Presses Home on the TV.)

## Python remote CLI

```powershell
python -m tv_remote.cli
```

| Key | Action |
|-----|--------|
| 1–9, 0 | Home, Back, Vol, D-Pad, OK, Power |
| c | Reconnect |
| d | List devices |
| q | Quit |

## Windows laptop — nothing special to enable

- Your laptop only needs **WiFi on the same router** as the TV (you are `192.168.1.x`).
- **Outbound** ADB from laptop → TV is fine on Public WiFi; you do **not** need to open Windows firewall ports for this.
- ADB port **5037** runs locally on the laptop; the TV listens on **5555** (or wireless debug port).

Run `.\scripts\check_connection.ps1` to verify ping, ports, and ADB.

## Troubleshooting

| Symptom | What to do |
|---------|------------|
| Ping fails / destination unreachable | Wake TV; confirm IP on TV Settings → Network; check TV is on same WiFi SSID |
| `cannot connect` timeout | Enable **Network debugging** on TV; TV must be awake |
| `unauthorized` | Accept debug prompt on TV |
| Mi app IP ≠ TV Settings IP | Trust **TV Settings** IP; update `config/tv.json` |
| Only Wireless debugging | Use `adb pair` then connect to debug port |
| Still stuck | One-time USB: plug TV to laptop, run `adb tcpip 5555`, then WiFi connect |

## Security / git

- `config/tv.json` (your TV IP) is **gitignored** — never commit local network details.
- Use `config/tv.json.example` as a template only.

## Later ideas

- Launch apps, type text, screenshots — see `tv_remote/keys.py`
