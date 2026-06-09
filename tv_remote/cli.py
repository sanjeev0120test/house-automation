"""Simple numbered menu — type 1-5 to control Mi TV."""

from tv_remote import adb, keys

MENU = """
=== Mi TV Remote ===
 1  Home
 2  Back
 3  Volume Up
 4  Volume Down
 5  OK / Select
 q  Quit
"""

ACTIONS = {
    "1": ("Home", keys.home),
    "2": ("Back", keys.back),
    "3": ("Volume Up", keys.volume_up),
    "4": ("Volume Down", keys.volume_down),
    "5": ("OK / Select", keys.ok),
}


def _connect() -> None:
    print(adb.connect())
    if adb.is_connected():
        print("Connected.")
    else:
        print("Not connected — verify IP in config/tv.json and Network debugging on TV.")
        print(adb.devices())


def main() -> None:
    print(MENU)
    _connect()

    while True:
        choice = input("> ").strip().lower()
        if choice in ("q", "quit", "exit"):
            print("Bye.")
            break
        action = ACTIONS.get(choice)
        if not action:
            print("Enter 1, 2, 3, 4, 5, or q.")
            continue
        label, fn = action
        try:
            fn()
            print(f"OK: {label}")
        except Exception as exc:
            print(f"Failed: {exc}")
            print("Retrying connect...")
            _connect()


if __name__ == "__main__":
    main()
