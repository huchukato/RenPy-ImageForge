# Changelog

All RenPy ImageForge releases with their respective release notes.

---

## v0.2.0 — 2026-08-28

First public release of RenPy ImageForge — cross-platform tool
(macOS, Linux, Windows) for batch image cropping, resizing, AI upscaling,
and Ren'Py game integration.

### Features

#### Batch image processing
- Crop with fixed aspect ratio (16:9, 16:10, 3:2, 4:3, 1:1, 9:16, 21:9, custom)
- Positional anchor on 3x3 grid (top-left, center, bottom-right, etc.)
- Final resize with proportional lock
- Supported formats: WebP, JPEG, PNG, TIFF, HEIC (read)
- Output formats: WebP, JPEG, PNG
- Configurable output quality (1-100, default 98)
- Optional suffix for generated files
- Live crop preview with overlay
- Pipeline: crop → (AI upscale) → final resize

#### AI Upscaling (Real-ESRGAN)
- Real-ESRGAN ncnn/Vulkan integration (Metal/MoltenVK on Apple Silicon)
- Models: realesrgan-x4plus (photorealistic, default), realesr-animevideov3, realesrgan-x4plus-anime
- Scale: x2, x3, x4
- **Smart Upscale**: automatically skips AI for small enlargements (factor < 1.5x) and uses only high-quality LANCZOS — avoids artifacts and detail loss
- Also skips AI for images already above the final target (downscale only)
- Binary + models bundled in `vendor/`

#### Ren'Py mode
- Ren'Py game selection (macOS .app or game/ folder)
- Automatic .rpa archive extraction (via rpatool)
- .rpyc decompilation (via unrpyc)
- .rpy scan for `scene`/`show` references
- Detection of **all** images on disk (not only referenced ones)
- "Ref." column indicating whether the image is used in scene/show
- Resolution reading with PIL
- Classification: full HD, below, above, unknown
- Automatic UI/button filtering (images below 800x400)
- Default filter: "To process (below full-HD, no UI)"
- Table with: name, file, resolution, status, ref., uses
- Filters: to process, all, below, above, full HD, UI, unknown
- Multi-selection and add to batch list
- Configurable full-HD target (default 1920x1080)

#### In-place processing (Ren'Py)
- Overwrites originals keeping name, extension and path
- Game code continues to work without modifications
- Preserves subfolder structure (images/P1/, images/P2/, etc.)
- **Automatic ZIP backup** before processing (`game/imageforge_backup.zip`)
  - Ren'Py does not read .zip files, safe
  - Preserves the first backup (does not overwrite if one exists)
- **Restore Backup** (panic button): restores original images by selecting the .app or the ZIP

#### Quick presets
- **Full HD 1080p**: crop 16:9 + smart upscale + resize 1920x1080
- **1440p**: crop 16:9 + AI upscale x2 + resize 2560x1440
- **4K UHD**: crop 16:9 + AI upscale x3 + resize 3840x2160

#### GUI
- PySide6 (Qt6) with dark Fusion theme
- Bronze/gold graphic theme inspired by the logo
- File and folder drag & drop
- Crop preview with overlay and pipeline dimensions
- Real-time log with output path for each file
- Progress bar with status
- Cancel processing
- Custom app icon (logo)

#### Infrastructure
- Cross-platform: macOS, Linux, Windows
- Launch with `uv` (automatic dependency and venv management)
- `start.sh` (macOS/Linux) and `start.bat` (Windows) to launch the app
- `build.sh` to create distributable packages
  - macOS: native .app + DMG
  - Linux: source + TAR.GZ (with start.sh)
  - Windows: source + ZIP (with start.bat)
- `pyproject.toml` with dependencies and metadata
- GitHub repo: https://github.com/huchukato/RenPy-ImageForge

### Bug fixes
- Fix `QThread: Destroyed while thread is still running` crash (Ren'Py dialog and batch worker)
- Fix undefined `_read_image_size` in workers.py (processing failed silently)
- Fix .app selection on macOS (file dialog instead of getExistingDirectory)
- Fix quality loss: default model changed from anime to photorealistic
- Fix quality loss: default WebP quality raised from 92 to 98
- Fix smart upscale: AI no longer used for factors < 1.5x (LANCZOS is better)

### Requirements
- macOS 11+ (Apple Silicon or Intel), Linux, or Windows 10+
- Python 3.10+ (managed by uv)
- [uv](https://docs.astral.sh/uv/) for launching
- Real-ESRGAN bundled in `vendor/` (no installation needed)

### Downloads
- macOS: `dist/RenPy-ImageForge-v0.2.0-macOS.dmg` (native .app)
- Linux: `dist/RenPy-ImageForge-v0.2.0-Linux.tar.gz` (source + start.sh)
- Windows: `dist/RenPy-ImageForge-v0.2.0-Windows.zip` (source + start.bat)
