"""Dialog for opening a Ren'Py game.

UI pipeline:
1. User selects .app or folder
2. .rpa extraction + .rpyc decompilation (with progress)
3. .rpy scan + resolution reading (with progress)
4. Table with all game images, resolution filters
5. Selection + "Add to batch list"
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFileDialog,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar,
    QComboBox, QCheckBox, QGroupBox, QAbstractItemView, QMessageBox,
    QSpinBox, QFormLayout,
)

from ..renpy import (
    find_game_dir, extract_rpa_files, decompile_rpyc_files,
    scan_game_images, GameImage, unren_tools_available,
)
from ..i18n import tr


# --------------------------------------------------------------------------- #
# Worker for extraction + scanning in background
# --------------------------------------------------------------------------- #

class RenpyScanWorker(QThread):
    """Runs .rpa extraction, .rpyc decompilation and scanning in background."""

    phase = Signal(str)
    progress = Signal(int, int)
    log = Signal(str)
    finished_images = Signal(list)
    error = Signal(str)

    def __init__(self, game_path: str, full_hd_target: tuple[int, int]):
        super().__init__()
        self.game_path = game_path
        self.full_hd_target = full_hd_target
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            game_dir = find_game_dir(self.game_path)
            self.log.emit(tr("phase_game_dir", path=game_dir))

            if not game_dir.is_dir():
                self.error.emit(tr("phase_game_not_found", path=game_dir))
                return

            self.phase.emit(tr("phase_extract_rpa"))
            if not extract_rpa_files(game_dir, log=self.log.emit,
                                     progress=lambda c, t: self.progress.emit(c, t)):
                self.error.emit(tr("phase_extract_failed"))
                return

            if self._cancel:
                self.log.emit(tr("phase_cancelled"))
                return

            self.phase.emit(tr("phase_decompile_rpyc"))
            if not decompile_rpyc_files(game_dir, log=self.log.emit,
                                        progress=lambda c, t: self.progress.emit(c, t)):
                self.error.emit(tr("phase_decompile_failed"))
                return

            if self._cancel:
                self.log.emit(tr("phase_cancelled"))
                return

            self.phase.emit(tr("phase_scan_images"))
            images = scan_game_images(
                game_dir,
                log=self.log.emit,
                progress=lambda c, t, phase: (
                    self.phase.emit(phase),
                    self.progress.emit(c, t),
                ),
                full_hd_target=self.full_hd_target,
            )
            self.finished_images.emit(images)
        except Exception as e:
            self.error.emit(str(e))


# --------------------------------------------------------------------------- #
# Main dialog
# --------------------------------------------------------------------------- #

class RenpyDialog(QDialog):
    """Dialog to open a Ren'Py game, scan it and select images."""

    images_selected = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("renpy_dialog_title"))
        self.resize(1000, 700)
        self._worker: RenpyScanWorker | None = None
        self._images: list[GameImage] = []
        self._build_ui()
        self.retranslate_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # --- Top bar: game selection ---
        self.top_group = QGroupBox()
        top_layout = QHBoxLayout(self.top_group)

        self.path_label = QLabel()
        self.path_label.setStyleSheet("color: #8a7a64;")
        self.browse_btn = QPushButton()
        self.browse_btn.clicked.connect(self._pick_game)
        self.scan_btn = QPushButton()
        self.scan_btn.setEnabled(False)
        self.scan_btn.clicked.connect(self._start_scan)

        top_layout.addWidget(self.path_label, 1)
        top_layout.addWidget(self.browse_btn)
        top_layout.addWidget(self.scan_btn)
        layout.addWidget(self.top_group)

        # --- Full HD target ---
        self.target_group = QGroupBox()
        target_layout = QFormLayout(self.target_group)
        self.target_w = QSpinBox()
        self.target_w.setRange(1, 32767)
        self.target_w.setValue(1920)
        self.target_h = QSpinBox()
        self.target_h.setRange(1, 32767)
        self.target_h.setValue(1080)
        th = QHBoxLayout()
        th.addWidget(self.target_w)
        th.addWidget(QLabel("x"))
        th.addWidget(self.target_h)
        th.addStretch()
        self._target_label = QLabel()
        target_layout.addRow(self._target_label, th)
        layout.addWidget(self.target_group)

        # --- UnRen Tools status ---
        if not unren_tools_available():
            self.unren_warn = QLabel(tr("renpy_unren_warn"))
            self.unren_warn.setStyleSheet("color: #c47040; font-size: 11px;")
            layout.addWidget(self.unren_warn)

        # --- Progress ---
        self.phase_label = QLabel("")
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setVisible(False)
        layout.addWidget(self.phase_label)
        layout.addWidget(self.progress)

        # --- Compact log ---
        self.log_label = QLabel("")
        self.log_label.setStyleSheet("color: #9a8a70; font-size: 10px;")
        layout.addWidget(self.log_label)

        # --- Images table ---
        self.table_group = QGroupBox()
        table_layout = QVBoxLayout(self.table_group)

        # Filters
        filter_row = QHBoxLayout()
        self._filter_label = QLabel()
        filter_row.addWidget(self._filter_label)
        self.filter_combo = QComboBox()
        self.filter_combo.currentIndexChanged.connect(self._apply_filter)
        filter_row.addWidget(self.filter_combo)

        self.select_visible_btn = QPushButton()
        self.select_visible_btn.clicked.connect(self._select_visible)
        filter_row.addWidget(self.select_visible_btn)

        self.count_label = QLabel()
        self.count_label.setStyleSheet("color: #8a7a64;")
        filter_row.addWidget(self.count_label)
        filter_row.addStretch()
        table_layout.addLayout(filter_row)

        self.table = QTableWidget(0, 7)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.horizontalHeader().resizeSection(0, 30)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        table_layout.addWidget(self.table)
        layout.addWidget(self.table_group, 1)

        # --- Bottom buttons ---
        bottom = QHBoxLayout()
        self.add_btn = QPushButton()
        self.add_btn.setStyleSheet(
            "QPushButton{font-weight:bold;padding:6px;"
            "background:#b8865c;color:#1a1815;border:none;border-radius:4px;}"
            "QPushButton:hover{background:#c8966c;}")
        self.add_btn.clicked.connect(self._add_selected)
        self.close_btn = QPushButton()
        self.close_btn.clicked.connect(self.reject)
        bottom.addStretch()
        bottom.addWidget(self.add_btn)
        bottom.addWidget(self.close_btn)
        layout.addLayout(bottom)

    def retranslate_ui(self):
        """Update all translatable strings."""
        self.setWindowTitle(tr("renpy_dialog_title"))
        self.top_group.setTitle(tr("renpy_game_group"))
        self.path_label.setText(tr("renpy_no_game"))
        self.browse_btn.setText(tr("renpy_browse"))
        self.scan_btn.setText(tr("renpy_scan"))
        self.target_group.setTitle(tr("renpy_target_group"))
        self._target_label.setText(tr("renpy_consider_fullhd"))

        # Filter combo: rebuild items
        cur_idx = self.filter_combo.currentIndex()
        self.filter_combo.blockSignals(True)
        self.filter_combo.clear()
        self.filter_combo.addItems([
            tr("renpy_filter_process"),
            tr("renpy_filter_all"),
            tr("renpy_filter_below"),
            tr("renpy_filter_above"),
            tr("renpy_filter_all_nonhd"),
            tr("renpy_filter_fullhd"),
            tr("renpy_filter_ui"),
            tr("renpy_filter_unknown"),
        ])
        self.filter_combo.setCurrentIndex(max(cur_idx, 0))
        self.filter_combo.blockSignals(False)

        self._filter_label.setText(tr("renpy_filter"))
        self.select_visible_btn.setText(tr("renpy_select_visible"))
        self.count_label.setText(tr("renpy_count", n=0))
        self.table_group.setTitle(tr("renpy_images_group"))
        self.table.setHorizontalHeaderLabels([
            "", tr("renpy_col_name"), tr("renpy_col_file"),
            tr("renpy_col_res"), tr("renpy_col_status"),
            tr("renpy_col_ref"), tr("renpy_col_uses"),
        ])
        self.add_btn.setText(tr("renpy_add_selected"))
        self.close_btn.setText(tr("renpy_close"))

        # Re-populate table if images exist
        if self._images:
            self._populate_table()

    # --- Game selection ---
    def _pick_game(self):
        path, _ = QFileDialog.getOpenFileName(
            self, tr("renpy_select_title"), "", tr("renpy_select_filter"))
        if path:
            self.path_label.setText(path)
            self.path_label.setStyleSheet("color: #d8c8b0;")
            self.scan_btn.setEnabled(True)
            return

        dlg = QFileDialog(self, tr("renpy_or_folder"))
        dlg.setFileMode(QFileDialog.Directory)
        dlg.setOption(QFileDialog.DontUseNativeDialog, True)
        if dlg.exec():
            paths = dlg.selectedFiles()
            if paths:
                self.path_label.setText(paths[0])
                self.path_label.setStyleSheet("color: #d8c8b0;")
                self.scan_btn.setEnabled(True)

    # --- Scan start ---
    def _start_scan(self):
        game_path = self.path_label.text()
        if not game_path or game_path == tr("renpy_no_game"):
            return

        target = (self.target_w.value(), self.target_h.value())
        self._worker = RenpyScanWorker(game_path, target)
        self._worker.phase.connect(self._on_phase)
        self._worker.progress.connect(self._on_progress)
        self._worker.log.connect(self._on_log)
        self._worker.finished_images.connect(self._on_finished)
        self._worker.error.connect(self._on_error)

        self.progress.setVisible(True)
        self.scan_btn.setEnabled(False)
        self.table.setRowCount(0)
        self._worker.start()

    def _on_phase(self, name):
        self.phase_label.setText(tr("renpy_phase", name=name))

    def _on_progress(self, current, total):
        self.progress.setRange(0, max(total, 1))
        self.progress.setValue(current)

    def _on_log(self, msg):
        self.log_label.setText(msg)

    def _on_error(self, msg):
        self.progress.setVisible(False)
        self.scan_btn.setEnabled(True)
        self._cleanup_worker()
        QMessageBox.critical(self, tr("renpy_error"), msg)

    def _on_finished(self, images: list[GameImage]):
        self.progress.setVisible(False)
        self.phase_label.setText(tr("renpy_scan_done"))
        self.scan_btn.setEnabled(True)
        self._images = images
        self._populate_table()
        self._cleanup_worker()

    def _cleanup_worker(self):
        if self._worker is not None:
            try:
                self._worker.phase.disconnect()
                self._worker.progress.disconnect()
                self._worker.log.disconnect()
                self._worker.finished_images.disconnect()
                self._worker.error.disconnect()
            except RuntimeError:
                pass
            self._worker.deleteLater()
            self._worker = None

    def _stop_worker(self):
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
            self._worker.quit()
            self._worker.wait(5000)
        self._cleanup_worker()

    def closeEvent(self, event):
        self._stop_worker()
        super().closeEvent(event)

    def reject(self):
        self._stop_worker()
        super().reject()

    # --- Table ---
    def _populate_table(self):
        self.table.setRowCount(0)
        for img in self._images:
            row = self.table.rowCount()
            self.table.insertRow(row)

            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            chk.setCheckState(Qt.Unchecked)
            self.table.setItem(row, 0, chk)

            self.table.setItem(row, 1, QTableWidgetItem(img.name))
            self.table.setItem(row, 2, QTableWidgetItem(str(img.file_path)))
            self.table.setItem(row, 3, QTableWidgetItem(img.resolution_str))

            status_item = QTableWidgetItem(img.status)
            if img.is_full_hd:
                status_item.setForeground(Qt.darkGreen)
            elif img.width > 1920 or img.height > 1080:
                status_item.setForeground(Qt.yellow)
            elif img.width > 0:
                status_item.setForeground(Qt.red)
            self.table.setItem(row, 4, status_item)

            ref_item = QTableWidgetItem(tr("renpy_ref_yes") if img.is_referenced else tr("renpy_ref_no"))
            if not img.is_referenced:
                ref_item.setForeground(Qt.gray)
            self.table.setItem(row, 5, ref_item)

            self.table.setItem(row, 6, QTableWidgetItem(str(img.used_in_count)))

        self._apply_filter()
        n_visible = sum(1 for r in range(self.table.rowCount())
                        if not self.table.isRowHidden(r))
        self.count_label.setText(
            tr("renpy_visible_total", visible=n_visible, total=len(self._images)))

    def _apply_filter(self):
        filt_idx = self.filter_combo.currentIndex()
        target_w = self.target_w.value()
        target_h = self.target_h.value()
        for row in range(self.table.rowCount()):
            img = self._images[row]
            show = True
            if filt_idx == 0:  # To process (below full-HD, no UI)
                show = (img.width > 0 and not img.is_full_hd
                        and not img.is_ui_element
                        and img.width <= target_w and img.height <= target_h)
            elif filt_idx == 1:  # All
                show = True
            elif filt_idx == 2:  # Only non-full-HD (below)
                show = (img.width > 0 and not img.is_full_hd
                        and img.width <= target_w and img.height <= target_h)
            elif filt_idx == 3:  # Only non-full-HD (above)
                show = (img.width > target_w or img.height > target_h)
            elif filt_idx == 4:  # Only non-full-HD (all)
                show = (img.width > 0 and not img.is_full_hd)
            elif filt_idx == 5:  # Only full HD
                show = img.is_full_hd
            elif filt_idx == 6:  # Only UI/buttons
                show = img.is_ui_element
            elif filt_idx == 7:  # Unknown resolution
                show = (img.width == 0)
            self.table.setRowHidden(row, not show)

        visible = sum(1 for r in range(self.table.rowCount())
                      if not self.table.isRowHidden(r))
        self.count_label.setText(
            tr("renpy_visible_total", visible=visible, total=len(self._images)))

    def _select_visible(self):
        for row in range(self.table.rowCount()):
            if not self.table.isRowHidden(row):
                self.table.item(row, 0).setCheckState(Qt.Checked)

    def _add_selected(self):
        selected = []
        for row in range(self.table.rowCount()):
            if self.table.item(row, 0).checkState() == Qt.Checked:
                selected.append(str(self._images[row].file_path))
        if not selected:
            QMessageBox.information(self, tr("renpy_no_selection"),
                                    tr("renpy_no_selection_msg"))
            return
        self.images_selected.emit(selected)
        self.log_label.setText(tr("renpy_added_n", n=len(selected)))
