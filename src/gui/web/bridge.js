/**
 * bridge.js — JS side of QWebChannel.
 * Atelier Lightbox edition: matches new light-theme HTML.
 */
(function () {
  "use strict";

  let bridge = null;

  const fmt = (val, kind) => {
    if (kind === "ev") {
      const v = parseFloat(val);
      return (v >= 0 ? "+" : "") + v.toFixed(1);
    }
    if (kind === "kelvin") return Math.round(val) + "K";
    if (kind === "deg") {
      const v = parseFloat(val);
      return (v >= 0 ? "+" : "") + v.toFixed(1) + "°";
    }
    const v = Math.round(parseFloat(val));
    return (v >= 0 ? "+" : "") + v;
  };

  const detectKind = (input) => {
    if (input.dataset.format) return input.dataset.format;
    const p = input.dataset.param || "";
    if (p === "wb_temperature") return "kelvin";
    if (p === "rotation") return "deg";
    if (parseFloat(input.min) >= 0) return "uint";
    return "int";
  };

  const updateVisual = (input) => {
    // Each slider row is .slr — scope the value label query inside it only.
    const row = input.closest(".slr");
    const valueLabel = row?.querySelector(".tnum");
    if (valueLabel) {
      const kind = detectKind(input);
      const v = parseFloat(input.value);
      let txt;
      if (kind === "uint") txt = String(Math.round(v));
      else txt = fmt(v, kind);
      valueLabel.textContent = txt;
    }
  };

  const wireSliders = () => {
    document.querySelectorAll("input[type=range][data-param]").forEach((input) => {
      updateVisual(input);
      input.addEventListener("input", () => {
        updateVisual(input);
        if (!bridge) return;
        const scale = parseFloat(input.dataset.scale || "1");
        const scaled = parseFloat(input.value) * scale;
        bridge.setGradeParam(input.dataset.param, scaled);
      });
    });
  };

  const setStatus = (text) => {
    const a = document.getElementById("status-line");
    if (a) a.textContent = text;
    const b = document.getElementById("filename-display");
    if (b && /已載入|loaded/.test(text)) {
      const m = text.match(/[^\/\s]+\.[a-zA-Z0-9]+/);
      if (m) b.textContent = m[0];
    }
  };

  const updateVitals = (img) => {
    const w = img.naturalWidth || 0;
    const h = img.naturalHeight || 0;
    const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
    if (w && h) {
      set("v-dims", w + " × " + h);
      const g = (a, b) => b === 0 ? a : g(b, a % b);
      const d = g(w, h);
      set("v-aspect", (w / d) + ":" + (h / d));
      set("v-format", "JPEG");
      const exif = document.getElementById("exif-strip");
      if (exif) exif.classList.remove("hidden");
    }
  };

  const onPreviewReady = (dataUrl) => {
    const img = document.getElementById("preview-img");
    const empty = document.getElementById("preview-empty");
    if (img) {
      img.onload = () => updateVitals(img);
      img.src = dataUrl;
      img.classList.remove("hidden");
    }
    if (empty) empty.style.display = "none";
  };

  const wireButtons = () => {
    const open = document.getElementById("btn-open");
    if (open) open.addEventListener("click", async () => {
      if (!bridge) return;
      setStatus("選擇相片中…");
      bridge.pickImage((path) => {
        setStatus(path ? ("已載入 " + path.split("/").pop()) : "已取消");
      });
    });
    const reset = document.getElementById("btn-reset");
    if (reset) reset.addEventListener("click", () => {
      if (!bridge) return;
      bridge.resetGrade();
      document.querySelectorAll("input[type=range][data-param]").forEach((input) => {
        // re-set to defaults stored in HTML's value attribute
        input.value = input.defaultValue;
        updateVisual(input);
      });
    });
    const exp = document.getElementById("btn-export");
    if (exp) exp.addEventListener("click", () => {
      if (!bridge) return;
      const fname = document.getElementById("filename-display")?.textContent?.trim() || "untitled";
      const stem = fname.replace(/\.[^.]+$/, "") + "_graded";
      setStatus("選擇輸出位置…");
      bridge.pickAndExport(stem, "JPEG", 92, (savedPath) => {
        if (savedPath && !savedPath.startsWith("error")) {
          setStatus("已輸出 " + savedPath.split("/").pop());
        } else if (savedPath.startsWith("error")) {
          setStatus("輸出失敗：" + savedPath);
        } else {
          setStatus("已取消");
        }
      });
    });

    wireZoomPan();
  };

  /**
   * Photo viewer zoom + pan controller.
   * State: { mode: 'fit' | 'free', zoom: number, panX: number, panY: number }
   * - Wheel zooms toward cursor (LR/Photoshop style).
   * - Drag pans (when zoomed in).
   * - Double-click toggles fit ↔ 1:1.
   * - Buttons: Fit, 1:1.
   */
  const wireZoomPan = () => {
    const img = document.getElementById("preview-img");
    const fitBtn = document.getElementById("btn-fit");
    const actualBtn = document.getElementById("btn-actual");
    const badge = document.getElementById("zoom-badge");
    const hint = document.getElementById("zoom-hint");
    if (!img) return;
    const container = img.parentElement; // .relative wrapper with overflow-hidden
    const ZMIN = 0.1;
    const ZMAX = 12;

    const state = { mode: "fit", zoom: 1, panX: 0, panY: 0 };

    /** Compute the on-screen scale ratio of the fit-rendered image. */
    const fitScale = () => {
      if (!img.naturalWidth || !img.naturalHeight) return 1;
      const r = img.getBoundingClientRect();
      // r.width is the rendered fit size; ratio to naturalWidth gives current display scale
      return r.width / img.naturalWidth;
    };

    const apply = () => {
      if (state.mode === "fit") {
        // Default flow: flex parent centers; max-w/h + object-contain shrinks naturally.
        img.style.position = "";
        img.style.left = "";
        img.style.top = "";
        img.style.transform = "";
        img.style.transformOrigin = "";
        img.style.objectFit = "contain";
        img.style.maxWidth = "100%";
        img.style.maxHeight = "100%";
        img.style.width = "";
        img.style.height = "";
        img.style.cursor = "";
        if (badge) badge.classList.add("hidden");
        if (hint) hint.classList.add("hidden");
      } else {
        // Free zoom — absolute-position so flex doesn't squeeze, transform owns layout.
        img.style.position = "absolute";
        img.style.left = "0";
        img.style.top = "0";
        img.style.objectFit = "none";
        img.style.maxWidth = "none";
        img.style.maxHeight = "none";
        img.style.width = `${img.naturalWidth}px`;
        img.style.height = `${img.naturalHeight}px`;
        img.style.transformOrigin = "0 0";
        img.style.transform = `translate(${state.panX}px, ${state.panY}px) scale(${state.zoom})`;
        img.style.cursor = state.zoom > fitScale() * 1.05 ? "grab" : "default";
        if (badge) {
          badge.textContent = `${Math.round(state.zoom * 100)}%`;
          badge.classList.remove("hidden");
        }
      }
    };

    const setFit = () => {
      state.mode = "fit";
      state.zoom = 1;
      state.panX = 0;
      state.panY = 0;
      apply();
      setStatus("適合畫面");
    };

    /** Center the image at zoom=1.0 (true 1:1 pixels). */
    const setActual = () => {
      state.mode = "free";
      state.zoom = 1;
      const cw = container.clientWidth;
      const ch = container.clientHeight;
      state.panX = (cw - img.naturalWidth) / 2;
      state.panY = (ch - img.naturalHeight) / 2;
      apply();
      setStatus("100% 實際像素");
    };

    /** Wheel zoom anchored at the viewport center (image stays centered). */
    const onWheel = (e) => {
      if (!img.naturalWidth) return;
      e.preventDefault();
      const cw = container.clientWidth;
      const ch = container.clientHeight;
      // Promote from fit to free on first wheel — start centered.
      if (state.mode === "fit") {
        const fs = fitScale();
        state.mode = "free";
        state.zoom = fs;
        state.panX = (cw - img.naturalWidth * fs) / 2;
        state.panY = (ch - img.naturalHeight * fs) / 2;
      }
      const factor = e.deltaY < 0 ? 1.15 : 1 / 1.15;
      const newZoom = Math.max(ZMIN, Math.min(ZMAX, state.zoom * factor));
      // Anchor at viewport center: keep the point at (cw/2, ch/2) fixed.
      const ax = cw / 2;
      const ay = ch / 2;
      state.panX = ax - (ax - state.panX) * (newZoom / state.zoom);
      state.panY = ay - (ay - state.panY) * (newZoom / state.zoom);
      state.zoom = newZoom;
      apply();
    };

    /** Drag-to-pan when zoomed in. */
    let dragging = false;
    let dragStart = { x: 0, y: 0, panX: 0, panY: 0 };
    const onMouseDown = (e) => {
      if (state.mode === "fit") return;
      if (e.button !== 0) return;
      dragging = true;
      dragStart = { x: e.clientX, y: e.clientY, panX: state.panX, panY: state.panY };
      img.style.cursor = "grabbing";
      e.preventDefault();
    };
    const onMouseMove = (e) => {
      if (!dragging) return;
      state.panX = dragStart.panX + (e.clientX - dragStart.x);
      state.panY = dragStart.panY + (e.clientY - dragStart.y);
      apply();
    };
    const onMouseUp = () => {
      if (!dragging) return;
      dragging = false;
      apply();
    };

    /** Double-click toggle fit ↔ 1:1. */
    const onDblClick = () => {
      if (state.mode === "fit") {
        setActual();
      } else {
        setFit();
      }
    };

    container.addEventListener("wheel", onWheel, { passive: false });
    container.addEventListener("mousedown", onMouseDown);
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
    container.addEventListener("dblclick", onDblClick);

    if (fitBtn) fitBtn.addEventListener("click", setFit);
    if (actualBtn) actualBtn.addEventListener("click", setActual);

    // Reset to fit whenever a new image loads (so panX/panY don't leak across photos)
    img.addEventListener("load", () => {
      setFit();
      if (hint) {
        hint.classList.remove("hidden");
        setTimeout(() => hint.classList.add("hidden"), 4000);
      }
    });

    // Keyboard shortcuts: F = fit, 1 = 1:1, 0 = fit (Photoshop-style)
    document.addEventListener("keydown", (e) => {
      if (e.target && (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA")) return;
      if (e.key === "f" || e.key === "F" || e.key === "0") setFit();
      else if (e.key === "1") setActual();
    });
  };

  const wireAccordion = () => {
    document.querySelectorAll("[data-acc] .acc-head").forEach((head) => {
      head.addEventListener("click", () => {
        head.parentElement.classList.toggle("is-open");
      });
    });
  };

  const wirePresets = () => {
    const grid = document.getElementById("preset-grid");
    if (!grid) return;
    grid.addEventListener("click", (ev) => {
      const btn = ev.target.closest(".preset-btn");
      if (!btn) return;
      grid.querySelectorAll(".preset-btn").forEach((b) => {
        b.classList.remove("active-preset", "bg-ink", "text-bg");
      });
      btn.classList.add("active-preset", "bg-ink", "text-bg");
      if (bridge) bridge.applyLut(btn.dataset.preset || "");
    });
  };

  const wireTreatment = () => {
    document.querySelectorAll(".treat-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".treat-btn").forEach((b) => {
          b.classList.remove("bg-accent", "text-bg", "border-accent");
          b.classList.add("border-line", "text-ink");
        });
        btn.classList.remove("border-line", "text-ink");
        btn.classList.add("bg-accent", "text-bg", "border-accent");
        if (bridge) bridge.setTreatment(btn.dataset.treatment);
      });
    });
  };

  const FLIP_STATE = { h: false, v: false };
  const wireFlip = () => {
    const fh = document.getElementById("btn-flip-h");
    const fv = document.getElementById("btn-flip-v");
    if (fh) fh.addEventListener("click", () => {
      FLIP_STATE.h = !FLIP_STATE.h;
      fh.classList.toggle("bg-accent", FLIP_STATE.h);
      fh.classList.toggle("text-bg", FLIP_STATE.h);
      if (bridge) bridge.setFlipH(FLIP_STATE.h);
    });
    if (fv) fv.addEventListener("click", () => {
      FLIP_STATE.v = !FLIP_STATE.v;
      fv.classList.toggle("bg-accent", FLIP_STATE.v);
      fv.classList.toggle("text-bg", FLIP_STATE.v);
      if (bridge) bridge.setFlipV(FLIP_STATE.v);
    });
  };

  const HSL_HUES = [
    { name: "Red",     bg: "#C84A3A" },
    { name: "Orange",  bg: "#D88A40" },
    { name: "Yellow",  bg: "#D4B85C" },
    { name: "Green",   bg: "#5FA56A" },
    { name: "Aqua",    bg: "#5FA0A8" },
    { name: "Blue",    bg: "#4A6EA8" },
    { name: "Purple",  bg: "#7E5AA8" },
    { name: "Magenta", bg: "#B85088" },
  ];
  const HSL_STATE = { hue: [0,0,0,0,0,0,0,0], saturation: [0,0,0,0,0,0,0,0], luminance: [0,0,0,0,0,0,0,0] };
  let HSL_TAB = "hue";

  const renderHslTab = () => {
    const grid = document.getElementById("hsl-grid");
    if (!grid) return;
    grid.innerHTML = HSL_HUES.map((h, i) => {
      const v = HSL_STATE[HSL_TAB][i];
      const sign = v >= 0 ? "+" : "";
      return `<div class="flex items-center gap-2">
        <span class="w-3 h-3 rounded-full flex-shrink-0" style="background:${h.bg}"></span>
        <label class="text-[11px] tracking-wider uppercase text-muted w-16">${h.name}</label>
        <input type="range" class="pen-slider flex-1" min="-100" max="100" value="${v}" data-hsl-idx="${i}"/>
        <span class="font-mono tnum text-xs text-ink w-8 text-right">${sign}${v}</span>
      </div>`;
    }).join("");
    grid.querySelectorAll("input[type=range]").forEach((input) => {
      input.addEventListener("input", () => {
        const idx = parseInt(input.dataset.hslIdx, 10);
        const v = parseInt(input.value, 10);
        HSL_STATE[HSL_TAB][idx] = v;
        const sign = v >= 0 ? "+" : "";
        input.nextElementSibling.textContent = sign + v;
        if (bridge) bridge.setHslComponent(HSL_TAB, idx, v);
      });
    });
  };

  const wireHslTabs = () => {
    document.querySelectorAll("[data-hsl-tab]").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll("[data-hsl-tab]").forEach((b) => {
          b.classList.remove("bg-accent", "text-bg", "border-accent");
          b.classList.add("border-line", "text-ink");
        });
        btn.classList.remove("border-line", "text-ink");
        btn.classList.add("bg-accent", "text-bg", "border-accent");
        HSL_TAB = btn.dataset.hslTab;
        renderHslTab();
      });
    });
    renderHslTab();
  };

  // ── Curves widget ────────────────────────────────────────────────────────
  const CURVES = {
    rgb: [[0,0],[1,1]], r: [[0,0],[1,1]], g: [[0,0],[1,1]], b: [[0,0],[1,1]],
  };
  let CURVE_TAB = "rgb";
  const CURVE_COLOR = { rgb: "#4A1F38", r: "#C84A3A", g: "#5FA56A", b: "#4A6EA8" };

  const renderCurve = () => {
    const svg = document.getElementById("curve-svg");
    if (!svg) return;
    const path = document.getElementById("curve-path");
    const ptsLayer = document.getElementById("curve-points");
    const pts = CURVES[CURVE_TAB];
    // Build smooth path through points (256x256 viewBox)
    let d = "";
    pts.forEach((p, i) => {
      const x = p[0] * 256;
      const y = (1 - p[1]) * 256;
      d += (i === 0 ? "M " : " L ") + x.toFixed(1) + " " + y.toFixed(1);
    });
    path.setAttribute("d", d);
    path.setAttribute("stroke", CURVE_COLOR[CURVE_TAB]);
    ptsLayer.innerHTML = pts.map((p, i) =>
      `<circle cx="${p[0]*256}" cy="${(1-p[1])*256}" r="6" fill="${CURVE_COLOR[CURVE_TAB]}" stroke="white" stroke-width="1.5" data-pi="${i}" class="cursor-grab"/>`
    ).join("");
    if (bridge) bridge.setCurve(CURVE_TAB, JSON.stringify(pts));
  };

  const wireCurves = () => {
    const svg = document.getElementById("curve-svg");
    if (!svg) return;
    let dragIdx = -1;
    const toCoords = (ev) => {
      const r = svg.getBoundingClientRect();
      const x = ((ev.clientX - r.left) / r.width);
      const y = 1 - ((ev.clientY - r.top) / r.height);
      return [Math.max(0, Math.min(1, x)), Math.max(0, Math.min(1, y))];
    };
    svg.addEventListener("mousedown", (ev) => {
      const target = ev.target;
      if (target.tagName === "circle" && target.dataset.pi) {
        dragIdx = parseInt(target.dataset.pi, 10);
      } else {
        // Add new point
        const [x, y] = toCoords(ev);
        const arr = CURVES[CURVE_TAB];
        arr.push([x, y]);
        arr.sort((a, b) => a[0] - b[0]);
        dragIdx = arr.findIndex((p) => p[0] === x && p[1] === y);
        renderCurve();
      }
    });
    document.addEventListener("mousemove", (ev) => {
      if (dragIdx < 0) return;
      const [x, y] = toCoords(ev);
      const arr = CURVES[CURVE_TAB];
      // Endpoints can move only vertically
      if (dragIdx === 0) arr[0] = [0, y];
      else if (dragIdx === arr.length - 1) arr[arr.length - 1] = [1, y];
      else arr[dragIdx] = [x, y];
      arr.sort((a, b) => a[0] - b[0]);
      renderCurve();
    });
    document.addEventListener("mouseup", () => { dragIdx = -1; });

    document.querySelectorAll("[data-curve-tab]").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll("[data-curve-tab]").forEach((b) => {
          b.classList.remove("bg-accent","text-bg","border-accent");
          b.classList.add("border-line","text-ink");
        });
        btn.classList.remove("border-line","text-ink");
        btn.classList.add("bg-accent","text-bg","border-accent");
        CURVE_TAB = btn.dataset.curveTab;
        renderCurve();
      });
    });
    const reset = document.getElementById("btn-curve-reset");
    if (reset) reset.addEventListener("click", () => {
      CURVES[CURVE_TAB] = [[0,0],[1,1]];
      renderCurve();
    });
    renderCurve();
  };

  // ── Frame / Border ────────────────────────────────────────────────────────
  const wireFrame = () => {
    const enable = document.getElementById("border-enable");
    if (enable) enable.addEventListener("change", () => {
      if (bridge) bridge.setBorderEnabled(enable.checked);
    });
    document.querySelectorAll("[data-border]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const field = btn.dataset.border;
        // Toggle active state in same group
        document.querySelectorAll(`[data-border="${field}"]`).forEach((b) => {
          b.classList.remove("active-bord","bg-accent","text-bg","border-accent");
          b.classList.add("border-line","text-ink");
        });
        btn.classList.remove("border-line","text-ink");
        btn.classList.add("active-bord","bg-accent","text-bg","border-accent");
        if (bridge) bridge.setBorderParam(field, btn.dataset.value);
      });
    });
    document.querySelectorAll("[data-border-bool]").forEach((cb) => {
      cb.addEventListener("change", () => {
        if (bridge) bridge.setBorderParam(cb.dataset.borderBool, cb.checked);
      });
    });
    const bg = document.getElementById("border-bg-color");
    if (bg) bg.addEventListener("input", () => {
      if (bridge) bridge.setBorderParam("bg_color", bg.value);
    });
  };

  // ── Output / Batch / IG ───────────────────────────────────────────────────
  const wireOutput = () => {
    const q = document.getElementById("exp-q");
    const qlabel = document.getElementById("exp-q-label");
    if (q && qlabel) q.addEventListener("input", () => { qlabel.textContent = q.value; });
    const le = document.getElementById("exp-le");
    const lelabel = document.getElementById("exp-le-label");
    if (le && lelabel) le.addEventListener("input", () => {
      lelabel.textContent = le.value === "0" ? "Original" : le.value + "px";
    });

    // Override Export button: now uses Output options
    const exp = document.getElementById("btn-export");
    if (exp) {
      const newExp = exp.cloneNode(true);
      exp.parentNode.replaceChild(newExp, exp);
      newExp.addEventListener("click", () => {
        if (!bridge) return;
        const fmt = document.getElementById("exp-fmt")?.value || "JPEG";
        const quality = parseInt(document.getElementById("exp-q")?.value || "92", 10);
        const longEdge = parseInt(document.getElementById("exp-le")?.value || "0", 10);
        setStatus("選擇輸出位置…");
        bridge.pickAndExportWithOptions(fmt, quality, longEdge, (saved) => {
          setStatus(saved && !saved.startsWith("error") ? "已輸出 " + saved.split("/").pop()
                  : (saved?.startsWith("error") ? "輸出失敗：" + saved : "已取消"));
        });
      });
    }

    wireBatchWizard();

    wireIGModal();
  };

  /** Snapshot of EXIF cached from the most recent exifReady event. */
  let exifCache = {};

  /**
   * IG Publish modal — builds a final caption from caption + EXIF + hashtags + watermark
   * and pushes options as JSON to the backend.
   */
  const wireIGModal = () => {
    const pub = document.getElementById("btn-publish");
    const modal = document.getElementById("ig-modal");
    const open = () => {
      if (!modal) return;
      modal.classList.remove("hidden");
      modal.style.display = "flex";
      updatePreview();
    };
    const close = () => {
      if (!modal) return;
      modal.classList.add("hidden");
      modal.style.display = "";
    };
    if (pub) pub.addEventListener("click", open);
    document.getElementById("ig-close")?.addEventListener("click", close);
    document.getElementById("ig-cancel")?.addEventListener("click", close);

    const cap = document.getElementById("ig-caption");
    const hash = document.getElementById("ig-hashtags");
    const loc = document.getElementById("ig-location");
    const addExif = document.getElementById("ig-add-exif");
    const hashNl = document.getElementById("ig-hash-newline");
    const watermark = document.getElementById("ig-add-watermark");
    const capCount = document.getElementById("ig-caption-count");
    const hashCount = document.getElementById("ig-hash-count");
    const preview = document.getElementById("ig-preview");

    /** @returns {string} the EXIF-derived line, or empty if no data / toggle off */
    const exifLine = () => {
      const e = exifCache || {};
      const parts = [];
      if (e.make || e.model) parts.push(`📷 ${[e.make, e.model].filter(Boolean).join(" ")}`);
      if (e.lens) parts.push(e.lens);
      const detail = [];
      if (e.iso) detail.push(`ISO ${e.iso}`);
      if (e.aperture) detail.push(`f/${String(e.aperture).replace(/^f\//, "")}`);
      if (e.shutter) detail.push(e.shutter);
      if (e.focal) detail.push(e.focal);
      if (detail.length) parts.push(detail.join(" · "));
      return parts.join("\n");
    };

    const buildFinal = () => {
      let body = (cap?.value || "").trim();
      const tagsRaw = (hash?.value || "").trim();
      const location = (loc?.value || "").trim();
      const wantExif = !!addExif?.checked;
      const wantNl = !!hashNl?.checked;
      const wantWm = !!watermark?.checked;

      if (location) body = body ? `${body}\n📍 ${location}` : `📍 ${location}`;
      if (wantExif) {
        const xl = exifLine();
        if (xl) body = body ? `${body}\n\n${xl}` : xl;
      }
      const tags = wantWm ? `${tagsRaw} #editedinpiclab`.trim() : tagsRaw;
      if (tags) body = body ? `${body}${wantNl ? "\n\n" : " "}${tags}` : tags;
      return body;
    };

    const updatePreview = () => {
      const final = buildFinal();
      if (preview) preview.textContent = final || "（即時預覽會顯示在這裡）";
      if (capCount && cap) capCount.textContent = `${cap.value.length} / 2200`;
      if (hashCount && hash) {
        const count = (hash.value.match(/#\w+/g) || []).length;
        hashCount.textContent = `${count} / 30`;
        if (count > 30) hashCount.classList.add("text-accent");
        else hashCount.classList.remove("text-accent");
      }
    };

    [cap, hash, loc, addExif, hashNl, watermark].forEach((el) => {
      el?.addEventListener("input", updatePreview);
      el?.addEventListener("change", updatePreview);
    });

    // Hashtag chips — append on click, dedupe.
    document.querySelectorAll(".ig-hash-chip").forEach((chip) => {
      chip.addEventListener("click", () => {
        const tag = chip.dataset.tag || "";
        if (!tag || !hash) return;
        if (hash.value.includes(tag)) return;
        hash.value = hash.value ? `${hash.value} ${tag}` : tag;
        updatePreview();
      });
    });

    document.getElementById("ig-confirm")?.addEventListener("click", () => {
      if (!bridge) return;
      const finalCaption = buildFinal();
      if (cap && cap.value.length > 2200) {
        setStatus("IG caption 超過 2200 字");
        return;
      }
      close();
      setStatus("發佈到 IG …");
      bridge.publishToIg(finalCaption, (resJson) => {
        try {
          const r = JSON.parse(resJson);
          setStatus(r.success ? "✓ IG 發佈成功" : "IG 失敗：" + (r.message || ""));
        } catch (_e) {
          setStatus("IG 發佈完成");
        }
      });
    });
  };

  // ── Real EXIF ─────────────────────────────────────────────────────────────
  const onExifReady = (json_str) => {
    try {
      const e = JSON.parse(json_str || "{}");
      exifCache = e;  // shared with IG modal so it can append camera info
      const exifText = document.getElementById("exif-text");
      const strip = document.getElementById("exif-strip");
      const parts = [];
      if (e.iso)      parts.push("ISO " + e.iso);
      if (e.aperture) parts.push("f/" + String(e.aperture).replace(/^f\//,""));
      if (e.shutter)  parts.push(e.shutter);
      if (e.focal)    parts.push(e.focal);
      if (parts.length && exifText) exifText.textContent = parts.join(" · ");
      if (parts.length && strip) strip.classList.remove("hidden");
    } catch (err) { /* ignore */ }
  };

  const wireAIDenoise = () => {
    const btn = document.getElementById("btn-ai-denoise");
    const prov = document.getElementById("ai-provider");
    if (btn) btn.addEventListener("click", () => {
      if (!bridge) return;
      btn.disabled = true;
      btn.classList.add("opacity-50");
      bridge.applyAIDenoise((resJson) => {
        btn.disabled = false;
        btn.classList.remove("opacity-50");
        try {
          const r = JSON.parse(resJson);
          if (prov && r.provider) prov.textContent = r.provider.replace("ExecutionProvider", "");
        } catch {}
      });
    });
    // Show provider on load
    setTimeout(() => {
      if (bridge && prov) bridge.aiProvider((p) => {
        prov.textContent = p.replace("ExecutionProvider", "") || "—";
      });
    }, 600);
  };

  /**
   * LR-style Crop mode: enter/exit, drag handles to resize, drag inside to move,
   * aspect ratio lock, apply/cancel/reset. Outputs to `bridge.setCrop(l,t,r,b)`.
   *
   * The cropbox stores its rect (left/top/width/height as 0..1 of the photo's
   * displayed area). On apply we convert to inset values (left/top/right/bottom).
   */
  const wireCrop = () => {
    const overlay = document.getElementById("crop-overlay");
    const box = document.getElementById("crop-box");
    const enterBtn = document.getElementById("btn-enter-crop");
    const resetBtnRail = document.getElementById("btn-reset-crop");
    const applyBtn = document.getElementById("crop-apply");
    const cancelBtn = document.getElementById("crop-cancel");
    const resetBtn = document.getElementById("crop-reset");
    const aspectSel = document.getElementById("crop-aspect");
    const img = document.getElementById("preview-img");
    if (!overlay || !box || !enterBtn || !img) return;

    let active = false;
    /** rect: relative to the displayed image bounds (0..1). */
    const rect = { x: 0.05, y: 0.05, w: 0.9, h: 0.9 };
    let imgRect = null; // current displayed image bounds within viewport

    const aspectValue = () => {
      const v = aspectSel?.value || "free";
      if (v === "free") return null;
      if (v === "orig") {
        if (!img.naturalWidth) return null;
        return img.naturalWidth / img.naturalHeight;
      }
      const [a, b] = v.split(":").map(parseFloat);
      return a && b ? a / b : null;
    };

    const computeImgRect = () => {
      const port = document.getElementById("photo-viewport");
      if (!port || !img.naturalWidth) return null;
      const portR = port.getBoundingClientRect();
      const imR = img.getBoundingClientRect();
      return {
        left: imR.left - portR.left,
        top: imR.top - portR.top,
        width: imR.width,
        height: imR.height,
      };
    };

    const renderBox = () => {
      if (!imgRect) return;
      box.style.left = `${imgRect.left + rect.x * imgRect.width}px`;
      box.style.top = `${imgRect.top + rect.y * imgRect.height}px`;
      box.style.width = `${rect.w * imgRect.width}px`;
      box.style.height = `${rect.h * imgRect.height}px`;
    };

    const enforceAspect = () => {
      const a = aspectValue();
      if (!a || !imgRect) return;
      // Aspect = image-pixel ratio; convert to box-rect units.
      const imgPxRatio = imgRect.width / imgRect.height;  // displayed
      // We want (rect.w * imgW) / (rect.h * imgH) = a
      //   →   rect.w / rect.h = a / imgPxRatio  (because imgW/imgH = imgPxRatio)
      const ratioBox = a / imgPxRatio;
      // Anchor at center, pick the smaller of (current w preserved → adjust h) vs vice versa.
      const cx = rect.x + rect.w / 2;
      const cy = rect.y + rect.h / 2;
      let w = rect.w;
      let h = w / ratioBox;
      if (h > 1) { h = 1; w = h * ratioBox; }
      rect.w = Math.min(1, w);
      rect.h = Math.min(1, h);
      rect.x = Math.max(0, Math.min(1 - rect.w, cx - rect.w / 2));
      rect.y = Math.max(0, Math.min(1 - rect.h, cy - rect.h / 2));
    };

    const enter = () => {
      if (!img.naturalWidth) return;
      imgRect = computeImgRect();
      if (!imgRect) return;
      active = true;
      overlay.classList.remove("hidden");
      enforceAspect();
      renderBox();
    };
    const exit = () => {
      active = false;
      overlay.classList.add("hidden");
    };

    enterBtn.addEventListener("click", enter);
    cancelBtn?.addEventListener("click", exit);
    resetBtn?.addEventListener("click", () => {
      rect.x = 0.05; rect.y = 0.05; rect.w = 0.9; rect.h = 0.9;
      enforceAspect();
      renderBox();
    });
    aspectSel?.addEventListener("change", () => {
      enforceAspect();
      renderBox();
    });
    applyBtn?.addEventListener("click", () => {
      if (!bridge) { exit(); return; }
      const left = rect.x;
      const top = rect.y;
      const right = 1 - (rect.x + rect.w);
      const bottom = 1 - (rect.y + rect.h);
      bridge.setCrop(left, top, right, bottom);
      exit();
    });
    resetBtnRail?.addEventListener("click", () => {
      if (bridge) bridge.resetCrop();
    });

    // Drag handlers — both move and resize use mouse delta in viewport px.
    let drag = null;  // { mode, startX, startY, startRect }
    const onDown = (e) => {
      if (!active) return;
      const handle = e.target.closest(".crop-handle");
      const move = e.target.closest(".crop-move");
      if (!handle && !move) return;
      e.preventDefault();
      drag = {
        mode: handle ? handle.dataset.h : "move",
        startX: e.clientX,
        startY: e.clientY,
        startRect: { ...rect },
      };
    };
    const onMove = (e) => {
      if (!drag || !imgRect) return;
      const dxPx = e.clientX - drag.startX;
      const dyPx = e.clientY - drag.startY;
      const dx = dxPx / imgRect.width;
      const dy = dyPx / imgRect.height;
      const r0 = drag.startRect;
      const a = aspectValue();
      const ratioBox = a ? (a / (imgRect.width / imgRect.height)) : null;

      const apply = (newRect) => {
        // Clamp inside [0,1] and ensure min 5% size
        const MIN = 0.05;
        newRect.w = Math.max(MIN, Math.min(1, newRect.w));
        newRect.h = Math.max(MIN, Math.min(1, newRect.h));
        newRect.x = Math.max(0, Math.min(1 - newRect.w, newRect.x));
        newRect.y = Math.max(0, Math.min(1 - newRect.h, newRect.y));
        Object.assign(rect, newRect);
        renderBox();
      };

      if (drag.mode === "move") {
        apply({ x: r0.x + dx, y: r0.y + dy, w: r0.w, h: r0.h });
        return;
      }

      // Resize: derive new edges; if aspect lock, drive the other axis from the dragged one.
      let nx = r0.x, ny = r0.y, nw = r0.w, nh = r0.h;
      if (drag.mode.includes("e")) nw = r0.w + dx;
      if (drag.mode.includes("w")) { nx = r0.x + dx; nw = r0.w - dx; }
      if (drag.mode.includes("s")) nh = r0.h + dy;
      if (drag.mode.includes("n")) { ny = r0.y + dy; nh = r0.h - dy; }

      if (ratioBox) {
        // Pick the dominant axis (whichever changed more) and slave the other
        const wChange = Math.abs(nw - r0.w);
        const hChange = Math.abs(nh - r0.h);
        if (wChange >= hChange) {
          nh = nw / ratioBox;
          if (drag.mode.includes("n")) ny = r0.y + r0.h - nh;
        } else {
          nw = nh * ratioBox;
          if (drag.mode.includes("w")) nx = r0.x + r0.w - nw;
        }
      }
      apply({ x: nx, y: ny, w: nw, h: nh });
    };
    const onUp = () => { drag = null; };

    overlay.addEventListener("mousedown", onDown);
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);

    // Keyboard: Esc cancel, Enter apply
    document.addEventListener("keydown", (e) => {
      if (!active) return;
      if (e.target?.tagName === "SELECT" || e.target?.tagName === "INPUT") return;
      if (e.key === "Escape") exit();
      else if (e.key === "Enter") applyBtn?.click();
    });

    // Re-anchor on resize / image change
    const reAnchor = () => {
      if (!active) return;
      imgRect = computeImgRect();
      renderBox();
    };
    window.addEventListener("resize", reAnchor);
    img.addEventListener("load", () => { if (active) reAnchor(); });
  };

  /**
   * LR-style Batch Wizard: file picker → output dir → filename template →
   * collision policy → selective sync (which setting groups to apply) → auto tone →
   * progress bar with cancel → result summary.
   *
   * Wired to backend signals: batchProgress + batchFinished.
   */
  const wireBatchWizard = () => {
    const modal = document.getElementById("batch-modal");
    const trigger = document.getElementById("btn-batch");
    if (!modal || !trigger) return;

    const open = () => { modal.classList.remove("hidden"); modal.style.display = "flex"; };
    const close = () => { modal.classList.add("hidden"); modal.style.display = ""; };

    /** @type {string[]} */
    let pickedFiles = [];
    let pickedDir = "";
    let running = false;

    const filesInfo = document.getElementById("batch-files-info");
    const dirInfo = document.getElementById("batch-dir-info");
    const fmtEcho = document.getElementById("batch-fmt-echo");

    const refreshFmtEcho = () => {
      const fmt = document.getElementById("exp-fmt")?.value || "JPEG";
      const q = document.getElementById("exp-q")?.value || "92";
      const le = document.getElementById("exp-le")?.value || "0";
      const leText = (parseInt(le, 10) || 0) === 0 ? "原始" : `${le}px`;
      if (fmtEcho) fmtEcho.textContent = `${fmt} · Q${q} · 長邊 ${leText}`;
    };

    trigger.addEventListener("click", () => {
      pickedFiles = [];
      pickedDir = "";
      if (filesInfo) filesInfo.textContent = "（尚未選擇）";
      if (dirInfo) dirInfo.textContent = "（取消＝原檔同目錄）";
      refreshFmtEcho();
      open();
    });
    document.getElementById("batch-close")?.addEventListener("click", () => { if (!running) close(); });
    document.getElementById("batch-cancel")?.addEventListener("click", () => { if (!running) close(); });

    document.getElementById("batch-pick-files")?.addEventListener("click", () => {
      if (!bridge) return;
      bridge.pickFiles((json) => {
        try { pickedFiles = JSON.parse(json || "[]"); } catch (_e) { pickedFiles = []; }
        if (filesInfo) filesInfo.textContent = pickedFiles.length
          ? `${pickedFiles.length} 張已選`
          : "（尚未選擇）";
      });
    });
    document.getElementById("batch-pick-dir")?.addEventListener("click", () => {
      if (!bridge) return;
      bridge.pickOutputDir((dir) => {
        pickedDir = dir || "";
        if (dirInfo) dirInfo.textContent = pickedDir || "（取消＝原檔同目錄）";
      });
    });

    document.getElementById("batch-groups-all")?.addEventListener("click", () => {
      document.querySelectorAll('#batch-groups input[type=checkbox]').forEach((c) => { c.checked = true; });
    });
    document.getElementById("batch-groups-none")?.addEventListener("click", () => {
      document.querySelectorAll('#batch-groups input[type=checkbox]').forEach((c) => { c.checked = false; });
    });

    const progWrap = document.getElementById("batch-progress-wrap");
    const progBar = document.getElementById("batch-progress-bar");
    const progText = document.getElementById("batch-progress-text");
    const progCurrent = document.getElementById("batch-progress-current");
    const startBtn = document.getElementById("batch-start");
    const stopBtn = document.getElementById("batch-stop");

    const setRunning = (on) => {
      running = on;
      if (startBtn) startBtn.classList.toggle("hidden", on);
      if (stopBtn) stopBtn.classList.toggle("hidden", !on);
      if (progWrap) progWrap.classList.toggle("hidden", !on);
      // Disable inputs while running
      modal.querySelectorAll("input, select, button").forEach((el) => {
        if (el.id === "batch-stop") return;
        if (el.id === "batch-close") return;
        el.disabled = on && el.id !== "batch-stop" && el.id !== "batch-close";
      });
    };

    startBtn?.addEventListener("click", () => {
      if (!bridge) return;
      if (!pickedFiles.length) { setStatus("批次：請先選擇來源檔案"); return; }
      const collision = document.querySelector('input[name="batch-collision"]:checked')?.value || "increment";
      const apply_groups = Array.from(
        document.querySelectorAll('#batch-groups input[type=checkbox]:checked')
      ).map((c) => c.dataset.group).filter(Boolean);
      const opts = {
        paths: pickedFiles,
        out_dir: pickedDir,
        fmt: document.getElementById("exp-fmt")?.value || "JPEG",
        quality: parseInt(document.getElementById("exp-q")?.value || "92", 10),
        filename_template: document.getElementById("batch-template")?.value || "{name}_graded",
        collision,
        apply_groups,
        auto_tone_per_image: !!document.getElementById("batch-auto-tone")?.checked,
      };
      // Reset progress UI
      if (progBar) progBar.style.width = "0%";
      if (progText) progText.textContent = `0 / ${pickedFiles.length}`;
      if (progCurrent) progCurrent.textContent = "啟動中…";
      setRunning(true);
      bridge.batchExport(JSON.stringify(opts));
    });

    stopBtn?.addEventListener("click", () => {
      if (!bridge) return;
      bridge.cancelBatch();
      if (progCurrent) progCurrent.textContent = "已要求中止…";
    });

    // Wire signals once. Connection happens in init() after channel ready, but the
    // handler below references DOM elements scoped to this closure.
    window.__batchHandlers = {
      onProgress: (json) => {
        try {
          const p = JSON.parse(json);
          const pct = p.total ? Math.round((p.done / p.total) * 100) : 0;
          if (progBar) progBar.style.width = `${pct}%`;
          if (progText) progText.textContent = `${p.done} / ${p.total}`;
          if (progCurrent) progCurrent.textContent = `${p.current || ""}　[成功 ${p.ok} ／ 失敗 ${p.fail}]`;
        } catch (_e) { /* ignore */ }
      },
      onFinished: (json) => {
        let r;
        try { r = JSON.parse(json); } catch (_e) { r = { ok: 0, fail: 0, out_dir: pickedDir || "原檔同目錄", errors: ["解析失敗"], cancelled: false }; }
        setRunning(false);
        close();
        const fmt = document.getElementById("exp-fmt")?.value || "JPEG";
        showBatchResultModal(r, fmt);
      },
    };
  };

  /**
   * Show a modal summarising a batch export result.
   * @param {{ok:number, fail:number, out_dir:string, errors?:string[]}} r
   * @param {string} fmt
   */
  const showBatchResultModal = (r, fmt) => {
    const overlay = document.createElement("div");
    overlay.className = "fixed inset-0 z-50 bg-ink/40 backdrop-blur-sm flex items-center justify-center";
    const errLines = (r.errors || []).map(e => `<li class="truncate">• ${e}</li>`).join("");
    overlay.innerHTML = `
      <div class="bg-surface rounded-xl shadow-deep w-[460px] p-6 space-y-4">
        <div class="flex items-baseline gap-2">
          <span class="material-symbols-outlined text-accent text-[22px]">${r.fail === 0 ? "task_alt" : "report"}</span>
          <h3 class="text-lg font-semibold tracking-tight text-ink">批次處理完成</h3>
        </div>
        <div class="grid grid-cols-2 gap-3 text-sm">
          <div class="p-3 rounded bg-bg/60 border border-line">
            <div class="text-[10px] tracking-widest text-muted">成功</div>
            <div class="text-2xl font-mono tnum text-ink">${r.ok}</div>
          </div>
          <div class="p-3 rounded bg-bg/60 border border-line">
            <div class="text-[10px] tracking-widest text-muted">失敗</div>
            <div class="text-2xl font-mono tnum ${r.fail > 0 ? 'text-accent' : 'text-ink/60'}">${r.fail}</div>
          </div>
        </div>
        <div class="text-xs text-muted">輸出格式：${fmt}</div>
        <div class="text-xs">
          <div class="text-[10px] tracking-widest text-muted mb-1">輸出位置</div>
          <div class="font-mono text-ink/80 break-all bg-bg/60 border border-line rounded px-2 py-1.5">${r.out_dir}</div>
        </div>
        ${errLines ? `<div class="text-xs"><div class="text-[10px] tracking-widest text-muted mb-1">失敗清單（前 5 筆）</div><ul class="font-mono text-ink/80 bg-bg/60 border border-line rounded px-2 py-1.5 max-h-24 overflow-auto space-y-0.5">${errLines}</ul></div>` : ""}
        <div class="flex gap-2 pt-2">
          <button id="batch-modal-open-folder" class="flex-1 px-3 py-2 text-xs tracking-wider rounded bg-accent text-bg hover:opacity-90 flex items-center justify-center gap-1">
            <span class="material-symbols-outlined text-[16px]">folder_open</span>開啟資料夾
          </button>
          <button id="batch-modal-close" class="flex-1 px-3 py-2 text-xs tracking-wider rounded border border-line hover:bg-ink hover:text-bg">關閉</button>
        </div>
      </div>
    `;
    document.body.appendChild(overlay);
    const close = () => overlay.remove();
    overlay.querySelector("#batch-modal-close").addEventListener("click", close);
    overlay.querySelector("#batch-modal-open-folder").addEventListener("click", () => {
      if (bridge && r.out_dir && !r.out_dir.startsWith("（")) bridge.openInFileManager(r.out_dir);
      close();
    });
    overlay.addEventListener("click", (e) => { if (e.target === overlay) close(); });
    setStatus(`批次：${r.ok} 成功 / ${r.fail} 失敗 → ${r.out_dir}`);
  };

  /**
   * LR-style 5-zone color tonal map. Bin ranges match Lightroom Classic's
   * Blacks / Shadows / Exposure / Highlights / Whites slider regions.
   */
  const HIST_ZONES = [
    { from: 0,   to: 25,  label: "黑色 Blacks",       slider: "blacks" },
    { from: 25,  to: 76,  label: "陰影 Shadows",      slider: "shadows" },
    { from: 76,  to: 178, label: "曝光度 Exposure",   slider: "exposure" },
    { from: 178, to: 229, label: "亮部 Highlights",   slider: "highlights" },
    { from: 229, to: 255, label: "白色 Whites",       slider: "whites" },
  ];

  /**
   * Render an LR-grade histogram on the canvas.
   * Features:
   *  - Linear Y-scale (matches LR) with smart auto-zoom that ignores spike outliers
   *  - White overlay where R≈G≈B (shows the luma curve in neutral images, LR signature)
   *  - 5 faint vertical zone bands aligned to LR's slider regions
   *  - Smoothed curve via local averaging (kills 256-bin jagged noise)
   *  - Corner clipping triangles light up when ≥0.5% pixels are clipped
   * @param {string} payload - JSON {r:[...], g:[...], b:[...], stats:{...}}
   */
  const onHistogramReady = (payload) => {
    const canvas = document.getElementById("histogram-canvas");
    if (!canvas) return;
    let data;
    try {
      data = JSON.parse(payload);
    } catch (_e) {
      return;
    }
    // HiDPI buffer sync
    const dpr = window.devicePixelRatio || 1;
    const cssW = canvas.clientWidth;
    const cssH = canvas.clientHeight;
    if (canvas.width !== cssW * dpr || canvas.height !== cssH * dpr) {
      canvas.width = cssW * dpr;
      canvas.height = cssH * dpr;
    }
    const ctx = canvas.getContext("2d");
    const W = canvas.width;
    const H = canvas.height;
    ctx.clearRect(0, 0, W, H);

    // ── Step 1: smooth each channel with a 3-bin moving average to kill jaggies
    const smooth = (arr) => {
      const out = new Array(256);
      for (let i = 0; i < 256; i++) {
        const a = arr[Math.max(0, i - 1)] || 0;
        const b = arr[i] || 0;
        const c = arr[Math.min(255, i + 1)] || 0;
        out[i] = (a + b + c) / 3;
      }
      return out;
    };
    const r = smooth(data.r);
    const g = smooth(data.g);
    const b = smooth(data.b);

    // ── Step 2: derive luma curve = pointwise min(R, G, B). This produces the
    // white peak in LR where all three channels agree (pure greys/neutrals).
    const luma = new Array(256);
    for (let i = 0; i < 256; i++) luma[i] = Math.min(r[i], g[i], b[i]);

    // ── Step 3: peak with outlier suppression — use 99.5th percentile of all
    // bin values (excluding bin 0 and 255 which are spikes from clipping)
    const sample = [];
    for (let i = 1; i < 255; i++) sample.push(r[i], g[i], b[i]);
    sample.sort((a, b2) => a - b2);
    const peak = sample[Math.floor(sample.length * 0.995)] || 1;

    // (Zone tints removed — kept canvas clean. Hover still shows zone label in JS.)

    // ── Step 5: draw filled R, G, B with screen blending (LR-like overlap)
    const drawCurve = (arr, fill) => {
      ctx.beginPath();
      ctx.moveTo(0, H);
      for (let i = 0; i < 256; i++) {
        const x = (i / 255) * W;
        const v = Math.min(1, arr[i] / peak);
        const y = H - v * H;
        ctx.lineTo(x, y);
      }
      ctx.lineTo(W, H);
      ctx.closePath();
      ctx.fillStyle = fill;
      ctx.fill();
    };

    ctx.globalCompositeOperation = "lighter";
    drawCurve(r, "rgba(220, 70, 50, 0.65)");   // R
    drawCurve(g, "rgba(70, 175, 110, 0.65)");  // G
    drawCurve(b, "rgba(60, 100, 220, 0.65)");  // B
    ctx.globalCompositeOperation = "source-over";

    // ── Step 6: white "luma" curve on top — where channels agree (greys)
    drawCurve(luma, "rgba(255, 255, 255, 0.55)");

    // ── Step 7: thin stroke outline along combined max envelope
    ctx.strokeStyle = "rgba(31, 26, 20, 0.35)";
    ctx.lineWidth = dpr;
    ctx.beginPath();
    for (let i = 0; i < 256; i++) {
      const x = (i / 255) * W;
      const m = Math.max(r[i], g[i], b[i]);
      const v = Math.min(1, m / peak);
      const y = H - v * H;
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // ── Step 8: stats text + corner clip indicators
    const s = data.stats || {};
    const stats = document.getElementById("hist-stats");
    if (stats) {
      stats.textContent = `μ ${Math.round(s.mean || 0)}`;
    }
    const shadowClip = (s.clip_low || 0) >= 0.5;
    const highClip = (s.clip_high || 0) >= 0.5;
    const sBtn = document.getElementById("hist-clip-shadow");
    const hBtn = document.getElementById("hist-clip-high");
    if (sBtn) {
      sBtn.style.background = "rgba(60, 100, 220, 0.95)";
      sBtn.style.opacity = shadowClip ? "1" : "0";
      sBtn.title = shadowClip ? `陰影裁切 ${(s.clip_low || 0).toFixed(2)}%` : "";
    }
    if (hBtn) {
      hBtn.style.background = "rgba(220, 60, 50, 0.95)";
      hBtn.style.opacity = highClip ? "1" : "0";
      hBtn.title = highClip ? `亮部裁切 ${(s.clip_high || 0).toFixed(2)}%` : "";
    }
  };

  /**
   * Wire histogram interactions: hover to show zone label + value-at-cursor.
   */
  const wireHistogramInteraction = () => {
    const wrap = document.getElementById("hist-wrap");
    const cursor = document.getElementById("hist-cursor");
    const label = document.getElementById("hist-zone-label");
    if (!wrap || !cursor || !label) return;

    wrap.addEventListener("mousemove", (e) => {
      const rect = wrap.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const ratio = Math.max(0, Math.min(1, x / rect.width));
      const bin = Math.round(ratio * 255);
      const zone = HIST_ZONES.find(z => bin >= z.from && bin <= z.to) || HIST_ZONES[0];
      cursor.style.left = `${x}px`;
      cursor.classList.remove("hidden");
      label.textContent = `${zone.label} · ${bin}`;
      label.classList.remove("hidden");
    });
    wrap.addEventListener("mouseleave", () => {
      cursor.classList.add("hidden");
      label.classList.add("hidden");
    });
  };

  /**
   * Update slider DOM to reflect new GradeSettings values pushed from Python.
   * @param {Object<string, number>} deltas - Field → new raw value (in settings units).
   */
  const syncSlidersFromDeltas = (deltas) => {
    Object.entries(deltas).forEach(([param, value]) => {
      const input = document.querySelector(`input[type=range][data-param="${param}"]`);
      if (!input) return;
      const scale = parseFloat(input.dataset.scale || "1") || 1;
      const sliderValue = scale === 1 ? value : value / scale;
      input.value = String(sliderValue);
      // Reuse the existing label updater
      input.dispatchEvent(new Event("input", { bubbles: false }));
    });
  };

  const wireAutoTone = () => {
    const btn = document.getElementById("btn-auto-tone");
    if (btn) {
      btn.addEventListener("click", async () => {
        if (!bridge) {
          setStatus("僅預覽模式 — 尚未連接後端");
          return;
        }
        btn.disabled = true;
        btn.style.opacity = "0.6";
        try {
          await new Promise((resolve) => bridge.applyAutoTone((res) => resolve(res)));
        } finally {
          btn.disabled = false;
          btn.style.opacity = "";
        }
      });
    }
    const reset = document.getElementById("btn-reset-light");
    if (reset) {
      reset.addEventListener("click", () => {
        const fields = ["exposure", "contrast", "highlights", "shadows", "whites", "blacks", "clarity", "dehaze"];
        const zeros = Object.fromEntries(fields.map((f) => [f, 0]));
        syncSlidersFromDeltas(zeros);
        // Push each zero to backend
        if (bridge) {
          fields.forEach((f) => bridge.setGradeParam(f, 0));
        }
      });
    }
  };

  const onSettingsApplied = (payload) => {
    try {
      const deltas = JSON.parse(payload);
      syncSlidersFromDeltas(deltas);
    } catch (_e) {
      // ignore
    }
  };

  const init = () => {
    wireSliders();
    wireButtons();
    wireAccordion();
    wirePresets();
    wireTreatment();
    wireFlip();
    wireHslTabs();
    wireCurves();
    wireFrame();
    wireOutput();
    wireAIDenoise();
    wireAutoTone();
    wireHistogramInteraction();
    wireCrop();
    if (typeof QWebChannel === "undefined") {
      setStatus("僅預覽模式（未連接 Qt 橋接）");
      return;
    }
    new QWebChannel(qt.webChannelTransport, (channel) => {
      bridge = channel.objects.bridge;
      bridge.previewReady.connect(onPreviewReady);
      bridge.statusChanged.connect(setStatus);
      bridge.exifReady.connect(onExifReady);
      bridge.histogramReady.connect(onHistogramReady);
      bridge.settingsApplied.connect(onSettingsApplied);
      if (bridge.batchProgress) bridge.batchProgress.connect((p) => window.__batchHandlers?.onProgress(p));
      if (bridge.batchFinished) bridge.batchFinished.connect((p) => window.__batchHandlers?.onFinished(p));
      setStatus("就緒 — 請載入相片");
    });
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
