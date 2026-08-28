#!/usr/bin/env bash
# Avvia RenPy ImageForge usando uv (gestisce automaticamente dipendenze e venv).
set -euo pipefail
cd "$(dirname "$0")"

# Verifica Real-ESRGAN bundled
if [ ! -x "vendor/realesrgan-ncnn-vulkan/realesrgan-ncnn-vulkan" ]; then
  echo "[warn] Real-ESRGAN non trovato in vendor/. L'upscaling AI sara' disabilitato."
fi

# uv run crea automaticamente il venv, installa le dipendenze da pyproject.toml
# e lancia il modulo. link-mode=copy per evitare warning su filesystem cross-volume.
exec uv run --link-mode=copy python -m batch_cropper "$@"
