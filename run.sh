#!/usr/bin/env bash
# PicLab Atelier launcher.
#
#   ./run.sh           — start the web UI prototype (main_web.py)
#   ./run.sh classic   — start the legacy PyQt UI (main.py)
#
# Auto-detects/builds .venv. Run from anywhere; we cd to the script's directory.
set -euo pipefail

cd "$(dirname "$0")"

# 1. Ensure venv exists
if [ ! -x ".venv/bin/python" ]; then
  echo "🔧 First run — building .venv (one-off, ~30s)..."
  python3 -m venv .venv
  .venv/bin/pip install --quiet --upgrade pip
  .venv/bin/pip install --quiet -r requirements.txt
fi

# 2. Display sanity
if [ -z "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]; then
  echo "⚠️  DISPLAY/WAYLAND_DISPLAY 都沒設 — 你需要在桌面 terminal 跑，不能純 SSH"
  echo "    若需 SSH 顯示，請用 'ssh -X' 或 VNC/RDP"
  exit 2
fi

# 3. Ensure web assets are built
if [ ! -f "src/gui/web/tailwind.css" ] || [ ! -f "src/gui/web/index.html" ]; then
  echo "❌ 找不到 src/gui/web/{tailwind.css,index.html} — assets 不完整"
  exit 3
fi

# 4. Pick entry
ENTRY="${1:-web}"
case "$ENTRY" in
  classic|legacy) FILE="main.py" ;;
  web|"")         FILE="main_web.py" ;;
  *)              echo "Unknown mode: $ENTRY (use 'web' or 'classic')"; exit 4 ;;
esac

# Auto-wire CUDA 12 pip wheel libs for onnxruntime-gpu (SCUNet AI Denoise)
NV="$PWD/.venv/lib/python3.12/site-packages/nvidia"
if [ -d "$NV" ]; then
  for d in cublas cudnn cuda_runtime curand cufft cuda_nvrtc; do
    if [ -d "$NV/$d/lib" ]; then
      LD_LIBRARY_PATH="$NV/$d/lib:${LD_LIBRARY_PATH:-}"
    fi
  done
  export LD_LIBRARY_PATH
fi

echo "🎬 Launching $FILE ..."
exec .venv/bin/python "$FILE"
