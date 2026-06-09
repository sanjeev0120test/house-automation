"""Simple numbered menu — type 1-18 to control Mi TV."""

from tv_remote import adb, keys

MENU = """
=== Mi TV Remote ===
 1  Home              2  Back
 3  Volume Up         4  Volume Down
 5  OK / Select
 6  YouTube           7  Netflix
 8  Prime Video       9  Hotstar
10  SonyLIV          11  JioCinema
12  Play / Pause     13  Screenshot
14  Eminem on YouTube   15  Enrique on YouTube
16  YouTube search (type anything)
17  Skip forward 30s    18  Now playing
 q  Quit
"""


def _youtube_preset(query: str) -> None:
    keys.youtube_search_play(query)
    print(f"Playing first result for: {query}")


def _youtube_custom_search() -> None:
    query = input("Search YouTube for: ").strip()
    if not query:
        raise ValueError("Search text cannot be empty")
    _youtube_preset(query)


def _now_playing() -> None:
    print(f"Now playing: {keys.now_playing()}")


ACTIONS = {
    "1": ("Home", keys.home),
    "2": ("Back", keys.back),
    "3": ("Volume Up", keys.volume_up),
    "4": ("Volume Down", keys.volume_down),
    "5": ("OK / Select", keys.ok),
    "6": ("YouTube", lambda: keys.launch_app("youtube")),
    "7": ("Netflix", lambda: keys.launch_app("netflix")),
    "8": ("Prime Video", lambda: keys.launch_app("prime")),
    "9": ("Hotstar", lambda: keys.launch_app("hotstar")),
    "10": ("SonyLIV", lambda: keys.launch_app("sonyliv")),
    "11": ("JioCinema", lambda: keys.launch_app("jio")),
    "12": ("Play / Pause", keys.play_pause),
    "13": ("Screenshot", lambda: print(f"Saved: {keys.screenshot()}")),
    "14": ("Eminem on YouTube", lambda: _youtube_preset("eminem not afraid official")),
    "15": ("Enrique on YouTube", lambda: _youtube_preset("enrique iglesias hero official")),
    "16": ("YouTube search", _youtube_custom_search),
    "17": ("Skip forward", keys.skip_forward),
    "18": ("Now playing", _now_playing),
}

QUIET_OK = {"13", "14", "15", "16", "18"}


def _connect() -> None:
    print(adb.connect())
    if adb.is_connected():
        print("Connected.")
    else:
        print("Not connected — verify config/tv.json and TV debugging settings.")
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
            print("Enter 1-18 or q.")
            continue
        label, fn = action
        try:
            fn()
            if choice not in QUIET_OK:
                print(f"OK: {label}")
        except Exception as exc:
            print(f"Failed: {exc}")
            print("Retrying connect...")
            _connect()


if __name__ == "__main__":
    main()
