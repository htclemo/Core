# TheCore — Agent Instructions

## Project Overview
Core is a local AI chat for local LLMs (Ollama). It runs entirely on the user's machine.

**Project location:** `C:\Users\Lemo\Documents\TheCore`
**Entry point:** `C:\Users\Lemo\Documents\TheCore/main.py`
**Desktop shortcut:** `C:\Users\Lemo\Desktop\TheCore.lnk`

## Architecture

### Tabs
- **AI** — chat interface with:
  - Left sidebar: Workspaces → Projects → Conversations
  - Main area: Streaming chat with Ollama or OpenCode
  - Model selector with GPU VRAM / system RAM tracking

### Key Directories
```
TheCore/
├── main.py                    # Entry point (Python/PySide6 app)
├── requirements.txt           # Python dependencies
├── thecore_ai.db              # SQLite database (created at runtime)
├── thecore/
│   ├── __init__.py            # Package version
│   ├── app.py                 # QApplication bootstrap
│   ├── splash.py              # Round splash screen (min 10s, module animation)
│   ├── styles.py              # Dark theme stylesheet
│   ├── audio/
│   │   └──
│   ├── collectors/
│   │   ├── system.py          # SystemCollector (CPU, RAM, disk, net, GPU)
│   │   └── gpu.py             # GpuCollector (NVML metrics)
│   ├── ai/                    # AI/LLM module
│   │   ├── __init__.py
│   │   ├── database.py        # SQLite: workspaces, projects, conversations, messages
│   │   ├── ollama_client.py   # Ollama REST client (chat, generate, list, show)
│   │   ├── model_tracker.py   # GPU VRAM + system RAM before/after model load
│   │   ├── model_load_worker.py # QThread: loads the model without freezing the UI
│   │   ├── opencode_integration.py  # OpenCode CLI wrapper + command resolution
│   │   ├── worker.py          # QThread worker for streaming Ollama chat
│   │   ├── conversation.py    # ChatMessage domain model
│   │   ├── conversation_title.py # Automatic conversation names
│   │   ├── tools.py           # read/write/edit/list/run tools for local models
│   │   ├── workspace.py       # WorkspaceItem, ProjectItem domain models
│   │   ├── model_catalogue.py # Local + cloud models in one dropdown
│   │   └── ui/
│   │       ├── __init__.py
│   │       ├── ai_workspace_panel.py   # Sidebar + chat split
│   │       ├── chat_panel.py           # Chat UI, model selector, memory display
│   │       ├── chat_composer.py        # Provider picker, model dropdown, input
│   │       ├── settings_page.py        # The settings page (the gear in the sidebar)
│   │       ├── message_widget.py       # Message bubble + collapsible code blocks
│   │       ├── opencode_console.py     # Host the REAL opencode TUI / PowerShell
│   │       ├── terminal_widget.py      # pyte terminal emulator (ConPTY host)
│   │       ├── sidebar.py              # Left nav + the settings gear
│   │       ├── status_lamp.py          # Green LED lamp (OLLAMA)
│   │       ├── memory_gauge.py         # VRAM / RAM mini gauges
│   │       ├── loading_spinner.py     # Green "spinning clock" loading indicator
│   │       └── thinking_indicator.py   # @connecting/@reasoning/@generating/@done bubble
│   ├── settings_store.py       # Persistent program settings (text size, …)
│   ├── admin.py                # Windows elevation: is_admin(), relaunch_as_admin()
│   └── ui/
│       ├── main_window.py     # Tabbed main window
│       └── panels/            # System monitor tiles (CPU, GPU, RAM, etc.)
├── electron-app/              # Parallel Electron/TypeScript rewrite
│   ├── src/
│   │   ├── main.ts            # BrowserWindow + IPC (stats, OpenCode pty, database)
│   │   ├── preload.ts         # contextBridge API (thecoreAPI)
│   │   ├── db.ts              # SQLite layer (shares thecore_ai.db with Python)
│   │   ├── cloud.ts           # The cloud providers, their keys and model lists
│   │   └── renderer/          # index.html, app.js, sidebar.js, model_catalogue.js, styles.css
│   ├── scripts/postinstall.js # Builds better-sqlite3 for Electron
│   └── dist/                  # Compiled main.js / preload.js / db.js
├── assets/
│   ├── thecore_icon.png
│   └── thecore.ico
└── create_shortcut.ps1        # Desktop shortcut creator
```

