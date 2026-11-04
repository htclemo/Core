import { app, BrowserWindow, ipcMain, shell, dialog, Menu } from "electron";
import { execFileSync } from "child_process";
import type { IPty } from "node-pty";
import * as os from "os";
import * as path from "path";
import * as fs from "fs";

import { TheCoreDatabase } from "./db";
import { ToolRegistry } from "./tools";
import { enableDebugging, log, logError, logTiming } from "./debug_log";
import {
  CLOUD_PROVIDERS,
  CLOUD_PROVIDERS_BY_ID,
  CloudClient,
  configuredProviders,
  listConfiguredModels,
  loadBaseUrl,
  loadCloudKey,
  providerFor,
  saveBaseUrl,
  saveCloudKey,
  tierLabel,
} from "./cloud";

// A plain require is needed here: the compiled CommonJS turns
// `import * as childProcess` into a getter-only namespace, and the patch
// below has to replace a property on the real module object.
const childProcess = require("child_process") as typeof import("child_process");

// node-pty spawns one helper process with `child_process.fork`, which uses
// `process.execPath`.  Under Electron that is electron.exe, and the helper
// then fails with "AttachConsole failed" when the pseudo console is torn
// down.  Setting ELECTRON_RUN_AS_NODE for *that helper only* makes it behave
// like plain Node.
//
// The flag must not go into `process.env` globally: Electron's own GPU and
// network services are child processes too, and they would then start as
// plain Node and crash.
const _origFork = childProcess.fork;
childProcess.fork = ((
  modulePath: string,
  args: string[],
  options?: Record<string, unknown>,
) => {
  const opts = { ...(options || {}) } as Record<string, unknown>;
  opts.env = {
    ...((opts.env as Record<string, string>) || process.env),
    ELECTRON_RUN_AS_NODE: "1",
  };
  // node-pty's helper attaches to the ConPTY pseudo console, which often
  // fails ("AttachConsole failed").  The helper then dies noisily while
  // node-pty falls back to a timeout.  Keep its output out of the way.
  opts.silent = true;
  const child = _origFork(modulePath, args, opts as never);
  (child.stdout as unknown as { resume?: () => void })?.resume?.();
  (child.stderr as unknown as { resume?: () => void })?.resume?.();
  child.on("error", () => {
    // The helper failing is handled by node-pty's fallback.
  });
  return child;
}) as typeof childProcess.fork;

// node-pty is loaded *after* the fork patch above, so its helper inherits it.
const pty = require("node-pty") as typeof import("node-pty");

// TheCore — Electron main process.
// Spawns the main BrowserWindow, handles IPC from the renderer (OpenCode
// console, model selection, system stats), and manages the splash screen timing.

let mainWindow: BrowserWindow | null = null;

// ------------------------------------------------------------------ window

function createWindow(): void {
  const buildStarted = Date.now();
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1000,
    minHeight: 700,
    title: "Core",
    icon: path.join(__dirname, "../../assets/thecore.ico"),
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
    show: false, // hidden until ready; the renderer asks for it after the splash
  });

  // Do *not* maximise here: Electron's maximize() also *shows* the window, so
  // it would appear straight away, behind the splash screen.  The window is
  // maximised and shown when the renderer says the splash is done.

  mainWindow.loadFile(path.join(__dirname, "../src/renderer/index.html"));

  mainWindow.webContents.on("render-process-gone", (_event, details) => {
    logError("renderer", new Error(JSON.stringify(details)));
  });
  mainWindow.webContents.on("did-fail-load", (_event, code, description) => {
    logError("renderer load", new Error(`${code} ${description}`));
  });

  logTiming("BrowserWindow created", buildStarted);

  mainWindow.once("ready-to-show", () => {
    // Let the renderer control when to show (after splash animation).
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
    stopOpencodeConsole();
  });
}

// ------------------------------------------------------------------ helpers

