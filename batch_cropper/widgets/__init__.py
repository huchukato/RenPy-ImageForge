"""Widget di anteprima con overlay del rettangolo di crop."""

from __future__ import annotations

from typing import Tuple

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QPixmap, QColor, QPen, QFont
from PySide6.QtWidgets import QWidget

from ..cropper import compute_crop_box, compute_resize_size


class CropPreviewWidget(QWidget):
    """Mostra un'immagine scalata con il rettangolo di crop sovrapposto
    e un riepilogo della pipeline (originale -> crop -> upscale -> finale)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(320, 260)
        self.setAcceptDrops(False)
        self._pixmap: QPixmap | None = None
        self._orig_size: Tuple[int, int] = (0, 0)
        self._crop_box: Tuple[int, int, int, int] | None = None
        self._crop_size: Tuple[int, int] = (0, 0)
        self._upscaled_size: Tuple[int, int] = (0, 0)
        self._final_size: Tuple[int, int] = (0, 0)
        self._upscale_enabled: bool = False
        self._upscale_scale: int = 0
        self._info_text: str = ""

    def set_image(self, path: str):
        pm = QPixmap(path)
        if pm.isNull():
            self._pixmap = None
            self._info_text = "Anteprima non disponibile"
        else:
            self._pixmap = pm
            self._orig_size = (pm.width(), pm.height())
            self._info_text = ""
        self.update()

    def clear(self):
        self._pixmap = None
        self._orig_size = (0, 0)
        self._crop_box = None
        self._crop_size = (0, 0)
        self._upscaled_size = (0, 0)
        self._final_size = (0, 0)
        self._info_text = "Trascina immagini qui o usa Aggiungi file"
        self.update()

    def update_overlay(self, aspect_ratio, anchor, resize_after,
                       upscale_enabled=False, upscale_scale=0):
        """Ricalcola crop box, dimensioni di tutti gli stadi e ridisegna.

        Pipeline:
          originale -> crop(aspect ratio) -> [upscale AI xN] -> [resize finale]
        """
        self._upscale_enabled = upscale_enabled
        self._upscale_scale = upscale_scale

        if self._pixmap is None or self._orig_size == (0, 0):
            self._crop_box = None
            self._crop_size = (0, 0)
            self._upscaled_size = (0, 0)
            self._final_size = (0, 0)
            self.update()
            return

        # Stage 1: crop
        if aspect_ratio is not None:
            self._crop_box = compute_crop_box(self._orig_size, aspect_ratio, anchor)
            self._crop_size = (self._crop_box[2] - self._crop_box[0],
                               self._crop_box[3] - self._crop_box[1])
        else:
            self._crop_box = None
            self._crop_size = self._orig_size

        # Stage 2: upscale AI (opzionale)
        if upscale_enabled and upscale_scale > 0:
            self._upscaled_size = (self._crop_size[0] * upscale_scale,
                                   self._crop_size[1] * upscale_scale)
        else:
            self._upscaled_size = self._crop_size

        # Stage 3: resize finale (opzionale, dopo upscale)
        if resize_after is not None:
            self._final_size = compute_resize_size(self._upscaled_size, resize_after)
        else:
            self._final_size = self._upscaled_size
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        w, h = self.width(), self.height()
        bg = QColor(26, 24, 21)  # #1a1815 sfondo caldo del logo
        painter.fillRect(0, 0, w, h, bg)

        if self._pixmap is None or self._pixmap.isNull():
            painter.setPen(QColor(140, 128, 110))  # grigio caldo
            painter.setFont(QFont(".AppleSystemUIFont", 11))
            painter.drawText(self.rect(), Qt.AlignCenter,
                             self._info_text or "Nessuna immagine")
            return

        # Scala immagine per contenuta nel widget mantenendo ratio
        pm = self._pixmap
        ow, oh = pm.width(), pm.height()
        margin = 12
        # spazio in basso per 2 righe di info (pipeline + dimensioni)
        info_h = 46
        avail_w = w - 2 * margin
        avail_h = h - 2 * margin - info_h
        scale = min(avail_w / ow, avail_h / oh, 1.0)
        disp_w = int(ow * scale)
        disp_h = int(oh * scale)
        disp_x = (w - disp_w) // 2
        disp_y = margin

        painter.drawPixmap(disp_x, disp_y, disp_w, disp_h, pm)

        # Overlay crop
        if self._crop_box is not None:
            cx0, cy0, cx1, cy1 = self._crop_box
            rx0 = disp_x + cx0 * scale
            ry0 = disp_y + cy0 * scale
            rx1 = disp_x + cx1 * scale
            ry1 = disp_y + cy1 * scale
            rect = QRectF(rx0, ry0, rx1 - rx0, ry1 - ry0)

            # Scurisci fuori dal crop
            mask = QColor(0, 0, 0, 140)
            painter.fillRect(QRectF(disp_x, disp_y, disp_w, ry0 - disp_y), mask)
            painter.fillRect(QRectF(disp_x, ry1, disp_w, disp_y + disp_h - ry1), mask)
            painter.fillRect(QRectF(disp_x, ry0, rx0 - disp_x, ry1 - ry0), mask)
            painter.fillRect(QRectF(rx1, ry0, disp_x + disp_w - rx1, ry1 - ry0), mask)

            # Bordo crop
            pen = QPen(QColor(200, 150, 90), 2)  # bronzo/oro del logo
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(rect)

            # Terzi (rule of thirds)
            pen_thin = QPen(QColor(200, 150, 90, 120), 1)  # bronzo semi-trasparente
            painter.setPen(pen_thin)
            for i in (1, 2):
                x = rx0 + (rx1 - rx0) * i / 3
                painter.drawLine(QRectF(x, ry0, x, ry1).topLeft(),
                                 QRectF(x, ry0, x, ry1).bottomLeft())
                y = ry0 + (ry1 - ry0) * i / 3
                painter.drawLine(QRectF(rx0, y, rx1, y).topLeft(),
                                 QRectF(rx0, y, rx1, y).topRight())

        # --- Riepilogo pipeline in basso (2 righe) ---
        ow, oh = self._orig_size
        cw, ch = self._crop_size
        uw, uh = self._upscaled_size
        fw, fh = self._final_size

        # Riga 1: pipeline con frecce
        painter.setPen(QColor(210, 200, 185))  # avorio caldo
        painter.setFont(QFont(".AppleSystemUIFont", 9))
        if self._crop_box is not None:
            crop_label = f"crop {cw}x{ch}"
        else:
            crop_label = "no crop"
        if self._upscale_enabled and self._upscale_scale > 0:
            ups_label = f"upscale x{self._upscale_scale} -> {uw}x{uh}"
        else:
            ups_label = ""
        if (fw, fh) != (uw, uh):
            final_label = f"resize -> {fw}x{fh}"
        else:
            final_label = f"{fw}x{fh}"

        parts = [f"{ow}x{oh}", crop_label]
        if ups_label:
            parts.append(ups_label)
        parts.append(final_label)
        pipeline = "  ->  ".join(parts)
        painter.drawText(QRectF(0, h - info_h, w, 20), Qt.AlignCenter, pipeline)

        # Riga 2: etichetta "Finale" evidenziata
        painter.setPen(QColor(200, 150, 90))  # bronzo/oro del logo
        painter.setFont(QFont(".AppleSystemUIFont", 10, QFont.Bold))
        painter.drawText(QRectF(0, h - 22, w, 22), Qt.AlignCenter,
                         f"Risultato finale: {fw}x{fh}")
