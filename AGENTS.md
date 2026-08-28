# AGENTS.md — RenPy ImageForge

## Comandi

- **Avvio app**: `./start.sh` (usa uv, gestisce automaticamente venv + dipendenze)
- **Avvio manuale**: `uv run python -m batch_cropper`
- **Test sintassi**: `python3 -c "import ast,glob; [ast.parse(open(f).read(),f) for f in glob.glob('batch_cropper/**/*.py',recursive=True)]"`
- **Test crop (no GUI)**: vedi sezione sotto

## Architettura

- `batch_cropper/cropper.py`: logica pura crop/resize con Pillow. Nessuna dipendenza Qt.
  Testabile standalone.
- `batch_cropper/upscaler.py`: wrapper subprocess per `realesrgan-ncnn-vulkan`.
  Trova binario+modelli in `vendor/` o via env var.
- `batch_cropper/workers.py`: `BatchWorker(QObject)` + `BatchJob` dataclass.
  Pipeline: crop -> (upscale AI) -> (resize finale). Usa QThread esterno.
- `batch_cropper/app.py`: `MainWindow` + `FileListWidget` (drag&drop).
- `batch_cropper/widgets/`: `CropPreviewWidget` (overlay crop) e `SettingsPanel`.

## Pipeline importante

Quando l'upscaling AI è attivo, il **resize finale NON va fatto prima** dell'upscaler
(altrimenti l'AI riceve un'immagine già ridimensionata). Ordine corretto:
1. crop (aspect ratio + anchor) -> intermedio PNG
2. upscale AI xN -> intermedio PNG
3. resize finale + conversione formato output -> file finale

## Real-ESRGAN su Apple Silicon

- Binario: `vendor/realesrgan-ncnn-vulkan/realesrgan-ncnn-vulkan` (v0.2.0 macOS)
- Modelli: `vendor/realesrgan-ncnn-vulkan/models/` (scaricati dalla release
  `realesrgan-ncnn-vulkan-20220424-macos.zip` del repo `xinntao/Real-ESRGAN`)
- Usa Metal via MoltenVK. Verificato funzionante su M2.
- CLI: `-i in -o out -s 2 -n realesr-animevideov3 -m models/ -f png`

## Test rapido pipeline (no GUI)

```python
from PIL import Image
from batch_cropper.cropper import CropSettings, Anchor, process_image
from batch_cropper.upscaler import UpscaleSettings, upscale
img = Image.new('RGB',(1620,1080),'#3366cc'); img.save('t.webp')
# crop 16:9 center
process_image('t.webp','c.png', CropSettings(aspect_ratio=(16,9), anchor=Anchor.CENTER, output_format='png'))
# upscale x2
upscale('c.png','u.png', UpscaleSettings(scale=2, model='realesr-animevideov3', output_format='png'))
# resize 1920x1080
process_image('u.png','f.webp', CropSettings(resize_after=(1920,1080), output_format='webp'))
```

## Convenzioni

- Italiano nei commenti utente / UI; codice in inglese.
- Tema Fusion scuro (QPalette in `app.py:main`).
- Font di sistema macOS: `.AppleSystemUIFont` (non "Sans").

## Modalità Ren'Py

- `batch_cropper/renpy.py`: estrazione .rpa (rpatool subprocess) + decompilazione
  .rpyc (unrpyc subprocess) + scansione .rpy per scene/show + lettura risoluzioni
  con PIL. Logica di scansione adattata da `RenPy-Fan-Video/fv_scanner.py`.
- `batch_cropper/widgets/renpy_dialog.py`: dialog con tabella immagini, filtri
  per risoluzione, selezione e invio alla lista batch.
- UnRen Tools path: `UNREN_TOOLS_DIR` env var, default
  `../RenPy-Fan-Video/UnRen Tools/UnRen Tools/`.
- Considera SOLO immagini referenziate in scene/show (no menu/UI/bottoni).
- Target full-HD configurabile nel dialog (default 1920x1080).
- Le immagini processate sovrascrivono gli originali in game/ (Ren'Py legge
  i file sciolti prima dei .rpa, non serve re-impackare).