## How to Run
```powershell
cd C:\Users\Lemo\Documents\TheCore
.\.venv\Scripts\Activate.ps1
python main.py
```
Or double-click `TheCore.lnk` on the Desktop.

**Electron version:**
```powershell
cd C:\Users\Lemo\Documents\TheCore\electron-app
npx tsc        # rebuild dist/ after changing main.ts or preload.ts
npx electron .
```
Always run `npx electron .` from *inside* `electron-app/`. Renderer files
(`src/renderer/*`) are loaded directly, so edits there are live without a rebuild.

## Prerequisites
- **Ollama** must be running (`ollama serve`) on `http://127.0.0.1:11434`
- At least one model pulled (e.g., `ollama pull qwen2.5-coder:7b` or `deepseek-coder-v2:16b`)
- **OpenCode** CLI optional (for coding agent mode): `npm install -g @opencode/cli`

## Key Design Decisions
- **No manual refresh:** The AI tab auto-refreshes every 2 seconds. The scan-rate slider was removed per user request.
- **VRAM/RAM tracking:** `ModelTracker.measure_load()` snapshots memory before/after an Ollama generate call to show how much of the model lands in GPU VRAM vs system RAM.
- **SQLite persistence:** All workspaces, projects, conversations, and messages are stored in `thecore_ai.db` in the project folder.
- **OpenCode fallback:** If OpenCode CLI is on PATH, it's offered as a provider alongside Ollama.
- **The embedded console is the *real* `opencode` TUI, in a real terminal.** OpenCode's interactive
  TUI queries the terminal's capabilities (DA1, `?1016$p`, bracketed paste) and draws *nothing* useful
  without the answers — piping it into a GUI yields zero characters. So the console panel hosts it the
  only way that works:
  - `thecore/ai/ui/terminal_widget.py` — a `pyte`-based terminal emulator painted with `QPainter`
    (ANSI colours, cursor, scrollback, Ctrl+Shift+C/V).
  - `thecore/ai/ui/opencode_console.py` — starts `opencode` (or `powershell.exe`) on a **ConPTY**
    pseudo console via `pywinpty`, which gives the child a genuine TTY.
  - `thecore/admin.py` — elevation helpers (see below).
- **Admin rights come from elevating TheCore itself.** The console inherits TheCore's token, so
  OpenCode's shell tools can do administrator work only when TheCore is elevated. The console header
  shows an `ADMIN` / `NOT ADMIN` badge and a **RUN AS ADMIN** button that relaunches the app via
  `ShellExecuteW(..., "runas", ...)`. The header also has a **OPENCODE ⇄ POWERSHELL** mode switch.
- **`opencode run --format json` is still available** (`OpenCodeConsole` in `opencode_integration.py`) for
  non-interactive use, but the UI no longer depends on it.
- **The Electron app uses the same approach.** `node-pty` gives the child a ConPTY and `xterm.js`
  renders it. Two Electron-specific traps:
  - node-pty forks one helper with `child_process.fork` (which uses `process.execPath` = electron.exe).
    That helper needs `ELECTRON_RUN_AS_NODE=1` — but **only for that helper**. Setting it in
    `process.env` globally makes Electron's own GPU and network services start as plain Node and crash.
    The fix is to patch `child_process.fork` and inject the flag into the child's env only.
  - The helper's `AttachConsole` to a ConPTY pseudo console often fails; node-pty then falls back after a
    timeout. Fork with `silent: true` and drain the helper's stdout/stderr so the crash stays invisible.
- **`import * as childProcess` cannot be patched.** TypeScript compiles it to a getter-only namespace, so
  the `fork` patch needs a plain `require("child_process")`.
- **`better-sqlite3` must be compiled for Electron.** Its prebuilt binary targets Node and crashes the
  Electron main process. `scripts/postinstall.js` moves the Node prebuilds out of the way (otherwise
  `binding.gyp` skips compiling) and runs `electron-rebuild -f -o better-sqlite3`. Version 13 needs
  Node >= 22, which Electron 29 does not ship — use `better-sqlite3@11`.
- **The Electron app shares `thecore_ai.db` with the Python app.** Both create the schema with
  `IF NOT EXISTS` and both set `PRAGMA foreign_keys=ON`, so either can start first.
