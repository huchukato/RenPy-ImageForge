"""Wrapper per Real-ESRGAN ncnn-vulkan (binario esterno).

Su Apple Silicon usa Metal via MoltenVK. Il binario e i modelli sono
bundled in vendor/realesrgan-ncnn-vulkan/.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple


# Modelli disponibili nel bundle
MODELS = {
    "realesrgan-x4plus": "Foto generali - alta qualità (solo x4)",
    "realesr-animevideov3": "Anime/video - veloce, buono per illustrazioni",
    "realesrgan-x4plus-anime": "Anime/illustrazioni - alta qualità (solo x4)",
}

VALID_SCALES = (2, 3, 4)


@dataclass
class UpscaleSettings:
    enabled: bool = False
    scale: int = 2
    model: str = "realesrgan-x4plus"
    tile_size: int = 0  # 0 = auto
    output_format: str = "png"  # formato intermedio per upscaler
    tta: bool = False


def _vendor_root() -> Path:
    """Root del progetto (4 livelli sopra questo file: batch_cropper/upscaler.py
    -> batch_cropper/ -> progetto/)."""
    return Path(__file__).resolve().parent.parent


def find_realesrgan_binary() -> str | None:
    """Trova il binario realesrgan-ncnn-vulkan.

    Ordine di ricerca:
    1. Variabile d'ambiente REALESRGAN_BIN
    2. vendor/realesrgan-ncnn-vulkan/realesrgan-ncnn-vulkan (bundle)
    3. PATH di sistema
    """
    env = os.environ.get("REALESRGAN_BIN")
    if env and os.path.isfile(env):
        return env

    bundled = _vendor_root() / "vendor" / "realesrgan-ncnn-vulkan" / "realesrgan-ncnn-vulkan"
    if bundled.is_file():
        return str(bundled)

    found = shutil.which("realesrgan-ncnn-vulkan")
    return found


def find_models_dir() -> str | None:
    """Trova la cartella models/ per Real-ESRGAN."""
    env = os.environ.get("REALESRGAN_MODELS")
    if env and os.path.isdir(env):
        return env

    bundled = _vendor_root() / "vendor" / "realesrgan-ncnn-vulkan" / "models"
    if bundled.is_dir():
        return str(bundled)

    return None


def is_available() -> bool:
    """True se binario + modelli sono disponibili."""
    return find_realesrgan_binary() is not None and find_models_dir() is not None


def upscale(src_path: str, dst_path: str, settings: UpscaleSettings,
            on_progress=None) -> Tuple[int, int]:
    """Esegue l'upscaling di una singola immagine.

    Ritorna la dimensione finale (w, h). Solleva RuntimeError se Real-ESRGAN
    non è disponibile o l'esecuzione fallisce.
    """
    binary = find_realesrgan_binary()
    models = find_models_dir()
    if not binary or not models:
        raise RuntimeError(
            "Real-ESRGAN non trovato. Imposta REALESRGAN_BIN e REALESRGAN_MODELS "
            "oppure installa il bundle in vendor/."
        )

    if settings.scale not in VALID_SCALES:
        raise RuntimeError(f"Scala non valida: {settings.scale}. Validi: {VALID_SCALES}")

    cmd = [
        binary,
        "-i", src_path,
        "-o", dst_path,
        "-s", str(settings.scale),
        "-n", settings.model,
        "-m", models,
        "-t", str(settings.tile_size),
        "-f", settings.output_format,
    ]
    if settings.tta:
        cmd.append("-x")

    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.rstrip()
        if not line:
            continue
        if on_progress is not None:
            on_progress(line)
    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"Real-ESRGAN fallito (exit {proc.returncode})")

    # Assicura estensione coerente con output_format
    base, _ = os.path.splitext(dst_path)
    expected = f"{base}.{settings.output_format}"
    if os.path.exists(expected):
        dst_path = expected

    from PIL import Image
    with Image.open(dst_path) as img:
        return img.size


def status_message() -> str:
    """Messaggio di stato leggibile per la GUI."""
    binary = find_realesrgan_binary()
    models = find_models_dir()
    if binary and models:
        return f"Real-ESRGAN pronto (Metal/MoltenVK)\n  binario: {binary}\n  modelli: {models}"
    missing = []
    if not binary:
        missing.append("binario")
    if not models:
        missing.append("modelli")
    return f"Real-ESRGAN non disponibile (manca: {', '.join(missing)})"
