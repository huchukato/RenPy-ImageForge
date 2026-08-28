"""Internationalization for RenPy ImageForge.

Simple dict-based translation system with 3 languages: English (default),
Italian, Spanish. Usage:

    from .i18n import tr, set_language, LANGUAGES

    set_language("it")
    label = QLabel(tr("input_images"))
"""

from __future__ import annotations

import locale
import os

# ---------------------------------------------------------------------------
# Supported languages
# ---------------------------------------------------------------------------

LANGUAGES = {
    "en": "English",
    "it": "Italiano",
    "es": "Español",
}

DEFAULT_LANG = "en"
_current_lang = DEFAULT_LANG


def detect_system_language() -> str:
    """Detect the system language and map to a supported one."""
    try:
        loc = locale.getlocale()[0] or os.environ.get("LANG", "")
    except Exception:
        loc = os.environ.get("LANG", "")
    loc = loc.lower().replace("_", "-")
    for code in LANGUAGES:
        if loc.startswith(code):
            return code
    return DEFAULT_LANG


def set_language(code: str):
    """Set the current language code (en, it, es)."""
    global _current_lang
    if code in LANGUAGES:
        _current_lang = code


def get_language() -> str:
    return _current_lang


def tr(key: str, **kwargs) -> str:
    """Translate a key to the current language.

    Supports format kwargs: tr("added_n_images", n=5)
    """
    table = _TRANSLATIONS.get(_current_lang, _TRANSLATIONS[DEFAULT_LANG])
    s = table.get(key, _TRANSLATIONS[DEFAULT_LANG].get(key, key))
    if kwargs:
        try:
            s = s.format(**kwargs)
        except Exception:
            pass
    return s


# ---------------------------------------------------------------------------
# Translation tables
# ---------------------------------------------------------------------------

# Each key maps to {lang: text}. English is the reference.
# Format placeholders: {n}, {path}, {name}, {w}, {h}, {ok}, {fail}, etc.

