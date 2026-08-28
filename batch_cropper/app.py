"""Finestra principale di Batch Cropper."""

from __future__ import annotations

import os
import platform
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QThread, QUrl
from PySide6.QtGui import QAction, QDragEnterEvent, QDropEvent, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QSplitter,
    QListWidget, QListWidgetItem, QPushButton, QProgressBar, QPlainTextEdit,
    QLabel, QFileDialog, QMessageBox, QAbstractItemView, QStatusBar,
)

from .cropper import is_supported_input, SUPPORTED_INPUT_EXT
from .workers import BatchWorker, BatchJob
from .widgets import CropPreviewWidget
from .widgets.settings_panel import SettingsPanel
from .widgets.renpy_dialog import RenpyDialog


class FileListWidget(QListWidget):
    """QListWidget che accetta drag & drop di file immagine."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setAlternatingRowColors(True)

    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            e.ignore()

    def dragMoveEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            e.ignore()

    def dropEvent(self, e: QDropEvent):
        if not e.mimeData().hasUrls():
            e.ignore()
            return
        paths = []
        for u in e.mimeData().urls():
            p = u.toLocalFile()
            if os.path.isdir(p):
                for f in sorted(os.listdir(p)):
                    fp = os.path.join(p, f)
                    if os.path.isfile(fp) and is_supported_input(fp):
                        paths.append(fp)
            elif os.path.isfile(p) and is_supported_input(p):
                paths.append(p)
        for p in paths:
            self.add_path(p)
        e.acceptProposedAction()

    def add_path(self, path: str):
        # evita duplicati
        for i in range(self.count()):
            if self.item(i).data(Qt.UserRole) == path:
                return
        item = QListWidgetItem(os.path.basename(path))
        item.setData(Qt.UserRole, path)
        item.setToolTip(path)
        self.addItem(item)

    def get_paths(self) -> list[str]:
        return [self.item(i).data(Qt.UserRole) for i in range(self.count())]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RenPy ImageForge")
        self.resize(1280, 820)
        self._worker = None
        self._thread = None
        # Icona della finestra
        icon_path = Path(__file__).resolve().parent.parent / "img" / "icon.iconset" / "icon_256x256.png"
        if icon_path.is_file():
            self.setWindowIcon(QIcon(str(icon_path)))
        self._build_ui()
        self._build_menu()
        self._refresh_preview()
        self.statusBar().showMessage("Pronto. Trascina immagini o usa File > Aggiungi file.")

    # ---- UI ----
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(6)

        splitter = QSplitter(Qt.Horizontal)

        # Colonna sinistra: lista file
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(4)
        ll.addWidget(QLabel("Immagini in input:"))
        self.file_list = FileListWidget()
        self.file_list.currentRowChanged.connect(self._on_file_selected)
        ll.addWidget(self.file_list, 1)
        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)
        self.add_btn = QPushButton("+ File")
        self.add_btn.clicked.connect(self._add_files)
        self.addfolder_btn = QPushButton("+ Cartella")
        self.addfolder_btn.clicked.connect(self._add_folder)
        self.renpy_btn = QPushButton("Ren'Py")
        self.renpy_btn.setToolTip("Apri un gioco Ren'Py (.app o cartella), "
                                  "estrailo e scansiona le immagini di gioco")
        self.renpy_btn.clicked.connect(self._open_renpy)
        self.remove_btn = QPushButton("- Rimuovi")
        self.remove_btn.clicked.connect(self._remove_selected)
        self.clear_btn = QPushButton("Pulisci")
        self.clear_btn.clicked.connect(self._clear_all)
        for b in (self.add_btn, self.addfolder_btn, self.renpy_btn,
                  self.remove_btn, self.clear_btn):
            btn_row.addWidget(b)
        ll.addLayout(btn_row)
        splitter.addWidget(left)

        # Colonna centro: anteprima + log
        center = QWidget()
        cl = QVBoxLayout(center)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(6)
        cl.addWidget(QLabel("Anteprima crop:"))
        self.preview = CropPreviewWidget()
        cl.addWidget(self.preview, 1)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(160)
        self.log.setStyleSheet("QPlainTextEdit{background:#1a1815;color:#d8c8b0;}")
        cl.addWidget(self.log)
        splitter.addWidget(center)

        # Colonna destra: impostazioni
        self.settings_panel = SettingsPanel()
        self.settings_panel.changed.connect(self._refresh_preview)
        splitter.addWidget(self.settings_panel)

        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 2)
        splitter.setSizes([300, 560, 360])
        outer.addWidget(splitter, 1)

        # Barra azione + progresso
        action_row = QHBoxLayout()
        self.process_btn = QPushButton("▶  Avvia elaborazione")
        self.process_btn.setStyleSheet(
            "QPushButton{font-weight:bold;padding:6px 14px;"
            "background:#b8865c;color:#1a1815;border:none;border-radius:4px;}"
            "QPushButton:hover{background:#c8966c;}"
            "QPushButton:disabled{background:#3a342c;color:#6a5e4e;}")
        self.process_btn.clicked.connect(self._start_processing)
        self.cancel_btn = QPushButton("Annulla")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel_processing)

        # Panic button: ripristina backup
        self.restore_btn = QPushButton("⟲ Restore Backup")
        self.restore_btn.setToolTip(
            "Ripristina le immagini originali dal backup ZIP\n"
            "(game/imageforge_backup.zip)")
        self.restore_btn.setStyleSheet(
            "QPushButton{padding:6px 10px;"
            "background:#5a2a2a;color:#e8d0d0;border:1px solid #8a3a3a;border-radius:4px;}"
            "QPushButton:hover{background:#6a3a3a;}"
            "QPushButton:disabled{background:#3a342c;color:#6a5e4e;border:none;}")
        self.restore_btn.clicked.connect(self._restore_backup)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress_label = QLabel("0 / 0")
        action_row.addWidget(self.process_btn)
        action_row.addWidget(self.cancel_btn)
        action_row.addWidget(self.restore_btn)
        action_row.addWidget(self.progress, 1)
        action_row.addWidget(self.progress_label)
        outer.addLayout(action_row)

    def _build_menu(self):
        mb = self.menuBar()
        file_menu = mb.addMenu("File")
        a_add = QAction("Aggiungi file...", self)
        a_add.setShortcut("Ctrl+O")
        a_add.triggered.connect(self._add_files)
        file_menu.addAction(a_add)
        a_addf = QAction("Aggiungi cartella...", self)
        a_addf.setShortcut("Ctrl+Shift+O")
        a_addf.triggered.connect(self._add_folder)
        file_menu.addAction(a_addf)
        file_menu.addSeparator()
        a_renpy = QAction("Apri gioco Ren'Py...", self)
        a_renpy.setShortcut("Ctrl+R")
        a_renpy.triggered.connect(self._open_renpy)
        file_menu.addAction(a_renpy)
        file_menu.addSeparator()
        a_clear = QAction("Pulisci lista", self)
        a_clear.triggered.connect(self._clear_all)
        file_menu.addAction(a_clear)
        file_menu.addSeparator()
        a_quit = QAction("Esci", self)
        a_quit.setShortcut("Ctrl+Q")
        a_quit.triggered.connect(self.close)
        file_menu.addAction(a_quit)

        help_menu = mb.addMenu("Aiuto")
        a_about = QAction("Informazioni...", self)
        a_about.triggered.connect(self._about)
        help_menu.addAction(a_about)

    # ---- File list ops ----
    def _add_files(self):
        exts = " ".join(f"*{e}" for e in SUPPORTED_INPUT_EXT)
        files, _ = QFileDialog.getOpenFileNames(
            self, "Seleziona immagini", "", f"Immagini ({exts})")
        for f in files:
            self.file_list.add_path(f)
        self._update_count()

    def _add_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Seleziona cartella")
        if not d:
            return
        added = 0
        for f in sorted(os.listdir(d)):
            fp = os.path.join(d, f)
            if os.path.isfile(fp) and is_supported_input(fp):
                self.file_list.add_path(fp)
                added += 1
        self._log(f"Aggiunte {added} immagini da {d}")
        self._update_count()

    def _remove_selected(self):
        for item in self.file_list.selectedItems():
            self.file_list.takeItem(self.file_list.row(item))
        self._update_count()
        self._refresh_preview()

    def _clear_all(self):
        self.file_list.clear()
        self.preview.clear()
        self._update_count()

    def _open_renpy(self):
        """Apre il dialog Ren'Py per scansionare un gioco e aggiungere immagini."""
        dlg = RenpyDialog(self)
        dlg.images_selected.connect(self._on_renpy_images_selected)
        dlg.exec()

    def _on_renpy_images_selected(self, paths: list):
        """Riceve le immagini selezionate dal dialog Ren'Py."""
        added = 0
        for p in paths:
            if is_supported_input(p):
                self.file_list.add_path(p)
                added += 1
        self._log(f"Aggiunte {added} immagini dal gioco Ren'Py")
        self._update_count()
        # Seleziona la prima per mostrare l'anteprima
        if self.file_list.count() > 0:
            self.file_list.setCurrentRow(0)

    def _update_count(self):
        n = self.file_list.count()
        self.progress_label.setText(f"0 / {n}")
        self.progress.setRange(0, max(n, 1))
        self.progress.setValue(0)

    def _on_file_selected(self, row):
        if row < 0:
            self.preview.clear()
            return
        path = self.file_list.item(row).data(Qt.UserRole)
        self.preview.set_image(path)
        self._refresh_preview()

    # ---- Preview ----
    def _refresh_preview(self):
        cs = self.settings_panel.crop_settings()
        us = self.settings_panel.upscale_settings()
        self.preview.update_overlay(
            cs.aspect_ratio, cs.anchor, cs.resize_after,
            upscale_enabled=us.enabled, upscale_scale=us.scale,
        )

    # ---- Logging ----
    def _log(self, msg: str):
        self.log.appendPlainText(msg)

    # ---- Processing ----
    def _start_processing(self):
        paths = self.file_list.get_paths()
        if not paths:
            QMessageBox.information(self, "Nessuna immagine",
                                    "Aggiungi almeno un'immagine alla lista.")
            return

        in_place = self.settings_panel.in_place()
        out_dir = self.settings_panel.output_dir()

        if in_place:
            # In-place: backup automatico in ZIP, non serve out_dir
            pass
        else:
            if not out_dir:
                d = QFileDialog.getExistingDirectory(self, "Cartella di destinazione")
                if not d:
                    return
                out_dir = d
                self.settings_panel.outdir_edit.setText(out_dir)
            if not os.path.isdir(out_dir):
                QMessageBox.warning(self, "Cartella non valida",
                                    f"La cartella di destinazione non esiste:\n{out_dir}")
                return

        job = BatchJob(
            inputs=paths,
            output_dir=out_dir,
            crop_settings=self.settings_panel.crop_settings(),
            upscale_settings=self.settings_panel.upscale_settings(),
            suffix=self.settings_panel.suffix(),
            in_place=in_place,
        )

        if in_place:
            self._log(f"\n=== Avvio batch: {len(paths)} immagini "
                      f"(IN-PLACE, backup automatico ZIP) ===")
        else:
            self._log(f"\n=== Avvio batch: {len(paths)} immagini -> {out_dir} ===")
        if job.upscale_settings.enabled:
            self._log(f"Upscaling AI: x{job.upscale_settings.scale} "
                      f"modello={job.upscale_settings.model}")

        self._thread = QThread()
        self._worker = BatchWorker(job)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.file_done.connect(self._on_file_done)
        self._worker.log.connect(self._log)
        self._worker.error.connect(lambda m: self._log(f"[ERRORE] {m}"))
        self._worker.finished.connect(self._on_finished)
        # cleanup: il thread fa quit, poi deleteLater su worker e thread,
        # poi azzzeremo i riferimenti quando il thread è realmente fermato.
        self._worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._on_thread_finished)

        self.process_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress.setRange(0, len(paths))
        self.progress.setValue(0)
        self._thread.start()

    def _cancel_processing(self):
        if self._worker is not None:
            self._worker.cancel()
            self._log("Annullamento richiesto...")

    def _on_thread_finished(self):
        """Chiamato quando il QThread è realmente fermato: sicuro azzerare."""
        self._worker = None
        self._thread = None

    # ---- Restore Backup (panic button) ----
    def _restore_backup(self):
        """Ripristina le immagini originali dal backup ZIP.

        Permette di selezionare:
        - Un file .app (cerca imageforge_backup.zip al suo interno)
        - Un file imageforge_backup.zip diretto
        - Una cartella (cerca imageforge_backup.zip al suo interno)
        """
        from PySide6.QtWidgets import QFileDialog
        import zipfile

        # Dialog che accetta .app, .zip, o cartelle
        # Usa getOpenFileName con filtro per .app e .zip
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Seleziona il gioco .app o il backup ZIP",
            "", "Gioco Ren'Py (*.app);;Backup ZIP (imageforge_backup.zip);;Tutti i file (*.*)")

        if not file_path:
            # Fallback: prova con getExistingDirectory
            folder = QFileDialog.getExistingDirectory(
                self, "Oppure seleziona la cartella game/")
            if not folder:
                return
            file_path = folder

        # Trova il backup ZIP
        zip_path = None
        if file_path.endswith(".app"):
            # Cerca in Game.app/Contents/Resources/autorun/game/
            candidate = os.path.join(file_path, "Contents", "Resources",
                                     "autorun", "game", "imageforge_backup.zip")
            if os.path.isfile(candidate):
                zip_path = candidate
        elif file_path.endswith("imageforge_backup.zip"):
            zip_path = file_path
        elif os.path.isdir(file_path):
            # Cartella: cerca imageforge_backup.zip dentro
            candidate = os.path.join(file_path, "imageforge_backup.zip")
            if os.path.isfile(candidate):
                zip_path = candidate
            else:
                # Cerca ricorsivamente
                for root, dirs, files in os.walk(file_path):
                    if "imageforge_backup.zip" in files:
                        zip_path = os.path.join(root, "imageforge_backup.zip")
                        break

        if not zip_path or not os.path.isfile(zip_path):
            QMessageBox.warning(
                self, "Backup non trovato",
                f"Impossibile trovare imageforge_backup.zip in:\n{file_path}\n\n"
                f"Assicurati che il backup esista.")
            return

        # La directory dove estrarre è la directory che contiene il ZIP
        extract_dir = os.path.dirname(zip_path)

        reply = QMessageBox.question(
            self, "Conferma ripristino",
            f"Ripristinare le immagini originali dal backup?\n\n"
            f"Backup: {zip_path}\n"
            f"Destinazione: {extract_dir}\n\n"
            f"Le immagini attuali verranno sovrascritte con gli originali.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return

        self._log(f"\n=== Ripristino backup da {zip_path} ===")
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                names = zf.namelist()
                self._log(f"Estrazione di {len(names)} file...")
                zf.extractall(extract_dir)
            self._log(f"Ripristino completato: {len(names)} immagini ripristinate.")
            QMessageBox.information(
                self, "Ripristino completato",
                f"{len(names)} immagini originali ripristinate con successo.\n"
                f"Da: {zip_path}")
        except Exception as e:
            self._log(f"Errore ripristino: {e}")
            QMessageBox.critical(self, "Errore",
                                 f"Errore durante il ripristino:\n{e}")

    def _on_progress(self, done, total, name):
        self.progress.setRange(0, max(total, 1))
        self.progress.setValue(done)
        self.progress_label.setText(f"{done} / {total}")
        self.statusBar().showMessage(f"Elaborazione: {name} ({done}/{total})")

    def _on_file_done(self, result):
        if result.status == "ok":
            w, h = result.final_size
            self._log(f"  OK: {os.path.basename(result.output_path)} ({w}x{h})")
        else:
            self._log(f"  FALLITO: {os.path.basename(result.input_path)} - {result.error}")

    def _on_finished(self, results):
        ok = sum(1 for r in results if r.status == "ok")
        fail = len(results) - ok
        self._log(f"=== Completato: {ok} OK, {fail} falliti ===")
        self.statusBar().showMessage(f"Completato: {ok} OK, {fail} falliti.")
        self.process_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        # NON azzerare _worker/_thread qui: il thread è ancora in fase di quit.
        # Verranno puliti da deleteLater quando il thread sarà realmente fermato.
        if fail == 0 and ok > 0:
            if self.settings_panel.in_place():
                msg = f"Elaborate {ok} immagini (originali sovrascritti in-place).\nBackup ZIP creato in game/."
            else:
                msg = f"Elaborate {ok} immagini con successo in:\n{self.settings_panel.output_dir()}"
            QMessageBox.information(self, "Fatto", msg)
        elif fail > 0:
            QMessageBox.warning(self, "Completato con errori",
                                f"OK: {ok}\nFalliti: {fail}\nVedi log per dettagli.")

    # ---- About ----
    def _about(self):
        from . import __version__
        from .upscaler import status_message
        QMessageBox.about(
            self, "RenPy ImageForge",
            f"<h3>RenPy ImageForge v{__version__}</h3>"
            f"<p>Tool macOS per crop batch con aspect ratio fisso, resize, "
            f"upscaling AI (Real-ESRGAN ncnn/Metal) e integrazione giochi Ren'Py.</p>"
            f"<p>Python {platform.python_version()} · {platform.machine()}</p>"
            f"<pre style='color:#8a7a64;font-size:10px'>{status_message()}</pre>"
        )

    def closeEvent(self, e):
        # Ferma il worker in modo sicuro prima di chiudere
        if self._thread and self._thread.isRunning():
            if self._worker:
                self._worker.cancel()
            self._thread.quit()
            self._thread.wait(5000)  # max 5 secondi
        # Ferma anche il dialog Ren'Py se aperto
        super().closeEvent(e)
        super().closeEvent(e)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("RenPy ImageForge")
    app.setApplicationDisplayName("RenPy ImageForge")
    app.setStyle("Fusion")

    # Icona dell'app (dock + finestra)
    icon_path = Path(__file__).resolve().parent.parent / "img" / "icon.iconset" / "icon_256x256.png"
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))

    # Tema scuro caldo con accenti bronzo/oro (palette del logo)
    from PySide6.QtGui import QPalette, QColor
    # Palette ispirata al logo: nero caldo + bronzo/oro
    C_BG = QColor(26, 24, 21)          # #1a1815 sfondo principale
    C_BASE = QColor(34, 31, 27)        # #221f1b campi di testo/liste
    C_ALT = QColor(42, 38, 33)         # #2a2621 righe alternate
    C_TEXT = QColor(232, 226, 214)     # #e8e2d6 testo (avorio caldo)
    C_BTN = QColor(46, 41, 35)         # #2e2923 bottoni
    C_ACCENT = QColor(184, 134, 92)    # #b8865c bronzo (highlight)
    C_ACCENT_TEXT = QColor(26, 24, 21) # testo su highlight
    pal = app.palette()
    pal.setColor(QPalette.Window, C_BG)
    pal.setColor(QPalette.Base, C_BASE)
    pal.setColor(QPalette.AlternateBase, C_ALT)
    pal.setColor(QPalette.Text, C_TEXT)
    pal.setColor(QPalette.Button, C_BTN)
    pal.setColor(QPalette.ButtonText, C_TEXT)
    pal.setColor(QPalette.WindowText, C_TEXT)
    pal.setColor(QPalette.Highlight, C_ACCENT)
    pal.setColor(QPalette.HighlightedText, C_ACCENT_TEXT)
    pal.setColor(QPalette.ToolTipBase, C_BASE)
    pal.setColor(QPalette.ToolTipText, C_TEXT)
    pal.setColor(QPalette.PlaceholderText, QColor(120, 110, 95))
    app.setPalette(pal)

    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
