"""About dialog for product identity and local paths."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFrame, QHBoxLayout, QLabel, QVBoxLayout

from lap_coach_logger import APP_NAME, COMPANY_NAME, VERSION
from lap_coach_logger.assets import monogram_path
from lap_coach_logger.utils.paths import config_dir, logs_dir

_CHALK = "#F0EDE5"
_STEEL = "#949494"
_PIT_ORANGE = "#C9A84C"
_CONCRETE = "#141414"


class AboutDialog(QDialog):
    def __init__(self, *, install_path: str, parent=None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self.setWindowTitle(f"About {APP_NAME}")
        self.setMinimumWidth(520)
        self.setMinimumHeight(400)

        root = QVBoxLayout(self)
        root.setSpacing(16)
        root.setContentsMargins(28, 28, 28, 24)

        # ── Header: monogram + branding text ────────────────────────
        header = QHBoxLayout()
        header.setSpacing(16)

        mono_svg = monogram_path()
        if mono_svg and mono_svg.exists():
            mono = QSvgWidget(str(mono_svg))
            mono.setFixedSize(64, 64)
            mono.setStyleSheet("background:transparent;")
            header.addWidget(mono)

        branding = QVBoxLayout()
        branding.setSpacing(2)
        title = QLabel("LAP COACH")
        title.setStyleSheet(
            f"font-size:22px; font-weight:700; color:{_CHALK};"
            " letter-spacing:3px;"
        )
        tagline = QLabel("TELEMETRY LOGGER")
        tagline.setStyleSheet(
            f"font-size:10px; font-weight:600; color:{_PIT_ORANGE};"
            " letter-spacing:2px;"
        )
        ver = QLabel(f"v{VERSION}")
        ver.setStyleSheet(
            f"font-size:12px; color:{_STEEL};"
            " font-family:'Consolas','Space Mono',monospace;"
        )
        branding.addWidget(title)
        branding.addWidget(tagline)
        branding.addWidget(ver)
        header.addLayout(branding)
        header.addStretch(1)
        root.addLayout(header)

        # ── Separator ────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: rgba(240,237,229,0.06);")
        sep.setFixedHeight(1)
        root.addWidget(sep)

        # ── Info card ────────────────────────────────────────────────
        info = QFrame()
        info.setObjectName("Card")
        il = QVBoxLayout(info)
        il.setContentsMargins(16, 16, 16, 16)
        il.setSpacing(8)

        desc = QLabel("Local-first telemetry capture.\nNo cloud sync. No account. No nonsense.")
        desc.setStyleSheet(f"color:{_STEEL}; font-size:12px; line-height:1.4;")
        desc.setWordWrap(True)
        il.addWidget(desc)

        for label, value in (
            ("PUBLISHER", COMPANY_NAME),
            ("INSTALL PATH", install_path),
            ("CONFIG PATH", str(config_dir())),
            ("LOG PATH", str(logs_dir())),
        ):
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            lbl = QLabel(label)
            lbl.setStyleSheet(
                f"font-size:10px; color:{_PIT_ORANGE};"
                " letter-spacing:1.5px; font-weight:600;"
            )
            lbl.setFixedWidth(110)
            val = QLabel(value)
            val.setStyleSheet(
                f"font-size:11px; color:{_CHALK};"
                " font-family:'Consolas','Space Mono',monospace;"
            )
            val.setWordWrap(True)
            row.addWidget(lbl)
            row.addWidget(val, 1)
            il.addLayout(row)

        root.addWidget(info)
        root.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        root.addWidget(buttons)
