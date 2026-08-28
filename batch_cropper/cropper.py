"""Logica di crop e resize basata su Pillow.

Supporta crop con aspect ratio fisso e anchor posizionale, resize finale
opzionale e gestione multi-formato (webp, jpg, png, tiff, heic).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import Tuple

from PIL import Image

# pillow-heif registra i plugin HEIC/HEIF in PIL all'import
try:
    import pillow_heif  # noqa: F401

    pillow_heif.register_heif_opener()
except Exception:  # pragma: no cover - HEIC opzionale
    pass


SUPPORTED_INPUT_EXT = {".webp", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".heic", ".heif"}
SUPPORTED_OUTPUT_EXT = {".webp", ".jpg", ".jpeg", ".png"}


class Anchor(str, Enum):
    """Posizione del crop rispetto all'immagine originale (griglia 3x3)."""

    TOP_LEFT = "top-left"
    TOP = "top"
    TOP_RIGHT = "top-right"
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"
    BOTTOM_LEFT = "bottom-left"
    BOTTOM = "bottom"
    BOTTOM_RIGHT = "bottom-right"


# Preset di aspect ratio comuni (nome -> (w, h))
ASPECT_PRESETS = {
    "16:9": (16, 9),
    "16:10": (16, 10),
    "3:2": (3, 2),
    "4:3": (4, 3),
    "2:3": (2, 3),
    "3:4": (3, 4),
    "1:1": (1, 1),
    "9:16": (9, 16),
    "21:9": (21, 9),
}


@dataclass
class CropSettings:
    """Impostazioni di crop/resize per un batch.

    aspect_ratio: tuple (w, h) del ratio target, oppure None per nessun crop.
    anchor: posizione del crop.
    resize_after: tupla (width, height) per resize finale post-crop, oppure None.
      Se target_w o target_h è None mantiene le proporzioni sull'asse specificato.
    output_format: estensione di output senza punto (es. 'webp', 'png', 'jpg').
    output_quality: qualità per jpg/webp (1-100).
    """

    aspect_ratio: Tuple[int, int] | None = (16, 9)
    anchor: Anchor = Anchor.CENTER
    resize_after: Tuple[int | None, int | None] | None = None
    output_format: str = "webp"
    output_quality: int = 92


def compute_crop_box(img_size: Tuple[int, int], aspect_ratio: Tuple[int, int],
                     anchor: Anchor) -> Tuple[int, int, int, int]:
    """Calcola il rettangolo di crop (left, upper, right, lower) che massimizza
    l'area rispettando l'aspect ratio richiesto, posizionato secondo anchor.
    """
    w, h = img_size
    target_w, target_h = aspect_ratio
    target_ratio = target_w / target_h
    img_ratio = w / h

    if img_ratio > target_ratio:
        # Immagine più larga del target: limita larghezza
        crop_w = int(round(h * target_ratio))
        crop_h = h
    else:
        # Immagine più alta del target: limita altezza
        crop_w = w
        crop_h = int(round(w / target_ratio))

    # Posizionamento orizzontale
    if anchor.value.endswith("left"):
        x0 = 0
    elif anchor.value.endswith("right"):
        x0 = w - crop_w
    else:
        x0 = (w - crop_w) // 2

    # Posizionamento verticale
    if anchor.value.startswith("top"):
        y0 = 0
    elif anchor.value.startswith("bottom"):
        y0 = h - crop_h
    else:
        y0 = (h - crop_h) // 2

    x0 = max(0, min(x0, w - crop_w))
    y0 = max(0, min(y0, h - crop_h))
    return (x0, y0, x0 + crop_w, y0 + crop_h)


def compute_resize_size(size: Tuple[int, int],
                        target: Tuple[int | None, int | None]) -> Tuple[int, int]:
    """Calcola la dimensione finale dopo resize mantenendo le proporzioni.

    target: (width, height). Se uno dei due è None, l'asse viene derivato
    dall'altro mantenendo il ratio. Se entrambi valorizzati, usa entrambi
    (stretch consentito solo se esplicito).
    """
    w, h = size
    tw, th = target
    if tw is None and th is None:
        return size
    if tw is None:
        new_h = th
        new_w = int(round(w * th / h))
        return (new_w, new_h)
    if th is None:
        new_w = tw
        new_h = int(round(h * tw / w))
        return (new_w, new_h)
    return (tw, th)


def process_image(src_path: str, dst_path: str, settings: CropSettings) -> Tuple[int, int]:
    """Processa una singola immagine: crop -> resize -> salva.

    Ritorna la dimensione finale (w, h) dell'immagine salvata.
    """
    with Image.open(src_path) as img:
        # Converti in RGB se necessario per i formati senza alpha
        img.load()
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")

        # Crop
        if settings.aspect_ratio is not None:
            box = compute_crop_box(img.size, settings.aspect_ratio, settings.anchor)
            img = img.crop(box)

        # Resize finale
        if settings.resize_after is not None:
            new_size = compute_resize_size(img.size, settings.resize_after)
            if new_size != img.size:
                img = img.resize(new_size, Image.LANCZOS)

        # Forza estensione di output
        base, _ = os.path.splitext(dst_path)
        fmt = settings.output_format.lower().lstrip(".")
        dst_path = f"{base}.{fmt}"

        save_kwargs = {}
        if fmt in ("jpg", "jpeg"):
            if img.mode == "RGBA":
                img = img.convert("RGB")
            save_kwargs["quality"] = settings.output_quality
            save_kwargs["optimize"] = True
        elif fmt == "webp":
            save_kwargs["quality"] = settings.output_quality
            save_kwargs["method"] = 6
        elif fmt == "png":
            save_kwargs["optimize"] = True

        img.save(dst_path, **save_kwargs)
        return img.size


def is_supported_input(path: str) -> bool:
    ext = os.path.splitext(path)[1].lower()
    return ext in SUPPORTED_INPUT_EXT
