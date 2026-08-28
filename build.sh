#!/usr/bin/env bash
# Build RenPy ImageForge come .app macOS nativo con PyInstaller.
# Usa uv per gestire le dipendenze (incluse quelle di build).
set -euo pipefail
cd "$(dirname "$0")"

APP_NAME="RenPy ImageForge"
ICON_PATH="img/logo.icns"
VENDOR_DIR="vendor/realesrgan-ncnn-vulkan"

echo "=== RenPy ImageForge Build ==="
echo ""

# 1. Verifica dipendenze di build (pyinstaller) con uv
echo "[1/5] Verifica dipendenze di build..."
uv sync --extra build
echo "  OK"

# 2. Verifica icona
echo "[2/5] Verifica icona..."
if [ ! -f "$ICON_PATH" ]; then
    echo "  [warn] Icona non trovata: $ICON_PATH"
    ICON_ARG=""
else
    echo "  OK: $ICON_PATH"
    ICON_ARG="--icon=$ICON_PATH"
fi

# 3. Verifica vendor (Real-ESRGAN)
echo "[3/5] Verifica Real-ESRGAN..."
if [ ! -x "$VENDOR_DIR/realesrgan-ncnn-vulkan" ]; then
    echo "  [warn] Binario Real-ESRGAN non trovato in $VENDOR_DIR/"
    echo "  L'upscaling AI sara' disabilitato nell'app."
else
    echo "  OK: binario + modelli trovati"
fi

# 4. Pulizia build precedente
echo "[4/5] Pulizia build precedente..."
rm -rf build/ dist/ *.spec 2>/dev/null || true
echo "  OK"

# 5. Build con PyInstaller
echo "[5/5] Build con PyInstaller..."

# Crea entry point temporaneo (PyInstaller non supporta -m direttamente)
cat > _entry.py << 'ENTRYEOF'
from batch_cropper.__main__ import main
if __name__ == "__main__":
    main()
ENTRYEOF

uv run pyinstaller \
    --noconfirm \
    --clean \
    --windowed \
    --name "$APP_NAME" \
    $ICON_ARG \
    --add-data "batch_cropper:batch_cropper" \
    --add-data "img:img" \
    --add-data "${VENDOR_DIR}:${VENDOR_DIR}" \
    --hidden-import "pillow_heif" \
    --hidden-import "PySide6.QtCore" \
    --hidden-import "PySide6.QtGui" \
    --hidden-import "PySide6.QtWidgets" \
    _entry.py

# Pulisci entry point temporaneo
rm -f _entry.py

echo ""
echo "=== Build completata ==="
echo "App creata in: dist/${APP_NAME}.app"
echo ""
echo "Per avviarla:"
echo "  open \"dist/${APP_NAME}.app\""
echo ""
echo "Per distribuirla (opzionale, crea DMG):"
echo "  hdiutil create -volname \"${APP_NAME}\" -srcfolder \"dist/${APP_NAME}.app\" -ov -format UDZO \"dist/${APP_NAME}.dmg\""
