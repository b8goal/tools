import sys
import threading
import time
from typing import Callable

try:
    from .models import MIN_TAP_INTERVAL_MS, ActionStep, MacroSequence
except ImportError:  # pragma: no cover - direct script fallback
    from models import MIN_TAP_INTERVAL_MS, ActionStep, MacroSequence


TAP_HOLD_SECONDS = 0.08
SEQUENTIAL_TAP_GAP_SECONDS = 0.06
CHORD_KEY_PRESS_GAP_SECONDS = 0.012


KEY_ALIASES = {
    "return": "enter",
    "escape": "esc",
    "del": "delete",
    "pageup": "page_up",
    "pagedown": "page_down",
    "control": "ctrl",
    "option": "alt",
    "command": "cmd",
    "meta": "cmd",
    "capslock": "caps_lock",
    "ins": "insert",
}


MAC_KEY_CODES = {
    "a": 0,
    "s": 1,
    "d": 2,
    "f": 3,
    "h": 4,
    "g": 5,
    "z": 6,
    "x": 7,
    "c": 8,
    "v": 9,
    "b": 11,
    "q": 12,
    "w": 13,
    "e": 14,
    "r": 15,
    "y": 16,
    "t": 17,
    "1": 18,
    "2": 19,
    "3": 20,
    "4": 21,
    "6": 22,
    "5": 23,
    "=": 24,
    "9": 25,
    "7": 26,
    "-": 27,
    "8": 28,
    "0": 29,
    "]": 30,
    "o": 31,
    "u": 32,
    "[": 33,
    "i": 34,
    "p": 35,
    "enter": 36,
    "l": 37,
    "j": 38,
    "'": 39,
    "k": 40,
    ";": 41,
    "\\": 42,
    ",": 43,
    "/": 44,
    "n": 45,
    "m": 46,
    ".": 47,
    "tab": 48,
    "space": 49,
    "`": 50,
    "backspace": 51,
    "esc": 53,
    "cmd": 55,
    "cmd_l": 55,
    "shift": 56,
    "shift_l": 56,
    "caps_lock": 57,
    "alt": 58,
    "alt_l": 58,
    "ctrl": 59,
    "ctrl_l": 59,
    "shift_r": 60,
    "alt_r": 61,
    "ctrl_r": 62,
    "fn": 63,
    "f17": 64,
    "f18": 79,
    "f19": 80,
    "f20": 90,
    "f5": 96,
    "f6": 97,
    "f7": 98,
    "f3": 99,
    "f8": 100,
    "f9": 101,
    "f11": 103,
    "f13": 105,
    "f16": 106,
    "f14": 107,
    "f10": 109,
    "f12": 111,
    "f15": 113,
    "home": 115,
    "page_up": 116,
    "delete": 117,
    "f4": 118,
    "end": 119,
    "f2": 120,
    "page_down": 121,
    "f1": 122,
    "left": 123,
    "right": 124,
    "down": 125,
    "up": 126,
}


class QuartzKeyboardController:
    def __init__(self) -> None:
        import Quartz

        self._quartz = Quartz
        self._source = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStateHIDSystemState)

    def press(self, key_name: str) -> None:
        self._post(key_name, True)

    def release(self, key_name: str) -> None:
        self._post(key_name, False)

    def _post(self, key_name: str, is_down: bool) -> None:
        key_code = MAC_KEY_CODES[key_name]
        event = self._quartz.CGEventCreateKeyboardEvent(self._source, key_code, is_down)
        self._quartz.CGEventPost(self._quartz.kCGHIDEventTap, event)


class PynputKeyboardController:
    def __init__(self) -> None:
        from pynput import keyboard

        self._keyboard = keyboard
        self._controller = keyboard.Controller()

    def parse_key(self, key_name: str):
        if len(key_name) == 1:
            return key_name

        key = getattr(self._keyboard.Key, key_name, None)
        if key is not None:
            return key

        raise ValueError(f"Unsupported key: {key_name}")

    def press(self, key) -> None:
        self._controller.press(key)

    def release(self, key) -> None:
        self._controller.release(key)


def macos_accessibility_trusted(prompt: bool = False) -> bool | None:
    if sys.platform != "darwin":
        return True

    try:
        import ApplicationServices

        if prompt:
            options = {ApplicationServices.kAXTrustedCheckOptionPrompt: True}
            return bool(ApplicationServices.AXIsProcessTrustedWithOptions(options))
        return bool(ApplicationServices.AXIsProcessTrusted())
    except Exception:
        return None


