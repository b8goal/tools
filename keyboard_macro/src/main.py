import json
import sys
import threading
import time
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, Qt, QThread, Signal, Slot
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

try:
    from .macro_engine import MAC_KEY_CODES, MacroEngine, macos_accessibility_trusted
    from .models import MIN_TAP_INTERVAL_MS, ActionStep, MacroSequence, new_step_id
except ImportError:  # pragma: no cover - direct script fallback
    from macro_engine import MAC_KEY_CODES, MacroEngine, macos_accessibility_trusted
    from models import MIN_TAP_INTERVAL_MS, ActionStep, MacroSequence, new_step_id


DIRECTION_LABELS = ["None", "LEFT", "RIGHT", "UP", "DOWN"]
CONFIG_VERSION = 1
DEFAULT_START_DELAY_SECONDS = 3.0
DEFAULT_TARGET_APP = "MapleStory Worlds"

QT_KEY_NAMES = {
    int(Qt.Key.Key_Left): "left",
    int(Qt.Key.Key_Right): "right",
    int(Qt.Key.Key_Up): "up",
    int(Qt.Key.Key_Down): "down",
    int(Qt.Key.Key_Return): "enter",
    int(Qt.Key.Key_Enter): "enter",
    int(Qt.Key.Key_Space): "space",
    int(Qt.Key.Key_Tab): "tab",
    int(Qt.Key.Key_Backspace): "backspace",
    int(Qt.Key.Key_Delete): "delete",
    int(Qt.Key.Key_Home): "home",
    int(Qt.Key.Key_End): "end",
    int(Qt.Key.Key_PageUp): "page_up",
    int(Qt.Key.Key_PageDown): "page_down",
    int(Qt.Key.Key_Escape): "esc",
    int(Qt.Key.Key_Shift): "shift",
    int(Qt.Key.Key_Control): "ctrl",
    int(Qt.Key.Key_Alt): "alt",
    int(Qt.Key.Key_Meta): "cmd",
    int(Qt.Key.Key_CapsLock): "caps_lock",
}

for number in range(1, 21):
    QT_KEY_NAMES[int(getattr(Qt.Key, f"Key_F{number}"))] = f"f{number}"

MAC_KEY_NAMES_BY_CODE = {}
for name, code in MAC_KEY_CODES.items():
    MAC_KEY_NAMES_BY_CODE.setdefault(code, name)


def parse_key_list(text: str) -> list[str]:
    groups = []
    for item in text.split(","):
        group = "+".join(part.strip().lower() for part in item.split("+") if part.strip())
        if group:
            groups.append(group)
    return groups


def format_key_list(keys: list[str]) -> str:
    return ", ".join(keys)


class MacroWorker(QObject):
    log = Signal(str)
    finished = Signal()

    def __init__(self, sequence: MacroSequence, start_delay_seconds: float) -> None:
        super().__init__()
        self._sequence = sequence
        self._start_delay_seconds = start_delay_seconds
        self._engine: MacroEngine | None = None
        self._stop_requested = False

    @Slot()
    def run(self) -> None:
        try:
            if self._start_delay_seconds > 0:
                self.log.emit(f"[WAIT] Starting in {self._start_delay_seconds:.1f}s")
                end_at = time.monotonic() + self._start_delay_seconds
                while not self._stop_requested and time.monotonic() < end_at:
                    time.sleep(0.05)

            if self._stop_requested:
                self.log.emit("[STOPPED] Start cancelled.")
                return

            self._engine = MacroEngine(self.log.emit)
            self._engine.start(self._sequence)
        except Exception as exc:  # noqa: BLE001
            self.log.emit(f"[ERROR] {exc}")
        finally:
            self.finished.emit()

    @Slot()
    def stop(self) -> None:
        self._stop_requested = True
        if self._engine is not None:
            self._engine.stop()


