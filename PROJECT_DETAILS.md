# TheCore — Project Details

## Goal
A local LLM workspace inside Core.
Use a local LLM (Ollama) for AI chat, keep track of PC metrics, save workspaces/conversations,
and eventually package as `The_Core_Setup.exe`.

## Features Implemented

### PC Monitor (SYSTEMS tab)
- CPU usage (per-core + total)
- NVIDIA GPU: utilization, VRAM used/total, temperature (via NVML)
- System RAM: used/total/available/percent
- Per-drive: space, read/write MB/s
- Network: up/down MB/s
- Top processes by CPU
- Microphone mute/unmute
- **Live/automatic refresh at 1 second** (no manual scan control)

### AI Chat (AI tab)
- **Chat input:** a composer — provider and scope pickers, a multi-line input, an
  attach button, the model picker, dictation (Win+H) and read-aloud (SAPI) and the "Multitask"
  action chip that pre-fills the input
- **Left sidebar:**
  - Workspaces → Projects → Conversations, each row with a hover trash bin
  - Deleting a project removes its conversations and messages too
  - A new conversation is named after its first question ("Mouse", "Tesla", "Python"…)
  - Workspaces list with "+ NEW WORKSPACE"
  - Projects list (filtered by selected workspace) with "+ NEW PROJECT"
  - Conversations list (filtered by selected project) with "+ NEW CHAT"
  - Hovering a conversation reveals a red trash bin; deletion asks for confirmation
  - A **gear** in the bottom-left corner opens the settings page (also `Ctrl+,`)
- **Header row:**
  - Provider selector with icons: a **chip** for Ollama (local), a **cloud** for the free cloud
    providers and a **prompt** for OpenCode's console
  - Model dropdown: the **whole catalogue** — the local Ollama models plus the
    models of every cloud provider with a key, grouped per provider and
    labelled `Provider · model  ● FREE` / `○ PAID`.  OpenCode has a single
    fixed entry.
  - LOAD / UNLOAD button (loads an Ollama model, or starts/stops the OpenCode console)
  - Green LED lamp captioned `OLLAMA` (tooltip carries the full status text)
  - VRAM + system RAM mini gauges, sampled continuously
  - Optional REASONING ON/OFF toggle, only shown when the model advertises `thinking`
- **Main chat area:**
  - Streaming chat responses with a STOP button
  - In-chat status bubble: `@connecting` → `@reasoning` → `@generating` → `@done`
    (or `@error` / `@stopped`) with elapsed time, tokens and tok/s
  - Message bubbles (user right, assistant left); code fences render as a
    **collapsed** block with a COPY button
  - Draggable grip bar between chat and the OpenCode console (double-click resets)
- **Persistence:** SQLite database (`thecore_ai.db`) stores all workspaces, projects, conversations, messages
- **OpenCode console:** the **real** OpenCode interface, embedded (see "How the OpenCode console works")

## Model capabilities: tools, vision and reasoning

Ollama reports what each model can do, and TheCore reads that from
`POST /api/show`. The **bottom-right corner** shows it as three small icons
next to the model name — a blue wrench (Tool Use), a yellow eye (Vision) and a
green brain (Reasoning). Only the capabilities the model actually has are
drawn, and the name of each stays available as a tooltip. The chat offers
exactly what the model supports.

| Model | Tools | Vision | Reasoning | Size |
|---|---|---|---|---|
| `qwen2.5-coder:7b-instruct` | yes | no | no | 4,7 GB |
| `muse-glimmer:latest` | yes | **yes** | **yes** | 18 GB |
| `deepseek-coder-v2:16b` | no | no | no | 8,9 GB |

**Tools** (`thecore/ai/tools.py`, `electron-app/src/tools.ts`) — `read_file`, `write_file`,
`edit_file`, `list_directory` and `run_command`. The model decides to call them, they run,
and the results go back into the conversation (up to 8 rounds). Every path is
resolved inside the project folder and may not escape it, so a confused model
cannot touch the rest of the machine. The chat shows each call as
`⚙ wrote bye.py`.

Smaller models often ignore Ollama's structured `tool_calls` field and print
the JSON as plain text instead. `parse_tool_calls()` recognises that and
`strip_tool_calls_from_content()` takes it out of the answer again, so the
tools work with `qwen2.5-coder:7b-instruct` too.

**Vision** — the 📎 button attaches an image; it is only enabled for models
with the `vision` capability. The image is sent base64-encoded in the message.

**Reasoning** — models with the `thinking` capability get `think: true` and
their chain of thought appears in the status bubble. The REASONING toggle
switches it off.

