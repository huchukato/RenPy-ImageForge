@echo off
REM Launch RenPy ImageForge using uv (auto-manages dependencies and venv).
cd /d "%~dp0"

REM Check Real-ESRGAN bundled
if not exist "vendor\realesrgan-ncnn-vulkan\realesrgan-ncnn-vulkan.exe" (
    echo [warn] Real-ESRGAN not found in vendor\. AI upscaling will be disabled.
)

REM uv run automatically creates the venv, installs dependencies from pyproject.toml
REM and launches the module.
uv run --link-mode=copy python -m batch_cropper %*
