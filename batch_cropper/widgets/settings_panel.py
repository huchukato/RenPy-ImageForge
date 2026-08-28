"""Pannello impostazioni: aspect ratio, anchor, resize, output, upscaling."""

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


class AnchorGrid(QWidget):
    """Griglia 3x3 di bottoni per selezionare l'anchor del crop."""

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
    """Pannello completo di impostazioni. Emette `changed` a ogni modifica."""

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._wire_signals()
        self._on_aspect_changed()  # stato iniziale

    # ---- UI ----
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # --- Preset rapidi ---
        preset_group = QGroupBox("Preset rapido")
        preset_layout = QHBoxLayout(preset_group)
        self.preset_1080p = QPushButton("Full HD 1080p")
        self.preset_1080p.setToolTip(
            "Crop 16:9 + upscale AI x2 + resize 1920x1080\n"
            "Pipeline: crop -> upscale -> resize al target esatto")
        self.preset_1080p.clicked.connect(lambda: self._apply_preset("1080p"))
        self.preset_1440p = QPushButton("1440p")
        self.preset_1440p.setToolTip("Crop 16:9 + upscale AI x2 + resize 2560x1440")
        self.preset_1440p.clicked.connect(lambda: self._apply_preset("1440p"))
        self.preset_4k = QPushButton("4K UHD")
        self.preset_4k.setToolTip("Crop 16:9 + upscale AI x3 + resize 3840x2160")
        self.preset_4k.clicked.connect(lambda: self._apply_preset("4k"))
        for b in (self.preset_1080p, self.preset_1440p, self.preset_4k):
            preset_layout.addWidget(b)
        root.addWidget(preset_group)

        # --- Nota pipeline ---
        self.note_label = QLabel(
            "Pipeline: <b>crop</b> (aspect ratio) &rarr; <b>upscale AI</b> (x2/x3/x4) "
            "&rarr; <b>resize finale</b> al target esatto.\n"
            "L'AI porta sopra il target, il resize down conserva il dettaglio."
        )
        self.note_label.setWordWrap(True)
        self.note_label.setStyleSheet(
            "QLabel{color:#b89878;font-size:10px;padding:4px;background:#2a2621;"
            "border-radius:4px;}")
        root.addWidget(self.note_label)

        # --- Crop ---
        crop_group = QGroupBox("Crop")
        crop_layout = QFormLayout(crop_group)

        self.aspect_combo = QComboBox()
        self.aspect_combo.addItem("Nessuno (no crop)", "none")
        for name in ASPECT_PRESETS:
            self.aspect_combo.addItem(name, name)
        self.aspect_combo.addItem("Custom...", "custom")
        self.aspect_combo.setCurrentText("16:9")
        crop_layout.addRow("Aspect ratio:", self.aspect_combo)

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
        crop_layout.addRow("Custom W:H:", self.custom_widget)

        self.anchor_grid = AnchorGrid()
        crop_layout.addRow("Posizione:", self.anchor_grid)

        root.addWidget(crop_group)

        # --- Resize finale ---
        resize_group = QGroupBox("Resize finale (dopo crop)")
        resize_layout = QFormLayout(resize_group)

        self.resize_check = QCheckBox("Abilita resize")
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
        resize_layout.addRow("Dimensione (auto=proporzionale):", self.resize_widget)

        self.resize_lock = QCheckBox("Mantieni proporzioni (auto altezza)")
        self.resize_lock.setChecked(True)
        resize_layout.addRow(self.resize_lock)

        root.addWidget(resize_group)

        # --- Output ---
        out_group = QGroupBox("Output")
        out_layout = QFormLayout(out_group)

        self.format_combo = QComboBox()
        self.format_combo.addItems(["webp", "png", "jpg"])
        out_layout.addRow("Formato:", self.format_combo)

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
        out_layout.addRow("Qualità:", q_widget)

        self.suffix_edit = QLineEdit()
        self.suffix_edit.setPlaceholderText("(nessuno)")
        out_layout.addRow("Suffisso nome:", self.suffix_edit)

        # --- Modalità in-place (sovrascrivi originali) ---
        self.inplace_check = QCheckBox(
            "Sovrascrivi originali (in-place)\n"
            "Mantiene nome e posizione — ideale per Ren'Py")
        self.inplace_check.setToolTip(
            "Salta ogni immagine processata nello stesso path dell'originale,\n"
            "mantenendo nome ed estensione. Il codice del gioco continua a\n"
            "funzionare senza modifiche. Crea un backup prima di sovrascrivere.")
        out_layout.addRow(self.inplace_check)

        self.backup_label = QLabel(
            "Backup automatico: ZIP in game/imageforge_backup.zip\n"
            "(Ren'Py non legge i .zip, sicuro)")
        self.backup_label.setStyleSheet(
            "QLabel{color:#b89878;font-size:10px;padding:2px;}")
        out_layout.addRow(self.backup_label)

        # Destinazione (disabilitata se in-place)
        self.outdir_edit = QLineEdit()
        self.outdir_edit.setPlaceholderText("Cartella di destinazione...")
        browse_btn = QPushButton("Sfoglia...")
        browse_btn.clicked.connect(self._pick_outdir)
        oh = QHBoxLayout()
        oh.setContentsMargins(0, 0, 0, 0)
        oh.addWidget(self.outdir_edit)
        oh.addWidget(browse_btn)
        oh_widget = QWidget()
        oh_widget.setLayout(oh)
        self.outdir_row = oh_widget
        out_layout.addRow("Destinazione:", oh_widget)

        root.addWidget(out_group)

        # --- Upscaling AI ---
        up_group = QGroupBox("Upscaling AI (Real-ESRGAN)")
        up_layout = QFormLayout(up_group)

        self.upscale_check = QCheckBox("Abilita upscaling dopo crop")
        up_layout.addRow(self.upscale_check)

        self.scale_combo = QComboBox()
        for s in VALID_SCALES:
            self.scale_combo.addItem(f"x{s}", s)
        up_layout.addRow("Scala:", self.scale_combo)

        self.model_combo = QComboBox()
        for mid, desc in MODELS.items():
            self.model_combo.addItem(f"{mid} — {desc}", mid)
        up_layout.addRow("Modello:", self.model_combo)

        self.tile_spin = QSpinBox()
        self.tile_spin.setRange(0, 4096)
        self.tile_spin.setValue(0)
        self.tile_spin.setSpecialValueText("auto")
        up_layout.addRow("Tile size:", self.tile_spin)

        self.tta_check = QCheckBox("TTA (più qualità, più lento)")
        up_layout.addRow(self.tta_check)

        self.upscale_status = QLabel(status_message())
        self.upscale_status.setWordWrap(True)
        self.upscale_status.setStyleSheet("color: #b89878; font-size: 10px;")
        up_layout.addRow(self.upscale_status)

        root.addWidget(up_group)
        root.addStretch()

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
        """Configura crop+upscale+resize per un target comune."""
        # Blocca i signal per aggiornare tutto in un colpo solo
        widgets = [self.aspect_combo, self.resize_check, self.resize_w,
                   self.resize_h, self.upscale_check, self.scale_combo]
        for w in widgets:
            w.blockSignals(True)

        # Crop 16:9 center
        self.aspect_combo.setCurrentText("16:9")
        # anchor center (già default)

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

        # Resize finale al target
        self.resize_check.setChecked(True)
        self.resize_w.setValue(target[0])
        self.resize_h.setValue(target[1])

        # Upscale AI
        self.upscale_check.setChecked(True)
        idx = self.scale_combo.findData(scale)
        if idx >= 0:
            self.scale_combo.setCurrentIndex(idx)

        for w in widgets:
            w.blockSignals(False)

        # Aggiorna stati abilitato/disabilitato + emetti changed
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
            # aggiorna altezza in base all'aspect del crop corrente
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
        """Quando in-place è attivo, disabilita destinazione e suffisso."""
        self.outdir_row.setEnabled(not on)
        self.suffix_edit.setEnabled(not on)
        self.format_combo.setEnabled(not on)  # in-place mantiene estensione originale
        self.changed.emit()

    def _pick_outdir(self):
        d = QFileDialog.getExistingDirectory(self, "Cartella di destinazione")
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
            # specialValueText -> minimum value means "auto"
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
            output_format="png",  # intermedio di alta qualità
            tta=self.tta_check.isChecked(),
        )

    def output_dir(self) -> str:
        return self.outdir_edit.text().strip()

    def suffix(self) -> str:
        return self.suffix_edit.text().strip()
