"""Main window for RenPy ImageForge."""

from __future__ import annotations

import os
import platform
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QThread, QUrl
from PySide6.QtGui import QAction, QActionGroup, QDragEnterEvent, QDropEvent, QIcon, QPixmap
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
from .i18n import tr, set_language, get_language, LANGUAGES


class FileListWidget(QListWidget):
    """QListWidget that accepts file drag & drop."""

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
        # avoid duplicates
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
        # Window icon
        icon_path = Path(__file__).resolve().parent.parent / "img" / "icon.iconset" / "icon_256x256.png"
        if icon_path.is_file():
            self.setWindowIcon(QIcon(str(icon_path)))
        self._build_ui()
        self._build_menu()
        self._refresh_preview()
        self._retranslate_ui()

    # ---- UI ----
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(6)

        splitter = QSplitter(Qt.Horizontal)

        # Left column: file list
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(4)
        self.input_label = QLabel()
        ll.addWidget(self.input_label)
        self.file_list = FileListWidget()
        self.file_list.currentRowChanged.connect(self._on_file_selected)
        ll.addWidget(self.file_list, 1)
        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)
        self.add_btn = QPushButton()
        self.add_btn.clicked.connect(self._add_files)
        self.addfolder_btn = QPushButton()
        self.addfolder_btn.clicked.connect(self._add_folder)
        self.renpy_btn = QPushButton()
        self.renpy_btn.clicked.connect(self._open_renpy)
        self.remove_btn = QPushButton()
        self.remove_btn.clicked.connect(self._remove_selected)
        self.clear_btn = QPushButton()
        self.clear_btn.clicked.connect(self._clear_all)
        for b in (self.add_btn, self.addfolder_btn, self.renpy_btn,
                  self.remove_btn, self.clear_btn):
            btn_row.addWidget(b)
        ll.addLayout(btn_row)
        splitter.addWidget(left)

        # Center column: preview + log
        center = QWidget()
        cl = QVBoxLayout(center)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(6)
        self.preview_label = QLabel()
        cl.addWidget(self.preview_label)
        self.preview = CropPreviewWidget()
        cl.addWidget(self.preview, 1)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(160)
        self.log.setStyleSheet("QPlainTextEdit{background:#1a1815;color:#d8c8b0;}")
        cl.addWidget(self.log)
        splitter.addWidget(center)

        # Right column: settings
        self.settings_panel = SettingsPanel()
        self.settings_panel.changed.connect(self._refresh_preview)
        splitter.addWidget(self.settings_panel)

        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 2)
        splitter.setSizes([300, 560, 360])
        outer.addWidget(splitter, 1)

        # Action bar + progress
        action_row = QHBoxLayout()
        self.process_btn = QPushButton()
        self.process_btn.setStyleSheet(
            "QPushButton{font-weight:bold;padding:6px 14px;"
            "background:#b8865c;color:#1a1815;border:none;border-radius:4px;}"
            "QPushButton:hover{background:#c8966c;}"
            "QPushButton:disabled{background:#3a342c;color:#6a5e4e;}")
        self.process_btn.clicked.connect(self._start_processing)
        self.cancel_btn = QPushButton()
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel_processing)

        # Panic button: restore backup
        self.restore_btn = QPushButton()
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
        self.file_menu = mb.addMenu("")
        self.a_add = QAction("", self)
        self.a_add.setShortcut("Ctrl+O")
        self.a_add.triggered.connect(self._add_files)
        self.file_menu.addAction(self.a_add)
        self.a_addf = QAction("", self)
        self.a_addf.setShortcut("Ctrl+Shift+O")
        self.a_addf.triggered.connect(self._add_folder)
        self.file_menu.addAction(self.a_addf)
        self.file_menu.addSeparator()
        self.a_renpy = QAction("", self)
        self.a_renpy.setShortcut("Ctrl+R")
        self.a_renpy.triggered.connect(self._open_renpy)
        self.file_menu.addAction(self.a_renpy)
        self.file_menu.addSeparator()
        self.a_clear = QAction("", self)
        self.a_clear.triggered.connect(self._clear_all)
        self.file_menu.addAction(self.a_clear)
        self.file_menu.addSeparator()
        self.a_quit = QAction("", self)
        self.a_quit.setShortcut("Ctrl+Q")
        self.a_quit.triggered.connect(self.close)
        self.file_menu.addAction(self.a_quit)

        # Language menu
        self.lang_menu = mb.addMenu("")
        self._lang_group = QActionGroup(self)
        self._lang_group.setExclusive(True)
        for code, name in LANGUAGES.items():
            a = QAction(name, self, checkable=True)
            a.setChecked(code == get_language())
            a.triggered.connect(lambda checked, c=code: self._change_language(c))
            self._lang_group.addAction(a)
            self.lang_menu.addAction(a)

        self.help_menu = mb.addMenu("")
        self.a_about = QAction("", self)
        self.a_about.triggered.connect(self._about)
        self.help_menu.addAction(self.a_about)

    def _change_language(self, code: str):
        set_language(code)
        self._retranslate_ui()

    def _retranslate_ui(self):
        """Update all translatable strings when language changes."""
        self.input_label.setText(tr("input_images"))
        self.add_btn.setText(tr("add_file"))
        self.addfolder_btn.setText(tr("add_folder"))
        self.renpy_btn.setText(tr("renpy_btn"))
        self.renpy_btn.setToolTip(tr("renpy_btn_tip"))
        self.remove_btn.setText(tr("remove_selected"))
        self.clear_btn.setText(tr("clear"))
        self.preview_label.setText(tr("crop_preview"))
        self.process_btn.setText(tr("start_processing"))
        self.cancel_btn.setText(tr("cancel"))
        self.restore_btn.setText(tr("restore_backup"))
        self.restore_btn.setToolTip(tr("restore_backup_tip"))

        # Menu
        self.file_menu.setTitle(tr("menu_file"))
        self.a_add.setText(tr("menu_add_files"))
        self.a_addf.setText(tr("menu_add_folder"))
        self.a_renpy.setText(tr("menu_open_renpy"))
        self.a_clear.setText(tr("menu_clear_list"))
        self.a_quit.setText(tr("menu_quit"))
        self.lang_menu.setTitle(tr("menu_language"))
        self.help_menu.setTitle(tr("menu_help"))
        self.a_about.setText(tr("menu_about"))

        # Status bar
        self.statusBar().showMessage(tr("status_ready"))

        # Settings panel
        self.settings_panel.retranslate_ui()

    # ---- File list ops ----
    def _add_files(self):
        exts = " ".join(f"*{e}" for e in SUPPORTED_INPUT_EXT)
        files, _ = QFileDialog.getOpenFileNames(
            self, tr("select_images"), "", tr("images_filter", exts=exts))
        for f in files:
            self.file_list.add_path(f)
        self._update_count()

    def _add_folder(self):
        d = QFileDialog.getExistingDirectory(self, tr("select_folder"))
        if not d:
            return
        added = 0
        for f in sorted(os.listdir(d)):
            fp = os.path.join(d, f)
            if os.path.isfile(fp) and is_supported_input(fp):
                self.file_list.add_path(fp)
                added += 1
        self._log(tr("added_n_from_folder", n=added, path=d))
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
        dlg = RenpyDialog(self)
        dlg.images_selected.connect(self._on_renpy_images_selected)
        dlg.exec()

    def _on_renpy_images_selected(self, paths: list):
        added = 0
        for p in paths:
            if is_supported_input(p):
                self.file_list.add_path(p)
                added += 1
        self._log(tr("added_n_from_renpy", n=added))
        self._update_count()
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
            QMessageBox.information(self, tr("no_images"), tr("no_images_msg"))
            return

        in_place = self.settings_panel.in_place()
        out_dir = self.settings_panel.output_dir()

        if in_place:
            pass
        else:
            if not out_dir:
                d = QFileDialog.getExistingDirectory(self, tr("select_dest_folder"))
                if not d:
                    return
                out_dir = d
                self.settings_panel.outdir_edit.setText(out_dir)
            if not os.path.isdir(out_dir):
                QMessageBox.warning(self, tr("invalid_folder"),
                                    tr("invalid_folder_msg", path=out_dir))
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
            self._log(tr("batch_start_inplace", n=len(paths)))
        else:
            self._log(tr("batch_start_outdir", n=len(paths), path=out_dir))
        if job.upscale_settings.enabled:
            self._log(tr("upscale_info", scale=job.upscale_settings.scale,
                         model=job.upscale_settings.model))

        self._thread = QThread()
        self._worker = BatchWorker(job)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.file_done.connect(self._on_file_done)
        self._worker.log.connect(self._log)
        self._worker.error.connect(lambda m: self._log(tr("log_error", msg=m)))
        self._worker.finished.connect(self._on_finished)
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
            self._log(tr("cancel_requested"))

    def _on_thread_finished(self):
        self._worker = None
        self._thread = None

    # ---- Restore Backup (panic button) ----
    def _restore_backup(self):
        from PySide6.QtWidgets import QFileDialog
        import zipfile

        file_path, _ = QFileDialog.getOpenFileName(
            self, tr("restore_select"), "", tr("restore_filter"))

        if not file_path:
            folder = QFileDialog.getExistingDirectory(
                self, tr("restore_or_folder"))
            if not folder:
                return
            file_path = folder

        zip_path = None
        if file_path.endswith(".app"):
            candidate = os.path.join(file_path, "Contents", "Resources",
                                     "autorun", "game", "imageforge_backup.zip")
            if os.path.isfile(candidate):
                zip_path = candidate
        elif file_path.endswith("imageforge_backup.zip"):
            zip_path = file_path
        elif os.path.isdir(file_path):
            candidate = os.path.join(file_path, "imageforge_backup.zip")
            if os.path.isfile(candidate):
                zip_path = candidate
            else:
                for root, dirs, files in os.walk(file_path):
                    if "imageforge_backup.zip" in files:
                        zip_path = os.path.join(root, "imageforge_backup.zip")
                        break

        if not zip_path or not os.path.isfile(zip_path):
            QMessageBox.warning(
                self, tr("restore_not_found"),
                tr("restore_not_found_msg", path=file_path))
            return

        extract_dir = os.path.dirname(zip_path)

        reply = QMessageBox.question(
            self, tr("restore_confirm"),
            tr("restore_confirm_msg", zip=zip_path, dest=extract_dir),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return

        self._log(tr("restore_start", path=zip_path))
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                names = zf.namelist()
                self._log(tr("restore_extracting", n=len(names)))
                zf.extractall(extract_dir)
            self._log(tr("restore_done", n=len(names)))
            QMessageBox.information(
                self, tr("restore_done_title"),
                tr("restore_done_msg", n=len(names), zip=zip_path))
        except Exception as e:
            self._log(tr("restore_error", e=e))
            QMessageBox.critical(self, tr("restore_error_title"),
                                 tr("restore_error_msg", e=e))

    def _on_progress(self, done, total, name):
        self.progress.setRange(0, max(total, 1))
        self.progress.setValue(done)
        self.progress_label.setText(f"{done} / {total}")
        self.statusBar().showMessage(tr("status_processing", name=name, done=done, total=total))

    def _on_file_done(self, result):
        if result.status == "ok":
            w, h = result.final_size
            self._log(tr("log_ok", name=os.path.basename(result.output_path), w=w, h=h))
        else:
            self._log(tr("log_failed", name=os.path.basename(result.input_path), error=result.error))

    def _on_finished(self, results):
        ok = sum(1 for r in results if r.status == "ok")
        fail = len(results) - ok
        self._log(tr("done_ok_fail", ok=ok, fail=fail))
        self.statusBar().showMessage(tr("status_done", ok=ok, fail=fail))
        self.process_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        if fail == 0 and ok > 0:
            if self.settings_panel.in_place():
                msg = tr("done_inplace_msg", ok=ok)
            else:
                msg = tr("done_outdir_msg", ok=ok, path=self.settings_panel.output_dir())
            QMessageBox.information(self, tr("done_title"), msg)
        elif fail > 0:
            QMessageBox.warning(self, tr("done_with_errors"),
                                tr("done_with_errors_msg", ok=ok, fail=fail))

    # ---- About ----
    def _about(self):
        from . import __version__
        from .upscaler import status_message
        QMessageBox.about(
            self, "RenPy ImageForge",
            tr("about_text",
               version=__version__,
               pyver=platform.python_version(),
               machine=platform.machine(),
               status=status_message())
        )

    def closeEvent(self, e):
        if self._thread and self._thread.isRunning():
            if self._worker:
                self._worker.cancel()
            self._thread.quit()
            self._thread.wait(5000)
        super().closeEvent(e)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("RenPy ImageForge")
    app.setApplicationDisplayName("RenPy ImageForge")
    app.setStyle("Fusion")

    icon_path = Path(__file__).resolve().parent.parent / "img" / "icon.iconset" / "icon_256x256.png"
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))

    # Dark warm theme with bronze/gold accents (logo palette)
    from PySide6.QtGui import QPalette, QColor
    C_BG = QColor(26, 24, 21)
    C_BASE = QColor(34, 31, 27)
    C_ALT = QColor(42, 38, 33)
    C_TEXT = QColor(232, 226, 214)
    C_BTN = QColor(46, 41, 35)
    C_ACCENT = QColor(184, 134, 92)
    C_ACCENT_TEXT = QColor(26, 24, 21)
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
