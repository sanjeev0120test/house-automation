"""Interactive CLI to control Mi TV over ADB."""

from tv_remote import adb, keys

ACTIONS = {
    "1": ("Home", keys.home),
    "2": ("Back", keys.back),
    "3": ("Volume Up", keys.volume_up),
    "4": ("Volume Down", keys.volume_down),
    "5": ("D-Pad Up", keys.dpad_up),
    "6": ("D-Pad Down", keys.dpad_down),
    "7": ("D-Pad Left", keys.dpad_left),
    "8": ("D-Pad Right", keys.dpad_right),
    "9": ("OK / Select", keys.ok),
    "0": ("Power", keys.power),
    "c": ("Connect", lambda: print(adb.connect())),
    "d": ("Devices", lambda: print(adb.devices())),
}

MENU = """
=== Mi TV Remote (ADB over WiFi) ===
 1 Home       2 Back       3 Vol+       4 Vol-
 5 Up         6 Down       7 Left       8 Right
 9 OK         0 Power      c Connect    d Devices
 q Quit
"""


def main() -> None:
    print(MENU)
    print("Tip: enable USB + Network debugging on TV first.")
    try:
        print(adb.connect())
    except Exception as exc:
        print(f"Connect skipped: {exc}")

    while True:
        choice = input("> ").strip().lower()
        if choice in ("q", "quit", "exit"):
            break
        action = ACTIONS.get(choice)
        if not action:
            print("Unknown key. Use 1-9, 0, c, d, or q.")
            continue
        label, fn = action
        try:
            fn()
            print(f"Sent: {label}")
        except Exception as exc:
            print(f"Failed ({label}): {exc}")


if __name__ == "__main__":
    main()
