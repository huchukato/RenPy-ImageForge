"""Dialog per l'apertura di un gioco Ren'Py.

Pipeline UI:
1. Utente seleziona .app o cartella
2. Estrazione .rpa + decompilazione .rpyc (con progress)
3. Scansione .rpy + lettura risoluzioni (con progress)
4. Tabella con tutte le immagini di gioco, filtri per risoluzione
5. Selezione + "Aggiungi alla lista batch"
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


# --------------------------------------------------------------------------- #
# Worker per estrazione + scansione in background
# --------------------------------------------------------------------------- #

class RenpyScanWorker(QThread):
    """Esegue estrazione .rpa, decompilazione .rpyc e scansione in background."""

    phase = Signal(str)           # nome fase corrente
    progress = Signal(int, int)   # current, total
    log = Signal(str)
    finished_images = Signal(list)  # list[GameImage]
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
            self.log.emit(f"Game dir: {game_dir}")

            if not game_dir.is_dir():
                self.error.emit(f"Directory game non trovata: {game_dir}")
                return

            # Fase 1: estrazione .rpa
            self.phase.emit("Estrazione archivi .rpa")
            if not extract_rpa_files(game_dir, log=self.log.emit,
                                     progress=lambda c, t: self.progress.emit(c, t)):
                self.error.emit("Estrazione .rpa fallita")
                return

            if self._cancel:
                self.log.emit("Annullato")
                return

            # Fase 2: decompilazione .rpyc
            self.phase.emit("Decompilazione .rpyc")
            if not decompile_rpyc_files(game_dir, log=self.log.emit,
                                        progress=lambda c, t: self.progress.emit(c, t)):
                self.error.emit("Decompilazione .rpyc fallita")
                return

            if self._cancel:
                self.log.emit("Annullato")
                return

            # Fase 3: scansione
            self.phase.emit("Scansione immagini")
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
# Dialog principale
# --------------------------------------------------------------------------- #

class RenpyDialog(QDialog):
    """Dialog per aprire un gioco Ren'Py, scansionarlo e selezionare immagini."""

    images_selected = Signal(list)  # list[str] path selezionati

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("RenPy ImageForge — Apri gioco Ren'Py")
        self.resize(1000, 700)
        self._worker: RenpyScanWorker | None = None
        self._images: list[GameImage] = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # --- Barra superiore: selezione gioco ---
        top = QGroupBox("Gioco Ren'Py")
        top_layout = QHBoxLayout(top)

        self.path_label = QLabel("Nessun gioco selezionato")
        self.path_label.setStyleSheet("color: #8a7a64;")
        browse_btn = QPushButton("Sfoglia...")
        browse_btn.clicked.connect(self._pick_game)
        self.scan_btn = QPushButton("Scansiona")
        self.scan_btn.setEnabled(False)
        self.scan_btn.clicked.connect(self._start_scan)

        top_layout.addWidget(self.path_label, 1)
        top_layout.addWidget(browse_btn)
        top_layout.addWidget(self.scan_btn)
        layout.addWidget(top)

        # --- Target full HD configurabile ---
        target_group = QGroupBox("Target risoluzione")
        target_layout = QFormLayout(target_group)
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
        target_layout.addRow("Considera 'full HD':", th)
        layout.addWidget(target_group)

        # --- Stato UnRen Tools ---
        if not unren_tools_available():
            warn = QLabel("⚠ UnRen Tools non trovati. Imposta UNREN_TOOLS_DIR.")
            warn.setStyleSheet("color: #c47040; font-size: 11px;")
            layout.addWidget(warn)

        # --- Progress ---
        self.phase_label = QLabel("")
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setVisible(False)
        layout.addWidget(self.phase_label)
        layout.addWidget(self.progress)

        # --- Log compatto ---
        self.log_label = QLabel("")
        self.log_label.setStyleSheet("color: #9a8a70; font-size: 10px;")
        layout.addWidget(self.log_label)

        # --- Tabella immagini ---
        table_group = QGroupBox("Immagini di gioco trovate")
        table_layout = QVBoxLayout(table_group)

        # Filtri
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filtra:"))
        self.filter_combo = QComboBox()
        self.filter_combo.addItems([
            "Da elaborare (sotto full-HD, no UI)",
            "Tutte",
            "Solo non-full-HD (sotto)",
            "Solo non-full-HD (sopra)",
            "Solo non-full-HD (tutte)",
            "Solo full HD",
            "Solo UI/bottoni",
            "Risoluzione sconosciuta",
        ])
        self.filter_combo.currentIndexChanged.connect(self._apply_filter)
        filter_row.addWidget(self.filter_combo)

        self.select_visible_btn = QPushButton("Seleziona visibili")
        self.select_visible_btn.clicked.connect(self._select_visible)
        filter_row.addWidget(self.select_visible_btn)

        self.count_label = QLabel("0 immagini")
        self.count_label.setStyleSheet("color: #8a7a64;")
        filter_row.addWidget(self.count_label)
        filter_row.addStretch()
        table_layout.addLayout(filter_row)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["", "Nome", "File", "Risoluzione", "Stato", "Ref.", "Usi"])
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
        layout.addWidget(table_group, 1)

        # --- Bottoni fondo ---
        bottom = QHBoxLayout()
        self.add_btn = QPushButton("Aggiungi selezionate alla lista batch")
        self.add_btn.setStyleSheet(
            "QPushButton{font-weight:bold;padding:6px;"
            "background:#b8865c;color:#1a1815;border:none;border-radius:4px;}"
            "QPushButton:hover{background:#c8966c;}")
        self.add_btn.clicked.connect(self._add_selected)
        close_btn = QPushButton("Chiudi")
        close_btn.clicked.connect(self.reject)
        bottom.addStretch()
        bottom.addWidget(self.add_btn)
        bottom.addWidget(close_btn)
        layout.addLayout(bottom)

    # --- Selezione gioco ---
    def _pick_game(self):
        """Apre un dialog che permette di selezionare sia .app che cartelle.

        Su macOS i .app sono bundle (directory) ma il dialog nativo non li
        fa selezionare come cartelle. Usiamo getOpenFileName con filtro .app
        per i bundle, e il dialog non-nativo per le cartelle.
        """
        # Prima prova con getOpenFileName filtrando .app
        path, _ = QFileDialog.getOpenFileName(
            self, "Seleziona il gioco Ren'Py (.app o cartella)",
            "", "Applicazione Mac (*.app);;Tutti i file (*)")
        if path:
            self.path_label.setText(path)
            self.path_label.setStyleSheet("color: #d8c8b0;")
            self.scan_btn.setEnabled(True)
            return

        # Se l'utente annulla o vuole una cartella, riprova con directory
        # non-nativa (tratta i .app come directory normali)
        dlg = QFileDialog(self, "Oppure seleziona una cartella")
        dlg.setFileMode(QFileDialog.Directory)
        dlg.setOption(QFileDialog.DontUseNativeDialog, True)
        if dlg.exec():
            paths = dlg.selectedFiles()
            if paths:
                self.path_label.setText(paths[0])
                self.path_label.setStyleSheet("color: #d8c8b0;")
                self.scan_btn.setEnabled(True)

    # --- Avvio scansione ---
    def _start_scan(self):
        game_path = self.path_label.text()
        if not game_path:
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
        self.phase_label.setText(f"Fase: {name}")

    def _on_progress(self, current, total):
        self.progress.setRange(0, max(total, 1))
        self.progress.setValue(current)

    def _on_log(self, msg):
        self.log_label.setText(msg)

    def _on_error(self, msg):
        self.progress.setVisible(False)
        self.scan_btn.setEnabled(True)
        self._cleanup_worker()
        QMessageBox.critical(self, "Errore", msg)

    def _on_finished(self, images: list[GameImage]):
        self.progress.setVisible(False)
        self.phase_label.setText("Scansione completata")
        self.scan_btn.setEnabled(True)
        self._images = images
        self._populate_table()
        self._cleanup_worker()

    def _cleanup_worker(self):
        """Scollega i signal e programma la deleteLater del worker."""
        if self._worker is not None:
            try:
                self._worker.phase.disconnect()
                self._worker.progress.disconnect()
                self._worker.log.disconnect()
                self._worker.finished_images.disconnect()
                self._worker.error.disconnect()
            except RuntimeError:
                pass  # signal già disconnessi
            self._worker.deleteLater()
            self._worker = None

    def _stop_worker(self):
        """Ferma il worker se in esecuzione (bloccante, max 5s)."""
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

    # --- Tabella ---
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

            ref_item = QTableWidgetItem("sì" if img.is_referenced else "no")
            if not img.is_referenced:
                ref_item.setForeground(Qt.gray)
            self.table.setItem(row, 5, ref_item)

            self.table.setItem(row, 6, QTableWidgetItem(str(img.used_in_count)))

        self._apply_filter()
        n_visible = sum(1 for r in range(self.table.rowCount())
                        if not self.table.isRowHidden(r))
        self.count_label.setText(
            f"{n_visible} visibili / {len(self._images)} totali")

    def _apply_filter(self):
        filt = self.filter_combo.currentText()
        target_w = self.target_w.value()
        target_h = self.target_h.value()
        for row in range(self.table.rowCount()):
            img = self._images[row]
            show = True
            if filt == "Da elaborare (sotto full-HD, no UI)":
                # Sotto full-HD: vanno upscalate. Esclude UI, sopra full-HD e sconosciute
                show = (img.width > 0 and not img.is_full_hd
                        and not img.is_ui_element
                        and img.width <= target_w and img.height <= target_h)
            elif filt == "Solo non-full-HD (sotto)":
                show = (img.width > 0 and not img.is_full_hd
                        and img.width <= target_w and img.height <= target_h)
            elif filt == "Solo non-full-HD (sopra)":
                show = (img.width > target_w or img.height > target_h)
            elif filt == "Solo non-full-HD (tutte)":
                show = (img.width > 0 and not img.is_full_hd)
            elif filt == "Solo full HD":
                show = img.is_full_hd
            elif filt == "Solo UI/bottoni":
                show = img.is_ui_element
            elif filt == "Risoluzione sconosciuta":
                show = (img.width == 0)
            self.table.setRowHidden(row, not show)

        visible = sum(1 for r in range(self.table.rowCount())
                      if not self.table.isRowHidden(r))
        self.count_label.setText(
            f"{visible} visibili / {len(self._images)} totali")

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
            QMessageBox.information(self, "Nessuna selezione",
                                    "Seleziona almeno un'immagine.")
            return
        self.images_selected.emit(selected)
        self.log_label.setText(f"Aggiunte {len(selected)} immagini alla lista batch.")
