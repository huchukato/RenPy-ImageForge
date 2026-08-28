"""Settings panel: aspect ratio, anchor, resize, output, upscaling."""

from __future__ import annotations

from typing import Tuple

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QComboBox, QSpinBox, QCheckBox,
    QSlider, QLabel, QPushButton, QGridLayout, QGroupBox, QLineEdit,
    QFileDialog, QHBoxLayout, QButtonGroup, QToolButton,
)

from ..cropper import CropSettings, Anchor, ASPECT_PRESETS
from ..upscaler import UpscaleSettings, MODELS, VALID_SCALES, status_message
from ..i18n import tr


class AnchorGrid(QWidget):
    """3x3 grid of buttons to select the crop anchor."""

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        layout = QGridLayout(self)
        layout.setSpacing(4)
        layout.setContentsMargins(0, 0, 0, 0)
        positions = [
            (Anchor.TOP_LEFT, 0, 0), (Anchor.TOP, 0, 1), (Anchor.TOP_RIGHT, 0, 2),
            (Anchor.LEFT, 1, 0), (Anchor.CENTER, 1, 1), (Anchor.RIGHT, 1, 2),
            (Anchor.BOTTOM_LEFT, 2, 0), (Anchor.BOTTOM, 2, 1), (Anchor.BOTTOM_RIGHT, 2, 2),
        ]
        self._buttons = {}
        for anchor, row, col in positions:
            btn = QToolButton()
            btn.setCheckable(True)
            btn.setFixedSize(28, 28)
            btn.setProperty("anchor", anchor.value)
            if anchor == Anchor.CENTER:
                btn.setChecked(True)
            self._group.addButton(btn)
            layout.addWidget(btn, row, col)
            self._buttons[anchor] = btn
            btn.toggled.connect(lambda _c, a=anchor: self._on_toggled(a))

    def _on_toggled(self, anchor):
        if self._buttons[anchor].isChecked():
            self.changed.emit()

    def value(self) -> Anchor:
        btn = self._group.checkedButton()
        if btn is None:
            return Anchor.CENTER
        return Anchor(btn.property("anchor"))


