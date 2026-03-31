# FigmaFlow

Interactive CLI to configure Figma MCP server for every major coding agent.

一鍵設定 Figma MCP 到所有主流 Coding Agent 的互動式 CLI 工具。

```
npx figmaflow
```

## What it does / 功能簡介

FigmaFlow walks you through an interactive setup to connect Figma's MCP server to your coding agent. It generates the correct config file — in the right format, at the right path, with the right key names — so you don't have to look up the differences between 14 agents.

FigmaFlow 透過互動式問答，幫你產生正確的 Figma MCP 設定檔。不同 agent 的格式 (JSON/TOML/YAML)、檔案路徑、key 名稱全部自動處理，不用再查文件。

## Features / 特色

- **14 coding agents** — Claude Code, Cursor, VS Code, Windsurf, Codex, Zed, JetBrains, Augment, Cline, Roo Code, Continue, Amazon Q, Gemini CLI, Antigravity
- **4 MCP modes** — Official Remote (OAuth), Official Desktop, Framelink Community (PAT), or Both (recommended)
- **3 languages** — English, 繁體中文, 日本語
- **Multi-agent select** — configure multiple agents in one run / 一次設定多個 agent
- **Smart merge** — detects existing config, merges Figma entries while preserving your other MCP servers / 偵測現有設定檔，合併而非覆蓋
- **Auto backup** — creates `.bak` before modifying any existing file / 修改前自動備份
- **CSS + Frontend framework** — independent selection: Tailwind / Bootstrap / CSS Modules / SCSS / Pure CSS × React / Vue / Svelte / Angular / Next.js / Nuxt
- **Style modes** — Pixel Perfect, Balanced, or Design Reference
- **Design-to-code rules** — generates best-practice rules file in each agent's native format (`.mdc`, `.md`, `.clinerules`, etc.)
- **SVG fallback** — when rate-limited, rules guide the agent to infer design from copied SVG
- **Rate limit awareness** — shows Figma API limits for your plan tier and embeds limits in rules

## Supported Agents / 支援的 Agent

| Agent | Format | Key | Scope |
|---|---|---|---|
| Claude Code | JSON | `mcpServers` | Project / Global |
| Cursor | JSON | `mcpServers` | Project / Global |
| VS Code (Copilot) | JSON | `servers` | Project / Global |
| Windsurf | JSON | `mcpServers` | Global only |
| Codex (OpenAI) | TOML | `mcp_servers` | Project / Global |
| Zed | JSON | `context_servers` | Global only |
| JetBrains AI (Junie) | JSON | `mcpServers` | GUI only |
| Augment Code | JSON | `mcpServers` | Project only |
| Cline | JSON | `mcpServers` | GUI only |
| Roo Code | JSON | `mcpServers` | Project only |
| Continue | YAML | `mcpServers` | Project / Global |
| Amazon Q | JSON | `mcpServers` | Global only |
| Gemini CLI | JSON | `mcpServers` | Global only |
| Antigravity (Google) | JSON | `mcpServers` | Global only |

## MCP Server Options / MCP 伺服器選項

| Mode | Auth | Transport | Notes |
|---|---|---|---|
| **Official Remote** | OAuth | HTTP | Broadest features, all plans including free |
| **Official Desktop** | N/A | localhost:3845 | Requires Figma desktop app, paid plans only |
| **Framelink Community** | PAT | stdio (npm) | 25% smaller output, open source |
| **Both** (recommended) | OAuth + PAT | HTTP + stdio | Framelink for reads, Official for writes & design system |

> All MCP servers share the same Figma API rate limits. Starter/View/Collab seats = 6 calls/month (unusable). Pro Full/Dev = 200/day. Enterprise Full/Dev = 600/day.
>
> 所有 MCP 伺服器共用 Figma API 速率限制。Starter/View/Collab 座位每月僅 6 次（基本無法使用）。

## Interactive Flow / 互動流程

```
🌐 Language        → English / 繁體中文 / 日本語
🤖 Agents          → Multi-select (space to pick, enter to confirm)
🔌 MCP Type        → Remote / Desktop / Framelink / Both
⚠  Rate Limits     → Shows your plan's API limits
📁 Scope           → Project / Global
🎨 CSS Framework   → Tailwind / Bootstrap / CSS Modules / SCSS / Pure CSS
⚛️  Frontend        → React / Vue / Svelte / Angular / Next.js / Nuxt / None
✏️  Style Mode      → Pixel Perfect / Balanced / Design Reference
🧩 Components      → Component First / No Components
🔑 API Key         → Figma PAT (required for Framelink/Both)
📋 Rules           → Generate design-to-code rules file? Yes / No
```

## Development / 開發

```bash
git clone https://github.com/NelsonChen1982/figmaflow.git
cd figmaflow
npm install
npm run dev      # Run with tsx (development)
npm run build    # Build with tsup
```

## License

MIT
