#!/usr/bin/env bash
# Build RenPy ImageForge: crea pacchetti per macOS, Linux e Windows.
#
# Nomi file generati (con versione letta da batch_cropper/__init__.py):
#   RenPy-ImageForge-v0.2.0-macOS.dmg        (installer macOS, buildato su macOS)
#   RenPy-ImageForge-v0.2.0-Linux.tar.gz     (sorgente per Linux, con start.sh)
#   RenPy-ImageForge-v0.2.0-Windows.zip      (sorgente per Windows, con start.bat)
#
# PyInstaller non puo' cross-compilare: ogni piattaforma va buildata
# sulla piattaforma stessa. I pacchetti sorgente sono cross-platform
# e funzionano ovunque sia installato uv + Python 3.10+.
#
# Uso:
#   ./build.sh              # build completa + pacchetti
#   ./build.sh --mac-only   # solo macOS (DMG)
#   ./build.sh --source     # solo distribuzioni sorgente (Linux + Windows)
set -euo pipefail
cd "$(dirname "$0")"

APP_NAME="RenPy ImageForge"
PKG_NAME="RenPy-ImageForge"
ICON_PATH="img/logo.icns"
VENDOR_DIR="vendor/realesrgan-ncnn-vulkan"
DIST_DIR="dist"
PLATFORM=$(uname -s)

# Legge la versione da batch_cropper/__init__.py
VERSION=$(python3 -c "from batch_cropper import __version__; print(__version__)")
echo "=== RenPy ImageForge Build ==="
echo "Versione: v${VERSION}"
echo "Piattaforma: $PLATFORM"
echo "Modalita': ${1:-all}"
echo ""

# Prefisso nome file: RenPy-ImageForge-v0.2.0-
PKG_PREFIX="${PKG_NAME}-v${VERSION}"

# ---------------------------------------------------------------------------
# 1. Dipendenze di build
# ---------------------------------------------------------------------------
echo "[1/6] Verifica dipendenze di build..."
uv sync --extra build
echo "  OK"

# ---------------------------------------------------------------------------
# 2. Verifica asset
# ---------------------------------------------------------------------------
echo "[2/6] Verifica asset..."
if [ -f "$ICON_PATH" ]; then
    echo "  Icona: OK"
else
    echo "  [warn] Icona non trovata: $ICON_PATH"
fi
if [ -x "$VENDOR_DIR/realesrgan-ncnn-vulkan" ]; then
    echo "  Real-ESRGAN: OK"
else
    echo "  [warn] Real-ESRGAN non trovato in $VENDOR_DIR/"
fi

# ---------------------------------------------------------------------------
# 3. Pulizia
# ---------------------------------------------------------------------------
echo "[3/6] Pulizia build precedente..."
rm -rf build/ "$DIST_DIR" *.spec _entry.py 2>/dev/null || true
mkdir -p "$DIST_DIR"
echo "  OK"

# ---------------------------------------------------------------------------
# 4. Build PyInstaller (piattaforma corrente)
# ---------------------------------------------------------------------------
build_pyinstaller() {
    echo "[4/6] Build PyInstaller..."

    # Entry point temporaneo
    cat > _entry.py << 'ENTRYEOF'
from batch_cropper.__main__ import main
if __name__ == "__main__":
    main()
ENTRYEOF

    # Argomenti comuni
    local COMMON_ARGS=(
        --noconfirm --clean --windowed
        --name "$APP_NAME"
        --add-data "batch_cropper:batch_cropper"
        --add-data "img:img"
        --add-data "${VENDOR_DIR}:${VENDOR_DIR}"
        --hidden-import "pillow_heif"
        --hidden-import "PySide6.QtCore"
        --hidden-import "PySide6.QtGui"
        --hidden-import "PySide6.QtWidgets"
        _entry.py
    )

    if [ "$PLATFORM" = "Darwin" ]; then
        # macOS: .app con icona
        if [ -f "$ICON_PATH" ]; then
            uv run pyinstaller "${COMMON_ARGS[@]}" "--icon=$ICON_PATH" \
                --osx-bundle-identifier "com.imageforge.renpy"
        else
            uv run pyinstaller "${COMMON_ARGS[@]}" \
                --osx-bundle-identifier "com.imageforge.renpy"
        fi
    elif [ "$PLATFORM" = "Linux" ]; then
        # Linux: directory standalone
        uv run pyinstaller "${COMMON_ARGS[@]}"
    else
        # Windows (MSYS/Git Bash): .exe
        # Su Windows il separatore --add-data e' ; non :
        local WIN_ARGS=()
        for arg in "${COMMON_ARGS[@]}"; do
            arg="${arg//:/;}"
            WIN_ARGS+=("$arg")
        done
        uv run pyinstaller "${WIN_ARGS[@]}"
    fi

    rm -f _entry.py
    echo "  OK"
}