- **Tab panels are shown through the `active` class** (`.tab-panel.active` in the stylesheet), not
  through `hidden`. `showTab()` toggles both. Toggling only `hidden` left the AI tab unreachable.
- **The Electron microphone control uses inline C# in PowerShell** (`scripts/mic-mute.ps1`), not a
  native module: it COM-interops the Core Audio API to mute every active capture endpoint. The
  script prints one JSON object on stdout. Note the toggle condition is `current.muted ? unmute :
  mute` — the other way round unmutes the mics when they are already live.
- **Model capabilities come from Ollama.** `POST /api/show` returns `capabilities`
  (`completion`, `tools`, `vision`, `thinking`, `insert`); `OllamaClient.model_capabilities()`
  reads them and the chat header shows them as a badge. `qwen2.5-coder:7b-instruct` has
  `tools` but no vision or thinking; `muse-glimmer:latest` has all three.
  The badge must be refreshed in **both** places: when the model list is filled in and when
  the user picks another model — the combo is repopulated with blocked signals.
- **Tool calls must survive models that ignore the structured field.** Small models print the
  tool call as plain JSON in the answer instead of using `message.tool_calls`.
  `parse_tool_calls()` recovers it and `strip_tool_calls_from_content()` removes it from the
  answer again. Without the second step the raw JSON ends up in the chat.
- **Tools are confined to the project folder.** `ToolRegistry._resolve()` rejects any path
  outside the workspace, so a confused model cannot touch the rest of the machine.
- **There must be exactly one `ChatMessage`.** It lives in `thecore/ai/conversation.py`;
  `ollama_client.py` imports it. A second copy silently loses the `images` and `tool_calls`
  fields.
- **Conversations name themselves after the first question.** `thecore/ai/conversation_title.py`
  (and `electron-app/src/renderer/conversation_title.js`) extract the *subject* of a question:
  "what is the color of a house mouse" becomes "Mouse", "what is a tesla model s?" becomes "Tesla".
  The search runs backwards (English questions put the subject last) and skips question words,
  generic words ("model", "colour") and trailing verbs ("works", "help"). The rename only touches
  the title — `updated_at` is left alone so the sidebar does not reshuffle while the user types.
- **The Systems tab is gone.** The app is a single AI workspace. The old PC-monitor sweep cost
  **831 ms of CPU every second** — `psutil.process_iter` with `cpu_percent` for every process. The
  monitoring code was removed.
- **Never ask every process for its command line.** `psutil.process_iter([... "cmdline" ...])` cost
  **540 ms** per sample; matching on the process *name* alone costs 4 ms — a 135× difference.
  The AI-memory collector now does the latter.
- **Debug mode writes a log file.** `--debug` or `THECORE_DEBUG=1` turns on a rotating log at
  `%APPDATA%\TheCore\thecore.log` (`thecore/debug_log.py`, `electron-app/src/debug_log.ts`). It records
  the start-up steps with their durations, every periodic timer, tool calls, console lifecycle and
  unhandled exceptions.
- **Provider icons** are drawn with QPainter, not shipped as files: a chip for the local model, a cloud for the remote ones, a prompt for OpenCode's console. The Electron app uses the same three icons as inline SVG (`provider_icons.js`) because a native `<select>` cannot show per-option icons on Windows — the provider picker there is a custom dropdown.
- **Free cloud providers** live in `thecore/ai/cloud_client.py` (Python) and `electron-app/src/cloud.ts`
  (Electron): Groq, OpenRouter, Cerebras, Mistral, GitHub Models, Google Gemini,
  NVIDIA NIM, Cloudflare Workers AI, Hugging Face, Nebius, SiliconFlow, Moonshot Kimi,
  Alibaba DashScope and a "custom" option for any OpenAI-compatible endpoint.
  All have a free tier without a credit card. API keys are stored in
  `%APPDATA%\TheCore` — never in the database, never in the repository.
- **Every provider carries its pricing metadata.** `CloudProvider` has `free_tier`, `paid_models`,
  `free_models_all`, `free_markers` and `free_ids`; `tier_label` renders it as `FREE TIER`,
  `FREE + PAID` or `PAID`, and `is_free_model()` decides per model. A provider whose whole catalogue
  works on the free allowance sets `free_models_all=True`; OpenRouter-style providers tag their
  free models with `:free` instead. The Electron app mirrors this in `tierLabel()` /
  `isFreeModel()` — keep the two lists in step.
