"""Qt settings dialog for logger runtime options."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
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

        self.sample_rate_hz = QDoubleSpinBox()
        self.sample_rate_hz.setRange(1.0, 100.0)
        self.sample_rate_hz.setSingleStep(1.0)
        self.sample_rate_hz.setValue(float(values["sample_rate_hz"]))
        form.addRow("Sample rate (Hz)", self.sample_rate_hz)

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

        self.enable_iracing = QCheckBox("Enable iRacing")
        self.enable_iracing.setChecked(bool(values["enable_iracing"]))
        form.addRow("Sims", self.enable_iracing)

        self.enable_acc = QCheckBox("Enable ACC")
        self.enable_acc.setChecked(bool(values["enable_acc"]))
        form.addRow("", self.enable_acc)

        self.start_with_windows = QCheckBox("Start with Windows")
        self.start_with_windows.setChecked(bool(values["start_with_windows"]))
        form.addRow("Startup", self.start_with_windows)

        self.debug_csv = QCheckBox("Write telemetry_debug.csv")
        self.debug_csv.setChecked(bool(values["debug_csv"]))
        form.addRow("Debug", self.debug_csv)

        root.addLayout(form)

        note = QLabel("Sim enable changes apply on next restart.")
        note.setStyleSheet("color:#949494;")
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
        self.sample_rate_hz.setValue(float(self._original["sample_rate_hz"]))
        self.min_duration_s.setValue(float(self._original["min_duration_s"]))
        self.min_samples.setValue(int(self._original["min_samples"]))
        self.disconnect_timeout_s.setValue(float(self._original["disconnect_timeout_s"]))
        self.enable_iracing.setChecked(bool(self._original["enable_iracing"]))
        self.enable_acc.setChecked(bool(self._original["enable_acc"]))
        self.start_with_windows.setChecked(bool(self._original["start_with_windows"]))
        self.debug_csv.setChecked(bool(self._original["debug_csv"]))

    def values(self) -> dict:
        out = Path(self.output_dir.text().strip())
        return {
            "output_dir": str(out),
            "sample_rate_hz": float(self.sample_rate_hz.value()),
            "min_duration_s": float(self.min_duration_s.value()),
            "min_samples": int(self.min_samples.value()),
            "disconnect_timeout_s": float(self.disconnect_timeout_s.value()),
            "enable_iracing": self.enable_iracing.isChecked(),
            "enable_acc": self.enable_acc.isChecked(),
            "start_with_windows": self.start_with_windows.isChecked(),
            "debug_csv": self.debug_csv.isChecked(),
        }