## Free cloud providers

Besides the local models, TheCore can talk to free cloud LLMs.  All of these
have a free tier **without a credit card** (checked October 2026):

| Provider | Free allowance | Card? | Trains on your data? |
|---|---|---|---|
| **Groq** | 30 rpm, thousands/day, very fast | no | no |
| **OpenRouter** | 20 rpm, 50/day (1000 after a $10 top-up), 20+ `:free` models | no | no |
| **Cerebras** | 30 rpm, ~1M tokens/day | no | no |
| **Mistral** | free "Experiment" tier, ~1B tokens/month, Codestral/Devstral | no | yes (Experiment) |
| **GitHub Models** | 15 rpm, 150–1000/day, GPT-4o + Claude + Llama | no | no |
| **Google Gemini** | 15 rpm / 1500 per day on the Flash models, 1M context | no | yes (except EU/UK/EEA) |

There are more: NVIDIA NIM, Cloudflare Workers AI, Hugging Face, Nebius AI
Studio, SiliconFlow, Moonshot Kimi, Alibaba DashScope — and a "custom" entry
for any OpenAI-compatible endpoint.

### Where the keys live

Open the **settings page** with the gear in the **bottom-left corner of the
sidebar** (or `Ctrl+,`).  It holds every setting of the program:

* one card per cloud provider with its **FREE TIER / FREE + PAID / PAID**
  badge, the key field, a *GET A FREE KEY* button and a *SAVE* / *CLEAR* pair,
* the model list of the selected provider, every model labelled
  **● FREE** or **○ PAID**,
* the local Ollama models with their sizes,
* the text size and the about box.

The key is stored under `%APPDATA%\TheCore` — never in the database, never in
the repository.

### One dropdown for every model

The model picker at the **bottom-right of the chat** holds the *whole*
catalogue: the local Ollama models first, then the models of every cloud
provider that has a key — grouped per provider and labelled
`Provider · model  ● FREE`.  Pick one and the provider picker follows on its
own, so there is one place to choose from.

Most providers speak the OpenAI chat-completions API, so one client covers them
all; Google Gemini has its own shape and is handled separately.

**Caveats.**  Free tiers change often — Google alone cut its free quota by
50–80% in December 2025.  Treat them as a prototyping budget, not a
production budget.  A wrong key is normal: the model list comes back empty
and the chat raises a readable HTTP error.

## How the OpenCode console works

TheCore shows the **genuine `opencode` CLI** — the same interactive TUI you
get in a terminal window — not a re-implementation.

The hard part is that the OpenCode TUI is a terminal application. It queries
the terminal's capabilities (DA1, `?1016$p`, bracketed paste, SGR mouse) and
draws nothing useful without the answers, so piping it into a GUI produces
**zero characters**. The console panel therefore provides the missing half:

1. **A real terminal.** `thecore/ai/ui/terminal_widget.py` is a terminal
   emulator built on `pyte`: it interprets the VT sequences the child emits
   and paints the resulting screen with `QPainter` (ANSI colours, cursor,
   scrollback, Ctrl+Shift+C/V copy-paste, mouse-wheel scrolling).
2. **A real TTY.** `thecore/ai/ui/opencode_console.py` launches the child on
   a **ConPTY** pseudo console through `pywinpty`, so `opencode` sees the
   terminal it expects and negotiates with it normally.
3. **Real privileges.** The console inherits TheCore's token. The header
   shows an `ADMIN` / `NOT ADMIN` badge, and **RUN AS ADMIN** relaunches
   TheCore elevated via `ShellExecuteW(..., "runas", ...)` — after which
   OpenCode's shell tools can do administrator work.
4. **A mode switch.** The header toggles between `OPENCODE` and `POWERSHELL`,
   giving the same environment you would get from an administrator PowerShell.

The header also has START and STOP for the session; the chat panel's
LOAD/UNLOAD OPENCODE button does the same thing.