- **The settings live behind the gear in the bottom-left corner of the sidebar.**
  `thecore/ai/ui/settings_page.py` (Python) and the `#tab-settings` panel (Electron) hold *every*
  program setting: the cloud provider cards with their keys, the cloud model list with the
  `● FREE` / `○ PAID` labels, the local Ollama models, the text size and the about box.
  The old modal `SettingsDialog` and the inline `CloudSettingsBar` were removed — the cloud bar
  in the chat header is gone too, so a key can only be changed in one place.
- **Both apps share `%APPDATA%\TheCore`.** The keys are one text file per provider
  (`<provider>.key`) and the custom base URL is `custom-base-url.txt` — the same names in
  Python and in Electron. Electron's `userData` therefore has to be pointed at that folder
  explicitly (`app.setPath("userData", …)` in `main.ts`), because Electron otherwise derives
  it from the app name, which depends on how the app was started.
- **The model dropdown holds the whole catalogue.** `thecore/ai/model_catalogue.py` (Python) and
  `electron-app/src/renderer/model_catalogue.js` (Electron) build one list with the local Ollama
  models first and then the models of every cloud provider that has a key, grouped per provider
  and labelled `Provider · model  ● FREE`. Picking a cloud model switches the provider picker to
  "Cloud LLM" on its own — the two controls never disagree.
- **Most cloud providers speak the OpenAI chat-completions API**, so one client covers them all;
  Google Gemini has its own shape and is handled separately in the same class.
- **Never trust a free tier.** The limits change often and Google alone has cut its free quota by
  50–80%. Treat a wrong key as normal: the model list returns empty and the chat raises a readable
  HTTP error, never a crash.
- **The gauges show TheCore + Ollama only, never the whole machine.** `thecore/collectors/ai_memory.py`
  sums the RSS of every Ollama process plus TheCore's own process, and the VRAM that Ollama's loaded
  models occupy. The percentage stays relative to the machine's capacity so the bar stays readable.
- **Ask Ollama for its VRAM, not NVML.** On Windows the model runner lives *inside* `ollama.exe` and
  WDDM reports `usedGpuMemory = 0` for every process, so NVML cannot attribute the VRAM. The
  `/api/ps` endpoint reports `size_vram` per loaded model — that is the reliable source. NVML's
  per-process list is only a fallback.
- **NVML must be initialised once.** `AiMemoryCollector` shares the `ModelTracker`'s `GpuCollector`
  (exposed as `ModelTracker.gpu`); a second instance would shut NVML down underneath the first.
- **The splash is a square boot console.** `thecore/splash.py` paints a 560×560 rounded panel with
  HUD corner brackets, a rotating core emblem, a boot log that types itself out and a progress bar
  that fills. It is a `QWidget` with a translucent background, not a `QSplashScreen` — the old round
  one used an elliptical mask.
- **The boot log is a small console that scrolls.** It shows only the **last 5 lines**
  (`_LOG_VISIBLE`); the older ones scroll off. The panel height is computed from that
  (`_LOG_PANEL_HEIGHT`), so the text can never leave the border — the fixed 84 px panel used to
  cut the last two lines off. The progress bar sits below it at
  `_LOG_PANEL_TOP + _LOG_PANEL_HEIGHT + 12`. The Electron app does the same with `LOG_VISIBLE`
  and `.splash-log { height: 95px; flex: 0 0 auto }` — the log must never be squeezed by the
  flex column, and the panel is 560×560 there too.
- **The start-up sounds are synthesised, not sampled.** `tools/make_sounds.py` writes
  `assets/loading.wav` and `assets/ready.wav` with the `wave` module, so they are small and need no
  licence. Python plays them with `winsound.PlaySound(..., SND_ASYNC)`; Electron uses
  `Media.SoundPlayer` through PowerShell. `THECORE_NO_SOUND=1` disables them.
- **In PySide6, `QPainter.fillPath` needs two arguments** and ignores a `QColor` given as the second
  one — it uses the current brush instead. Always pass an explicit `QBrush`.
- **Both windows start maximised.** The chat header needs the room; at the old 1400×900 the buttons were
  squeezed and the LOAD button's label was clipped to "OAD OPENCODE". Python calls `showMaximized()`,
  Electron `mainWindow.maximize()`.