class SettingsPanel(QWidget):
    """Complete settings panel. Emits `changed` on every modification."""

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._wire_signals()
        self._on_aspect_changed()
        self.retranslate_ui()

    # ---- UI ----
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # --- Quick presets ---
        self.preset_group = QGroupBox()
        preset_layout = QHBoxLayout(self.preset_group)
        self.preset_1080p = QPushButton("Full HD 1080p")
        self.preset_1080p.clicked.connect(lambda: self._apply_preset("1080p"))
        self.preset_1440p = QPushButton("1440p")
        self.preset_1440p.clicked.connect(lambda: self._apply_preset("1440p"))
        self.preset_4k = QPushButton("4K UHD")
        self.preset_4k.clicked.connect(lambda: self._apply_preset("4k"))
        for b in (self.preset_1080p, self.preset_1440p, self.preset_4k):
            preset_layout.addWidget(b)
        root.addWidget(self.preset_group)

        # --- Pipeline note ---
        self.note_label = QLabel()
        self.note_label.setWordWrap(True)
        self.note_label.setStyleSheet(
            "QLabel{color:#b89878;font-size:10px;padding:4px;background:#2a2621;"
            "border-radius:4px;}")
        root.addWidget(self.note_label)

        # --- Crop ---
        self.crop_group = QGroupBox()
        crop_layout = QFormLayout(self.crop_group)

        self.aspect_combo = QComboBox()
        self.aspect_combo.addItem("", "none")
        for name in ASPECT_PRESETS:
            self.aspect_combo.addItem(name, name)
        self.aspect_combo.addItem("", "custom")
        self.aspect_combo.setCurrentText("16:9")
        self._aspect_label = QLabel()
        crop_layout.addRow(self._aspect_label, self.aspect_combo)

        self.custom_w = QSpinBox()
        self.custom_w.setRange(1, 9999)
        self.custom_w.setValue(16)
        self.custom_h = QSpinBox()
        self.custom_h.setRange(1, 9999)
        self.custom_h.setValue(9)
        custom_row = QHBoxLayout()
        custom_row.setContentsMargins(0, 0, 0, 0)
        custom_row.addWidget(self.custom_w)
        custom_row.addWidget(QLabel(":"))
        custom_row.addWidget(self.custom_h)
        custom_row.addStretch()
        self.custom_widget = QWidget()
        self.custom_widget.setLayout(custom_row)
        self._custom_label = QLabel()
        crop_layout.addRow(self._custom_label, self.custom_widget)

        self.anchor_grid = AnchorGrid()
        self._anchor_label = QLabel()
        crop_layout.addRow(self._anchor_label, self.anchor_grid)

        root.addWidget(self.crop_group)

        # --- Final resize ---
        self.resize_group = QGroupBox()
        resize_layout = QFormLayout(self.resize_group)

        self.resize_check = QCheckBox()
        resize_layout.addRow(self.resize_check)

        self.resize_w = QSpinBox()
        self.resize_w.setRange(1, 32767)
        self.resize_w.setValue(1920)
        self.resize_w.setSpecialValueText("auto")
        self.resize_h = QSpinBox()
        self.resize_h.setRange(1, 32767)
        self.resize_h.setValue(1080)
        self.resize_h.setSpecialValueText("auto")
        rh = QHBoxLayout()
        rh.setContentsMargins(0, 0, 0, 0)
        rh.addWidget(self.resize_w)
        rh.addWidget(QLabel("x"))
        rh.addWidget(self.resize_h)
        rh.addStretch()
        self.resize_widget = QWidget()
        self.resize_widget.setLayout(rh)
        self._dim_label = QLabel()
        resize_layout.addRow(self._dim_label, self.resize_widget)

        self.resize_lock = QCheckBox()
        self.resize_lock.setChecked(True)
        resize_layout.addRow(self.resize_lock)

        root.addWidget(self.resize_group)

        # --- Output ---
        self.out_group = QGroupBox()
        out_layout = QFormLayout(self.out_group)

        self.format_combo = QComboBox()
        self.format_combo.addItems(["webp", "png", "jpg"])
        self._format_label = QLabel()
        out_layout.addRow(self._format_label, self.format_combo)

        self.quality_slider = QSlider(Qt.Horizontal)
        self.quality_slider.setRange(1, 100)
        self.quality_slider.setValue(98)
        self.quality_label = QLabel("98")
        qh = QHBoxLayout()
        qh.setContentsMargins(0, 0, 0, 0)
        qh.addWidget(self.quality_slider)
        qh.addWidget(self.quality_label)
        q_widget = QWidget()
        q_widget.setLayout(qh)
        self._quality_label = QLabel()
        out_layout.addRow(self._quality_label, q_widget)

        self.suffix_edit = QLineEdit()
        self._suffix_label = QLabel()
        out_layout.addRow(self._suffix_label, self.suffix_edit)

        # --- In-place mode ---
        self.inplace_check = QCheckBox()
        out_layout.addRow(self.inplace_check)

        self.backup_label = QLabel()
        self.backup_label.setStyleSheet(
            "QLabel{color:#b89878;font-size:10px;padding:2px;}")
        out_layout.addRow(self.backup_label)

        # Destination (disabled if in-place)
        self.outdir_edit = QLineEdit()
        self.browse_btn = QPushButton()
        self.browse_btn.clicked.connect(self._pick_outdir)
        oh = QHBoxLayout()
        oh.setContentsMargins(0, 0, 0, 0)
        oh.addWidget(self.outdir_edit)
        oh.addWidget(self.browse_btn)
        oh_widget = QWidget()
        oh_widget.setLayout(oh)
        self.outdir_row = oh_widget
        self._dest_label = QLabel()
        out_layout.addRow(self._dest_label, oh_widget)

        root.addWidget(self.out_group)

        # --- AI Upscaling ---
        self.up_group = QGroupBox()
        up_layout = QFormLayout(self.up_group)

        self.upscale_check = QCheckBox()
        up_layout.addRow(self.upscale_check)

        self.scale_combo = QComboBox()
        for s in VALID_SCALES:
            self.scale_combo.addItem(f"x{s}", s)
        self._scale_label = QLabel()
        up_layout.addRow(self._scale_label, self.scale_combo)

        self.model_combo = QComboBox()
        for mid, desc in MODELS.items():
            self.model_combo.addItem(f"{mid} \u2014 {desc}", mid)
        self._model_label = QLabel()
        up_layout.addRow(self._model_label, self.model_combo)

        self.tile_spin = QSpinBox()
        self.tile_spin.setRange(0, 4096)
        self.tile_spin.setValue(0)
        self.tile_spin.setSpecialValueText("auto")
        self._tile_label = QLabel()
        up_layout.addRow(self._tile_label, self.tile_spin)

        self.tta_check = QCheckBox()
        up_layout.addRow(self.tta_check)

        self.upscale_status = QLabel(status_message())
        self.upscale_status.setWordWrap(True)
        self.upscale_status.setStyleSheet("color: #b89878; font-size: 10px;")
        up_layout.addRow(self.upscale_status)

        root.addWidget(self.up_group)
        root.addStretch()

    def retranslate_ui(self):
        """Update all translatable strings."""
        self.preset_group.setTitle(tr("preset_group"))
        self.preset_1080p.setToolTip(tr("preset_1080p_tip"))
        self.preset_1440p.setToolTip(tr("preset_1440p_tip"))
        self.preset_4k.setToolTip(tr("preset_4k_tip"))
        self.note_label.setText(tr("pipeline_note"))

        self.crop_group.setTitle(tr("crop_group"))
        self.aspect_combo.setItemText(0, tr("aspect_none"))
        self.aspect_combo.setItemText(self.aspect_combo.count() - 1, tr("aspect_custom"))
        self._aspect_label.setText(tr("aspect_ratio"))
        self._custom_label.setText(tr("custom_wh"))
        self._anchor_label.setText(tr("anchor_pos"))

        self.resize_group.setTitle(tr("resize_group"))
        self.resize_check.setText(tr("enable_resize"))
        self._dim_label.setText(tr("dimension_auto"))
        self.resize_lock.setText(tr("keep_ratio"))

        self.out_group.setTitle(tr("output_group"))
        self._format_label.setText(tr("format"))
        self._quality_label.setText(tr("quality"))
        self._suffix_label.setText(tr("suffix_name"))
        self.suffix_edit.setPlaceholderText(tr("suffix_placeholder"))
        self.inplace_check.setText(tr("inplace_check"))
        self.inplace_check.setToolTip(tr("inplace_tip"))
        self.backup_label.setText(tr("backup_label"))
        self.outdir_edit.setPlaceholderText(tr("dest_placeholder"))
        self.browse_btn.setText(tr("browse"))
        self._dest_label.setText(tr("destination"))

        self.up_group.setTitle(tr("upscale_group"))
        self.upscale_check.setText(tr("enable_upscale"))
        self._scale_label.setText(tr("scale"))
        self._model_label.setText(tr("model"))
        self._tile_label.setText(tr("tile_size"))
        self.tta_check.setText(tr("tta"))

    # --- Signals ---
    def _wire_signals(self):
        self.aspect_combo.currentIndexChanged.connect(self._on_aspect_changed)
        self.custom_w.valueChanged.connect(self.changed)
        self.custom_h.valueChanged.connect(self.changed)
        self.anchor_grid.changed.connect(self.changed)
        self.resize_check.toggled.connect(self._on_resize_toggled)
        self.resize_check.toggled.connect(self.changed)
        self.resize_w.valueChanged.connect(self._on_resize_w_changed)
        self.resize_h.valueChanged.connect(self._on_resize_h_changed)
        self.resize_lock.toggled.connect(self.changed)
        self.format_combo.currentIndexChanged.connect(self._on_format_changed)
        self.quality_slider.valueChanged.connect(self._on_quality_changed)
        self.suffix_edit.textChanged.connect(self.changed)
        self.outdir_edit.textChanged.connect(self.changed)
        self.inplace_check.toggled.connect(self._on_inplace_toggled)
        self.inplace_check.toggled.connect(self.changed)
        self.upscale_check.toggled.connect(self._on_upscale_toggled)
        self.upscale_check.toggled.connect(self.changed)
        self.scale_combo.currentIndexChanged.connect(self.changed)
        self.model_combo.currentIndexChanged.connect(self.changed)
        self.tile_spin.valueChanged.connect(self.changed)
        self.tta_check.toggled.connect(self.changed)

    def _apply_preset(self, name: str):
        widgets = [self.aspect_combo, self.resize_check, self.resize_w,
                   self.resize_h, self.upscale_check, self.scale_combo]
        for w in widgets:
            w.blockSignals(True)

        self.aspect_combo.setCurrentText("16:9")

        if name == "1080p":
            target = (1920, 1080)
            scale = 2
        elif name == "1440p":
            target = (2560, 1440)
            scale = 2
        elif name == "4k":
            target = (3840, 2160)
            scale = 3
        else:
            return

        self.resize_check.setChecked(True)
        self.resize_w.setValue(target[0])
        self.resize_h.setValue(target[1])

        self.upscale_check.setChecked(True)
        idx = self.scale_combo.findData(scale)
        if idx >= 0:
            self.scale_combo.setCurrentIndex(idx)

        for w in widgets:
            w.blockSignals(False)

        self._on_aspect_changed()
        self._on_resize_toggled(True)
        self._on_upscale_toggled(True)
        self.changed.emit()

    def _on_aspect_changed(self):
        is_custom = self.aspect_combo.currentData() == "custom"
        self.custom_widget.setEnabled(is_custom)
        self.anchor_grid.setEnabled(self.aspect_combo.currentData() != "none")
        self.changed.emit()

    def _on_resize_toggled(self, on):
        self.resize_widget.setEnabled(on)
        self.changed.emit()

    def _on_resize_w_changed(self, val):
        if self.resize_lock.isChecked() and val != 0:
            ar = self.aspect_ratio()
            if ar is not None:
                self.resize_h.blockSignals(True)
                self.resize_h.setValue(int(round(val * ar[1] / ar[0])))
                self.resize_h.blockSignals(False)
        self.changed.emit()

    def _on_resize_h_changed(self, val):
        if self.resize_lock.isChecked() and val != 0:
            ar = self.aspect_ratio()
            if ar is not None:
                self.resize_w.blockSignals(True)
                self.resize_w.setValue(int(round(val * ar[0] / ar[1])))
                self.resize_w.blockSignals(False)
        self.changed.emit()

    def _on_format_changed(self):
        is_jpg_webp = self.format_combo.currentText() in ("jpg", "webp")
        self.quality_slider.setEnabled(is_jpg_webp)
        self.changed.emit()

    def _on_quality_changed(self, val):
        self.quality_label.setText(str(val))
        self.changed.emit()

    def _on_upscale_toggled(self, on):
        for w in (self.scale_combo, self.model_combo, self.tile_spin, self.tta_check):
            w.setEnabled(on)
        self.changed.emit()

    def _on_inplace_toggled(self, on):
        self.outdir_row.setEnabled(not on)
        self.suffix_edit.setEnabled(not on)
        self.format_combo.setEnabled(not on)
        self.changed.emit()

    def _pick_outdir(self):
        d = QFileDialog.getExistingDirectory(self, tr("select_dest_folder"))
        if d:
            self.outdir_edit.setText(d)

    # --- Getters ---
    def in_place(self) -> bool:
        return self.inplace_check.isChecked()

    def aspect_ratio(self) -> Tuple[int, int] | None:
        data = self.aspect_combo.currentData()
        if data == "none":
            return None
        if data == "custom":
            return (self.custom_w.value(), self.custom_h.value())
        return ASPECT_PRESETS[data]

    def crop_settings(self) -> CropSettings:
        ar = self.aspect_ratio()
        resize_after = None
        if self.resize_check.isChecked():
            w = self.resize_w.value() if self.resize_w.value() != self.resize_w.minimum() else None
            h = self.resize_h.value() if self.resize_h.value() != self.resize_h.minimum() else None
            if self.resize_w.value() == self.resize_w.minimum():
                w = None
            if self.resize_h.value() == self.resize_h.minimum():
                h = None
            resize_after = (w, h)
        return CropSettings(
            aspect_ratio=ar,
            anchor=self.anchor_grid.value(),
            resize_after=resize_after,
            output_format=self.format_combo.currentText(),
            output_quality=self.quality_slider.value(),
        )

    def upscale_settings(self) -> UpscaleSettings:
        return UpscaleSettings(
            enabled=self.upscale_check.isChecked(),
            scale=self.scale_combo.currentData(),
            model=self.model_combo.currentData(),
            tile_size=self.tile_spin.value(),
            output_format="png",
            tta=self.tta_check.isChecked(),
        )

    def output_dir(self) -> str:
        return self.outdir_edit.text().strip()

    def suffix(self) -> str:
        return self.suffix_edit.text().strip()
