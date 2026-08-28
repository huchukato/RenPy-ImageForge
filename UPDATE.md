# Changelog

Tutte le versioni di RenPy ImageForge con le relative note di rilascio.

---

## v0.2.0 — 2026-08-28

Prima release pubblica di RenPy ImageForge.

### Funzionalità

#### Batch processing immagini
- Crop con aspect ratio fisso (16:9, 16:10, 3:2, 4:3, 1:1, 9:16, 21:9, custom)
- Anchor posizionale su griglia 3x3 (top-left, center, bottom-right, ecc.)
- Resize finale con blocco proporzionale
- Formati supportati: WebP, JPEG, PNG, TIFF, HEIC (lettura)
- Formati output: WebP, JPEG, PNG
- Qualità output configurabile (1-100, default 98)
- Suffisso opzionale per i file generati
- Anteprima live del crop con overlay
- Pipeline: crop → (AI upscale) → resize finale

#### AI Upscaling (Real-ESRGAN)
- Integrazione Real-ESRGAN ncnn/Vulkan (Metal/MoltenVK su Apple Silicon)
- Modelli: realesrgan-x4plus (fotorealistico, default), realesr-animevideov3, realesrgan-x4plus-anime
- Scale: x2, x3, x4
- **Smart Upscale**: salta automaticamente l'AI per piccoli ingrandimenti (fattore < 1.5x) e usa solo LANCZOS ad alta qualità — evita artefatti e perdita di dettaglio
- Skip AI anche per immagini già sopra il target finale (solo downscale)
- Binario + modelli bundled in `vendor/`

#### Modalità Ren'Py
- Selezione giochi Ren'Py (.app macOS o cartella game/)
- Estrazione automatica archivi .rpa (via rpatool)
- Decompilazione .rpyc (via unrpyc)
- Scansione .rpy per riferimenti `scene`/`show`
- Individuazione di **tutte** le immagini su disco (non solo referenziate)
- Colonna "Ref." che indica se l'immagine è usata in scene/show
- Lettura risoluzioni con PIL
- Classificazione: full HD, sotto, sopra, sconosciuta
- Filtro automatico UI/bottoni (immagini sotto 800x400)
- Filtro default: "Da elaborare (sotto full-HD, no UI)"
- Tabella con: nome, file, risoluzione, stato, ref., usi
- Filtri: da elaborare, tutte, sotto, sopra, full HD, UI, sconosciute
- Selezione multipla e aggiunta alla lista batch
- Target full-HD configurabile (default 1920x1080)

#### Elaborazione in-place (Ren'Py)
- Sovrascrive gli originali mantenendo nome, estensione e percorso
- Il codice del gioco continua a funzionare senza modifiche
- Mantiene la struttura delle sottocartelle (images/P1/, images/P2/, ecc.)
- **Backup automatico in ZIP** prima dell'elaborazione (`game/imageforge_backup.zip`)
  - Ren'Py non legge i .zip, sicuro
  - Preserva il primo backup (non sovrascrive se esiste già)
- **Restore Backup** (panic button): ripristina le immagini originali selezionando il .app o lo ZIP

#### Preset rapidi
- **Full HD 1080p**: crop 16:9 + smart upscale + resize 1920x1080
- **1440p**: crop 16:9 + AI upscale x2 + resize 2560x1440
- **4K UHD**: crop 16:9 + AI upscale x3 + resize 3840x2160

#### GUI
- PySide6 (Qt6) con tema Fusion scuro
- Tema grafico bronzo/oro ispirato al logo
- Drag & drop file e cartelle
- Anteprima crop con overlay e dimensioni pipeline
- Log in tempo reale con path di output per ogni file
- Progress bar con stato
- Annulla elaborazione
- Icona app personalizzata (logo)

#### Infrastruttura
- Avvio con `uv` (gestione automatica dipendenze e venv)
- `start.sh` per avviare l'app
- `build.sh` per creare pacchetti distribuibili
  - macOS: .app + DMG + ZIP
  - Linux: binario + TAR.GZ
  - Windows: .exe + ZIP
  - Source: TAR.GZ + ZIP (cross-platform)
- `pyproject.toml` con dipendenze e metadata
- Repo GitHub: https://github.com/huchukato/RenPy-ImageForge

### Risoluzione problemi noti
- Fix crash `QThread: Destroyed while thread is still running` (dialog Ren'Py e worker batch)
- Fix bug `_read_image_size` non definito in workers.py (elaborazione falliva silenziosamente)
- Fix selezione .app su macOS (dialog file invece di getExistingDirectory)
- Fix perdita qualità: modello default cambiato da anime a fotorealistico
- Fix perdita qualità: qualità WebP default alzata da 92 a 98
- Fix smart upscale: AI non più usata per fattori < 1.5x (LANCZOS migliore)

### Requisiti
- macOS 11+ (Apple Silicon o Intel)
- Python 3.10+ (gestito da uv)
- [uv](https://docs.astral.sh/uv/) per l'avvio
- Real-ESRGAN bundled in `vendor/` (nessuna installazione necessaria)

### Download
- macOS DMG: `dist/RenPy ImageForge-macOS.dmg`
- macOS ZIP: `dist/RenPy ImageForge-macOS.zip`
- Sorgente: `dist/RenPy ImageForge-source.tar.gz` / `.zip`