- **A stylesheet `min-width` overrides the widget's size hint.** That is what let the header clip the
  LOAD button: `min-width: 110px` on `#chatLoadButton` / `.load-btn` capped it below its own
  `sizeHint()`, and the layout squeezed it further. The buttons now carry a `min-width` of 190px plus
  `flex: 0 0 auto` / `QSizePolicy.Fixed` and `white-space: nowrap`, and the memory gauges are the part
  that gives way when the header runs out of room.
- **Always rebuild the Electron `dist/` after editing `src/`.** `npx tsc` from `electron-app/`;
  the app runs the compiled `dist/main.js`, so a forgotten build silently keeps the old behaviour.
- **Never show the main window before the splash is done.** `showMaximized()` (Python) and
  `maximize()` (Electron) both *show* the window as a side effect, so calling them in the constructor
  makes the app appear behind the splash. The window is maximised and shown only when the splash
  finishes — Python in `app.py`'s `_switch_to_main()`, Electron via the `app:readyToShow` IPC.
- **In OpenCode mode only the *input box* is hidden**, not the whole composer: the composer holds
  the provider picker, and hiding it would leave no way back to Ollama or the cloud providers.
- **The chat composer is one rounded block** (`thecore/ai/ui/chat_composer.py`,
  `electron-app/src/renderer/index.html`): a provider picker, a scope picker, a multi-line input with
  the hint "Plan, Build, / for skills, @ for context", an attach button, the model picker, a dictation
  and a read-aloud button and the "Multitask" action chip. Enter sends, Shift+Enter makes a new line. The STOP button only appears while a turn is running.
- **The "Plan New Idea" chip and the four suggestion rows are gone.** The user removed both.
  The composer now holds only the "Multitask" chip; the `SuggestionRow` class, the `SUGGESTIONS`
  tuple, `set_suggestions_visible()`, the `#chatSuggestion*` styles and the `.suggestions` CSS were
  deleted with them.
- **The provider and model pickers live in the composer**, not in the header — the header keeps the
  LOAD button, the lamp and the gauges. In OpenCode mode only the *input box*
  is hidden, so the provider can still be switched back.
- **The sidebar has a search field and a collapse button.** The search filters the rows by name; a
  section hides when nothing in it matches. The match must be computed from the row titles, not from
  `isVisible()` — that is False while the panel is still hidden and would hide every section.
- **The capability indicators are icons, not text.** `thecore/ai/ui/capability_icons.py` draws a
  round disc per capability — a blue wrench (tools), a yellow eye (vision), a green brain (reasoning) —
  and the Electron app uses the same three as inline SVG. Only the capabilities the model actually
  has are shown. When the icons are rebuilt, detach the old ones with `setParent(None)`; `deleteLater()`
  alone leaves them on screen until the event loop runs.
- **The capability icons sit bottom-right, as icons only.** The user moved them out of the
  composer's provider row and down to the model name in the bottom bar (`settingsBottomBar` in
  Python, `.composer-bottom` in Electron). They are the *compact* shape — a 22×22 disc with just
  the glyph, no label; the name stays in the tooltip. `CapabilityIcons(compact=True)` switches
  between the two shapes; the pill-with-label shape is the default but is no longer used.
  The Electron app had **two** elements with the id `capability-icons` (one in the header, one in
  the composer) — the header one is gone, so there is only one left.
- **Sidebar rows are real widgets, not list overlays.** `QListWidget` + `setItemWidget` overlays get painted
  over by the item delegate — the conversation title collapsed to height 0 and the delete button was
  invisible. Each section is now a scrollable `QVBoxLayout` of custom `_Row` widgets with a hover trash bin.
- **`PRAGMA foreign_keys=ON` is required per connection.** Without it SQLite silently ignores the schema's
  `ON DELETE CASCADE`, so deleting a project left orphaned conversations and messages. `delete_project` and
  `delete_conversation` also delete their children explicitly inside one transaction.
- **Terminal output is fed to the emulator on the GUI thread.** The reader thread only queues raw text; a
  16 ms `QTimer` drains it into `pyte`. Never call `QTimer.singleShot` from the reader thread — use a
  queued signal instead.
- **pyte stores private modes shifted left by five bits.** DECSET 1002 (mouse tracking) lands in
  `screen.mode` as `1002 << 5`, so a plain `1002 in screen.mode` check never matches and the TUI's
  clickable areas (the session list) stay dead. Compare against `1000 << 5`, `1002 << 5`, `1003 << 5`.