/** Resolve an executable on PATH (Windows aware). */
function whichSync(name: string): string | null {
  const exts = (process.env.PATHEXT || ".COM;.EXE;.BAT;.CMD")
    .split(";")
    .filter(Boolean);
  const hasExt = path.extname(name) !== "";
  const dirs = (process.env.PATH || "").split(path.delimiter).filter(Boolean);

  for (const dir of dirs) {
    if (hasExt) {
      const exact = path.join(dir, name);
      if (fs.existsSync(exact)) return exact;
    }
    for (const ext of exts) {
      const candidate = path.join(dir, name + ext.toLowerCase());
      if (fs.existsSync(candidate)) return candidate;
    }
  }
  return null;
}

/**
 * Locate the OpenCode CLI.
 *
 * OpenCode's interactive TUI needs a real TTY and produces *no* readable
 * characters when piped, so TheCore drives `opencode run --format json`
 * instead.  The npm `opencode.cmd` wrapper is a batch file — Node refuses to
 * spawn `.cmd` files without a shell, and `cmd.exe` mangles prompts that
 * contain `&`, `|`, `>` or `%`.  So we call the real `opencode.exe` directly
 * whenever we can find it.
 */
function findOpencodeCommand(): { cmd: string; args: string[] } | null {
  const appData = process.env.APPDATA || "";
  if (appData) {
    const npmExe = path.join(
      appData,
      "npm",
      "node_modules",
      "@opencode",
      "cli",
      "bin",
      "opencode.exe"
    );
    if (fs.existsSync(npmExe)) return { cmd: npmExe, args: [] };
  }

  for (const name of ["opencode.exe", "opencode"]) {
    const found = whichSync(name);
    if (found && !/\.(cmd|bat)$/i.test(found)) return { cmd: found, args: [] };
  }

  const wrapper = whichSync("opencode.cmd");
  if (wrapper) return { cmd: "cmd.exe", args: ["/c", wrapper] };

  return null;
}

function stripAnsi(text: string): string {
  // eslint-disable-next-line no-control-regex
  return text.replace(/\x1b\[[0-9;?]*[a-zA-Z]|\x1b\].*?\x07|\x1b[()][A-B0-9]/g, "");
}

function sendOutput(text: string): void {
  if (mainWindow) mainWindow.webContents.send("opencode:output", text);
}

function sendStatus(text: string): void {
  if (mainWindow) mainWindow.webContents.send("opencode:status", text);
}

// ------------------------------------------------------------------ OpenCode IPC
//
// The OpenCode CLI is an interactive TUI.  It queries the terminal's
// capabilities (DA1, ?1016$p, bracketed paste) and draws nothing useful
// without the answers, so it must run on a real pseudo console.  node-pty
// provides ConPTY on Windows, which gives the child a genuine TTY; the
// renderer draws the stream with xterm.js.

let ptyProcess: IPty | null = null;

function startOpencodeConsole(cwd: string, cols: number, rows: number): void {
  stopOpencodeConsole();

  const command = findOpencodeCommand();
  if (!command) {
    sendStatus("OPENCODE: NOT FOUND");
    if (mainWindow) mainWindow.webContents.send("opencode:done", -1);
    return;
  }

  try {
    ptyProcess = pty.spawn(command.cmd, command.args, {
      name: "xterm-256color",
      cols: Math.max(20, cols || 120),
      rows: Math.max(5, rows || 40),
      cwd: cwd || process.cwd(),
      env: {
        ...process.env,
        TERM: "xterm-256color",
        COLORTERM: "truecolor",
      },
    });
  } catch (err) {
    ptyProcess = null;
    sendStatus("OPENCODE: START FAILED");
    sendOutput(`[OpenCode] Could not start the console: ${(err as Error).message}\n`);
    if (mainWindow) mainWindow.webContents.send("opencode:done", -1);
    return;
  }

  ptyProcess.onData((data: string) => {
    if (mainWindow) mainWindow.webContents.send("opencode:output", data);
  });

  ptyProcess.onExit(({ exitCode }: { exitCode: number }) => {
    ptyProcess = null;
    sendStatus(exitCode === 0 ? "OPENCODE: SESSION ENDED" : `OPENCODE: EXITED (${exitCode})`);
    if (mainWindow) mainWindow.webContents.send("opencode:done", exitCode);
  });

  sendStatus("OPENCODE: RUNNING");
}