# ---------------------------------------------------------------------------
# 5. Packaging per piattaforma
# ---------------------------------------------------------------------------
package_macos() {
    echo "[5/6] Packaging macOS..."

    local APP_PATH="$DIST_DIR/${APP_NAME}.app"

    # DMG (installer macOS)
    echo "  Creazione DMG..."
    local DMG_PATH="$DIST_DIR/${PKG_PREFIX}-macOS.dmg"
    hdiutil create -volname "$APP_NAME" \
        -srcfolder "$APP_PATH" \
        -ov -format UDZO \
        "$DMG_PATH" 2>/dev/null
    echo "  DMG: $DMG_PATH"
}

package_linux() {
    echo "[5/6] Packaging Linux..."

    local APP_PATH="$DIST_DIR/${APP_NAME}"

    # TAR.GZ (binario Linux)
    echo "  Creazione TAR.GZ..."
    local TAR_PATH="$DIST_DIR/${PKG_PREFIX}-Linux.tar.gz"
    cd "$DIST_DIR"
    tar -czf "${PKG_PREFIX}-Linux.tar.gz" "${APP_NAME}" 2>/dev/null
    cd ..
    echo "  TAR.GZ: $TAR_PATH"
}

package_windows() {
    echo "[5/6] Packaging Windows..."

    local APP_PATH="$DIST_DIR/${APP_NAME}"

    # ZIP (binario Windows)
    echo "  Creazione ZIP..."
    local ZIP_PATH="$DIST_DIR/${PKG_PREFIX}-Windows.zip"
    cd "$DIST_DIR"
    if command -v 7z &>/dev/null; then
        7z a -tzip "${PKG_PREFIX}-Windows.zip" "${APP_NAME}" 2>/dev/null
    else
        powershell -Command "Compress-Archive -Path '${APP_NAME}' -DestinationPath '${PKG_PREFIX}-Windows.zip'"
    fi
    cd ..
    echo "  ZIP: $ZIP_PATH"
}

# ---------------------------------------------------------------------------
# 6. Distribuzioni sorgente (Linux + Windows, sempre create)
# ---------------------------------------------------------------------------
package_source() {
    echo "[6/6] Distribuzioni sorgente (Linux + Windows)..."

    # --- Pacchetto Linux (TAR.GZ con start.sh) ---
    local LINUX_DIR="$DIST_DIR/${PKG_NAME}-v${VERSION}-Linux"
    mkdir -p "$LINUX_DIR"
    rsync -a --exclude='.git' --exclude='.venv' --exclude='build' \
        --exclude='dist' --exclude='__pycache__' --exclude='*.spec' \
        --exclude='_entry.py' --exclude='.DS_Store' \
        --exclude='start.bat' \
        . "$LINUX_DIR/"

    echo "  Creazione Linux TAR.GZ..."
    cd "$DIST_DIR"
    tar -czf "${PKG_PREFIX}-Linux.tar.gz" "${PKG_NAME}-v${VERSION}-Linux" 2>/dev/null
    cd ..
    echo "  TAR.GZ: $DIST_DIR/${PKG_PREFIX}-Linux.tar.gz"
    rm -rf "$LINUX_DIR"

    # --- Pacchetto Windows (ZIP con start.bat) ---
    local WIN_DIR="$DIST_DIR/${PKG_NAME}-v${VERSION}-Windows"
    mkdir -p "$WIN_DIR"
    rsync -a --exclude='.git' --exclude='.venv' --exclude='build' \
        --exclude='dist' --exclude='__pycache__' --exclude='*.spec' \
        --exclude='_entry.py' --exclude='.DS_Store' \
        --exclude='start.sh' \
        . "$WIN_DIR/"

    echo "  Creazione Windows ZIP..."
    cd "$DIST_DIR"
    zip -r -y "${PKG_PREFIX}-Windows.zip" "${PKG_NAME}-v${VERSION}-Windows" 2>/dev/null
    cd ..
    echo "  ZIP: $DIST_DIR/${PKG_PREFIX}-Windows.zip"
    rm -rf "$WIN_DIR"
}

# ---------------------------------------------------------------------------
# Esecuzione
# ---------------------------------------------------------------------------
MODE="${1:-all}"

if [ "$MODE" = "--source" ]; then
    # Solo sorgenti (Linux + Windows)
    package_source
elif [ "$MODE" = "--mac-only" ]; then
    build_pyinstaller
    package_macos
else
    # Build completa: PyInstaller + packaging + sorgenti
    build_pyinstaller

    if [ "$PLATFORM" = "Darwin" ]; then
        package_macos
    elif [ "$PLATFORM" = "Linux" ]; then
        package_linux
    else
        package_windows
    fi

    package_source
fi

# ---------------------------------------------------------------------------
# Riepilogo
# ---------------------------------------------------------------------------
echo ""
echo "=== Build completata ==="
echo ""
echo "Pacchetti creati in $DIST_DIR/:"
ls -lh "$DIST_DIR"/${PKG_PREFIX}* 2>/dev/null | awk '{print "  " $NF " (" $5 ")"}'
echo ""
echo "Per avviare l'app (macOS):"
echo "  open \"$DIST_DIR/${APP_NAME}.app\""
