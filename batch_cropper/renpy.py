"""Integrazione Ren'Py: estrazione archivi, decompilazione, scansione immagini.

Riutilizza gli UnRen Tools dal progetto RenPy-Fan-Video:
  - rpatool per l'estrazione dei .rpa
  - unrpyc.py + decompiler/ per la decompilazione dei .rpyc

La logica di scansione (scene/show -> file su disco) è adattata da
fv_scanner.py del progetto RenPy-Fan-Video.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from PIL import Image

# pillow-heif per HEIC (opzionale)
try:
    import pillow_heif  # noqa: F401
    pillow_heif.register_heif_opener()
except Exception:
    pass


# --------------------------------------------------------------------------- #
# Configurazione path UnRen Tools
# --------------------------------------------------------------------------- #

# Default: cerca nel progetto RenPy-Fan-Video sibling
_DEFAULT_UNREN = Path(__file__).resolve().parent.parent.parent / "RenPy-Fan-Video" / "UnRen Tools" / "UnRen Tools"


def get_unren_tools_dir() -> Path:
    """Restituisce la directory degli UnRen Tools.

    Override via env var UNREN_TOOLS_DIR.
    """
    env = os.environ.get("UNREN_TOOLS_DIR")
    if env and Path(env).is_dir():
        return Path(env)
    return _DEFAULT_UNREN


def get_rpatool_path() -> Path:
    return get_unren_tools_dir() / "rpatool"


def get_unrpyc_path() -> Path:
    return get_unren_tools_dir() / "unrpyc.py"


def unren_tools_available() -> bool:
    d = get_unren_tools_dir()
    return d.is_dir() and get_rpatool_path().is_file() and get_unrpyc_path().is_file()


# --------------------------------------------------------------------------- #
# Risoluzione percorso gioco
# --------------------------------------------------------------------------- #

def find_game_dir(game_path: str | Path) -> Path:
    """Trova la directory `game` di un gioco Ren'Py.

    Supporta:
    - .app macOS: Game.app/Contents/Resources/autorun/game
    - Cartella con sub-dir `game`
    - Path già puntante a `game`
    """
    p = Path(game_path)
    if p.suffix == ".app":
        candidate = p / "Contents" / "Resources" / "autorun" / "game"
        if candidate.is_dir():
            return candidate
    game_sub = p / "game"
    if game_sub.is_dir():
        return game_sub
    # Assume sia già la game dir
    return p


# --------------------------------------------------------------------------- #
# Estrazione .rpa
# --------------------------------------------------------------------------- #

def extract_rpa_files(game_dir: Path,
                      log: Callable[[str], None] = print,
                      progress: Callable[[int, int], None] | None = None) -> bool:
    """Estrae tutti i .rpa nella game dir usando rpatool.

    Usa un marker (.rpa.extracted) per saltare file già estratti.
    Ritorna True se tutto OK.
    """
    rpa_files = sorted(game_dir.glob("*.rpa"))
    if not rpa_files:
        log("Nessun file .rpa trovato")
        return True

    log(f"Trovati {len(rpa_files)} file .rpa da estrarre")
    rpatool = get_rpatool_path()

    for i, rpa_file in enumerate(rpa_files):
        if progress:
            progress(i, len(rpa_files))

        marker = rpa_file.with_suffix(".rpa.extracted")
        if marker.exists():
            log(f"Già estratto, salto: {rpa_file.name}")
            continue

        log(f"Estrazione di {rpa_file.name}...")
        try:
            result = subprocess.run(
                [sys.executable, str(rpatool), "-x",
                 str(rpa_file), "-o", str(game_dir)],
                capture_output=True, text=True,
            )
            if result.returncode != 0:
                log(f"Errore estrazione {rpa_file.name}: {result.stderr}")
                return False
        except Exception as e:
            log(f"Errore: {e}")
            return False

        try:
            marker.touch()
            log(f"Estratto: {rpa_file.name}")
        except Exception:
            pass

    if progress:
        progress(len(rpa_files), len(rpa_files))
    log("Estrazione .rpa completata")
    return True


# --------------------------------------------------------------------------- #
# Decompilazione .rpyc
# --------------------------------------------------------------------------- #

def decompile_rpyc_files(game_dir: Path,
                         log: Callable[[str], None] = print,
                         progress: Callable[[int, int], None] | None = None) -> bool:
    """Decompila i .rpyc in .rpy usando unrpyc.

    Salta file di sistema (gui, screens, options, images) e file
    per cui esiste già un .rpy più recente.
    """
    rpyc_files = []
    for rpyc in game_dir.rglob("*.rpyc"):
        if any(x in rpyc.name.lower()
               for x in ["gui", "screens", "options", "images"]):
            continue
        rpy = rpyc.with_suffix(".rpy")
        if rpy.exists() and rpy.stat().st_mtime >= rpyc.stat().st_mtime:
            continue
        rpyc_files.append(rpyc)

    if not rpyc_files:
        log("Nessun file .rpyc da decompilare (già presenti)")
        return True

    log(f"Trovati {len(rpyc_files)} file .rpyc da decompilare")
    unrpyc = get_unrpyc_path()

    batch_size = 50
    for start in range(0, len(rpyc_files), batch_size):
        batch = rpyc_files[start:start + batch_size]
        if progress:
            progress(start + len(batch), len(rpyc_files))
        try:
            result = subprocess.run(
                [sys.executable, str(unrpyc), "-c"] + [str(f) for f in batch],
                capture_output=True, text=True, cwd=str(game_dir),
            )
            if result.returncode != 0:
                log(f"Errore decompilazione: {result.stderr[:200]}")
                return False
        except Exception as e:
            log(f"Errore: {e}")
            return False

    if progress:
        progress(len(rpyc_files), len(rpyc_files))
    log("Decompilazione .rpyc completata")
    return True


# --------------------------------------------------------------------------- #
# Scansione .rpy per riferimenti immagine
# --------------------------------------------------------------------------- #

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".avif", ".bmp", ".gif"}

SCENE_KEYWORDS = {
    "with", "at", "as", "behind", "expression", "onlayer", "zorder",
    "to", "from",
}

EXCLUDE_NAMES = {
    "black", "white", "bg", "background", "overlay", "text",
    "vbox", "hbox", "screen", "transform", "null", "solid",
    "imagebutton", "textbutton", "frame", "window", "viewport",
}

_RE_SCENE = re.compile(r"^(\s*)(scene|show)\s+(.+)$")
_RE_IMAGE_DEF = re.compile(r'^image\s+(.+?)\s*=\s*(.+)$')
_RE_MOVIE = re.compile(r"Movie\s*\(", re.IGNORECASE)
_RE_STRING = re.compile(r'"([^"]+)"')


@dataclass
class GameImage:
    """Immagine di gioco con risoluzione letta da PIL."""
    name: str                          # nome file (stem) o nome Ren'Py
    file_path: Path                    # file su disco
    width: int = 0
    height: int = 0
    is_full_hd: bool = False           # True se == target
    already_movie: bool = False        # True se esiste già def Movie
    used_in_count: int = 0             # quante volte referenziata in scene/show
    is_referenced: bool = False        # True se usata in scene/show
    is_ui_element: bool = False        # True se troppo piccola (UI/bottoni)

    # Soglia minima per considerare un'immagine "di gioco" (non UI)
    MIN_GAME_WIDTH = 800
    MIN_GAME_HEIGHT = 400

    @property
    def resolution_str(self) -> str:
        if self.width == 0 or self.height == 0:
            return "??"
        return f"{self.width}x{self.height}"

    @property
    def status(self) -> str:
        if self.width == 0:
            return "sconosciuta"
        if self.is_full_hd:
            return "full HD"
        if self.width > 1920 or self.height > 1080:
            return "sopra full HD"
        return "sotto full HD"


def _normalize(name: str) -> str:
    return name.strip().lower().replace(" ", "_")


def _build_file_index(images_dir: Path,
                      log: Callable[[str], None] = print,
                      progress: Callable[[int, int], None] | None = None
                      ) -> dict[str, Path]:
    """Indicizza i file immagine in game/images/ ricorsivamente."""
    index: dict[str, Path] = {}
    if not images_dir.is_dir():
        log(f"Directory immagini non trovata: {images_dir}")
        return index

    all_files = list(images_dir.rglob("*"))
    total = len(all_files)
    log(f"Indicizzazione di {total} file in {images_dir}...")

    for i, f in enumerate(all_files):
        if progress and (i % 500 == 0 or i == total - 1):
            progress(i + 1, total)
        if f.is_file() and f.suffix.lower() in IMAGE_EXTS:
            key = _normalize(f.stem)
            if key not in index:
                index[key] = f

    if progress:
        progress(total, total)
    log(f"Indicizzati {len(index)} file immagine")
    return index


def _parse_image_definitions(rpy_file: Path,
                             image_defs: dict, movie_defs: dict):
    """Estrae le definizioni `image <name> = ...` da un .rpy."""
    try:
        lines = rpy_file.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return

    for i, line in enumerate(lines, 1):
        if line.startswith((" ", "\t")):
            continue
        m = _RE_IMAGE_DEF.match(line)
        if not m:
            continue
        name = m.group(1).strip()
        value = m.group(2).strip()
        if "=" in name:
            continue
        if _RE_MOVIE.search(value):
            movie_defs[name] = (value, rpy_file, i)
        else:
            image_defs[name] = (value, rpy_file, i)


def _parse_scene_show(rpy_file: Path, usages: dict):
    """Estrae le istruzioni scene/show da un .rpy."""
    try:
        lines = rpy_file.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return

    for i, line in enumerate(lines, 1):
        m = _RE_SCENE.match(line)
        if not m:
            continue
        rest = m.group(3).strip()
        if rest.startswith("expression"):
            continue

        tokens = rest.split()
        name_tokens = []
        for tok in tokens:
            if tok in SCENE_KEYWORDS:
                break
            name_tokens.append(tok)
        if not name_tokens:
            continue

        name = " ".join(name_tokens)
        if name.lower() in EXCLUDE_NAMES:
            continue
        if name.startswith(("#", '"', "'", "$")):
            continue
        if any(c in name for c in "[]{}$"):
            continue

        usages.setdefault(name, []).append((rpy_file, i))


def _resolve_image_file(name: str, file_index: dict, image_defs: dict,
                        game_dir: Path, images_dir: Path) -> Path | None:
    """Risolve un nome immagine Ren'Py in un file su disco."""
    key = _normalize(name)
    if key in file_index:
        return file_index[key]

    if name in image_defs:
        def_text, _, _ = image_defs[name]
        match = _RE_STRING.search(def_text)
        if match:
            path_str = match.group(1)
            candidate = game_dir / path_str
            if candidate.exists():
                return candidate
            candidate2 = images_dir / path_str
            if candidate2.exists():
                return candidate2
    return None