class KeyRecorder(QObject):
    step_recorded = Signal(object)
    log = Signal(str)
    stopped = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._pressed_at: dict[str, float] = {}
        self._started_at = 0.0
        self._event_count = 0
        self._active = False
        self._global_recording = False
        self._event_tap = None
        self._run_loop_source = None
        self._run_loop = None
        self._event_thread: threading.Thread | None = None
        self._pynput_listener = None

    def start(self) -> None:
        if self._active:
            return
        self._active = True
        self._pressed_at.clear()
        self._started_at = time.monotonic()
        self._event_count = 0
        self._global_recording = False

        if sys.platform == "darwin":
            try:
                self._start_macos_global_recording()
                self._global_recording = True
                self.log.emit("[RECORD] Recording global keyboard input. Press Esc or Stop Recording to finish.")
                return
            except Exception as exc:  # noqa: BLE001
                self.log.emit(f"[RECORD] Global recording unavailable: {exc}")
        elif sys.platform == "win32":
            try:
                self._start_pynput_global_recording()
                self._global_recording = True
                self.log.emit("[RECORD] Recording global keyboard input. Press Esc or Stop Recording to finish.")
                return
            except Exception as exc:  # noqa: BLE001
                self.log.emit(f"[RECORD] Global recording unavailable: {exc}")

        self.log.emit("[RECORD] Recording focused app input. Press Esc or Stop Recording to finish.")

    def stop(self) -> None:
        self._finish()

    def handle_key_press(self, event) -> None:
        if self._global_recording:
            return
        if not self._active:
            return
        if event.isAutoRepeat():
            return
        key_name = self._key_name(event)
        if key_name:
            self._record_key_down(key_name, time.monotonic())

    def handle_key_release(self, event) -> None:
        if self._global_recording:
            return
        if not self._active or event.isAutoRepeat():
            return

        key_name = self._key_name(event)
        if key_name == "esc":
            self._finish()
            return

        if key_name:
            self._record_key_up(key_name, time.monotonic())

    def _finish(self) -> None:
        if not self._active:
            return
        self._active = False
        self._stop_macos_global_recording()
        self._stop_pynput_global_recording()
        self._pressed_at.clear()
        total_ms = int((time.monotonic() - self._started_at) * 1000) if self._started_at else 0
        self.log.emit(f"[RECORD] Recording stopped. events={self._event_count}, duration={total_ms}ms")
        self.stopped.emit()

    def _record_key_down(self, key_name: str, timestamp: float) -> None:
        if key_name not in self._pressed_at:
            self._pressed_at[key_name] = timestamp
            elapsed_ms = int((timestamp - self._started_at) * 1000)
            self.log.emit(f"[RECORD] down key={key_name} at={elapsed_ms}ms")

    def _record_key_up(self, key_name: str, timestamp: float) -> None:
        started_at = self._pressed_at.pop(key_name, timestamp)
        duration = max(timestamp - started_at, 0.05)
        self._event_count += 1
        elapsed_ms = int((timestamp - self._started_at) * 1000)
        self.log.emit(f"[RECORD] up key={key_name} hold={int(duration * 1000)}ms at={elapsed_ms}ms")
        self.step_recorded.emit(self._step_from_key(key_name, duration))

    def _start_macos_global_recording(self) -> None:
        if macos_accessibility_trusted(prompt=False) is not True:
            raise RuntimeError("macOS Accessibility permission is not granted.")

        import Quartz

        mask = (1 << Quartz.kCGEventKeyDown) | (1 << Quartz.kCGEventKeyUp)
        self._event_tap = Quartz.CGEventTapCreate(
            Quartz.kCGSessionEventTap,
            Quartz.kCGHeadInsertEventTap,
            0,
            mask,
            self._macos_event_callback,
            None,
        )
        if self._event_tap is None:
            raise RuntimeError("Could not create keyboard event tap. Check Input Monitoring/Accessibility.")

        self._run_loop_source = Quartz.CFMachPortCreateRunLoopSource(None, self._event_tap, 0)
        self._event_thread = threading.Thread(target=self._run_macos_event_loop, daemon=True)
        self._event_thread.start()

    def _run_macos_event_loop(self) -> None:
        import Quartz

        self._run_loop = Quartz.CFRunLoopGetCurrent()
        Quartz.CFRunLoopAddSource(self._run_loop, self._run_loop_source, Quartz.kCFRunLoopDefaultMode)
        Quartz.CGEventTapEnable(self._event_tap, True)
        Quartz.CFRunLoopRun()

    def _stop_macos_global_recording(self) -> None:
        if not self._global_recording:
            return

        try:
            if self._event_tap is not None:
                import Quartz

                Quartz.CGEventTapEnable(self._event_tap, False)
            if self._run_loop is not None:
                import Quartz

                Quartz.CFRunLoopStop(self._run_loop)
            if self._event_thread is not None and self._event_thread is not threading.current_thread():
                self._event_thread.join(timeout=0.5)
        finally:
            self._event_tap = None
            self._run_loop_source = None
            self._run_loop = None
            self._event_thread = None
            self._global_recording = False

    def _macos_event_callback(self, _proxy, event_type, event, _refcon):
        import Quartz

        if event_type in {
            Quartz.kCGEventTapDisabledByTimeout,
            Quartz.kCGEventTapDisabledByUserInput,
        }:
            if self._event_tap is not None:
                Quartz.CGEventTapEnable(self._event_tap, True)
            return event

        if not self._active:
            return event

        if event_type not in {Quartz.kCGEventKeyDown, Quartz.kCGEventKeyUp}:
            return event

        is_repeat = bool(Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventAutorepeat))
        if is_repeat:
            return event

        key_code = int(Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventKeycode))
        key_name = MAC_KEY_NAMES_BY_CODE.get(key_code)
        if key_name is None:
            return event

        timestamp = time.monotonic()
        if event_type == Quartz.kCGEventKeyDown:
            self._record_key_down(key_name, timestamp)
        else:
            if key_name == "esc":
                self._finish()
            else:
                self._record_key_up(key_name, timestamp)

        return event

    def _start_pynput_global_recording(self) -> None:
        from pynput import keyboard

        self._pynput_listener = keyboard.Listener(
            on_press=self._pynput_key_down,
            on_release=self._pynput_key_up,
        )
        self._pynput_listener.start()

    def _stop_pynput_global_recording(self) -> None:
        if self._pynput_listener is None:
            return

        try:
            self._pynput_listener.stop()
            try:
                self._pynput_listener.join(timeout=0.5)
            except RuntimeError:
                pass
        finally:
            self._pynput_listener = None
            if sys.platform == "win32":
                self._global_recording = False

    def _pynput_key_down(self, key) -> None:
        if not self._active:
            return

        key_name = self._pynput_key_name(key)
        if key_name:
            self._record_key_down(key_name, time.monotonic())

    def _pynput_key_up(self, key) -> bool | None:
        if not self._active:
            return False

        key_name = self._pynput_key_name(key)
        if key_name == "esc":
            self._finish()
            return False

        if key_name:
            self._record_key_up(key_name, time.monotonic())
        return None

    def _pynput_key_name(self, key) -> str | None:
        char = getattr(key, "char", None)
        if char and len(char) == 1 and not char.isspace():
            return char.lower()

        name = getattr(key, "name", None)
        if not name:
            return None

        aliases = {
            "alt_l": "alt",
            "alt_r": "alt",
            "ctrl_l": "ctrl",
            "ctrl_r": "ctrl",
            "shift_l": "shift",
            "shift_r": "shift",
            "cmd_l": "cmd",
            "cmd_r": "cmd",
        }
        return aliases.get(name, name)

    def _key_name(self, event) -> str | None:
        key = event.key()
        if key in QT_KEY_NAMES:
            return QT_KEY_NAMES[key]

        text = event.text()
        if text and len(text) == 1 and not text.isspace():
            return text.lower()

        return None

    def _step_from_key(self, key_name: str, duration: float) -> ActionStep:
        if key_name in {"left", "right", "up", "down"}:
            return ActionStep(
                direction_key=key_name.upper(),
                tap_keys=[],
                hold_seconds=round(duration, 2),
                tap_interval_ms=200,
            )

        return ActionStep(
            direction_key=None,
            tap_keys=[key_name],
            hold_seconds=0.05,
            tap_interval_ms=200,
        )


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Keyboard Macro Planner - v0.1")

        self.sequence = self._default_sequence()
        self._thread: QThread | None = None
        self._worker: MacroWorker | None = None
        self._recorder: KeyRecorder | None = None
        self._refreshing = False
        self._editor_refreshing = False
        self._current_path: Path | None = None

        self._build_actions()
        self._build_ui()
        self._refresh_table(select_row=0)
        self._sync_sequence_controls()
        QApplication.instance().installEventFilter(self)
        self._append_log("[READY] Build or load a sequence, then press Start.")
        self._log_accessibility_status(prompt=False)

    def _build_actions(self) -> None:
        file_menu = self.menuBar().addMenu("File")

        new_action = QAction("New", self)
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.triggered.connect(self.new_sequence)
        file_menu.addAction(new_action)

        open_action = QAction("Open Config JSON", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self.load_sequence)
        file_menu.addAction(open_action)

        save_action = QAction("Save Config JSON", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self.save_sequence)
        file_menu.addAction(save_action)

        save_as_action = QAction("Save Config JSON As", self)
        save_as_action.triggered.connect(self.save_sequence_as)
        file_menu.addAction(save_as_action)

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)

        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("Name"))
        self.name_edit = QLineEdit()
        self.name_edit.setText(self.sequence.name)
        self.name_edit.textChanged.connect(self._sequence_controls_changed)
        top_bar.addWidget(self.name_edit, 1)

        self.loop_check = QCheckBox("Loop")
        self.loop_check.toggled.connect(self._loop_toggled)
        top_bar.addWidget(self.loop_check)

        top_bar.addWidget(QLabel("Count"))
        self.loop_count_spin = QSpinBox()
        self.loop_count_spin.setRange(0, 999)
        self.loop_count_spin.setSpecialValueText("Infinite")
        self.loop_count_spin.valueChanged.connect(self._sequence_controls_changed)
        top_bar.addWidget(self.loop_count_spin)

        top_bar.addWidget(QLabel("Delay"))
        self.start_delay_spin = QDoubleSpinBox()
        self.start_delay_spin.setRange(0.0, 30.0)
        self.start_delay_spin.setDecimals(1)
        self.start_delay_spin.setSingleStep(0.5)
        self.start_delay_spin.setSuffix(" sec")
        self.start_delay_spin.setValue(DEFAULT_START_DELAY_SECONDS)
        top_bar.addWidget(self.start_delay_spin)

        top_bar.addWidget(QLabel("Target"))
        self.target_app_edit = QLineEdit()
        self.target_app_edit.setPlaceholderText(DEFAULT_TARGET_APP)
        self.target_app_edit.setText(DEFAULT_TARGET_APP)
        top_bar.addWidget(self.target_app_edit, 1)

        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(self.start_macro)
        top_bar.addWidget(self.start_button)

        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_macro)
        self.stop_button.setEnabled(False)
        top_bar.addWidget(self.stop_button)

        self.emergency_button = QPushButton("Emergency Stop")
        self.emergency_button.clicked.connect(self.stop_macro)
        self.emergency_button.setEnabled(False)
        top_bar.addWidget(self.emergency_button)

        root_layout.addLayout(top_bar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_step_table_panel())
        splitter.addWidget(self._build_editor_panel())
        splitter.setSizes([560, 420])
        root_layout.addWidget(splitter, 1)

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Idle")
        self.setCentralWidget(root)
        self.resize(1040, 640)

    def _build_step_table_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        header_row = QHBoxLayout()
        header_row.addWidget(QLabel("Sequence Steps"))
        header_row.addStretch(1)
        layout.addLayout(header_row)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Direction", "Tap keys", "Hold (s)", "Interval (ms)"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.AnyKeyPressed
        )
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.table.itemChanged.connect(self._table_item_changed)
        layout.addWidget(self.table, 1)

        button_grid = QGridLayout()
        self.add_button = QPushButton("Add")
        self.add_button.clicked.connect(self.add_step)
        button_grid.addWidget(self.add_button, 0, 0)

        self.duplicate_button = QPushButton("Duplicate")
        self.duplicate_button.clicked.connect(self.duplicate_step)
        button_grid.addWidget(self.duplicate_button, 0, 1)

        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self.delete_step)
        button_grid.addWidget(self.delete_button, 0, 2)

        self.up_button = QPushButton("Move Up")
        self.up_button.clicked.connect(self.move_step_up)
        button_grid.addWidget(self.up_button, 1, 0)

        self.down_button = QPushButton("Move Down")
        self.down_button.clicked.connect(self.move_step_down)
        button_grid.addWidget(self.down_button, 1, 1)

        self.clear_log_button = QPushButton("Clear Log")
        self.clear_log_button.clicked.connect(lambda: self.log_view.clear())
        button_grid.addWidget(self.clear_log_button, 1, 2)

        self.record_button = QPushButton("Record")
        self.record_button.clicked.connect(self.start_recording)
        button_grid.addWidget(self.record_button, 2, 0)

        self.stop_recording_button = QPushButton("Stop Recording")
        self.stop_recording_button.clicked.connect(self.stop_recording)
        self.stop_recording_button.setEnabled(False)
        button_grid.addWidget(self.stop_recording_button, 2, 1, 1, 2)

        self.permission_button = QPushButton("Permission")
        self.permission_button.clicked.connect(self.request_accessibility_permission)
        button_grid.addWidget(self.permission_button, 3, 0)

        self.test_input_button = QPushButton("Test Input")
        self.test_input_button.clicked.connect(self.test_input)
        button_grid.addWidget(self.test_input_button, 3, 1, 1, 2)

        self.load_config_button = QPushButton("Load Config")
        self.load_config_button.clicked.connect(self.load_sequence)
        button_grid.addWidget(self.load_config_button, 4, 0)

        self.save_config_button = QPushButton("Save Config")
        self.save_config_button.clicked.connect(self.save_sequence)
        button_grid.addWidget(self.save_config_button, 4, 1, 1, 2)

        layout.addLayout(button_grid)
        return panel

    def _build_editor_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        editor_group = QGroupBox("Selected Step")
        form = QFormLayout(editor_group)

        self.direction_combo = QComboBox()
        self.direction_combo.addItems(DIRECTION_LABELS)
        self.direction_combo.currentTextChanged.connect(self._editor_changed)
        form.addRow("Direction", self.direction_combo)

        self.tap_keys_edit = QLineEdit()
        self.tap_keys_edit.setPlaceholderText("1, space or shift+a")
        self.tap_keys_edit.setReadOnly(False)
        self.tap_keys_edit.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.tap_keys_edit.textEdited.connect(self._editor_changed)
        form.addRow("Tap keys", self.tap_keys_edit)

        self.hold_spin = QDoubleSpinBox()
        self.hold_spin.setRange(0.05, 3600.0)
        self.hold_spin.setDecimals(2)
        self.hold_spin.setSingleStep(0.25)
        self.hold_spin.setSuffix(" sec")
        self.hold_spin.valueChanged.connect(self._editor_changed)
        form.addRow("Hold", self.hold_spin)

        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(MIN_TAP_INTERVAL_MS, 10000)
        self.interval_spin.setSingleStep(50)
        self.interval_spin.setSuffix(" ms")
        self.interval_spin.valueChanged.connect(self._editor_changed)
        form.addRow("Tap interval", self.interval_spin)

        self.apply_button = QPushButton("Apply Selected")
        self.apply_button.clicked.connect(self.apply_selected_step)
        form.addRow(self.apply_button)

        layout.addWidget(editor_group)

        log_group = QGroupBox("Run Log")
        log_layout = QVBoxLayout(log_group)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        log_layout.addWidget(self.log_view, 1)
        layout.addWidget(log_group, 1)

        return panel

    def _default_sequence(self) -> MacroSequence:
        return MacroSequence(
            name="Left Right Tap 1 Space",
            steps=[
                ActionStep(direction_key="LEFT", tap_keys=["1", "space"], hold_seconds=5.0, tap_interval_ms=200),
                ActionStep(direction_key="RIGHT", tap_keys=["1", "space"], hold_seconds=5.0, tap_interval_ms=200),
            ],
            loop=False,
            loop_count=None,
        )

    def _refresh_table(self, select_row: int | None = None) -> None:
        self._refreshing = True
        self.table.setRowCount(len(self.sequence.steps))
        for row, step in enumerate(self.sequence.steps):
            self._set_table_row_values(row, step)

        self._refreshing = False

        if select_row is not None and self.sequence.steps:
            self.table.selectRow(max(0, min(select_row, len(self.sequence.steps) - 1)))
        else:
            self._load_step_into_editor(None)

        self._update_button_state()

    def _set_table_row_values(self, row: int, step: ActionStep) -> None:
        values = [
            step.direction_key or "None",
            format_key_list(step.tap_keys),
            f"{step.hold_seconds:.2f}",
            str(step.tap_interval_ms),
        ]
        for column, value in enumerate(values):
            item = self.table.item(row, column)
            if item is None:
                item = QTableWidgetItem()
                self.table.setItem(row, column, item)
            item.setText(value)
            item.setData(Qt.ItemDataRole.UserRole, step.id)

    def _sync_sequence_controls(self) -> None:
        self.name_edit.setText(self.sequence.name)
        self.loop_check.setChecked(self.sequence.loop)
        self.loop_count_spin.setEnabled(self.sequence.loop)
        self.loop_count_spin.setValue(self.sequence.loop_count or 0)

    def _sync_execution_controls(self, start_delay_seconds: float, target_app: str) -> None:
        self.start_delay_spin.setValue(max(float(start_delay_seconds), 0.0))
        self.target_app_edit.setText(str(target_app or DEFAULT_TARGET_APP))

    def _sequence_controls_changed(self) -> None:
        self.sequence.name = self.name_edit.text().strip() or "Untitled Macro"
        self.sequence.loop = self.loop_check.isChecked()
        self.sequence.loop_count = self.loop_count_spin.value() or None

    def _loop_toggled(self, checked: bool) -> None:
        self.loop_count_spin.setEnabled(checked)
        self._sequence_controls_changed()

    def _selected_row(self) -> int | None:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        return selected[0].row()

    def _selection_changed(self) -> None:
        if self._refreshing:
            return
        row = self._selected_row()
        step = self.sequence.steps[row] if row is not None else None
        self._load_step_into_editor(step)
        self._update_button_state()

    def _load_step_into_editor(self, step: ActionStep | None) -> None:
        self._editor_refreshing = True
        enabled = step is not None
        self.direction_combo.setEnabled(enabled)
        self.tap_keys_edit.setEnabled(enabled)
        self.hold_spin.setEnabled(enabled)
        self.interval_spin.setEnabled(enabled)
        self.apply_button.setEnabled(enabled)

        if step is None:
            self.direction_combo.setCurrentText("None")
            self.tap_keys_edit.clear()
            self.hold_spin.setValue(1.0)
            self.interval_spin.setValue(200)
            self._editor_refreshing = False
            return

        self.direction_combo.setCurrentText(step.direction_key or "None")
        self.tap_keys_edit.setText(format_key_list(step.tap_keys))
        self.hold_spin.setValue(step.hold_seconds)
        self.interval_spin.setValue(step.tap_interval_ms)
        self._editor_refreshing = False

    def _step_from_editor(self, step_id: str | None = None) -> ActionStep:
        direction = self.direction_combo.currentText()
        if direction == "None":
            direction = None

        return ActionStep(
            id=step_id or new_step_id(),
            direction_key=direction,
            tap_keys=parse_key_list(self.tap_keys_edit.text()),
            hold_seconds=self.hold_spin.value(),
            tap_interval_ms=self.interval_spin.value(),
        )

    def _editor_changed(self, *_args) -> None:
        if self._refreshing or self._editor_refreshing or self._thread is not None or self._recorder is not None:
            return

        row = self._selected_row()
        if row is None:
            return

        current_id = self.sequence.steps[row].id
        self.sequence.steps[row] = self._step_from_editor(step_id=current_id)

        self._refreshing = True
        self._set_table_row_values(row, self.sequence.steps[row])
        self._refreshing = False

    def _table_item_changed(self, item: QTableWidgetItem) -> None:
        if self._refreshing or self._thread is not None or self._recorder is not None:
            return

        row = item.row()
        column = item.column()
        if row < 0 or row >= len(self.sequence.steps):
            return

        step = self.sequence.steps[row]
        raw_value = item.text().strip()

        try:
            if column == 0:
                direction = raw_value.upper()
                if direction in {"", "-", "NONE"}:
                    step.direction_key = None
                elif direction in {"LEFT", "RIGHT", "UP", "DOWN"}:
                    step.direction_key = direction
                else:
                    raise ValueError("Direction must be LEFT, RIGHT, UP, DOWN, or None.")
            elif column == 1:
                step.tap_keys = parse_key_list(raw_value)
            elif column == 2:
                step.hold_seconds = max(float(raw_value), 0.05)
            elif column == 3:
                interval_ms = int(float(raw_value))
                if interval_ms < MIN_TAP_INTERVAL_MS:
                    self._append_log(
                        f"[WARN] Interval {interval_ms}ms is too short; clamped to {MIN_TAP_INTERVAL_MS}ms."
                    )
                step.tap_interval_ms = max(interval_ms, MIN_TAP_INTERVAL_MS)
        except ValueError as exc:
            self._append_log(f"[WARN] Invalid table value: {exc}")

        self._refreshing = True
        self._set_table_row_values(row, step)
        self._refreshing = False

        if self._selected_row() == row:
            self._load_step_into_editor(step)

    def _update_button_state(self) -> None:
        row = self._selected_row()
        has_selection = row is not None
        is_running = self._thread is not None
        is_recording = self._recorder is not None
        is_busy = is_running or is_recording

        self.duplicate_button.setEnabled(has_selection and not is_busy)
        self.delete_button.setEnabled(has_selection and not is_busy)
        self.up_button.setEnabled(has_selection and row != 0 and not is_busy)
        self.down_button.setEnabled(
            has_selection and row is not None and row < len(self.sequence.steps) - 1 and not is_busy
        )
        self.apply_button.setEnabled(has_selection and not is_busy)
        self.record_button.setEnabled(not is_busy)
        self.stop_recording_button.setEnabled(is_recording)

    def add_step(self) -> None:
        self.sequence.steps.append(self._step_from_editor())
        self._refresh_table(select_row=len(self.sequence.steps) - 1)

    def duplicate_step(self) -> None:
        row = self._selected_row()
        if row is None:
            return
        copied = ActionStep.from_dict(self.sequence.steps[row].to_dict())
        copied.id = new_step_id()
        self.sequence.steps.insert(row + 1, copied)
        self._refresh_table(select_row=row + 1)

    def delete_step(self) -> None:
        row = self._selected_row()
        if row is None:
            return
        del self.sequence.steps[row]
        self._refresh_table(select_row=min(row, len(self.sequence.steps) - 1) if self.sequence.steps else None)

    def move_step_up(self) -> None:
        row = self._selected_row()
        if row is None or row == 0:
            return
        self.sequence.steps[row - 1], self.sequence.steps[row] = self.sequence.steps[row], self.sequence.steps[row - 1]
        self._refresh_table(select_row=row - 1)

    def move_step_down(self) -> None:
        row = self._selected_row()
        if row is None or row >= len(self.sequence.steps) - 1:
            return
        self.sequence.steps[row + 1], self.sequence.steps[row] = self.sequence.steps[row], self.sequence.steps[row + 1]
        self._refresh_table(select_row=row + 1)

    def apply_selected_step(self) -> None:
        row = self._selected_row()
        if row is None:
            return
        current_id = self.sequence.steps[row].id
        self.sequence.steps[row] = self._step_from_editor(step_id=current_id)
        self._refresh_table(select_row=row)

    def new_sequence(self) -> None:
        if self._thread is not None or self._recorder is not None:
            return
        self.sequence = self._default_sequence()
        self._current_path = None
        self._sync_execution_controls(DEFAULT_START_DELAY_SECONDS, DEFAULT_TARGET_APP)
        self._sync_sequence_controls()
        self._refresh_table(select_row=0)
        self._append_log("[NEW] Reset to default sequence.")

    def load_sequence(self) -> None:
        if self._thread is not None or self._recorder is not None:
            return
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Open Macro Config",
            "",
            "Macro Config (*.json);;All Files (*)",
        )
        if not file_name:
            return

        try:
            path = Path(file_name)
            self._apply_config(json.loads(path.read_text(encoding="utf-8")))
            self._current_path = path
            self._append_log(f"[LOAD] {path}")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Load failed", str(exc))

    def save_sequence(self) -> None:
        if self._current_path is None:
            self.save_sequence_as()
            return
        self._write_sequence(self._current_path)

    def save_sequence_as(self) -> None:
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "Save Macro Config",
            "",
            "Macro Config (*.json);;All Files (*)",
        )
        if not file_name:
            return
        path = Path(file_name)
        if path.suffix.lower() != ".json":
            path = path.with_suffix(".json")
        self._current_path = path
        self._write_sequence(path)

    def _write_sequence(self, path: Path) -> None:
        path.write_text(json.dumps(self._config_to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        self._append_log(f"[SAVE] {path}")

    def _config_to_dict(self) -> dict:
        self.apply_selected_step()
        self._sequence_controls_changed()
        return {
            "version": CONFIG_VERSION,
            "sequence": self.sequence.to_dict(),
            "start_delay_seconds": self.start_delay_spin.value(),
            "target_app": self.target_app_edit.text().strip(),
        }

    def _apply_config(self, data: dict) -> None:
        if not isinstance(data, dict):
            raise ValueError("Config must be a JSON object.")

        if "sequence" in data:
            sequence_data = data["sequence"]
            start_delay_seconds = data.get("start_delay_seconds", DEFAULT_START_DELAY_SECONDS)
            target_app = data.get("target_app", DEFAULT_TARGET_APP)
        else:
            # Backward compatibility: older files contained only MacroSequence data.
            sequence_data = data
            start_delay_seconds = data.get("start_delay_seconds", DEFAULT_START_DELAY_SECONDS)
            target_app = data.get("target_app", DEFAULT_TARGET_APP)

        self.sequence = MacroSequence.from_dict(sequence_data)
        self._sync_execution_controls(float(start_delay_seconds), str(target_app or DEFAULT_TARGET_APP))
        self._sync_sequence_controls()
        self._refresh_table(select_row=0)

    def start_macro(self) -> None:
        if self._thread is not None or self._recorder is not None:
            return

        self.apply_selected_step()
        self._sequence_controls_changed()

        if not self.sequence.steps:
            QMessageBox.warning(self, "No steps", "Add at least one step before starting.")
            return

        self._activate_target_app()
        self._start_sequence(self.sequence.clone(), self.start_delay_spin.value())

    def test_input(self) -> None:
        if self._thread is not None or self._recorder is not None:
            return

        self._append_log("[TEST] Focus a text input during the delay. This will type 'a' once.")
        sequence = MacroSequence(
            name="Input Test",
            steps=[ActionStep(direction_key=None, tap_keys=["a"], hold_seconds=0.08, tap_interval_ms=1000)],
            loop=False,
            loop_count=None,
        )
        self._start_sequence(sequence, self.start_delay_spin.value())

    def _activate_target_app(self) -> None:
        if sys.platform not in {"darwin", "win32"}:
            return

        target_name = self.target_app_edit.text().strip()
        if not target_name:
            return

        try:
            if sys.platform == "darwin":
                app_name = self._activate_macos_app(target_name)
            else:
                app_name = self._activate_windows_window(target_name)
            if app_name:
                self._append_log(f"[TARGET] Activated {app_name}.")
            else:
                self._append_log(f"[WARN] Target app not found: {target_name}")
        except Exception as exc:  # noqa: BLE001
            self._append_log(f"[WARN] Could not activate target app '{target_name}': {exc}")

    def _activate_macos_app(self, target_name: str) -> str | None:
        import AppKit

        normalized_target = target_name.casefold()
        workspace = AppKit.NSWorkspace.sharedWorkspace()
        apps = list(workspace.runningApplications())

        for app in apps:
            bundle_id = str(app.bundleIdentifier() or "")
            localized_name = str(app.localizedName() or "")
            if normalized_target in {bundle_id.casefold(), localized_name.casefold()}:
                app.activateWithOptions_(AppKit.NSApplicationActivateIgnoringOtherApps)
                return localized_name or bundle_id

        for app in apps:
            bundle_id = str(app.bundleIdentifier() or "")
            localized_name = str(app.localizedName() or "")
            haystack = f"{localized_name} {bundle_id}".casefold()
            if normalized_target in haystack:
                app.activateWithOptions_(AppKit.NSApplicationActivateIgnoringOtherApps)
                return localized_name or bundle_id

        return None

    def _activate_windows_window(self, target_name: str) -> str | None:
        import ctypes

        user32 = ctypes.windll.user32
        normalized_target = target_name.casefold()
        matches: list[tuple[int, str]] = []

        enum_windows_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def callback(hwnd, _lparam):
            if not user32.IsWindowVisible(hwnd):
                return True

            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True

            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            title = buffer.value.strip()
            if title and normalized_target in title.casefold():
                matches.append((hwnd, title))
                return False
            return True

        user32.EnumWindows(enum_windows_proc(callback), 0)
        if not matches:
            return None

        hwnd, title = matches[0]
        user32.ShowWindow(hwnd, 9)
        user32.SetForegroundWindow(hwnd)
        return title

    def _start_sequence(self, sequence: MacroSequence, start_delay_seconds: float) -> None:
        self._thread = QThread(self)
        self._worker = MacroWorker(sequence, start_delay_seconds)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.log.connect(self._append_log)
        self._worker.finished.connect(self._worker_finished)
        self._worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(self._thread.deleteLater)

        self._set_running(True)
        self._thread.start()

    def stop_macro(self) -> None:
        if self._worker is None:
            return
        self._append_log("[STOP REQUESTED]")
        self._worker.stop()

    def start_recording(self) -> None:
        if self._thread is not None or self._recorder is not None:
            return

        self._recorder = KeyRecorder()
        self._recorder.step_recorded.connect(self._add_recorded_step)
        self._recorder.log.connect(self._append_log)
        self._recorder.stopped.connect(self._recording_finished)
        self._set_recording(True)

        try:
            self._recorder.start()
            self.activateWindow()
            self.raise_()
            self.setFocus(Qt.FocusReason.OtherFocusReason)
        except Exception as exc:  # noqa: BLE001
            self._append_log(f"[ERROR] Recorder failed: {exc}")
            self._recording_finished()

    def stop_recording(self) -> None:
        if self._recorder is not None:
            self._recorder.stop()

    def _add_recorded_step(self, step: ActionStep) -> None:
        self.sequence.steps.append(step)
        self._refresh_table(select_row=len(self.sequence.steps) - 1)
        if step.direction_key:
            self._append_log(f"[RECORD] Added direction {step.direction_key} for {step.hold_seconds:.2f}s")
        else:
            self._append_log(f"[RECORD] Added tap {format_key_list(step.tap_keys)}")

    def _recording_finished(self) -> None:
        self._recorder = None
        self._set_recording(False)

    def _set_recording(self, recording: bool) -> None:
        for widget in (
            self.table,
            self.name_edit,
            self.loop_check,
            self.loop_count_spin,
            self.start_delay_spin,
            self.target_app_edit,
            self.permission_button,
            self.test_input_button,
            self.load_config_button,
            self.save_config_button,
            self.start_button,
            self.add_button,
            self.duplicate_button,
            self.delete_button,
            self.up_button,
            self.down_button,
            self.direction_combo,
            self.tap_keys_edit,
            self.hold_spin,
            self.interval_spin,
            self.apply_button,
            self.record_button,
        ):
            widget.setEnabled(not recording)

        self.stop_recording_button.setEnabled(recording)
        self.statusBar().showMessage("Recording" if recording else "Idle")
        if not recording:
            self._set_running(False)

    def _set_running(self, running: bool) -> None:
        self.start_button.setEnabled(not running)
        self.stop_button.setEnabled(running)
        self.emergency_button.setEnabled(running)

        for widget in (
            self.table,
            self.name_edit,
            self.loop_check,
            self.loop_count_spin,
            self.start_delay_spin,
            self.target_app_edit,
            self.permission_button,
            self.test_input_button,
            self.load_config_button,
            self.save_config_button,
            self.add_button,
            self.duplicate_button,
            self.delete_button,
            self.up_button,
            self.down_button,
            self.direction_combo,
            self.tap_keys_edit,
            self.hold_spin,
            self.interval_spin,
            self.apply_button,
        ):
            widget.setEnabled(not running)

        if not running:
            self.loop_count_spin.setEnabled(self.loop_check.isChecked())
            row = self._selected_row()
            step = self.sequence.steps[row] if row is not None else None
            self._load_step_into_editor(step)

        self.statusBar().showMessage("Running" if running else "Idle")

    def _worker_finished(self) -> None:
        self._set_running(False)
        self._worker = None
        self._thread = None
        self._update_button_state()

    def _append_log(self, message: str) -> None:
        self.log_view.append(message)
        self.log_view.verticalScrollBar().setValue(self.log_view.verticalScrollBar().maximum())

    def request_accessibility_permission(self) -> None:
        self._log_accessibility_status(prompt=True)
        if macos_accessibility_trusted(prompt=False) is not True and sys.platform == "darwin":
            self._open_accessibility_settings()

    def _log_accessibility_status(self, prompt: bool) -> None:
        if sys.platform != "darwin":
            self._append_log("[PERMISSION] No macOS Accessibility permission is required on this OS.")
            return

        trusted = macos_accessibility_trusted(prompt=prompt)
        if trusted is True:
            self._append_log("[PERMISSION] macOS Accessibility permission is granted.")
        elif trusted is False:
            executable_path = Path(sys.executable)
            resolved_path = executable_path.resolve()
            self._append_log(
                "[PERMISSION] macOS Accessibility permission is missing. "
                "Enable Terminal and Python in System Settings > Privacy & Security > Accessibility."
            )
            self._append_log(
                f"[PERMISSION] Python path: {executable_path} -> {resolved_path}"
            )
        else:
            self._append_log("[PERMISSION] Could not check macOS Accessibility permission.")

    def _open_accessibility_settings(self) -> None:
        import subprocess

        try:
            subprocess.run(
                ["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"],
                check=False,
                timeout=2,
            )
        except Exception as exc:  # noqa: BLE001
            self._append_log(f"[WARN] Could not open Accessibility settings: {exc}")

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if self._recorder is None:
            return super().eventFilter(obj, event)

        event_type = event.type()
        if event_type == QEvent.Type.KeyPress:
            self._recorder.handle_key_press(event)
            return True
        if event_type == QEvent.Type.KeyRelease:
            self._recorder.handle_key_release(event)
            return True

        return super().eventFilter(obj, event)

    def closeEvent(self, event) -> None:  # noqa: N802
        QApplication.instance().removeEventFilter(self)
        if self._recorder is not None:
            self._recorder.stop()
        if self._worker is not None:
            self._worker.stop()
        if self._thread is not None and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(1500)
        event.accept()


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