class MacroEngine:
    """Runs a macro sequence and guarantees pressed keys are released on stop."""

    def __init__(self, on_log: Callable[[str], None], dry_run: bool = False) -> None:
        self._on_log = on_log
        self._running = False
        self._dry_run = dry_run
        self._is_macos = sys.platform == "darwin"
        self._warned_permission = False
        self._controller = self._build_controller()
        self._pressed_keys = []
        self._key_lock = threading.RLock()

    def start(self, sequence: MacroSequence) -> None:
        self._running = True
        self._on_log(f"[START] sequence={sequence.name}")
        self._log_permission_status()

        try:
            if not sequence.steps:
                self._on_log("[WARN] No steps to run.")
                return

            loops = 0
            while self._running:
                loops += 1
                self._on_log(f"[LOOP] {loops}")
                for index, step in enumerate(sequence.steps, start=1):
                    if not self._running:
                        break
                    self._run_step(index, step)

                if not sequence.loop:
                    break
                if sequence.loop_count is not None and loops >= sequence.loop_count:
                    break
        finally:
            self._running = False
            self._release_all()
            self._on_log("[STOPPED]")

    def stop(self) -> None:
        self._running = False
        self._release_all()

    def _build_controller(self):
        if self._dry_run:
            return None
        if self._is_macos:
            return QuartzKeyboardController()
        return PynputKeyboardController()

    def _log_permission_status(self) -> None:
        if not self._is_macos or self._dry_run or self._warned_permission:
            return

        trusted = macos_accessibility_trusted(prompt=False)
        if trusted is False:
            self._on_log("[WARN] macOS Accessibility permission is not granted. Key events may be ignored.")
        elif trusted is None:
            self._on_log("[WARN] Could not check macOS Accessibility permission.")
        self._warned_permission = True

    def _run_step(self, index: int, step: ActionStep) -> None:
        direction = step.direction_key.lower() if step.direction_key else None
        tap_keys = [key.strip().lower() for key in step.tap_keys if key.strip()]
        tap_groups = [self._parse_tap_group(key) for key in tap_keys]
        hold_seconds = max(float(step.hold_seconds), 0.01)
        requested_interval_ms = int(step.tap_interval_ms)
        interval_ms = max(requested_interval_ms, MIN_TAP_INTERVAL_MS)
        interval_seconds = interval_ms / 1000.0

        self._on_log(
            f"[STEP {index}] direction={direction or '-'}, taps={tap_keys or '-'}, "
            f"hold={hold_seconds:.2f}s, interval={interval_ms}ms"
        )
        if requested_interval_ms < MIN_TAP_INTERVAL_MS:
            self._on_log(
                f"[WARN] interval {requested_interval_ms}ms is too short for reliable input; "
                f"using {MIN_TAP_INTERVAL_MS}ms."
            )

        direction_key = self._parse_key(direction) if direction else None

        try:
            if direction_key is not None:
                self._press(direction_key)

            end_at = time.monotonic() + hold_seconds
            next_tap_at = time.monotonic()

            while self._running and time.monotonic() < end_at:
                now = time.monotonic()
                if tap_groups and now >= next_tap_at:
                    self._tap_groups(tap_groups)
                    next_tap_at = time.monotonic() + interval_seconds

                remaining = max(end_at - time.monotonic(), 0.0)
                time.sleep(min(0.02, remaining))
        finally:
            if direction_key is not None:
                self._release(direction_key)

    def _parse_key(self, key_name: str):
        if not key_name:
            raise ValueError("Empty key name")

        normalized = KEY_ALIASES.get(key_name.strip().lower(), key_name.strip().lower())

        if self._is_macos or self._dry_run:
            if normalized in MAC_KEY_CODES:
                return normalized
            raise ValueError(f"Unsupported key: {key_name}")

        return self._controller.parse_key(normalized)

    def _parse_tap_group(self, tap_expression: str) -> list:
        keys = []
        for key_name in tap_expression.split("+"):
            key_name = key_name.strip()
            if key_name:
                keys.append(self._parse_key(key_name))
        if not keys:
            raise ValueError(f"Empty tap expression: {tap_expression}")
        return keys

    def _press(self, key) -> None:
        with self._key_lock:
            if self._dry_run:
                self._on_log(f"[DRY] press {key}")
                return
            self._controller.press(key)
            self._pressed_keys.append(key)

    def _release(self, key) -> None:
        with self._key_lock:
            if self._dry_run:
                self._on_log(f"[DRY] release {key}")
                return
            try:
                self._controller.release(key)
            finally:
                if key in self._pressed_keys:
                    self._pressed_keys.remove(key)

    def _tap_groups(self, groups: list[list]) -> None:
        for group in groups:
            if not self._running:
                return
            self._tap(group)
            time.sleep(SEQUENTIAL_TAP_GAP_SECONDS)

    def _tap(self, keys: list) -> None:
        pressed = []
        try:
            for key in keys:
                self._press(key)
                pressed.append(key)
                if len(keys) > 1:
                    time.sleep(CHORD_KEY_PRESS_GAP_SECONDS)
            time.sleep(TAP_HOLD_SECONDS)
        finally:
            for key in reversed(pressed):
                self._release(key)

    def _release_all(self) -> None:
        with self._key_lock:
            for key in reversed(self._pressed_keys[:]):
                try:
                    if self._dry_run:
                        self._on_log(f"[DRY] release {key}")
                    else:
                        self._controller.release(key)
                except Exception as exc:  # noqa: BLE001
                    self._on_log(f"[WARN] Failed to release {key}: {exc}")
                finally:
                    if key in self._pressed_keys:
                        self._pressed_keys.remove(key)