Note: `opencode serve` (OpenCode's local *web* app) is deliberately not used —
it asks for a pairing login, which is not what an interactive console should
be. `opencode run --format json` still exists in
`thecore/ai/opencode_integration.py` for non-interactive scripting, but the UI
no longer depends on it.

## Tech Stack
- Python 3.x
- PySide6 (Qt for Python) — UI
- psutil — system metrics
- nvidia-ml-py (pynvml) — NVIDIA GPU metrics
- SQLite (built-in) — AI data persistence
- urllib (built-in) — Ollama REST client
- pywinpty — ConPTY pseudo console (gives the child a real TTY)
- pyte — terminal emulator (interprets the VT sequences the child emits)
- PyInstaller — EXE packaging (to be added)
- Electron 29 + TypeScript — parallel rewrite in `electron-app/`

## File Inventory (new/changed)

### AI module
- `thecore/ai/__init__.py` — AI package exports
- `thecore/ai/database.py` — SQLite schema + CRUD
- `thecore/ai/ollama_client.py` — Ollama REST client
- `thecore/ai/model_tracker.py` — GPU VRAM / RAM tracker
- `thecore/ai/opencode_integration.py` — OpenCodeIntegration + command resolution
- `thecore/ai/worker.py` — QThread streaming worker
- `thecore/ai/conversation.py` — ChatMessage domain model
- `thecore/ai/workspace.py` — WorkspaceItem, ProjectItem
- `thecore/ai/ui/__init__.py` — AI UI exports
- `thecore/ai/ui/ai_workspace_panel.py` — Sidebar + chat split panel
- `thecore/ai/ui/chat_panel.py` — Chat UI with model selector & memory tracker
- `thecore/ai/ui/message_widget.py` — Message bubble + collapsible code blocks
- `thecore/ai/ui/opencode_console.py` — Hosts the real `opencode` TUI / PowerShell
- `thecore/ai/ui/terminal_widget.py` — pyte terminal emulator (ConPTY host)
- `thecore/ai/ui/sidebar.py` — Left nav sidebar: custom row widgets + hover trash bin
- `thecore/ai/ui/status_lamp.py` — Green LED status lamp
- `thecore/ai/ui/memory_gauge.py` — VRAM / RAM mini gauges
- `thecore/ai/ui/thinking_indicator.py` — In-chat status bubble + stats

### Electron app (`electron-app/`)
- `electron-app/src/main.ts` — Window, system stats IPC, OpenCode ConPTY IPC, database IPC, elevation
- `electron-app/src/preload.ts` — `thecoreAPI` contextBridge
- `electron-app/src/db.ts` — SQLite layer; shares `thecore_ai.db` with the Python app
- `electron-app/src/renderer/app.js` — Renderer logic (chat, xterm terminal, gauges)
- `electron-app/src/renderer/sidebar.js` — Workspaces → projects → conversations with delete buttons
- `electron-app/src/renderer/index.html`, `styles.css` — Layout + theme
- `electron-app/src/renderer/vendor/` — Vendored `xterm.js` + `addon-fit` (UMD)
- `electron-app/scripts/postinstall.js` — Compiles `better-sqlite3` for Electron

### Modified files
- `thecore/ui/main_window.py` — Tabbed window (SYSTEMS + AI), removed manual refresh
- `thecore/styles.py` — dark theme
- `thecore/admin.py` — Windows elevation (`is_admin`, `relaunch_as_admin`)
- `thecore/app.py`, `thecore/splash.py` - Square boot-console splash, 10s minimum, boot log + sound
- `tools/make_sounds.py` - Synthesises the start-up WAV files
- `assets/loading.wav`, `assets/ready.wav` - Start-up and ready sounds
- `README.md` — Updated with AI tab docs
- `AGENTS.md` — Agent instructions

## Next Steps / Todo
- [x] OpenCode provider integration — **real `opencode` TUI** in an embedded terminal (ConPTY + pyte)
- [x] Admin rights for the console (elevation badge + RUN AS ADMIN)
- [x] Removable projects / conversations (sidebar trash bins + cascading deletes)
- [x] Status bubble, collapsible code blocks, VRAM/RAM gauges
- [x] Electron parity — the Electron app runs the same real TUI via node-pty + xterm.js
- [x] Electron parity — green loading spinner with elapsed time + ADMIN badge + RUN AS ADMIN
- [x] Electron parity — sidebar with workspaces/projects/conversations, delete buttons and
      SQLite persistence (shared `thecore_ai.db` with the Python app)
- [x] Electron parity — microphone mute button (inline C# over the Core Audio COM API)
- [ ] Build `The_Core_Setup.exe` with PyInstaller
- [ ] Test .exe launch from desktop shortcut

## Known Limitations
- Ollama must be running separately (`ollama serve`)
- GPU metrics require NVIDIA GPU + NVML
- OpenCode provider requires the `opencode` CLI (`npm install @opencode/cli`)
- Embedding the real OpenCode TUI needs `pywinpty` and `pyte` (Windows-only for pywinpty)
- The console can only be an administrator console while TheCore itself is elevated
- VRAM delta may read 0 if Ollama shares memory or model was already loaded