function stopOpencodeConsole(): void {
  if (ptyProcess) {
    try {
      ptyProcess.kill();
    } catch {
      // ignore
    }
    ptyProcess = null;
  }
}

function writeToOpencode(data: string): void {
  if (ptyProcess) {
    try {
      ptyProcess.write(data);
    } catch {
      // ignore
    }
  }
}

function resizeOpencode(cols: number, rows: number): void {
  if (ptyProcess) {
    try {
      ptyProcess.resize(Math.max(20, cols), Math.max(5, rows));
    } catch {
      // ignore
    }
  }
}

// ------------------------------------------------------------------ microphone IPC

const micScript = path.join(
  app.getAppPath(),
  "scripts",
  "mic-mute.ps1"
);

interface MicResult {
  ok: boolean;
  muted: boolean;
  count: number;
  message: string;
  mics: string[];
}

/**
 * Run the microphone helper script and parse its JSON result.
 *
 * The script uses inline C# (Core Audio COM interop) so the app needs no
 * native module for the microphone.
 */
function runMicScript(action: "status" | "mute" | "unmute"): MicResult {
  try {
    const out = execFileSync(
      "powershell.exe",
      ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", micScript, action],
      { encoding: "utf8", timeout: 20000, windowsHide: true }
    );
    const parsed = JSON.parse(out.trim());
    return {
      ok: Boolean(parsed.ok),
      muted: Boolean(parsed.muted),
      count: Number(parsed.count) || 0,
      message: String(parsed.message || ""),
      mics: Array.isArray(parsed.mics) ? parsed.mics : [],
    };
  } catch (err) {
    return {
      ok: false,
      muted: false,
      count: 0,
      message: `MIC CONTROL UNAVAILABLE: ${
        err instanceof Error ? err.message : String(err)
      }`,
      mics: [],
    };
  }
}

ipcMain.handle("mic:status", () => runMicScript("status"));
ipcMain.handle("mic:toggle", () => {
  const current = runMicScript("status");
  // Currently muted -> unmute, otherwise -> mute.
  return runMicScript(current.ok && current.muted ? "unmute" : "mute");
});

// ------------------------------------------------------------------ AI memory IPC

interface AiMemory {
  thecoreRamGB: number;
  ollamaRamGB: number;
  totalRamGB: number;
  thecoreVramMB: number;
  ollamaVramMB: number;
  totalVramMB: number;
  ramCapacityGB: number;
  vramCapacityMB: number;
  ramPercent: number;
  vramPercent: number;
  ollamaProcesses: number;
  gpuAvailable: boolean;
}

/** Run a PowerShell snippet and return its stdout. */
function ps(command: string, timeout = 8000): string {
  try {
    return execFileSync("powershell.exe", ["-NoProfile", "-Command", command], {
      encoding: "utf8",
      timeout,
      windowsHide: true,
    }).toString();
  } catch {
    return "";
  }
}

/**
 * Memory used by TheCore and Ollama only — not by the whole machine.
 *
 * The gauges used to report the total system RAM and VRAM, which says nothing
 * about this application.  Ollama's processes are found by name; their GPU
 * memory comes from the Ollama API (`/api/ps`), because on Windows the model
 * runner lives inside ollama.exe and WDDM hides the per-process numbers.
 */
