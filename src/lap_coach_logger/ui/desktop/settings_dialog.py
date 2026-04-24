"""Qt settings dialog for logger runtime options."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class SettingsDialog(QDialog):
    """Edit runtime config values with explicit apply/save/reset actions."""

    def __init__(self, values: dict, parent=None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(520)
        self._original = dict(values)

        root = QVBoxLayout(self)
        form = QFormLayout()
        form.setVerticalSpacing(10)

        self.output_dir = QLineEdit(values["output_dir"])
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        row = QHBoxLayout()
        row.addWidget(self.output_dir)
        row.addWidget(browse)
        wrap = QVBoxLayout()
        wrap.setContentsMargins(0, 0, 0, 0)
        wrap.addLayout(row)
        holder = QWidget()
        holder.setLayout(wrap)
        form.addRow("Output directory", holder)

        self.driver_name = QLineEdit(values["driver_name"])
        self.driver_name.setPlaceholderText("Optional driver name written into saved bundles")
        form.addRow("Driver name", self.driver_name)

        self.sample_rate_hz = QDoubleSpinBox()
        self.sample_rate_hz.setRange(1.0, 100.0)
        self.sample_rate_hz.setSingleStep(1.0)
        self.sample_rate_hz.setValue(float(values["sample_rate_hz"]))
        form.addRow("Sample rate (Hz)", self.sample_rate_hz)

        self.poll_interval_s = QDoubleSpinBox()
        self.poll_interval_s.setRange(0.1, 60.0)
        self.poll_interval_s.setSingleStep(0.1)
        self.poll_interval_s.setDecimals(1)
        self.poll_interval_s.setValue(float(values["poll_interval_s"]))
        form.addRow("Detection poll (s)", self.poll_interval_s)

        self.min_duration_s = QDoubleSpinBox()
        self.min_duration_s.setRange(0.0, 3600.0)
        self.min_duration_s.setValue(float(values["min_duration_s"]))
        form.addRow("Minimum duration (s)", self.min_duration_s)

        self.min_samples = QSpinBox()
        self.min_samples.setRange(0, 1_000_000)
        self.min_samples.setValue(int(values["min_samples"]))
        form.addRow("Minimum samples", self.min_samples)

        self.disconnect_timeout_s = QDoubleSpinBox()
        self.disconnect_timeout_s.setRange(0.5, 120.0)
        self.disconnect_timeout_s.setValue(float(values["disconnect_timeout_s"]))
        form.addRow("Disconnect timeout (s)", self.disconnect_timeout_s)

        self.session_end_grace_s = QDoubleSpinBox()
        self.session_end_grace_s.setRange(0.0, 120.0)
        self.session_end_grace_s.setSingleStep(0.5)
        self.session_end_grace_s.setValue(float(values["session_end_grace_s"]))
        form.addRow("End grace (s)", self.session_end_grace_s)

        self.enable_iracing = QCheckBox("Enable iRacing")
        self.enable_iracing.setChecked(bool(values["enable_iracing"]))
        form.addRow("Sims", self.enable_iracing)

        self.enable_assetto_corsa = QCheckBox("Enable Assetto Corsa")
        self.enable_assetto_corsa.setChecked(bool(values["enable_assetto_corsa"]))
        form.addRow("", self.enable_assetto_corsa)

        self.assetto_corsa_raw_capture_enabled = QCheckBox("Capture raw Assetto Corsa shared-memory data")
        self.assetto_corsa_raw_capture_enabled.setChecked(bool(values["assetto_corsa_raw_capture_enabled"]))
        form.addRow("", self.assetto_corsa_raw_capture_enabled)

        self.enable_acc = QCheckBox("Enable ACC")
        self.enable_acc.setChecked(bool(values["enable_acc"]))
        form.addRow("", self.enable_acc)

        self.acc_raw_capture_enabled = QCheckBox("Capture raw ACC shared-memory data")
        self.acc_raw_capture_enabled.setChecked(bool(values["acc_raw_capture_enabled"]))
        form.addRow("", self.acc_raw_capture_enabled)

        self.enable_lmu = QCheckBox("Enable Le Mans Ultimate")
        self.enable_lmu.setChecked(bool(values["enable_lmu"]))
        form.addRow("", self.enable_lmu)

        self.lmu_raw_capture_enabled = QCheckBox("Capture raw LMU shared-memory data")
        self.lmu_raw_capture_enabled.setChecked(bool(values["lmu_raw_capture_enabled"]))
        form.addRow("", self.lmu_raw_capture_enabled)

        self.iracing_sample_mode = QComboBox()
        self.iracing_sample_mode.addItem("Auto SDK tick", "auto_sdk")
        self.iracing_sample_mode.addItem("Manual sample rate", "manual")
        current_mode = str(values["iracing_sample_mode"])
        idx = self.iracing_sample_mode.findData(current_mode)
        self.iracing_sample_mode.setCurrentIndex(idx if idx >= 0 else 0)
        form.addRow("iRacing mode", self.iracing_sample_mode)

        self.iracing_raw_capture_enabled = QCheckBox("Capture raw iRacing SDK data")
        self.iracing_raw_capture_enabled.setChecked(bool(values["iracing_raw_capture_enabled"]))
        form.addRow("", self.iracing_raw_capture_enabled)

        self.start_with_windows = QCheckBox("Start with Windows")
        self.start_with_windows.setChecked(bool(values["start_with_windows"]))
        form.addRow("Startup", self.start_with_windows)

        self.low_resource_mode = QCheckBox("Enable low-resource mode")
        self.low_resource_mode.setChecked(bool(values["low_resource_mode"]))
        form.addRow("Performance", self.low_resource_mode)

        self.overlay_enabled = QCheckBox("Enable live telemetry overlay")
        self.overlay_enabled.setChecked(bool(values["overlay_enabled"]))
        form.addRow("Overlay", self.overlay_enabled)

        self.overlay_refresh_rate_hz = QSpinBox()
        self.overlay_refresh_rate_hz.setRange(15, 120)
        self.overlay_refresh_rate_hz.setSingleStep(5)
        self.overlay_refresh_rate_hz.setValue(int(values["overlay_refresh_rate_hz"]))
        form.addRow("Overlay refresh (Hz)", self.overlay_refresh_rate_hz)

        self.overlay_opacity = QDoubleSpinBox()
        self.overlay_opacity.setRange(0.30, 1.0)
        self.overlay_opacity.setSingleStep(0.05)
        self.overlay_opacity.setDecimals(2)
        self.overlay_opacity.setValue(float(values["overlay_opacity"]))
        form.addRow("Overlay opacity", self.overlay_opacity)

        self.overlay_pin_mode = QComboBox()
        self.overlay_pin_mode.addItem("Overlay on top", "overlay_on_top")
        self.overlay_pin_mode.addItem("Main window on top", "dashboard_on_top")
        self.overlay_pin_mode.addItem("Floating windows", "floating")
        pin_idx = self.overlay_pin_mode.findData(values["overlay_pin_mode"])
        self.overlay_pin_mode.setCurrentIndex(pin_idx if pin_idx >= 0 else 0)
        form.addRow("Pin mode", self.overlay_pin_mode)

        self.sync_enabled = QCheckBox("Enable Lap Coach sync")
        self.sync_enabled.setChecked(bool(values["sync_enabled"]))
        form.addRow("Sync", self.sync_enabled)

        self.sync_api_url = QLineEdit(values["sync_api_url"])
        form.addRow("Sync API URL", self.sync_api_url)

        self.sync_device_token = QLineEdit(values["sync_device_token"])
        self.sync_device_token.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        self.sync_device_token.setPlaceholderText("Device token")
        form.addRow("Sync token", self.sync_device_token)

        self.debug_csv = QCheckBox("Write telemetry_debug.csv")
        self.debug_csv.setChecked(bool(values["debug_csv"]))
        form.addRow("Debug", self.debug_csv)

        root.addLayout(form)

        self.enable_iracing.toggled.connect(self._update_iracing_controls)
        self.enable_assetto_corsa.toggled.connect(self._update_assetto_corsa_controls)
        self.enable_acc.toggled.connect(self._update_acc_controls)
        self.enable_lmu.toggled.connect(self._update_lmu_controls)
        self.overlay_enabled.toggled.connect(self._update_overlay_controls)
        self.iracing_sample_mode.currentIndexChanged.connect(self._update_iracing_controls)
        self.sync_enabled.toggled.connect(self._update_sync_controls)
        self._update_iracing_controls()
        self._update_assetto_corsa_controls()
        self._update_acc_controls()
        self._update_lmu_controls()
        self._update_overlay_controls()
        self._update_sync_controls()

        note = QLabel("Adapter and active-session capture changes may require the next session or an app restart to fully apply.")
        note.setStyleSheet("color:#949494;")
        note.setWordWrap(True)
        root.addWidget(note)

        buttons = QDialogButtonBox()
        self.btn_apply = buttons.addButton("Apply", QDialogButtonBox.ButtonRole.ApplyRole)
        self.btn_reset = buttons.addButton("Reset", QDialogButtonBox.ButtonRole.ResetRole)
        self.btn_close = buttons.addButton("Close", QDialogButtonBox.ButtonRole.RejectRole)
        self.btn_apply.clicked.connect(self.accept)
        self.btn_close.clicked.connect(self.reject)
        self.btn_reset.clicked.connect(self._reset)
        root.addWidget(buttons)

    def _browse(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Select Output Directory", self.output_dir.text())
        if selected:
            self.output_dir.setText(selected)

    def _reset(self) -> None:
        self.output_dir.setText(self._original["output_dir"])
        self.driver_name.setText(self._original["driver_name"])
        self.sample_rate_hz.setValue(float(self._original["sample_rate_hz"]))
        self.poll_interval_s.setValue(float(self._original["poll_interval_s"]))
        self.min_duration_s.setValue(float(self._original["min_duration_s"]))
        self.min_samples.setValue(int(self._original["min_samples"]))
        self.disconnect_timeout_s.setValue(float(self._original["disconnect_timeout_s"]))
        self.session_end_grace_s.setValue(float(self._original["session_end_grace_s"]))
        self.enable_iracing.setChecked(bool(self._original["enable_iracing"]))
        self.enable_assetto_corsa.setChecked(bool(self._original["enable_assetto_corsa"]))
        self.assetto_corsa_raw_capture_enabled.setChecked(bool(self._original["assetto_corsa_raw_capture_enabled"]))
        self.enable_acc.setChecked(bool(self._original["enable_acc"]))
        self.acc_raw_capture_enabled.setChecked(bool(self._original["acc_raw_capture_enabled"]))
        self.enable_lmu.setChecked(bool(self._original["enable_lmu"]))
        self.lmu_raw_capture_enabled.setChecked(bool(self._original["lmu_raw_capture_enabled"]))
        idx = self.iracing_sample_mode.findData(self._original["iracing_sample_mode"])
        self.iracing_sample_mode.setCurrentIndex(idx if idx >= 0 else 0)
        self.iracing_raw_capture_enabled.setChecked(bool(self._original["iracing_raw_capture_enabled"]))
        self.start_with_windows.setChecked(bool(self._original["start_with_windows"]))
        self.low_resource_mode.setChecked(bool(self._original["low_resource_mode"]))
        self.overlay_enabled.setChecked(bool(self._original["overlay_enabled"]))
        self.overlay_refresh_rate_hz.setValue(int(self._original["overlay_refresh_rate_hz"]))
        self.overlay_opacity.setValue(float(self._original["overlay_opacity"]))
        idx = self.overlay_pin_mode.findData(self._original["overlay_pin_mode"])
        self.overlay_pin_mode.setCurrentIndex(idx if idx >= 0 else 0)
        self.sync_enabled.setChecked(bool(self._original["sync_enabled"]))
        self.sync_api_url.setText(self._original["sync_api_url"])
        self.sync_device_token.setText(self._original["sync_device_token"])
        self.debug_csv.setChecked(bool(self._original["debug_csv"]))
        self._update_iracing_controls()
        self._update_assetto_corsa_controls()
        self._update_acc_controls()
        self._update_lmu_controls()
        self._update_overlay_controls()
        self._update_sync_controls()

    def _update_iracing_controls(self) -> None:
        iracing_enabled = self.enable_iracing.isChecked()
        self.iracing_sample_mode.setEnabled(iracing_enabled)
        raw_capture_allowed = iracing_enabled and self.iracing_sample_mode.currentData() == "auto_sdk"
        self.iracing_raw_capture_enabled.setEnabled(raw_capture_allowed)
        if not raw_capture_allowed:
            self.iracing_raw_capture_enabled.setChecked(False)

    def _update_assetto_corsa_controls(self) -> None:
        enabled = self.enable_assetto_corsa.isChecked()
        self.assetto_corsa_raw_capture_enabled.setEnabled(enabled)
        if not enabled:
            self.assetto_corsa_raw_capture_enabled.setChecked(False)

    def _update_acc_controls(self) -> None:
        acc_enabled = self.enable_acc.isChecked()
        self.acc_raw_capture_enabled.setEnabled(acc_enabled)
        if not acc_enabled:
            self.acc_raw_capture_enabled.setChecked(False)

    def _update_lmu_controls(self) -> None:
        enabled = self.enable_lmu.isChecked()
        self.lmu_raw_capture_enabled.setEnabled(enabled)
        if not enabled:
            self.lmu_raw_capture_enabled.setChecked(False)

    def _update_overlay_controls(self) -> None:
        enabled = self.overlay_enabled.isChecked()
        self.overlay_refresh_rate_hz.setEnabled(enabled)
        self.overlay_opacity.setEnabled(enabled)
        self.overlay_pin_mode.setEnabled(enabled)

    def _update_sync_controls(self) -> None:
        enabled = self.sync_enabled.isChecked()
        self.sync_api_url.setEnabled(enabled)
        self.sync_device_token.setEnabled(enabled)

    def values(self) -> dict:
        out = Path(self.output_dir.text().strip())
        return {
            "output_dir": str(out),
            "driver_name": self.driver_name.text().strip(),
            "sample_rate_hz": float(self.sample_rate_hz.value()),
            "poll_interval_s": float(self.poll_interval_s.value()),
            "min_duration_s": float(self.min_duration_s.value()),
            "min_samples": int(self.min_samples.value()),
            "disconnect_timeout_s": float(self.disconnect_timeout_s.value()),
            "session_end_grace_s": float(self.session_end_grace_s.value()),
            "enable_iracing": self.enable_iracing.isChecked(),
            "enable_assetto_corsa": self.enable_assetto_corsa.isChecked(),
            "assetto_corsa_raw_capture_enabled": self.assetto_corsa_raw_capture_enabled.isChecked(),
            "enable_acc": self.enable_acc.isChecked(),
            "acc_raw_capture_enabled": self.acc_raw_capture_enabled.isChecked(),
            "enable_lmu": self.enable_lmu.isChecked(),
            "lmu_raw_capture_enabled": self.lmu_raw_capture_enabled.isChecked(),
            "iracing_sample_mode": str(self.iracing_sample_mode.currentData()),
            "iracing_raw_capture_enabled": self.iracing_raw_capture_enabled.isChecked(),
            "start_with_windows": self.start_with_windows.isChecked(),
            "low_resource_mode": self.low_resource_mode.isChecked(),
            "overlay_enabled": self.overlay_enabled.isChecked(),
            "overlay_refresh_rate_hz": int(self.overlay_refresh_rate_hz.value()),
            "overlay_opacity": float(self.overlay_opacity.value()),
            "overlay_pin_mode": str(self.overlay_pin_mode.currentData()),
            "sync_enabled": self.sync_enabled.isChecked(),
            "sync_api_url": self.sync_api_url.text().strip(),
            "sync_device_token": self.sync_device_token.text().strip(),
            "debug_csv": self.debug_csv.isChecked(),
        }
