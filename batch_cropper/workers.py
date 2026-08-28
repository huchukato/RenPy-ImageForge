"""Worker QThread per elaborazione batch non bloccante.

Pipeline per immagine:
1. Crop + resize (Pillow) -> file intermedio in cartella temp
2. (opzionale) Upscaling AI (Real-ESRGAN) -> file finale
3. Se upscaling disabilitato, il file intermedio diventa il finale
"""

from __future__ import annotations

import os
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from typing import List

from PySide6.QtCore import QObject, Signal
from PIL import Image

from .cropper import CropSettings, Anchor, process_image
from .upscaler import UpscaleSettings, upscale


@dataclass
class BatchJob:
    """Descrive un job batch completo."""
    inputs: List[str] = field(default_factory=list)
    output_dir: str = ""
    crop_settings: CropSettings = field(default_factory=CropSettings)
    upscale_settings: UpscaleSettings = field(default_factory=UpscaleSettings)
    keep_filenames: bool = True
    suffix: str = ""
    # Modalità in-place: sovrascrive gli originali mantenendo nome+estensione.
    # Backup automatico in ZIP (game/imageforge_backup.zip) prima di elaborare.
    in_place: bool = False
    backup_zip_path: str = ""  # path del ZIP di backup (auto-calcolato se vuoto)


@dataclass
class JobResult:
    input_path: str
    output_path: str
    final_size: tuple
    status: str  # "ok" | "error"
    error: str = ""