async function sampleAiMemory(): Promise<AiMemory> {
  const ollama = ps(
    "Get-Process | Where-Object { $_.ProcessName -like '*ollama*' } | " +
      "ForEach-Object { \"$($_.Id) $($_.WorkingSet64)\" }"
  );
  const ollamaPids = new Set<number>();
  let ollamaRamBytes = 0;
  for (const line of ollama.split(/\r?\n/)) {
    const m = line.trim().match(/^(\d+)\s+(\d+)$/);
    if (!m) continue;
    ollamaPids.add(Number(m[1]));
    ollamaRamBytes += Number(m[2]);
  }

  // TheCore's own footprint (the Electron main process).
  let thecoreRamBytes = 0;
  try {
    thecoreRamBytes = process.memoryUsage().rss;
  } catch {
    thecoreRamBytes = 0;
  }

  // GPU memory per process, from nvidia-smi.
  const vramByPid = new Map<number, number>();
  const smi = ps(
    "nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader,nounits"
  );
  for (const line of smi.split(/\r?\n/)) {
    const m = line.trim().match(/^(\d+)\s*,\s*(\d+)/);
    if (!m) continue;
    vramByPid.set(Number(m[1]), Number(m[2]) / 1024);
  }

  // On Windows the model runner lives inside ollama.exe and WDDM does not
  // report per-process GPU memory, so ask Ollama itself how much video
  // memory its loaded models occupy.
  let ollamaVram = 0;
  try {
    const response = await fetch("http://127.0.0.1:11434/api/ps");
    const payload = await response.json();
    for (const model of payload.models || []) {
      ollamaVram += Number(model.size_vram || 0) / (1024 * 1024);
    }
  } catch {
    ollamaVram = 0;
  }
  if (ollamaVram <= 0) {
    for (const pid of ollamaPids) ollamaVram += vramByPid.get(pid) ?? 0;
  }
  const thecoreVram = vramByPid.get(process.pid) ?? 0;

  const totalMem = os.totalmem();
  const stats = ps(
    "(Get-CimInstance Win32_OperatingSystem).TotalVisibleMemorySize * 1KB"
  );
  const ramCapacityGB = Number(stats.trim()) / (1024 ** 3) || totalMem / (1024 ** 3);

  // Total VRAM capacity.
  let vramCapacityMB = 0;
  const vramOut = ps(
    "nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits"
  );
  const v = Number(vramOut.split(/\r?\n/)[0]?.trim());
  if (Number.isFinite(v) && v > 0) vramCapacityMB = v;

  const totalRamGB = (ollamaRamBytes + thecoreRamBytes) / (1024 ** 3);
  const totalVramMB = ollamaVram + thecoreVram;

  return {
    thecoreRamGB: thecoreRamBytes / (1024 ** 3),
    ollamaRamGB: ollamaRamBytes / (1024 ** 3),
    totalRamGB,
    thecoreVramMB: thecoreVram,
    ollamaVramMB: ollamaVram,
    totalVramMB,
    ramCapacityGB,
    vramCapacityMB,
    ramPercent: ramCapacityGB > 0 ? (totalRamGB / ramCapacityGB) * 100 : 0,
    vramPercent: vramCapacityMB > 0 ? (totalVramMB / vramCapacityMB) * 100 : 0,
    ollamaProcesses: ollamaPids.size,
    gpuAvailable: vramCapacityMB > 0,
  };
}

ipcMain.handle("system:aiMemory", () => sampleAiMemory());

// ------------------------------------------------------------------ OpenCode availability

ipcMain.handle("opencode:available", () => {
  const command = findOpencodeCommand();
  if (!command) return false;
  try {
    execFileSync(command.cmd, [...command.args, "--version"], {
      stdio: "ignore",
      timeout: 5000,
    });
    return true;
  } catch {
    return false;
  }
});

// ------------------------------------------------------------------ Ollama capabilities

ipcMain.handle("ollama:capabilities", async (_e, model: string) => {
  if (!model) return [];
  try {
    const response = await fetch("http://127.0.0.1:11434/api/show", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model }),
    });
    const payload = await response.json();
    return Array.isArray(payload.capabilities) ? payload.capabilities : [];
  } catch {
    return [];
  }
});

// ------------------------------------------------------------------ tools IPC

let toolRegistry: ToolRegistry | null = null;
let toolRoot = "";

ipcMain.handle("tools:definitions", (_e, root: string) => {
  if (!root) return [];
  if (!toolRegistry || toolRoot !== root) {
    toolRegistry = new ToolRegistry(root);
    toolRoot = root;
  }
  return toolRegistry.definitions();
});

ipcMain.handle("tools:execute", async (_e, root: string, name: string, args: any) => {
  if (!toolRegistry || toolRoot !== root) {
    toolRegistry = new ToolRegistry(root);
    toolRoot = root;
  }
  return toolRegistry.execute(name, args || {});
});