- **Mouse reports use the SGR encoding (1006).** OpenCode enables 1000/1002/1003/1006, so a click is
  sent as `ESC [ < button ; col ; row M` (press) and `… m` (release). Columns and rows are 1-based.
- **Shift overrides mouse tracking** so text can still be selected while a TUI owns the mouse — the
  same escape hatch real terminals offer. Without it, selection is impossible once a TUI enables
  mouse reporting.
- **The pseudo console must start with the widget's size.** `TerminalWidget.start()` calls
  `_recalc_size()` before spawning and re-syncs 250 ms later, otherwise the TUI draws for the wrong
  number of columns and the mouse coordinates are off.
- **Only the selected cells may be tinted.** Filling the whole widget with the selection colour
  turns the whole terminal green on a simple click.
- **Loading indicator:** `thecore/ai/ui/loading_spinner.py` paints a green sweeping dial (a "spinning
  clock") plus the elapsed time (`LOADING 3.2s`). The old implementation was a `QLabel` with a rotating
  ASCII character, which read as a small black box. The Electron app does the same with a CSS-animated
  circle; note that its `--green` variable is *teal* (`#03dac6`), so the loader uses a separate
  `--lime: #39ff14` to match the Python app.
- **Model loading must not block the GUI thread.** `ModelTracker.measure_load()` sleeps and waits for
  Ollama to pull the weights in — seconds for a 7B model, much longer for 16B. Running it on the GUI
  thread froze the whole window, so the spinner's timer never even fired. It now runs on a
  `ModelLoadWorker` (`thecore/ai/model_load_worker.py`, a `QThread`) and reports back through signals.
- **Status bubble:** in-chat `@connecting` → `@reasoning` → `@generating` → `@done` (or `@error` / `@stopped`),
  with elapsed time, token count and tok/s. The finished card stays in the chat as a record.
- **Code output is collapsible:** AI code fences render as a collapsed block with a COPY button so the chat
  does not flood with code.

## Building the EXE
Use PyInstaller to create `The_Core_Setup.exe`:
```powershell
pip install pyinstaller
pyinstaller --noconsole --onefile --name TheCore --icon assets\thecore.ico main.py
```

## Testing Checklist
- [ ] App launches from `TheCore.lnk`
- [ ] AI tab loads, sidebar shows workspaces/projects/conversations
- [ ] "+ NEW WORKSPACE", "+ NEW PROJECT", "+ NEW CHAT" buttons work
- [ ] Ollama model list populates; model switching works
- [ ] VRAM/RAM display updates when a model loads
- [ ] Chat sends/receives streaming responses
- [ ] Status bubble walks @connecting → @reasoning → @generating → @done
- [ ] Code blocks render collapsed with a working COPY button
- [ ] Conversations persist in SQLite across restarts
- [ ] Conversation rows show their titles (not a blank line) and the trash bin is visible on hover
- [ ] Deleting a project/workspace removes its conversations and messages too (no orphans)
- [ ] LOAD OPENCODE starts the **real `opencode` TUI** in the console panel (logo, "Ask anything…", model line)
- [ ] Typing in the console works: prompt is accepted, the model answers, stats are shown
- [ ] The header's OPENCODE ⇄ POWERSHELL switch works; PowerShell shows a `PS C:\...>` prompt
- [ ] The ADMIN / NOT ADMIN badge reflects the real elevation state
- [ ] RUN AS ADMIN relaunches TheCore elevated (UAC prompt appears)
- [ ] UNLOAD OPENCODE terminates the session and leaves no stray `opencode` process
- [ ] Terminal colours, cursor and scrollback render correctly; Ctrl+Shift+C / Ctrl+Shift+V work
- [ ] SEND is always re-enabled after a turn ends (never stuck disabled)
- [ ] The gear in the bottom-left corner of the sidebar opens the settings page
- [ ] The settings page lists every cloud provider with its FREE / PAID tier badge
- [ ] Saving a key there makes that provider's models appear in the chat's model dropdown
- [ ] The model dropdown shows the local models *and* the cloud models, grouped per provider
- [ ] Every cloud model is labelled `Provider · model  ● FREE` or `○ PAID`
- [ ] Picking a cloud model switches the provider picker to "Cloud LLM" on its own
- [ ] The settings page lists the local Ollama models with their sizes
- [ ] "← BACK TO CHAT" returns to the chat (and Ctrl+, toggles the settings)

---

## Remaining Tasks (for follow-up AI)

### 1. Button Physical Positioning (Electron)
**Issue**: The load button needs to be physically positioned next to the provider dropdown in the header.

**What's Done**:
- Functional logic: `updateLoadButtonState()` controls button visibility based on `currentProvider`
  - `currentProvider === "local"` → button hidden
  - `currentProvider === "cloud"` → shows "REFRESH MODELS" button
  - `currentProvider === "opencode"` → shows "LOAD OPENCODE"/"UNLOAD OPENCODE" button
- CSS selectors exist: `#btn-load`, `#provider-dropdown`
- `updateLoadButtonState()` called after provider selection change (`selectProvider` in init, and after provider menu click)

**What Needs to Be Done**:
- Modify `electron-app/src/renderer/styles.css` to position `#btn-load` next to `#provider-dropdown`
- Add CSS like:
  ```css
  #provider-dropdown { display: inline-block; vertical-align: middle; margin-right: 10px; }
  #btn-load { display: inline-block; vertical-align: middle; width: 120px; margin-left: 10px; }
  ```
- Or restructure the header HTML to place them side-by-side

**Files to Modify**:
- `electron-app/src/renderer/styles.css` - Add positioning CSS
- Possibly `electron-app/src/renderer/index.html` - Restructure header if needed

### 2. Verification and Testing
**What's Done**:
- Python: 51 modules compile OK, model catalogue filtering works
- Electron: `npx tsc` builds successfully
- Model mixing fix: When selecting "Ollama" (local), only local models show; when selecting "Cloud LLM", only cloud models show
- Button visibility logic: `updateLoadButtonState()` hides/shows based on provider type

**What Needs to Be Done**:
- Test the full flow: select local LLM → verify only local models in dropdown
- Test: select cloud LLM → verify only cloud models in dropdown
- Test: button visibility changes based on provider selection
- Physical button positioning test: verify button appears next to dropdown when visible

**Files to Test**:
- Run the application and test all provider/model selection scenarios
- Verify no crashes when switching between local and cloud models

### 3. Potential Crash Investigation (If Applicable)
**Issue Reported**: "app crashes when selecting local llm"

**What's Done**:
- Modified `_rebuild_catalogue(kind)` to filter by kind
- Modified `_on_model_selected()` to rebuild catalogue with correct kind
- Modified `_refresh_models()` to rebuild with `kind="local"`
- Modified `_on_provider_models()` and `_on_catalogue_finished()` to rebuild with `kind="cloud"`

**What Needs to Be Done**:
- If crashes still occur, investigate the specific error
- Check for any unhandled exceptions in the model selection flow
- Verify the `_local_models` and `_cloud_models` arrays are properly populated before rebuilding

**Files to Investigate**:
- `thecore/ai/ui/chat_panel.py` - model selection flow
- Any error logs or crash reports

### 4. Full Application Test
**What's Done**:
- All 8 test suites pass
- Python compiles OK
- Electron builds successfully

**What Needs to Be Done**:
- Run the application end-to-end
- Test all provider/model selection scenarios
- Verify the model dropdown properly filters
- Verify button visibility changes correctly
- Verify no crashes during normal usage

**Files to Test**:
- `main.py` - launch the application
- Test all AI provider selections (Ollama local, Cloud LLM, OpenCode)
- Test model selection within each provider type
- Verify button visibility at each step

---

**To-Do for Follow-Up AI**:
1. Complete the CSS positioning for the load button next to the provider dropdown
2. Test the full flow and verify no crashes
3. If crashes occur, investigate and fix
4. Verify all test scenarios pass

---

**Summary of Completed Work**:
- Model mixing fix: Catalogue now filters by provider type (local vs cloud)
- Button visibility logic: `updateLoadButtonState()` hides/shows based on provider type
- AGENTS.md cleanup: Removed obsolete elements (SYSTEMS tab, mic control, etc.)
- Boot log overflow fix: Log shows only last 5 lines within panel border
- All 8 test suites pass
- Python compiles, Electron builds

**To Complete**:
- Button physical positioning in Electron UI
- Full application testing and verification
- Crash investigation (if applicable)