class BatchWorker(QObject):
    """Esegue il batch in background. Usa QThread esterno + moveToThread."""

    progress = Signal(int, int, str)  # done, total, current_file
    file_done = Signal(object)  # JobResult
    log = Signal(str)
    finished = Signal(list)  # list[JobResult]
    error = Signal(str)

    def __init__(self, job: BatchJob):
        super().__init__()
        self.job = job
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def _compute_output_path(self, src: str, name: str, out_ext: str) -> str:
        """Calcola il path di output per un'immagine.

        Se in_place: path originale con estensione di output (mantiene nome
        e cartella). Altrimenti: output_dir/name.ext.
        """
        if self.job.in_place:
            # Mantieni nome e cartella originali, cambia solo estensione
            base, _ = os.path.splitext(src)
            return f"{base}.{out_ext}"
        return os.path.join(self.job.output_dir, f"{name}.{out_ext}")

    @staticmethod
    def _read_image_size(path: str) -> tuple[int, int]:
        """Legge le dimensioni di un'immagine senza caricarla tutta."""
        try:
            with Image.open(path) as img:
                return img.size
        except Exception:
            return (0, 0)

    def _compute_game_dir(self) -> str:
        """Trova la directory game/ dagli input (per path relativi nei log)."""
        if not self.job.inputs:
            return ""
        p = os.path.abspath(self.job.inputs[0])
        parts = p.split(os.sep)
        for i, part in enumerate(parts):
            if part == "game":
                return os.sep.join(parts[:i + 1])
        return os.path.dirname(p)

    def _compute_backup_zip_path(self) -> str:
        """Calcola automaticamente il path del ZIP di backup.

        Cerca la directory game/ (parent comune degli input che contiene
        'game' nel path) e mette il ZIP lì. Fallback: directory del primo input.
        """
        if self.job.backup_zip_path:
            return self.job.backup_zip_path
        game_dir = self._compute_game_dir()
        if game_dir:
            return os.path.join(game_dir, "imageforge_backup.zip")
        # Fallback: directory del primo input
        p = os.path.abspath(self.job.inputs[0]) if self.job.inputs else ""
        return os.path.join(os.path.dirname(p), "imageforge_backup.zip")

    def _backup_to_zip(self):
        """Crea un ZIP con tutti gli originali prima di elaborare.

        Mantiene la struttura relativa alla directory game/.
        Se esiste già un backup, lo preserva (non sovrascrive).
        """
        zip_path = self._compute_backup_zip_path()
        # Se esiste già, non sovrascrivere (preserva il primo backup)
        if os.path.exists(zip_path):
            self.log.emit(f"Backup esistente: {zip_path} (preservato)")
            return zip_path

        # Calcola la root per i path relativi nel ZIP
        zip_dir = os.path.dirname(zip_path)
        total = len(self.job.inputs)
        self.log.emit(f"Creazione backup ZIP di {total} immagini...")

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for i, src in enumerate(self.job.inputs):
                if self._cancel:
                    self.log.emit("Annullato durante il backup.")
                    return zip_path
                self.progress.emit(i, total * 2, f"backup {os.path.basename(src)}")
                # Path relativo alla directory del ZIP (game/)
                rel = os.path.relpath(src, zip_dir)
                zf.write(src, rel)

        self.log.emit(f"Backup completato: {zip_path}")
        return zip_path

    def run(self):
        results: List[JobResult] = []
        total = len(self.job.inputs)

        # Prepara cartelle
        if not self.job.in_place:
            os.makedirs(self.job.output_dir, exist_ok=True)

        # === FASE 0: backup automatico in ZIP prima di elaborare ===
        backup_zip = None
        if self.job.in_place:
            backup_zip = self._backup_to_zip()
            if self._cancel:
                self.finished.emit(results)
                return

        # Cartella temp per intermedi (sempre necessaria per in-place con
        # upscale, perché non possiamo sovrascrivere l'input mentre lo leggiamo)
        use_temp = self.job.upscale_settings.enabled or self.job.in_place
        tmpdir_ctx = tempfile.TemporaryDirectory(prefix="batchcropper_") if use_temp else None
        tmpdir = tmpdir_ctx.name if tmpdir_ctx else None

        try:
            for i, src in enumerate(self.job.inputs):
                if self._cancel:
                    self.log.emit("Annullato dall'utente.")
                    break

                basename = os.path.basename(src)
                name, _ = os.path.splitext(basename)
                if self.job.suffix and not self.job.in_place:
                    name = f"{name}{self.job.suffix}"

                # Progress: se c'è stato backup, mappa su seconda metà
                if self.job.in_place:
                    self.progress.emit(total + i, total * 2, basename)
                else:
                    self.progress.emit(i, total, basename)

                try:
                    if use_temp:
                        # Pipeline con upscaling AI (o in-place):
                        # 1. crop SOLO (no resize) -> intermedio png
                        # 2. upscale xN -> file temporaneo
                        # 3. resize finale + conversione -> output (in-place o dir)
                        crop_only = CropSettings(
                            aspect_ratio=self.job.crop_settings.aspect_ratio,
                            anchor=self.job.crop_settings.anchor,
                            resize_after=None,
                            output_format="png",
                            output_quality=self.job.crop_settings.output_quality,
                        )
                        inter_path = os.path.join(tmpdir, f"{name}_crop.png")
                        process_image(src, inter_path, crop_only)

                        # === SMART UPSCALE ===
                        # Decide se usare AI o solo LANCZOS in base al fattore
                        # di ingrandimento necessario rispetto al target finale.
                        final_target = self.job.crop_settings.resize_after
                        crop_w, crop_h = self._read_image_size(inter_path)
                        skip_upscale = False

                        if self.job.upscale_settings.enabled and final_target:
                            tw, th = final_target
                            # Fattore di scala richiesto (take the max dimension)
                            scale_needed = max(tw / crop_w, th / crop_h) if crop_w > 0 else 0
                            if scale_needed <= 1.0:
                                # Già sopra/uguale al target: solo resize (downscale)
                                self.log.emit(
                                    f"  skip AI: {crop_w}x{crop_h} >= target {tw}x{th}")
                                skip_upscale = True
                            elif scale_needed < 1.5:
                                # Fattore piccolo (<1.5x): AI non aiuta, anzi peggiora
                                # LANCZOS ad alta qualità è meglio per piccoli ingrandimenti
                                self.log.emit(
                                    f"  skip AI: fattore {scale_needed:.2f}x < 1.5x, "
                                    f"uso LANCZOS ({crop_w}x{crop_h} -> {tw}x{th})")
                                skip_upscale = True

                        if self.job.upscale_settings.enabled and not skip_upscale:
                            upscaled_path = os.path.join(tmpdir, f"{name}_up.png")
                            self.log.emit(
                                f"  AI upscale {basename} "
                                f"x{self.job.upscale_settings.scale}...")
                            upscale(inter_path, upscaled_path,
                                    self.job.upscale_settings,
                                    on_progress=lambda l: self.log.emit(f"    {l}"))
                            src_for_final = upscaled_path
                        else:
                            # Skip AI: usa direttamente il crop con resize LANCZOS
                            src_for_final = inter_path

                        # Step 3: resize finale + conversione formato output
                        if self.job.in_place:
                            # Mantieni estensione originale
                            out_ext = os.path.splitext(src)[1].lstrip(".")
                            if out_ext not in ("webp", "png", "jpg", "jpeg"):
                                out_ext = self.job.crop_settings.output_format
                        else:
                            out_ext = self.job.crop_settings.output_format

                        out_path = self._compute_output_path(src, name, out_ext)
                        final_settings = CropSettings(
                            aspect_ratio=None,
                            anchor=Anchor.CENTER,
                            resize_after=self.job.crop_settings.resize_after,
                            output_format=out_ext,
                            output_quality=self.job.crop_settings.output_quality,
                        )
                        final_size = process_image(src_for_final, out_path, final_settings)
                    else:
                        # Solo crop+resize -> file finale diretto in output_dir
                        out_ext = self.job.crop_settings.output_format
                        out_path = self._compute_output_path(src, name, out_ext)
                        self.log.emit(f"  crop {basename}...")
                        final_size = process_image(src, out_path, self.job.crop_settings)

                    rel_out = out_path
                    try:
                        rel_out = os.path.relpath(out_path, self._compute_game_dir())
                    except Exception:
                        pass
                    self.log.emit(f"  -> output: {rel_out} ({final_size[0]}x{final_size[1]})")

                    results.append(JobResult(src, out_path, final_size, "ok"))
                    self.file_done.emit(results[-1])
                except Exception as e:  # noqa: BLE001
                    self.log.emit(f"  ERRORE {basename}: {e}")
                    results.append(JobResult(src, "", (0, 0), "error", str(e)))
                    self.file_done.emit(results[-1])

                # Progress finale: mappa su seconda metà se c'è backup
                if self.job.in_place:
                    self.progress.emit(total + i + 1, total * 2, basename)
                else:
                    self.progress.emit(i + 1, total, basename)
        except Exception as e:  # noqa: BLE001
            self.error.emit(str(e))
        finally:
            if tmpdir_ctx is not None:
                tmpdir_ctx.cleanup()
            self.finished.emit(results)
