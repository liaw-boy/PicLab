# PicLab

> 桌面版照片後製工具 — 為照片加上白邊、疊加 EXIF 相機資訊，未來整合 RAW 調色功能。

![Classic Template](docs/center_with_exif.jpg)

---

## 目錄

- [功能特色](#功能特色)
- [輸出範例](#輸出範例)
- [安裝](#安裝)
- [使用說明](#使用說明)
- [版型介紹](#版型介紹)
- [EXIF 資訊條](#exif-資訊條)
- [技術架構](#技術架構)
- [路線圖](#路線圖)

---

## 功能特色

| 功能 | 說明 |
|------|------|
| **三種版型** | Classic / Rounded / Split，各自獨立排版邏輯 |
| **9 種輸出比例** | 1:1、4:5、3:4、2:3、9:16、1.91:1、16:9、5:4、自由尺寸 |
| **品牌 Logo** | Sony、Canon、Nikon、Fujifilm、Leica 等 15+ 品牌，支援自訂 PNG |
| **EXIF 自動讀取** | 焦距、光圈、快門、ISO、日期，piexif + exifread 雙重解析 |
| **Inter 字型** | 仿 Cameramark 風格排版，幾何無襯線字體 |
| **邊框顏色** | 9 種預設色票（純白 → 大地棕），支援模糊背景填充 |
| **批次匯入** | 選多張照片或整個資料夾，含即時進度條 |
| **拖放載入** | 直接拖照片到視窗即可載入 |
| **每照片獨立設定** | 各張照片記憶自己的設定，支援全部同步模式 |
| **IG 安全區顯示** | 1:1 / 4:5 比例顯示網格縮圖遮罩區域 |
| **深色 / 淺色主題** | 即時切換，所有元件同步更新 |

---

## 輸出範例

### Classic — 白邊 + EXIF 條（中等邊框）

照片上下左右等量白邊，底部 EXIF 條顯示品牌 Logo、機身型號、鏡頭、拍攝參數。

![Classic Medium](docs/final_medium.jpg)

---

### Classic — 細邊框

邊框較窄，視覺重心落在照片本身。

![Classic Thin](docs/final_thin.jpg)

---

### Classic — 無 EXIF / 有 EXIF 對比

左：僅白邊　右：加上完整 EXIF 資訊條

| 無 EXIF | 有 EXIF |
|---------|---------|
| ![No EXIF](docs/center_no_exif.jpg) | ![With EXIF](docs/center_with_exif.jpg) |

---

## 安裝

### 需求

- Python 3.10+
- Windows 10 / 11（macOS 尚未測試）

### 步驟

```bash
# 1. Clone 專案
git clone https://github.com/liaw-boy/PicLab.git
cd PicLab

# 2. 建立虛擬環境（建議）
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # macOS / Linux

# 3. 安裝依賴
pip install -r requirements.txt

# 4. 啟動
python main.py
```

### 依賴套件

| 套件 | 用途 |
|------|------|
| `PyQt6` | GUI 框架 |
| `Pillow` | 影像合成 |
| `piexif` | EXIF 讀取（主要） |
| `exifread` | EXIF 讀取（備用） |

---

## 使用說明

### 載入照片

- **拖放**：直接把照片拖到視窗中央
- **點擊**：點左下角「開啟照片」→ 選擇照片或資料夾
- 支援格式：`JPG / PNG / TIFF / WebP / BMP`

### 調整設定（右側面板）

1. **輸出比例** — 選擇 Instagram 比例或自由尺寸
2. **邊框設定** — 細 / 中 / 粗 快速選，或拉滑桿自訂
3. **外框顏色** — 9 種預設色票，或開啟「模糊背景」
4. **品牌 & EXIF** — 勾選「品牌 Logo」和「拍攝參數」
5. **匯出設定** — JPEG / PNG，JPEG 品質 60–100

### 匯出

- 點右側「**匯出照片**」按鈕
- 或上方工具列快速匯出
- 快捷鍵：`Ctrl+S`

### 批次處理

- 載入多張照片後，底部縮圖列可逐張切換
- 各張照片設定**獨立記憶**
- 開啟上方「**同步所有**」後統一套用相同設定
- `Ctrl+點擊` / `Shift+點擊` 縮圖可多選同步群組

---

## 版型介紹

### Classic

```
┌─────────────────────────┐
│      （上邊框）           │
│   ┌─────────────────┐   │
│   │                 │   │
│   │      照片       │   │
│   │                 │   │
│   └─────────────────┘   │
│  ISO800 f/2.8  SONY │ R7 │  ← EXIF 條
└─────────────────────────┘
```

等量白邊 + 底部 EXIF 條。適合橫向風景、人像，最接近 Cameramark 風格。

---

### Rounded

```
┌─────────────────────────┐
│   ┌╮───────────────╭┐   │
│   │  照片（圓角）   │   │
│   └╯───────────────╰┘   │
│  EXIF 資訊               │
└─────────────────────────┘
```

等比白邊 + 圓角照片 + 細內框。適合質感個人照或食物攝影。

---

### Split

```
┌──────────┬──────────────┐
│  品牌    │              │
│  Logo    │   照片       │
│  機身    │  （填滿）    │
│  鏡頭    │              │
│  參數    │              │
└──────────┴──────────────┘
 左 35%       右 65%
```

左欄垂直排列品牌資訊，右欄照片填滿裁切。支援「**移動圖片**」模式調整顯示區段。

---

## EXIF 資訊條

排版參考 Cameramark / Sony 官方風格：

```
┌──────────────────────────────────────────────────────┐
│ 35mm  f/2.8  1/250s  ISO800    [ SONY ]  │  ILCE-7RM2 │
│ 2025.01.13  14:22:50                     │  FE 35mm F2.8 ZA │
└──────────────────────────────────────────────────────┘
```

- **左側**：拍攝參數 + 日期時間
- **中間**：品牌 Logo（Inter Bold 字型，品牌專屬配色）
- **分隔線 `|`**
- **右側**：機身型號 + 鏡頭

### 支援品牌

Sony · Canon · Nikon · Fujifilm · Leica · Panasonic · OM System · Ricoh · Pentax · Zeiss · DJI · Hasselblad · GoPro · Apple · 自訂 Logo

---

## 技術架構

```
PicLab/
├── main.py
├── src/
│   ├── models/         # 凍結 dataclass（純資料，無副作用）
│   │   ├── photo.py    # Photo, ExifData
│   │   └── settings.py # BorderSettings, AspectRatioPreset, TemplateStyle
│   ├── core/           # 純函式（可獨立測試）
│   │   ├── exif_reader.py      # EXIF 解析 + 正規化
│   │   ├── image_processor.py  # 三種版型合成邏輯
│   │   ├── aspect_ratio.py     # 畫布幾何計算
│   │   ├── brand_renderer.py   # 品牌 Logo 渲染
│   │   └── font_manager.py     # 字型探索 + LRU 快取
│   └── gui/            # PyQt6 介面層
│       ├── main_window.py      # 主視窗 + 背景執行緒協調
│       ├── preview_panel.py    # 預覽畫布 + 縮圖列
│       ├── settings_panel.py   # 右側設定面板
│       ├── top_bar.py          # 版型切換 + 工具列
│       ├── left_nav.py         # 左側導覽列
│       ├── widgets.py          # 可重用動畫元件
│       └── theme.py            # 設計 Token（深色/淺色）
└── src/assets/
    ├── fonts/          # Inter + Noto Sans TC
    └── brands/         # 品牌 Logo PNG
```

### 資料流

```
載入照片
  → exif_reader（piexif → exifread fallback）
  → Photo + ExifData dataclass
  → ProcessWorker（QThread）
  → image_processor.process()
  → PreviewPanel.show_image()
  → ExportWorker（QThread）→ 磁碟
```

---

## 路線圖

- [x] Classic / Rounded / Split 三種版型
- [x] EXIF 自動讀取與 Cameramark 風格排版
- [x] Inter 字型、品牌專屬 Logo
- [x] 批次匯入 + 每照片獨立設定
- [x] Split 版型拖曳調整顯示區段
- [x] IG 安全區遮罩顯示
- [ ] RAW 檔案讀取（libraw / rawpy）
- [ ] 色調曲線調整
- [ ] 白平衡 / 色溫調整
- [ ] 降噪 / 銳化
- [ ] HSL 色彩調整
- [ ] LUT / 預設值套用

---

## License

MIT