def _read_image_size(path: Path) -> tuple[int, int]:
    """Legge le dimensioni di un'immagine senza caricarla tutta."""
    try:
        with Image.open(path) as img:
            return img.size
    except Exception:
        return (0, 0)


def scan_game_images(game_dir: Path,
                     log: Callable[[str], None] = print,
                     progress: Callable[[int, int, str], None] | None = None,
                     full_hd_target: tuple[int, int] = (1920, 1080)
                     ) -> list[GameImage]:
    """Pipeline completa: scansiona .rpy, risolve file, legge risoluzioni.

    Args:
        game_dir: directory `game` del gioco Ren'Py.
        log: callback per log testuale.
        progress: callback (current, total, phase_name).
        full_hd_target: risoluzione considerata "full HD" per il filtro.

    Returns:
        list[GameImage] ordinate per nome.
    """
    game_dir = Path(game_dir)
    images_dir = game_dir / "images"
    target_w, target_h = full_hd_target

    # Fase 1: raccogli .rpy (esclude file di sistema)
    if progress:
        progress(0, 1, "Raccolta file .rpy")
    rpy_files = [
        f for f in game_dir.rglob("*.rpy")
        if not any(x in f.name.lower()
                   for x in ["gui", "screens", "options",
                             "fan_videos", "fan_video_patch"])
    ]
    log(f"Trovati {len(rpy_files)} file .rpy da analizzare")

    # Fase 2: parse definizioni image
    if progress:
        progress(0, len(rpy_files), "Parse definizioni image")
    image_defs: dict[str, tuple[str, Path, int]] = {}
    movie_defs: dict[str, tuple[str, Path, int]] = {}
    for idx, rpy_file in enumerate(rpy_files):
        if progress:
            progress(idx, len(rpy_files), "Parse definizioni image")
        _parse_image_definitions(rpy_file, image_defs, movie_defs)

    # Fase 3: parse scene/show
    if progress:
        progress(0, len(rpy_files), "Parse scene/show")
    usages: dict[str, list[tuple[Path, int]]] = {}
    for idx, rpy_file in enumerate(rpy_files):
        if progress:
            progress(idx, len(rpy_files), "Parse scene/show")
        _parse_scene_show(rpy_file, usages)

    # Fase 4: build file index
    def _idx_progress(c, t):
        if progress:
            progress(c, t, "Indicizzazione file")
    file_index = _build_file_index(images_dir, log, _idx_progress)

    # Fase 5: scansiona TUTTI i file immagine su disco, marca i referenziati
    # Costruisce un set dei file referenziati per lookup rapido
    referenced_files: set[Path] = set()
    referenced_names: dict[Path, str] = {}  # file -> nome Ren'Py
    referenced_count: dict[Path, int] = {}
    for name, locations in usages.items():
        fp = _resolve_image_file(name, file_index, image_defs,
                                 game_dir, images_dir)
        if fp is not None:
            referenced_files.add(fp)
            referenced_names[fp] = name
            referenced_count[fp] = len(locations)

    # Tutti i file immagine su disco
    all_image_files = list(file_index.values())
    # Deduplica (l'indice potrebbe avere collisioni ma values() è unico per chiave)
    seen = set()
    unique_files = []
    for fp in all_image_files:
        rp = fp.resolve()
        if rp not in seen:
            seen.add(rp)
            unique_files.append(fp)

    n_total = len(unique_files)
    images: list[GameImage] = []
    for idx, file_path in enumerate(unique_files):
        if progress and (idx % 200 == 0 or idx == n_total - 1):
            progress(idx, n_total, "Lettura risoluzioni")

        w, h = _read_image_size(file_path)
        is_ref = file_path in referenced_files
        renpy_name = referenced_names.get(file_path, file_path.stem)
        # UI/bottoni: immagini troppo piccole (es. 200x50, 235x62)
        is_ui = (w > 0 and h > 0
                 and (w < GameImage.MIN_GAME_WIDTH
                      or h < GameImage.MIN_GAME_HEIGHT))
        images.append(GameImage(
            name=renpy_name,
            file_path=file_path,
            width=w,
            height=h,
            is_full_hd=(w == target_w and h == target_h),
            already_movie=(renpy_name in movie_defs) if is_ref else False,
            used_in_count=referenced_count.get(file_path, 0),
            is_referenced=is_ref,
            is_ui_element=is_ui,
        ))

    # Ordina: prima non-full-HD (da elaborare), poi per nome
    images.sort(key=lambda img: (img.is_full_hd, img.name.lower()))

    n_full_hd = sum(1 for img in images if img.is_full_hd)
    n_below = sum(1 for img in images if img.width > 0 and not img.is_full_hd
                  and img.width <= target_w and img.height <= target_h)
    n_above = sum(1 for img in images if img.width > target_w or img.height > target_h)
    n_unknown = sum(1 for img in images if img.width == 0)
    n_ref = sum(1 for img in images if img.is_referenced)
    log(f"Trovate {len(images)} immagini totali ({n_ref} referenziate): "
        f"{n_full_hd} full HD, {n_below} sotto, {n_above} sopra, {n_unknown} sconosciute")

    return images
