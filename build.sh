#!/usr/bin/env bash
# Build RenPy ImageForge: crea pacchetti per macOS, Linux e Windows.
#
# Su macOS: builda .app con PyInstaller + crea DMG e ZIP
# Su Linux: builda binario con PyInstaller + crea TAR.GZ
# Su Windows: builda .exe con PyInstaller + crea ZIP
#
# PyInstaller non puo' cross-compilare: ogni piattaforma va buildata
# sulla piattaforma stessa. Usa GitHub Actions (.github/workflows/build.yml)
# per buildare automaticamente su tutte e 3.
#
# Uso:
#   ./build.sh              # build completa + pacchetti
#   ./build.sh --mac-only   # solo macOS (DMG + ZIP)
#   ./build.sh --source     # solo distribuzioni sorgente (cross-platform)
set -euo pipefail
cd "$(dirname "$0")"

APP_NAME="RenPy ImageForge"
APP_ID="com.imageforge.renpy"
ICON_PATH="img/logo.icns"
VENDOR_DIR="vendor/realesrgan-ncnn-vulkan"
DIST_DIR="dist"
PLATFORM=$(uname -s)

# Parse arg
MODE="${1:-all}"

echo "=== RenPy ImageForge Build ==="
echo "Piattaforma: $PLATFORM"
echo "Modalita': $MODE"
echo ""

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
                --osx-bundle-identifier "$APP_ID"
        else
            uv run pyinstaller "${COMMON_ARGS[@]}" \
                --osx-bundle-identifier "$APP_ID"
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

    # DMG
    echo "  Creazione DMG..."
    local DMG_PATH="$DIST_DIR/${APP_NAME}-macOS.dmg"
    hdiutil create -volname "$APP_NAME" \
        -srcfolder "$APP_PATH" \
        -ov -format UDZO \
        "$DMG_PATH" 2>/dev/null
    echo "  DMG: $DMG_PATH"

    # ZIP (per distribuzione generica macOS)
    echo "  Creazione ZIP..."
    local ZIP_PATH="$DIST_DIR/${APP_NAME}-macOS.zip"
    cd "$DIST_DIR"
    zip -r -y "${APP_NAME}-macOS.zip" "${APP_NAME}.app" 2>/dev/null
    cd ..
    echo "  ZIP: $ZIP_PATH"
}

package_linux() {
    echo "[5/6] Packaging Linux..."

    local APP_PATH="$DIST_DIR/${APP_NAME}"

    # TAR.GZ
    echo "  Creazione TAR.GZ..."
    local TAR_PATH="$DIST_DIR/${APP_NAME}-Linux.tar.gz"
    cd "$DIST_DIR"
    tar -czf "${APP_NAME}-Linux.tar.gz" "${APP_NAME}" 2>/dev/null
    cd ..
    echo "  TAR.GZ: $TAR_PATH"
}

package_windows() {
    echo "[5/6] Packaging Windows..."

    local APP_PATH="$DIST_DIR/${APP_NAME}"

    # ZIP
    echo "  Creazione ZIP..."
    local ZIP_PATH="$DIST_DIR/${APP_NAME}-Windows.zip"
    cd "$DIST_DIR"
    # Su Windows usa 7z o PowerShell Compress-Archive
    if command -v 7z &>/dev/null; then
        7z a -tzip "${APP_NAME}-Windows.zip" "${APP_NAME}" 2>/dev/null
    else
        powershell -Command "Compress-Archive -Path '${APP_NAME}' -DestinationPath '${APP_NAME}-Windows.zip'"
    fi
    cd ..
    echo "  ZIP: $ZIP_PATH"
}

# ---------------------------------------------------------------------------
# 6. Distribuzione sorgente (cross-platform, sempre creata)
# ---------------------------------------------------------------------------
package_source() {
    echo "[6/6] Distribuzione sorgente (cross-platform)..."

    local SRC_DIR="$DIST_DIR/${APP_NAME}-source"

    # Copia i file sorgente (esclude build artifacts)
    mkdir -p "$SRC_DIR"
    rsync -a --exclude='.git' --exclude='.venv' --exclude='build' \
        --exclude='dist' --exclude='__pycache__' --exclude='*.spec' \
        --exclude='_entry.py' --exclude='.DS_Store' \
        . "$SRC_DIR/"

    # Crea TAR.GZ per Linux
    echo "  Creazione sorgente TAR.GZ..."
    cd "$DIST_DIR"
    tar -czf "${APP_NAME}-source.tar.gz" "${APP_NAME}-source" 2>/dev/null
    cd ..
    echo "  TAR.GZ: $DIST_DIR/${APP_NAME}-source.tar.gz"

    # Crea ZIP per Windows
    echo "  Creazione sorgente ZIP..."
    cd "$DIST_DIR"
    zip -r -y "${APP_NAME}-source.zip" "${APP_NAME}-source" 2>/dev/null
    cd ..
    echo "  ZIP: $DIST_DIR/${APP_NAME}-source.zip"

    # Pulisci cartella sorgente temporanea
    rm -rf "$SRC_DIR"
}

# ---------------------------------------------------------------------------
# Esecuzione
# ---------------------------------------------------------------------------
if [ "$MODE" = "--source" ]; then
    # Solo sorgente
    package_source
elif [ "$MODE" = "--mac-only" ]; then
    build_pyinstaller
    package_macos
    package_source
else
    # Build completa: PyInstaller + packaging + sorgente
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
ls -lh "$DIST_DIR"/${APP_NAME}* 2>/dev/null | awk '{print "  " $NF " (" $5 ")"}'
echo ""
echo "Per avviare l'app (macOS):"
echo "  open \"$DIST_DIR/${APP_NAME}.app\""
echo ""
echo "Per buildare su altre piattaforme:"
echo "  Linux:  esegui ./build.sh su Linux"
echo "  Windows: esegui ./build.sh su Windows (Git Bash/MSYS2)"
echo ""
echo "Oppure usa GitHub Actions per build automatiche cross-platform."
