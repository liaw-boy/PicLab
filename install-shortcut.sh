#!/usr/bin/env bash
# PicLab 桌面捷徑安裝（v2 — 逐步診斷版）
# 不會因為單一步驟失敗整個爆掉，每一步都 echo 結果。
set +e

cd "$(dirname "$0")"
PROJ="$PWD"
RUN_SH="$PROJ/run.sh"

echo "════════════════════════════════════════"
echo "  PicLab 桌面捷徑安裝"
echo "════════════════════════════════════════"
echo "[0] 環境"
echo "    USER     = $(whoami)"
echo "    HOME     = $HOME"
echo "    PROJ     = $PROJ"
echo "    RUN_SH   = $RUN_SH"
echo ""

# ────────────────────────────────────────────
# Step 1: run.sh 必須存在且可執行
# ────────────────────────────────────────────
echo "[1] 檢查 run.sh"
if [ ! -x "$RUN_SH" ]; then
  echo "    ❌ $RUN_SH 不存在或沒有 x 權限"
  chmod +x "$RUN_SH" 2>/dev/null && echo "    🔧 已自動加 x 權限"
fi
[ -x "$RUN_SH" ] && echo "    ✅ run.sh 可執行" || { echo "    ❌ 修不好，停"; exit 1; }
echo ""

# ────────────────────────────────────────────
# Step 2: 應用程式選單（~/.local/share/applications）
# ────────────────────────────────────────────
echo "[2] 安裝到應用程式選單"
APP_DIR="$HOME/.local/share/applications"
mkdir -p "$APP_DIR" 2>&1
if [ -d "$APP_DIR" ] && [ -w "$APP_DIR" ]; then
  cat > "$APP_DIR/PicLab.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=PicLab
Name[zh_TW]=PicLab Atelier
GenericName=Photo Editor
Comment=PyQt6 + WebView photo editor with SCUNet AI denoise
Exec=$RUN_SH
Icon=$PROJ/src/assets/icons/piclab_256.png
Terminal=false
Categories=Graphics;Photography;
StartupNotify=true
StartupWMClass=PicLab
EOF
  chmod +x "$APP_DIR/PicLab.desktop"
  echo "    ✅ 寫入 $APP_DIR/PicLab.desktop"
  command -v update-desktop-database >/dev/null && update-desktop-database "$APP_DIR" 2>/dev/null && echo "    ✅ 已刷新 desktop database"
else
  echo "    ⚠️  $APP_DIR 不可寫，略過"
fi
echo ""

# ────────────────────────────────────────────
# Step 3: 桌面雙擊圖示（~/Desktop 或 ~/桌面）
# ────────────────────────────────────────────
echo "[3] 放雙擊圖示到桌面"
for DESKTOP in "$HOME/Desktop" "$HOME/桌面"; do
  if [ -d "$DESKTOP" ]; then
    cp -f "$APP_DIR/PicLab.desktop" "$DESKTOP/PicLab.desktop" 2>/dev/null
    chmod +x "$DESKTOP/PicLab.desktop"
    # GNOME 需要 trust
    command -v gio >/dev/null && gio set "$DESKTOP/PicLab.desktop" metadata::trusted true 2>/dev/null
    echo "    ✅ 桌面圖示已放在 $DESKTOP/PicLab.desktop"
    DESKTOP_OK=1
    break
  fi
done
[ -z "${DESKTOP_OK:-}" ] && echo "    ⚠️  找不到桌面資料夾（~/Desktop 或 ~/桌面）"
echo ""

# ────────────────────────────────────────────
# Step 4: 終端指令 piclab
# ────────────────────────────────────────────
echo "[4] 安裝終端指令 'piclab'"
BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR" 2>&1
if [ -d "$BIN_DIR" ] && [ -w "$BIN_DIR" ]; then
  ln -sf "$RUN_SH" "$BIN_DIR/piclab"
  echo "    ✅ ln $BIN_DIR/piclab → run.sh"
else
  echo "    ⚠️  $BIN_DIR 不可寫"
fi

# 加到 PATH（只加沒加過的）
for RC in "$HOME/.bashrc" "$HOME/.zshrc"; do
  if [ -f "$RC" ] && ! grep -q '.local/bin' "$RC" 2>/dev/null; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$RC"
    echo "    ✅ 加 PATH 到 $RC"
  fi
done
echo ""

# ────────────────────────────────────────────
# Step 5: 確認
# ────────────────────────────────────────────
echo "[5] 結果確認"
[ -f "$APP_DIR/PicLab.desktop" ]   && echo "    ✅ 應用程式選單" || echo "    ❌ 應用程式選單"
[ -f "$HOME/Desktop/PicLab.desktop" ] || [ -f "$HOME/桌面/PicLab.desktop" ] \
                                  && echo "    ✅ 桌面圖示" || echo "    ❌ 桌面圖示"
[ -L "$BIN_DIR/piclab" ]           && echo "    ✅ 終端指令 piclab" || echo "    ❌ 終端指令"
echo ""
echo "════════════════════════════════════════"
echo "  完成"
echo "════════════════════════════════════════"
echo ""
echo "啟動方式三選一："
echo "  1. 應用程式選單搜尋「PicLab」"
echo "  2. 桌面雙擊「PicLab」圖示（首次可能要右鍵→允許執行）"
echo "  3. 終端機打 piclab（若提示找不到，先 'source ~/.bashrc' 或重開）"
echo ""
echo "如果要立刻試一次：直接打 $RUN_SH"
