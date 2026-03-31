# PicLab

桌面版照片後製工具 — 為照片加上白邊、疊加 EXIF 相機資訊，未來將整合 RAW 調色功能。

---

## 功能特色

- **三種版型**
  - `CLASSIC` — 白邊 + 底部 EXIF 條（品牌 Logo、機身、鏡頭、拍攝參數、日期）
  - `ROUNDED` — 等比白邊 + 圓角照片
  - `SPLIT` — 左側資訊欄（35%）+ 右側照片（65%），可拖曳調整照片顯示區段

- **Instagram 最佳化輸出比例**
  - 1:1、4:5、3:4、2:3、9:16、1.91:1、16:9、5:4、自由尺寸

- **品牌 Logo 支援**
  - Sony、Canon、Nikon、Fujifilm、Leica、Panasonic、OM System、Ricoh、Pentax 等
  - 支援自訂 Logo PNG

- **EXIF 資訊顯示**
  - 焦距、光圈、快門、ISO、日期時間
  - 使用 Inter 字型，Cameramark 風格排版

- **批次匯入**
  - 支援選擇多張照片或整個資料夾匯入，含進度條顯示

- **每張照片獨立設定**
  - 切換照片時自動還原各自的設定，支援全部同步模式

- **深色 / 淺色主題切換**

---

## 安裝與執行

```bash
# 安裝依賴
pip install -r requirements.txt

# 執行
python main.py
```

### 系統需求

- Python 3.10+
- PyQt6
- Pillow

---

## 技術架構

```
models/   → 凍結 dataclass：Photo、ExifData、BorderSettings、CanvasGeometry
core/     → 純函式（無副作用）：exif_reader、image_processor、aspect_ratio、brand_renderer、font_manager
gui/      → PyQt6 元件 + 訊號路由 + 背景執行緒
```

### 資料流

```
使用者載入照片（拖放 或 檔案對話框）
  → exif_reader 讀取 EXIF（piexif 優先，exifread 備用）
  → 建立 Photo + ExifData 凍結 dataclass
  → 使用者在 SettingsPanel 設定 BorderSettings
  → ProcessWorker（QThread）在背景呼叫 image_processor.process()
  → PreviewPanel 顯示結果
  → ExportWorker（QThread）匯出至磁碟
```

---

## 路線圖

- [ ] RAW 檔案讀取與解碼
- [ ] 色調曲線調整
- [ ] 白平衡 / 色溫調整
- [ ] 降噪 / 銳化
- [ ] Lightroom 風格的調色面板

---

## License

MIT