// ------------------------------------------------------------------ images IPC

ipcMain.handle("images:pick", async () => {
  const result = await dialog.showOpenDialog({
    properties: ["openFile"],
    filters: [{ name: "Images", extensions: ["png", "jpg", "jpeg", "bmp", "gif", "webp"] }],
  });
  if (result.canceled || !result.filePaths.length) return null;
  const file = result.filePaths[0];
  const data = fs.readFileSync(file);
  if (data.length > 8 * 1024 * 1024) {
    return { error: "The image is larger than 8 MB." };
  }
  return {
    name: path.basename(file),
    path: file,
    data: data.toString("base64"),
  };
});

// ------------------------------------------------------------------ splash sound

/**
 * Play one of the startup sounds from the assets folder.
 *
 * The WAV files are synthesised (see `tools/make_sounds.py` in the project
 * root), so they are small and there is nothing to license.
 */
function playSound(name: "loading" | "ready"): void {
  if (process.env.THECORE_NO_SOUND) return;
  try {
    const file = path.join(app.getAppPath(), "..", "assets", `${name}.wav`);
    if (!fs.existsSync(file)) return;
    // `winsound` is Windows only; on other platforms there is simply no sound.
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const { spawn } = require("child_process");
    const child = spawn(
      "powershell.exe",
      [
        "-NoProfile",
        "-Command",
        `(New-Object Media.SoundPlayer '${file}').PlaySync()`,
      ],
      { detached: true, stdio: "ignore", windowsHide: true }
    );
    child.unref();
  } catch {
    // A missing sound must never break the start-up.
  }
}

ipcMain.on("app:playSound", (_event, name: string) => {
  if (name === "loading" || name === "ready") playSound(name);
});

ipcMain.on("app:readyToShow", () => {
  if (!mainWindow) return;
  // Full screen: the header needs the room, otherwise the buttons are
  // squeezed and their labels get clipped.
  mainWindow.maximize();
  mainWindow.show();
  mainWindow.focus();
});

// ------------------------------------------------------------------ voice IPC

ipcMain.handle("voice:dictate", () => {
  if (process.env.THECORE_NO_SOUND) return false;
  try {
    // Win+H is the Windows voice-typing shortcut.
    const script =
      "$ws = New-Object -ComObject WScript.Shell; " +
      "$ws.SendKeys('#h')";
    execFileSync("powershell.exe", ["-NoProfile", "-Command", script], {
      stdio: "ignore",
      windowsHide: true,
    });
    return true;
  } catch {
    return false;
  }
});

