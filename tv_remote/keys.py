"""TV remote key functions — Android KEYCODE_* values."""

from tv_remote import adb

HOME, BACK = 3, 4
VOL_UP, VOL_DOWN = 24, 25
UP, DOWN, LEFT, RIGHT = 19, 20, 21, 22
OK, POWER = 23, 26


def _press(code: int) -> None:
    adb.ensure_connected()
    adb.keyevent(code)


def home() -> None:
    _press(HOME)


def back() -> None:
    _press(BACK)


def volume_up() -> None:
    _press(VOL_UP)


def volume_down() -> None:
    _press(VOL_DOWN)


def dpad_up() -> None:
    _press(UP)


def dpad_down() -> None:
    _press(DOWN)


def dpad_left() -> None:
    _press(LEFT)


def dpad_right() -> None:
    _press(RIGHT)


def ok() -> None:
    _press(OK)


def power() -> None:
    _press(POWER)
