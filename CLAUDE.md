# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Photo Border Tool** — PyQt6 desktop GUI app that adds professional white borders to photos and overlays EXIF metadata with camera brand logos. Supports multiple Instagram-optimized output ratios and three layout templates.

## Tech Stack

- **GUI**: PyQt6 with QThread background workers
- **Image processing**: Pillow (PIL)
- **EXIF reading**: piexif (primary) + exifread (fallback)

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app
python main.py

# Run tests (pytest-qt required)
pytest

# Run a single test file
pytest tests/test_image_processor.py -v
```

## Architecture

### Layer Separation

```
models/   → Frozen dataclasses: Photo, ExifData, BorderSettings, CanvasGeometry
core/     → Pure functions (no side effects): exif_reader, image_processor, aspect_ratio, brand_renderer, font_manager
gui/      → PyQt6 widgets + signal routing + background threads
```

### Data Flow

```
User loads image (drag-drop or file dialog)
  → exif_reader.py reads EXIF (piexif first, exifread fallback)
  → Photo + ExifData frozen dataclasses created
  → User configures settings in SettingsPanel (BorderSettings)
  → ProcessWorker (QThread) calls image_processor.process() in background
  → Preview panel displays result
  → ExportWorker (QThread) saves to disk on export
```

### Three Output Templates (`image_processor.py`)

Each template is independently implemented and computes layout via `aspect_ratio.py → CanvasGeometry`:

- **CLASSIC**: White border + EXIF strip at bottom (camera/lens left, params right)
- **ROUNDED**: Equal border all sides + rounded photo corners + subtle inner ring
- **SPLIT**: Left panel 35% (vertical EXIF layout) + right photo 65% (crop-to-fill)

### Key Patterns

**EXIF Normalization** (`exif_reader.py`): camera makes normalized to title-case, values formatted as human-readable strings (f/2.8, 1/250s, 25mm, ISO 100). Falls back gracefully when tags are missing.

**Brand Renderer** (`brand_renderer.py`): 9 camera brands (Sony, Canon, Nikon, Fujifilm, OM System, Leica, Panasonic, Ricoh, Pentax) each with brand-specific color/weight. Supports custom logo PNG override. Returns transparent RGBA PIL image.

**Font Manager** (`font_manager.py`): Discovers system fonts with LRU cache. CJK fallback chain: Noto Sans TC → Microsoft JhengHei → SimSun → mingliu. Checks `src/assets/fonts/` first, then OS font directories.

**Theme System** (`theme.py` + `theme_manager.py`): Module-level color tokens updated globally on switch. `ThemeManager` singleton emits `theme_changed` signal; all widgets reconnect. Supports dark (default) and light palettes with live switching.

**Background Scaling** (`settings.py → BorderSettings.border_dims()`): All border sizes are defined at 1080px reference width and scaled proportionally to actual output width.

## UI Design System

All GUI components must use these tokens (defined in `src/gui/theme.py`):

- **Primary**: `#0066cc` (Premium Blue)
- **Background**: `#f5f5f7` (Soft Gray) / dark: `#1e1e1e`
- **Surface**: `#ffffff` / dark: `#2d2d2d`
- **Border**: `#e0e0e0` / dark: `#3d3d3d`
- **Text primary**: `#1d1d1f` / dark: `#f5f5f7`
- **Text secondary**: `#86868b`
- **Spacing**: 4px grid (M-1=4px, M-2=8px, M-4=16px)
- **Rounding**: 8px buttons/cards, 4px input fields
- **Micro-animations**: `QPropertyAnimation` for hover/state transitions

## Enums & Constants

- `TemplateStyle`: CLASSIC, ROUNDED, SPLIT
- `AspectRatioPreset`: SQUARE_1_1 (1080×1080), PORTRAIT_4_5 (1080×1350), LANDSCAPE_191_1 (1080×566), STORIES_9_16 (1080×1920), PORTRAIT_3_4 (1080×1440), FREE
- `BorderPreset`: THIN (20/20/80px), MEDIUM (40/40/110px), THICK (80/80/160px), CUSTOM — all at 1080px reference width

## Development Skills

To ensure Lightroom-level quality and consistency, follow these modular skills:

- [**IMAGE_ENGINE.md**](file:///g:/project_photo/.claude/skills/photo_processing/IMAGE_ENGINE.md): Handling Pillow, borders, and aspect ratios. Use for compositing logic.
- [**EXIF_READER.md**](file:///g:/project_photo/.claude/skills/photo_processing/EXIF_READER.md): Extracting and normalizing metadata. Use for camera/lens info.
- [**EXPORT_ADVANCED.md**](file:///g:/project_photo/.claude/skills/photo_processing/EXPORT_ADVANCED.md): Professional-grade export settings and social media presets. Use for saving/resizing logic.