ipcMain.handle("voice:speak", (_e, text: string) => {
  const cleaned = String(text || "").trim().slice(0, 600);
  if (!cleaned) return false;
  const escaped = cleaned.replace(/'/g, "''");
  const script =
    "Add-Type -AssemblyName System.Speech; " +
    "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; " +
    `$s.Speak('${escaped}')`;
  try {
    const child = require("child_process").spawn(
      "powershell.exe",
      ["-NoProfile", "-Command", script],
      { detached: true, stdio: "ignore", windowsHide: true }
    );
    child.unref();
    return true;
  } catch {
    return false;
  }
});

// ------------------------------------------------------------------ cloud IPC

ipcMain.handle("cloud:providers", () =>
  CLOUD_PROVIDERS.map((p) => ({ ...p, tierLabel: tierLabel(p) }))
);
ipcMain.handle("cloud:listModels", async (_e, providerId: string) => {
  const provider = providerFor(providerId);
  if (!provider) return [];
  const client = new CloudClient(provider, loadCloudKey(providerId));
  return client.listModels();
});
// Every model of every provider that has a key stored.
ipcMain.handle("cloud:catalogue", async () => listConfiguredModels());
ipcMain.handle("cloud:configured", async () =>
  configuredProviders().map((p) => ({ ...p, tierLabel: tierLabel(p) }))
);
ipcMain.handle("cloud:saveKey", (_e, providerId: string, key: string) => {
  saveCloudKey(providerId, key);
  return true;
});
ipcMain.handle("cloud:hasKey", (_e, providerId: string) =>
  Boolean(loadCloudKey(providerId))
);
ipcMain.handle("cloud:baseUrl", (_e, url: string) => {
  saveBaseUrl(url);
  return loadBaseUrl();
});
ipcMain.handle("cloud:getBaseUrl", () => loadBaseUrl());
ipcMain.on("cloud:chat", async (event, providerId: string, model: string, messages: any[]) => {
  const provider = providerFor(providerId);
  if (!provider) {
    event.sender.send("cloud:error", "Unknown cloud provider");
    return;
  }
  const client = new CloudClient(provider, loadCloudKey(providerId));
  try {
    for await (const piece of client.chatStream(model, messages)) {
      event.sender.send("cloud:chunk", piece);
    }
    event.sender.send("cloud:done", "");
  } catch (err) {
    event.sender.send("cloud:error", err instanceof Error ? err.message : String(err));
  }
});

// ------------------------------------------------------------------ system stats IPC

/**
 * True when this process runs with administrator rights.
 *
 * The OpenCode console inherits TheCore's privileges, so its shell tools can
 * only do administrator work when TheCore itself is elevated.
 */
function isAdmin(): boolean {
  if (process.platform !== "win32") {
    return typeof process.getuid === "function" && process.getuid() === 0;
  }
  try {
    // The integrity level SID in "whoami /groups" tells us whether the token
    // is elevated: S-1-16-12288 (High) or S-1-16-16384 (System).
    const out = execFileSync("whoami", ["/groups"], { encoding: "utf8" });
    return /S-1-16-(12288|16384)/.test(out);
  } catch {
    return false;
  }
}

ipcMain.handle("app:isAdmin", () => isAdmin());

ipcMain.on("app:openExternal", (_event, url: string) => {
  if (typeof url === "string" && /^https?:\/\//i.test(url)) {
    shell.openExternal(url);
  }
});

/**
 * Restart TheCore with administrator rights.
 *
 * The OpenCode console inherits TheCore's privileges, so its shell tools can
 * only do administrator work when TheCore itself is elevated.  `Start-Process
 * -Verb RunAs` triggers the UAC prompt.
 */
ipcMain.handle("app:relaunchAsAdmin", () => {
  if (isAdmin()) return false;
  const exe = process.execPath;
  const args = app.isPackaged ? [] : [app.getAppPath()];
  const argList = args.map((a) => `'${a.replace(/'/g, "''")}'`).join(",");
  const script =
    `Start-Process -FilePath '${exe.replace(/'/g, "''")}'` +
    (argList ? ` -ArgumentList ${argList}` : "") +
    ` -Verb RunAs`;
  try {
    execFileSync("powershell.exe", ["-NoProfile", "-Command", script], {
      stdio: "ignore",
    });
  } catch {
    return false;
  }
  // The elevated instance is up — close this one.
  setTimeout(() => app.quit(), 500);
  return true;
});


// ------------------------------------------------------------------ database IPC

const dbPath = path.join(
  path.dirname(app.getAppPath()),
  "thecore_ai.db"
);
const database = new TheCoreDatabase(dbPath);

ipcMain.handle("db:listWorkspaces", () => database.listWorkspaces());
ipcMain.handle("db:listProjects", (_e, workspaceId: number) =>
  database.listProjects(workspaceId)
);
ipcMain.handle("db:listConversations", (_e, projectId: number) =>
  database.listConversations(projectId)
);
ipcMain.handle("db:listMessages", (_e, conversationId: number) =>
  database.listMessages(conversationId)
);
ipcMain.handle("db:countConversations", (_e, projectId: number) =>
  database.countConversations(projectId)
);
ipcMain.handle("db:createWorkspace", (_e, name: string, wsPath: string) =>
  database.createWorkspace(name, wsPath)
);
ipcMain.handle(
  "db:createProject",
  (_e, workspaceId: number, name: string, description: string) =>
    database.createProject(workspaceId, name, description)
);
ipcMain.handle(
  "db:createConversation",
  (_e, projectId: number, title: string, model: string) =>
    database.createConversation(projectId, title, model)
);
ipcMain.handle("db:deleteWorkspace", (_e, id: number) => {
  database.deleteWorkspace(id);
  return true;
});
ipcMain.handle("db:deleteProject", (_e, id: number) => {
  database.deleteProject(id);
  return true;
});
ipcMain.handle("db:deleteConversation", (_e, id: number) => {
  database.deleteConversation(id);
  return true;
});
ipcMain.handle("db:addMessage", (_e, conversationId: number, role: string, content: string) =>
  database.addMessage(conversationId, role, content)
);
ipcMain.handle("db:touchConversation", (_e, conversationId: number) => {
  database.touchConversation(conversationId);
  return true;
});
ipcMain.handle("db:renameConversation", (_e, conversationId: number, title: string) => {
  database.renameConversation(conversationId, title);
  return true;
});
ipcMain.handle("db:countMessages", (_e, conversationId: number) =>
  database.countMessages(conversationId)
);

ipcMain.on("opencode:start", (_event, cwd: string, cols: number, rows: number) => {
  startOpencodeConsole(cwd, cols, rows);
});

ipcMain.on("opencode:stop", () => {
  stopOpencodeConsole();
});

ipcMain.on("opencode:data", (_event, data: string) => {
  writeToOpencode(data);
});

ipcMain.on("opencode:resize", (_event, cols: number, rows: number) => {
  resizeOpencode(cols, rows);
});

ipcMain.on("app:quit", () => {
  stopOpencodeConsole();
  app.quit();
});

// ------------------------------------------------------------------ menu

/** Build the application menu (File / Edit / View / Help), like Cursor. */
function buildMenu(): void {
  const send = (channel: string, ...args: any[]) => {
    if (mainWindow) mainWindow.webContents.send(channel, ...args);
  };

  const template: any[] = [
    {
      label: "&File",
      submenu: [
        { label: "&New Chat", accelerator: "CmdOrCtrl+N", click: () => send("menu:newChat") },
        { label: "New &Workspace…", accelerator: "CmdOrCtrl+Shift+N", click: () => send("menu:newWorkspace") },
        { label: "New &Project…", accelerator: "CmdOrCtrl+Shift+P", click: () => send("menu:newProject") },
        { type: "separator" },
        { label: "&Quit", accelerator: "CmdOrCtrl+Q", click: () => app.quit() },
      ],
    },
    {
      label: "&Edit",
      submenu: [
        { role: "undo" },
        { role: "redo" },
        { type: "separator" },
        { role: "cut" },
        { role: "copy" },
        { role: "paste" },
        { type: "separator" },
        { role: "selectAll" },
      ],
    },
    {
      label: "&View",
      submenu: [
        { label: "Toggle &Sidebar", accelerator: "CmdOrCtrl+B", click: () => send("menu:toggleSidebar") },
        { label: "&Reload", accelerator: "CmdOrCtrl+R", click: () => send("menu:reload") },
        { type: "separator" },
        { label: "&Settings", accelerator: "CmdOrCtrl+,", click: () => send("menu:settings") },
        { type: "separator" },
        { role: "resetZoom" },
        { role: "zoomIn" },
        { role: "zoomOut" },
        { type: "separator" },
        { role: "togglefullscreen" },
        { role: "toggleDevTools" },
      ],
    },
    {
      label: "&Help",
      submenu: [
        { label: "&About TheCore", click: () => send("menu:about") },
      ],
    },
  ];

  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

// ------------------------------------------------------------------ app lifecycle

/**
 * The data folder is `%APPDATA%\TheCore` — the very same folder the Python
 * app uses.  Electron would otherwise derive it from the app name, which
 * depends on how the app was started (a plain script gets "Electron").
 */
function useSharedDataFolder(): void {
  try {
    const shared = path.join(app.getPath("appData"), "TheCore");
    fs.mkdirSync(shared, { recursive: true });
    app.setPath("userData", shared);
  } catch (err) {
    logError("Could not set the shared data folder", err);
  }
}

useSharedDataFolder();

app.whenReady().then(() => {
  const logPath = enableDebugging();
  if (logPath) {
    log(`Debug logging is on — writing to ${logPath}`);
  }
  buildMenu();
  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