_TRANSLATIONS: dict[str, dict[str, str]] = {
    # =====================================================================
    # ENGLISH (default)
    # =====================================================================
    "en": {
        # --- Main window ---
        "input_images": "Input images:",
        "add_file": "+ File",
        "add_folder": "+ Folder",
        "renpy_btn": "Ren'Py",
        "renpy_btn_tip": "Open a Ren'Py game (.app or folder), extract it and scan game images",
        "remove_selected": "- Remove",
        "clear": "Clear",
        "crop_preview": "Crop preview:",
        "start_processing": "\u25b6  Start processing",
        "cancel": "Cancel",
        "restore_backup": "\u27f2 Restore Backup",
        "restore_backup_tip": "Restore original images from the ZIP backup\n(game/imageforge_backup.zip)",
        "status_ready": "Ready. Drag images or use File > Add files.",
        "status_processing": "Processing: {name} ({done}/{total})",
        "status_done": "Done: {ok} OK, {fail} failed.",

        # --- Menu ---
        "menu_file": "File",
        "menu_help": "Help",
        "menu_add_files": "Add files...",
        "menu_add_folder": "Add folder...",
        "menu_open_renpy": "Open Ren'Py game...",
        "menu_clear_list": "Clear list",
        "menu_quit": "Quit",
        "menu_about": "About...",
        "menu_language": "Language",

        # --- Dialogs ---
        "select_images": "Select images",
        "images_filter": "Images ({exts})",
        "select_folder": "Select folder",
        "select_dest_folder": "Destination folder",
        "no_images": "No images",
        "no_images_msg": "Add at least one image to the list.",
        "invalid_folder": "Invalid folder",
        "invalid_folder_msg": "The destination folder does not exist:\n{path}",
        "added_n_from_folder": "Added {n} images from {path}",
        "added_n_from_renpy": "Added {n} images from Ren'Py game",
        "cancel_requested": "Cancel requested...",
        "batch_start_inplace": "\n=== Batch start: {n} images (IN-PLACE, automatic ZIP backup) ===",
        "batch_start_outdir": "\n=== Batch start: {n} images -> {path} ===",
        "upscale_info": "AI upscaling: x{scale} model={model}",
        "done_ok_fail": "=== Complete: {ok} OK, {fail} failed ===",
        "done_inplace_msg": "Processed {ok} images (originals overwritten in-place).\nZIP backup created in game/.",
        "done_outdir_msg": "Processed {ok} images successfully in:\n{path}",
        "done_title": "Done",
        "done_with_errors": "Completed with errors",
        "done_with_errors_msg": "OK: {ok}\nFailed: {fail}\nSee log for details.",

        # --- Restore backup ---
        "restore_select": "Select the game .app or the backup ZIP",
        "restore_filter": "Ren'Py game (*.app);;Backup ZIP (imageforge_backup.zip);;All files (*.*)",
        "restore_or_folder": "Or select the game/ folder",
        "restore_not_found": "Backup not found",
        "restore_not_found_msg": "Cannot find imageforge_backup.zip in:\n{path}\n\nMake sure the backup exists.",
        "restore_confirm": "Confirm restore",
        "restore_confirm_msg": "Restore original images from backup?\n\nBackup: {zip}\nDestination: {dest}\n\nCurrent images will be overwritten with the originals.",
        "restore_start": "\n=== Restoring backup from {path} ===",
        "restore_extracting": "Extracting {n} files...",
        "restore_done": "Restore complete: {n} images restored.",
        "restore_done_title": "Restore complete",
        "restore_done_msg": "{n} original images restored successfully.\nFrom: {zip}",
        "restore_error": "Restore error: {e}",
        "restore_error_title": "Error",
        "restore_error_msg": "Error during restore:\n{e}",

        # --- File done log ---
        "log_ok": "  OK: {name} ({w}x{h})",
        "log_failed": "  FAILED: {name} - {error}",
        "log_error": "[ERROR] {msg}",

        # --- About ---
        "about_text": "<h3>RenPy ImageForge v{version}</h3>"
                      "<p>Cross-platform tool for batch image cropping with fixed aspect ratio, "
                      "resizing, AI upscaling (Real-ESRGAN ncnn/Vulkan) and Ren'Py game integration.</p>"
                      "<p>Python {pyver} \u00b7 {machine}</p>"
                      "<pre style='color:#8a7a64;font-size:10px'>{status}</pre>",

        # --- Settings panel ---
        "preset_group": "Quick preset",
        "preset_1080p_tip": "Crop 16:9 + AI upscale x2 + resize 1920x1080\nPipeline: crop -> upscale -> resize to exact target",
        "preset_1440p_tip": "Crop 16:9 + AI upscale x2 + resize 2560x1440",
        "preset_4k_tip": "Crop 16:9 + AI upscale x3 + resize 3840x2160",
        "pipeline_note": "Pipeline: <b>crop</b> (aspect ratio) &rarr; <b>AI upscale</b> (x2/x3/x4) "
                         "&rarr; <b>final resize</b> to exact target.\n"
                         "AI goes above target, downscale preserves detail.",
        "crop_group": "Crop",
        "aspect_none": "None (no crop)",
        "aspect_custom": "Custom...",
        "aspect_ratio": "Aspect ratio:",
        "custom_wh": "Custom W:H:",
        "anchor_pos": "Anchor:",
        "resize_group": "Final resize (after crop)",
        "enable_resize": "Enable resize",
        "dimension_auto": "Size (auto=proportional):",
        "keep_ratio": "Keep aspect ratio (auto height)",
        "output_group": "Output",
        "format": "Format:",
        "quality": "Quality:",
        "suffix_name": "Name suffix:",
        "suffix_placeholder": "(none)",
        "inplace_check": "Overwrite originals (in-place)\nKeeps name and location \u2014 ideal for Ren'Py",
        "inplace_tip": "Saves each processed image to the same path as the original,\n"
                       "keeping name and extension. Game code keeps working\n"
                       "without modifications. Creates a backup before overwriting.",
        "backup_label": "Automatic backup: ZIP in game/imageforge_backup.zip\n(Ren'Py doesn't read .zip, safe)",
        "dest_placeholder": "Destination folder...",
        "browse": "Browse...",
        "destination": "Destination:",
        "upscale_group": "AI Upscaling (Real-ESRGAN)",
        "enable_upscale": "Enable upscaling after crop",
        "scale": "Scale:",
        "model": "Model:",
        "tile_size": "Tile size:",
        "tta": "TTA (better quality, slower)",

        # --- Ren'Py dialog ---
        "renpy_dialog_title": "RenPy ImageForge \u2014 Open Ren'Py game",
        "renpy_game_group": "Ren'Py game",
        "renpy_no_game": "No game selected",
        "renpy_browse": "Browse...",
        "renpy_scan": "Scan",
        "renpy_target_group": "Resolution target",
        "renpy_consider_fullhd": "Consider 'full HD':",
        "renpy_unren_warn": "\u26a0 UnRen Tools not found. Set UNREN_TOOLS_DIR.",
        "renpy_images_group": "Game images found",
        "renpy_filter": "Filter:",
        "renpy_filter_process": "To process (below full-HD, no UI)",
        "renpy_filter_all": "All",
        "renpy_filter_below": "Only non-full-HD (below)",
        "renpy_filter_above": "Only non-full-HD (above)",
        "renpy_filter_all_nonhd": "Only non-full-HD (all)",
        "renpy_filter_fullhd": "Only full HD",
        "renpy_filter_ui": "Only UI/buttons",
        "renpy_filter_unknown": "Unknown resolution",
        "renpy_select_visible": "Select visible",
        "renpy_count": "{n} images",
        "renpy_col_name": "Name",
        "renpy_col_file": "File",
        "renpy_col_res": "Resolution",
        "renpy_col_status": "Status",
        "renpy_col_ref": "Ref.",
        "renpy_col_uses": "Uses",
        "renpy_add_selected": "Add selected to batch list",
        "renpy_close": "Close",
        "renpy_select_title": "Select Ren'Py game (.app or folder)",
        "renpy_select_filter": "Mac application (*.app);;All files (*)",
        "renpy_or_folder": "Or select a folder",
        "renpy_phase": "Phase: {name}",
        "renpy_scan_done": "Scan complete",
        "renpy_error": "Error",
        "renpy_no_selection": "No selection",
        "renpy_no_selection_msg": "Select at least one image.",
        "renpy_added_n": "Added {n} images to batch list.",
        "renpy_visible_total": "{visible} visible / {total} total",
        "renpy_ref_yes": "yes",
        "renpy_ref_no": "no",

        # --- Scan worker phases ---
        "phase_extract_rpa": "Extracting .rpa archives",
        "phase_decompile_rpyc": "Decompiling .rpyc files",
        "phase_scan_images": "Scanning images",
        "phase_cancelled": "Cancelled",
        "phase_game_dir": "Game dir: {path}",
        "phase_game_not_found": "Game directory not found: {path}",
        "phase_extract_failed": ".rpa extraction failed",
        "phase_decompile_failed": ".rpyc decompilation failed",

        # --- Worker log messages ---
        "worker_backup_exists": "Existing backup: {path} (preserved)",
        "worker_backup_start": "Creating ZIP backup of {n} images...",
        "worker_backup_cancelled": "Cancelled during backup.",
        "worker_backup_done": "Backup complete: {path}",
        "worker_cancelled": "Cancelled by user.",
        "worker_skip_ai_above": "  skip AI: {w}x{h} >= target {tw}x{th}",
        "worker_skip_ai_small": "  skip AI: factor {factor:.2f}x < 1.5x, using LANCZOS ({w}x{h} -> {tw}x{th})",
        "worker_ai_upscale": "  AI upscale {name} x{scale}...",
        "worker_crop": "  crop {name}...",
        "worker_output": "  -> output: {path} ({w}x{h})",
        "worker_error": "  ERROR {name}: {e}",
    },

    # =====================================================================
    # ITALIANO
    # =====================================================================
    "it": {
        # --- Main window ---
        "input_images": "Immagini in input:",
        "add_file": "+ File",
        "add_folder": "+ Cartella",
        "renpy_btn": "Ren'Py",
        "renpy_btn_tip": "Apri un gioco Ren'Py (.app o cartella), estrailo e scansiona le immagini di gioco",
        "remove_selected": "- Rimuovi",
        "clear": "Pulisci",
        "crop_preview": "Anteprima crop:",
        "start_processing": "\u25b6  Avvia elaborazione",
        "cancel": "Annulla",
        "restore_backup": "\u27f2 Restore Backup",
        "restore_backup_tip": "Ripristina le immagini originali dal backup ZIP\n(game/imageforge_backup.zip)",
        "status_ready": "Pronto. Trascina immagini o usa File > Aggiungi file.",
        "status_processing": "Elaborazione: {name} ({done}/{total})",
        "status_done": "Completato: {ok} OK, {fail} falliti.",

        # --- Menu ---
        "menu_file": "File",
        "menu_help": "Aiuto",
        "menu_add_files": "Aggiungi file...",
        "menu_add_folder": "Aggiungi cartella...",
        "menu_open_renpy": "Apri gioco Ren'Py...",
        "menu_clear_list": "Pulisci lista",
        "menu_quit": "Esci",
        "menu_about": "Informazioni...",
        "menu_language": "Lingua",

        # --- Dialogs ---
        "select_images": "Seleziona immagini",
        "images_filter": "Immagini ({exts})",
        "select_folder": "Seleziona cartella",
        "select_dest_folder": "Cartella di destinazione",
        "no_images": "Nessuna immagine",
        "no_images_msg": "Aggiungi almeno un'immagine alla lista.",
        "invalid_folder": "Cartella non valida",
        "invalid_folder_msg": "La cartella di destinazione non esiste:\n{path}",
        "added_n_from_folder": "Aggiunte {n} immagini da {path}",
        "added_n_from_renpy": "Aggiunte {n} immagini dal gioco Ren'Py",
        "cancel_requested": "Annullamento richiesto...",
        "batch_start_inplace": "\n=== Avvio batch: {n} immagini (IN-PLACE, backup automatico ZIP) ===",
        "batch_start_outdir": "\n=== Avvio batch: {n} immagini -> {path} ===",
        "upscale_info": "Upscaling AI: x{scale} modello={model}",
        "done_ok_fail": "=== Completato: {ok} OK, {fail} falliti ===",
        "done_inplace_msg": "Elaborate {ok} immagini (originali sovrascritti in-place).\nBackup ZIP creato in game/.",
        "done_outdir_msg": "Elaborate {ok} immagini con successo in:\n{path}",
        "done_title": "Fatto",
        "done_with_errors": "Completato con errori",
        "done_with_errors_msg": "OK: {ok}\nFalliti: {fail}\nVedi log per dettagli.",

        # --- Restore backup ---
        "restore_select": "Seleziona il gioco .app o il backup ZIP",
        "restore_filter": "Gioco Ren'Py (*.app);;Backup ZIP (imageforge_backup.zip);;Tutti i file (*.*)",
        "restore_or_folder": "Oppure seleziona la cartella game/",
        "restore_not_found": "Backup non trovato",
        "restore_not_found_msg": "Impossibile trovare imageforge_backup.zip in:\n{path}\n\nAssicurati che il backup esista.",
        "restore_confirm": "Conferma ripristino",
        "restore_confirm_msg": "Ripristinare le immagini originali dal backup?\n\nBackup: {zip}\nDestinazione: {dest}\n\nLe immagini attuali verranno sovrascritte con gli originali.",
        "restore_start": "\n=== Ripristino backup da {path} ===",
        "restore_extracting": "Estrazione di {n} file...",
        "restore_done": "Ripristino completato: {n} immagini ripristinate.",
        "restore_done_title": "Ripristino completato",
        "restore_done_msg": "{n} immagini originali ripristinate con successo.\nDa: {zip}",
        "restore_error": "Errore ripristino: {e}",
        "restore_error_title": "Errore",
        "restore_error_msg": "Errore durante il ripristino:\n{e}",

        # --- File done log ---
        "log_ok": "  OK: {name} ({w}x{h})",
        "log_failed": "  FALLITO: {name} - {error}",
        "log_error": "[ERRORE] {msg}",

        # --- About ---
        "about_text": "<h3>RenPy ImageForge v{version}</h3>"
                      "<p>Tool multipiattaforma per crop batch con aspect ratio fisso, "
                      "resize, upscaling AI (Real-ESRGAN ncnn/Vulkan) e integrazione giochi Ren'Py.</p>"
                      "<p>Python {pyver} \u00b7 {machine}</p>"
                      "<pre style='color:#8a7a64;font-size:10px'>{status}</pre>",

        # --- Settings panel ---
        "preset_group": "Preset rapido",
        "preset_1080p_tip": "Crop 16:9 + upscale AI x2 + resize 1920x1080\nPipeline: crop -> upscale -> resize al target esatto",
        "preset_1440p_tip": "Crop 16:9 + upscale AI x2 + resize 2560x1440",
        "preset_4k_tip": "Crop 16:9 + upscale AI x3 + resize 3840x2160",
        "pipeline_note": "Pipeline: <b>crop</b> (aspect ratio) &rarr; <b>upscale AI</b> (x2/x3/x4) "
                         "&rarr; <b>resize finale</b> al target esatto.\n"
                         "L'AI porta sopra il target, il resize down conserva il dettaglio.",
        "crop_group": "Crop",
        "aspect_none": "Nessuno (no crop)",
        "aspect_custom": "Custom...",
        "aspect_ratio": "Aspect ratio:",
        "custom_wh": "Custom W:H:",
        "anchor_pos": "Posizione:",
        "resize_group": "Resize finale (dopo crop)",
        "enable_resize": "Abilita resize",
        "dimension_auto": "Dimensione (auto=proporzionale):",
        "keep_ratio": "Mantieni proporzioni (auto altezza)",
        "output_group": "Output",
        "format": "Formato:",
        "quality": "Qualit\u00e0:",
        "suffix_name": "Suffisso nome:",
        "suffix_placeholder": "(nessuno)",
        "inplace_check": "Sovrascrivi originali (in-place)\nMantiene nome e posizione \u2014 ideale per Ren'Py",
        "inplace_tip": "Salta ogni immagine processata nello stesso path dell'originale,\n"
                       "mantenendo nome ed estensione. Il codice del gioco continua a\n"
                       "funzionare senza modifiche. Crea un backup prima di sovrascrivere.",
        "backup_label": "Backup automatico: ZIP in game/imageforge_backup.zip\n(Ren'Py non legge i .zip, sicuro)",
        "dest_placeholder": "Cartella di destinazione...",
        "browse": "Sfoglia...",
        "destination": "Destinazione:",
        "upscale_group": "Upscaling AI (Real-ESRGAN)",
        "enable_upscale": "Abilita upscaling dopo crop",
        "scale": "Scala:",
        "model": "Modello:",
        "tile_size": "Tile size:",
        "tta": "TTA (pi\u00f9 qualit\u00e0, pi\u00f9 lento)",

        # --- Ren'Py dialog ---
        "renpy_dialog_title": "RenPy ImageForge \u2014 Apri gioco Ren'Py",
        "renpy_game_group": "Gioco Ren'Py",
        "renpy_no_game": "Nessun gioco selezionato",
        "renpy_browse": "Sfoglia...",
        "renpy_scan": "Scansiona",
        "renpy_target_group": "Target risoluzione",
        "renpy_consider_fullhd": "Considera 'full HD':",
        "renpy_unren_warn": "\u26a0 UnRen Tools non trovati. Imposta UNREN_TOOLS_DIR.",
        "renpy_images_group": "Immagini di gioco trovate",
        "renpy_filter": "Filtra:",
        "renpy_filter_process": "Da elaborare (sotto full-HD, no UI)",
        "renpy_filter_all": "Tutte",
        "renpy_filter_below": "Solo non-full-HD (sotto)",
        "renpy_filter_above": "Solo non-full-HD (sopra)",
        "renpy_filter_all_nonhd": "Solo non-full-HD (tutte)",
        "renpy_filter_fullhd": "Solo full HD",
        "renpy_filter_ui": "Solo UI/bottoni",
        "renpy_filter_unknown": "Risoluzione sconosciuta",
        "renpy_select_visible": "Seleziona visibili",
        "renpy_count": "{n} immagini",
        "renpy_col_name": "Nome",
        "renpy_col_file": "File",
        "renpy_col_res": "Risoluzione",
        "renpy_col_status": "Stato",
        "renpy_col_ref": "Ref.",
        "renpy_col_uses": "Usi",
        "renpy_add_selected": "Aggiungi selezionate alla lista batch",
        "renpy_close": "Chiudi",
        "renpy_select_title": "Seleziona il gioco Ren'Py (.app o cartella)",
        "renpy_select_filter": "Applicazione Mac (*.app);;Tutti i file (*)",
        "renpy_or_folder": "Oppure seleziona una cartella",
        "renpy_phase": "Fase: {name}",
        "renpy_scan_done": "Scansione completata",
        "renpy_error": "Errore",
        "renpy_no_selection": "Nessuna selezione",
        "renpy_no_selection_msg": "Seleziona almeno un'immagine.",
        "renpy_added_n": "Aggiunte {n} immagini alla lista batch.",
        "renpy_visible_total": "{visible} visibili / {total} totali",
        "renpy_ref_yes": "s\u00ec",
        "renpy_ref_no": "no",

        # --- Scan worker phases ---
        "phase_extract_rpa": "Estrazione archivi .rpa",
        "phase_decompile_rpyc": "Decompilazione .rpyc",
        "phase_scan_images": "Scansione immagini",
        "phase_cancelled": "Annullato",
        "phase_game_dir": "Game dir: {path}",
        "phase_game_not_found": "Directory game non trovata: {path}",
        "phase_extract_failed": "Estrazione .rpa fallita",
        "phase_decompile_failed": "Decompilazione .rpyc fallita",

        # --- Worker log messages ---
        "worker_backup_exists": "Backup esistente: {path} (preservato)",
        "worker_backup_start": "Creazione backup ZIP di {n} immagini...",
        "worker_backup_cancelled": "Annullato durante il backup.",
        "worker_backup_done": "Backup completato: {path}",
        "worker_cancelled": "Annullato dall'utente.",
        "worker_skip_ai_above": "  skip AI: {w}x{h} >= target {tw}x{th}",
        "worker_skip_ai_small": "  skip AI: fattore {factor:.2f}x < 1.5x, uso LANCZOS ({w}x{h} -> {tw}x{th})",
        "worker_ai_upscale": "  AI upscale {name} x{scale}...",
        "worker_crop": "  crop {name}...",
        "worker_output": "  -> output: {path} ({w}x{h})",
        "worker_error": "  ERRORE {name}: {e}",
    },

    # =====================================================================
    # ESPAÑOL
    # =====================================================================
    "es": {
        # --- Main window ---
        "input_images": "Im\u00e1genes de entrada:",
        "add_file": "+ Archivo",
        "add_folder": "+ Carpeta",
        "renpy_btn": "Ren'Py",
        "renpy_btn_tip": "Abre un juego Ren'Py (.app o carpeta), extr\u00e1elo y escanea las im\u00e1genes del juego",
        "remove_selected": "- Quitar",
        "clear": "Limpiar",
        "crop_preview": "Vista previa de recorte:",
        "start_processing": "\u25b6  Iniciar procesado",
        "cancel": "Cancelar",
        "restore_backup": "\u27f2 Restaurar copia",
        "restore_backup_tip": "Restaura las im\u00e1genes originales desde la copia ZIP\n(game/imageforge_backup.zip)",
        "status_ready": "Listo. Arrastra im\u00e1genes o usa Archivo > A\u00f1adir archivos.",
        "status_processing": "Procesando: {name} ({done}/{total})",
        "status_done": "Completado: {ok} OK, {fail} fallidos.",

        # --- Menu ---
        "menu_file": "Archivo",
        "menu_help": "Ayuda",
        "menu_add_files": "A\u00f1adir archivos...",
        "menu_add_folder": "A\u00f1adir carpeta...",
        "menu_open_renpy": "Abrir juego Ren'Py...",
        "menu_clear_list": "Limpiar lista",
        "menu_quit": "Salir",
        "menu_about": "Acerca de...",
        "menu_language": "Idioma",

        # --- Dialogs ---
        "select_images": "Seleccionar im\u00e1genes",
        "images_filter": "Im\u00e1genes ({exts})",
        "select_folder": "Seleccionar carpeta",
        "select_dest_folder": "Carpeta de destino",
        "no_images": "Sin im\u00e1genes",
        "no_images_msg": "A\u00f1ade al menos una imagen a la lista.",
        "invalid_folder": "Carpeta no v\u00e1lida",
        "invalid_folder_msg": "La carpeta de destino no existe:\n{path}",
        "added_n_from_folder": "A\u00f1adidas {n} im\u00e1genes de {path}",
        "added_n_from_renpy": "A\u00f1adidas {n} im\u00e1genes del juego Ren'Py",
        "cancel_requested": "Cancelaci\u00f3n solicitada...",
        "batch_start_inplace": "\n=== Inicio batch: {n} im\u00e1genes (IN-PLACE, copia autom\u00e1tica ZIP) ===",
        "batch_start_outdir": "\n=== Inicio batch: {n} im\u00e1genes -> {path} ===",
        "upscale_info": "Upscaling IA: x{scale} modelo={model}",
        "done_ok_fail": "=== Completado: {ok} OK, {fail} fallidos ===",
        "done_inplace_msg": "Procesadas {ok} im\u00e1genes (originales sobrescritos in-place).\nCopia ZIP creada en game/.",
        "done_outdir_msg": "Procesadas {ok} im\u00e1genes con \u00e9xito en:\n{path}",
        "done_title": "Hecho",
        "done_with_errors": "Completado con errores",
        "done_with_errors_msg": "OK: {ok}\nFallidos: {fail}\nVer registro para detalles.",

        # --- Restore backup ---
        "restore_select": "Selecciona el juego .app o la copia ZIP",
        "restore_filter": "Juego Ren'Py (*.app);;Copia ZIP (imageforge_backup.zip);;Todos los archivos (*.*)",
        "restore_or_folder": "O selecciona la carpeta game/",
        "restore_not_found": "Copia no encontrada",
        "restore_not_found_msg": "No se puede encontrar imageforge_backup.zip en:\n{path}\n\nAseg\u00farate de que la copia exista.",
        "restore_confirm": "Confirmar restauraci\u00f3n",
        "restore_confirm_msg": "\u00bfRestaurar las im\u00e1genes originales desde la copia?\n\nCopia: {zip}\nDestino: {dest}\n\nLas im\u00e1genes actuales se sobrescribir\u00e1n con los originales.",
        "restore_start": "\n=== Restaurando copia desde {path} ===",
        "restore_extracting": "Extrayendo {n} archivos...",
        "restore_done": "Restauraci\u00f3n completada: {n} im\u00e1genes restauradas.",
        "restore_done_title": "Restauraci\u00f3n completada",
        "restore_done_msg": "{n} im\u00e1genes originales restauradas con \u00e9xito.\nDe: {zip}",
        "restore_error": "Error de restauraci\u00f3n: {e}",
        "restore_error_title": "Error",
        "restore_error_msg": "Error durante la restauraci\u00f3n:\n{e}",

        # --- File done log ---
        "log_ok": "  OK: {name} ({w}x{h})",
        "log_failed": "  FALLO: {name} - {error}",
        "log_error": "[ERROR] {msg}",

        # --- About ---
        "about_text": "<h3>RenPy ImageForge v{version}</h3>"
                      "<p>Herramienta multiplataforma para recorte por lotes con relaci\u00f3n de aspecto fija, "
                      "redimensionado, upscaling IA (Real-ESRGAN ncnn/Vulkan) e integraci\u00f3n con juegos Ren'Py.</p>"
                      "<p>Python {pyver} \u00b7 {machine}</p>"
                      "<pre style='color:#8a7a64;font-size:10px'>{status}</pre>",

        # --- Settings panel ---
        "preset_group": "Preset r\u00e1pido",
        "preset_1080p_tip": "Recorte 16:9 + IA upscale x2 + resize 1920x1080\nPipeline: recorte -> upscale -> resize al objetivo exacto",
        "preset_1440p_tip": "Recorte 16:9 + IA upscale x2 + resize 2560x1440",
        "preset_4k_tip": "Recorte 16:9 + IA upscale x3 + resize 3840x2160",
        "pipeline_note": "Pipeline: <b>recorte</b> (relaci\u00f3n de aspecto) &rarr; <b>IA upscale</b> (x2/x3/x4) "
                         "&rarr; <b>resize final</b> al objetivo exacto.\n"
                         "La IA sube por encima del objetivo, el downscale conserva el detalle.",
        "crop_group": "Recorte",
        "aspect_none": "Ninguno (sin recorte)",
        "aspect_custom": "Personalizado...",
        "aspect_ratio": "Relaci\u00f3n de aspecto:",
        "custom_wh": "Personalizado W:H:",
        "anchor_pos": "Posici\u00f3n:",
        "resize_group": "Resize final (despu\u00e9s de recorte)",
        "enable_resize": "Activar resize",
        "dimension_auto": "Tama\u00f1o (auto=proporcional):",
        "keep_ratio": "Mantener proporciones (auto altura)",
        "output_group": "Salida",
        "format": "Formato:",
        "quality": "Calidad:",
        "suffix_name": "Sufijo de nombre:",
        "suffix_placeholder": "(ninguno)",
        "inplace_check": "Sobrescribir originales (in-place)\nMantiene nombre y ubicaci\u00f3n \u2014 ideal para Ren'Py",
        "inplace_tip": "Guarda cada imagen procesada en la misma ruta que el original,\n"
                       "manteniendo nombre y extensi\u00f3n. El c\u00f3digo del juego sigue\n"
                       "funcionando sin cambios. Crea una copia antes de sobrescribir.",
        "backup_label": "Copia autom\u00e1tica: ZIP en game/imageforge_backup.zip\n(Ren'Py no lee .zip, seguro)",
        "dest_placeholder": "Carpeta de destino...",
        "browse": "Examinar...",
        "destination": "Destino:",
        "upscale_group": "Upscaling IA (Real-ESRGAN)",
        "enable_upscale": "Activar upscaling despu\u00e9s de recorte",
        "scale": "Escala:",
        "model": "Modelo:",
        "tile_size": "Tama\u00f1o de tile:",
        "tta": "TTA (mejor calidad, m\u00e1s lento)",

        # --- Ren'Py dialog ---
        "renpy_dialog_title": "RenPy ImageForge \u2014 Abrir juego Ren'Py",
        "renpy_game_group": "Juego Ren'Py",
        "renpy_no_game": "Ning\u00fan juego seleccionado",
        "renpy_browse": "Examinar...",
        "renpy_scan": "Escanear",
        "renpy_target_group": "Objetivo de resoluci\u00f3n",
        "renpy_consider_fullhd": "Considerar 'full HD':",
        "renpy_unren_warn": "\u26a0 UnRen Tools no encontrados. Establece UNREN_TOOLS_DIR.",
        "renpy_images_group": "Im\u00e1genes del juego encontradas",
        "renpy_filter": "Filtrar:",
        "renpy_filter_process": "A procesar (por debajo de full-HD, sin UI)",
        "renpy_filter_all": "Todas",
        "renpy_filter_below": "Solo no-full-HD (por debajo)",
        "renpy_filter_above": "Solo no-full-HD (por encima)",
        "renpy_filter_all_nonhd": "Solo no-full-HD (todas)",
        "renpy_filter_fullhd": "Solo full HD",
        "renpy_filter_ui": "Solo UI/botones",
        "renpy_filter_unknown": "Resoluci\u00f3n desconocida",
        "renpy_select_visible": "Seleccionar visibles",
        "renpy_count": "{n} im\u00e1genes",
        "renpy_col_name": "Nombre",
        "renpy_col_file": "Archivo",
        "renpy_col_res": "Resoluci\u00f3n",
        "renpy_col_status": "Estado",
        "renpy_col_ref": "Ref.",
        "renpy_col_uses": "Usos",
        "renpy_add_selected": "A\u00f1adir seleccionadas a la lista batch",
        "renpy_close": "Cerrar",
        "renpy_select_title": "Selecciona el juego Ren'Py (.app o carpeta)",
        "renpy_select_filter": "Aplicaci\u00f3n Mac (*.app);;Todos los archivos (*)",
        "renpy_or_folder": "O selecciona una carpeta",
        "renpy_phase": "Fase: {name}",
        "renpy_scan_done": "Escaneo completado",
        "renpy_error": "Error",
        "renpy_no_selection": "Sin selecci\u00f3n",
        "renpy_no_selection_msg": "Selecciona al menos una imagen.",
        "renpy_added_n": "A\u00f1adidas {n} im\u00e1genes a la lista batch.",
        "renpy_visible_total": "{visible} visibles / {total} total",
        "renpy_ref_yes": "s\u00ed",
        "renpy_ref_no": "no",

        # --- Scan worker phases ---
        "phase_extract_rpa": "Extrayendo archivos .rpa",
        "phase_decompile_rpyc": "Descompilando .rpyc",
        "phase_scan_images": "Escaneando im\u00e1genes",
        "phase_cancelled": "Cancelado",
        "phase_game_dir": "Dir del juego: {path}",
        "phase_game_not_found": "Directorio game no encontrado: {path}",
        "phase_extract_failed": "Extracci\u00f3n .rpa fallida",
        "phase_decompile_failed": "Descompilaci\u00f3n .rpyc fallida",

        # --- Worker log messages ---
        "worker_backup_exists": "Copia existente: {path} (preservada)",
        "worker_backup_start": "Creando copia ZIP de {n} im\u00e1genes...",
        "worker_backup_cancelled": "Cancelado durante la copia.",
        "worker_backup_done": "Copia completada: {path}",
        "worker_cancelled": "Cancelado por el usuario.",
        "worker_skip_ai_above": "  skip IA: {w}x{h} >= objetivo {tw}x{th}",
        "worker_skip_ai_small": "  skip IA: factor {factor:.2f}x < 1.5x, usando LANCZOS ({w}x{h} -> {tw}x{th})",
        "worker_ai_upscale": "  IA upscale {name} x{scale}...",
        "worker_crop": "  recorte {name}...",
        "worker_output": "  -> salida: {path} ({w}x{h})",
        "worker_error": "  ERROR {name}: {e}",
    },
}


# Initialize with system language
set_language(detect_system_language())
