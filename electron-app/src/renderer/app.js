/* TheCore — Renderer process (Electron + vanilla JS)

Handles: round splash animation (min 7 sec), tab switching, system stats polling,
AI chat (Ollama streaming + embedded OpenCode console), model load/unload with
elapsed-time animation, and UI state.
*/

const API = window.thecoreAPI;

// ------------------------------------------------------------------ state
let currentTab = "systems";
let currentProvider = "ollama"; // "ollama" | "opencode"
let opencodeLoaded = false;
let opencodeAvailable = false;
let opencodeBusy = false; // a CLI run is in flight
let currentProjectId = null;
let currentConversationId = null;
let ollamaAbortController = null;
let models = [];
let memInterval = null;
let healthInterval = null;
let ollamaModelLoaded = false;
let ollamaLoadedModel = null;
let ollamaLoadStart = null;
let ollamaLoading = false;

// ------------------------------------------------------------------ DOM refs
const $ = (id) => document.getElementById(id);
const splash = $("splash");
const app = $("app");

const modelCombo = $("model-combo");
const loadBtn = $("btn-load");
const loadSpinner = $("load-spinner");
const loadElapsed = $("load-elapsed");
const statusText = $("status-text");
const statusLamp = $("status-lamp");
const statusCaption = $("status-caption");
const memGauge = $("mem-gauge");
const memVramFill = $("mem-vram-fill");
const memVramValue = $("mem-vram-value");
const memRamFill = $("mem-ram-fill");
const memRamValue = $("mem-ram-value");
const chatSplit = $("chat-split");
const consoleGrip = $("console-grip");
const chatScroll = $("chat-scroll");

// ------------------------------------------------------------------ auto-scroll
//
// While the AI is writing the view follows the newest text. As soon as the
// user scrolls up to read something, the view stays where it is.
let autoScroll = true;

/** True when the scroll bar is (nearly) at the bottom. */
function isAtBottom() {
  return (
    chatScroll.scrollTop + chatScroll.clientHeight >=
    chatScroll.scrollHeight - 4
  );
}

/** Scroll to the bottom — but only when the view is following the text. */
function stickToBottom() {
  if (autoScroll) {
    chatScroll.scrollTop = chatScroll.scrollHeight;
  }
}

/** Follow the newest content while it grows. */
function setupAutoScroll() {
  chatScroll.addEventListener("scroll", () => {
    autoScroll = isAtBottom();
  });
  autoScroll = true;
}
const messageContainer = $("message-container");
const chatInput = $("chat-input");
const btnStop = $("btn-stop");
const opencodeConsole = $("opencode-console");
const consoleStatus = $("console-status");

// ------------------------------------------------------------------ splash: a square boot console
const BOOT_LOG = [
  ["core modules", "ready"],
  ["ai backend", "ready"],
  ["ollama bridge", "ready"],
  ["opencode bridge", "ready"],
  ["gpu telemetry", "ready"],
  ["workspace index", "ready"],
  ["interface", "ready"],
];

const splashLog = $("splash-log");
const splashBarFill = $("splash-bar-fill");
const splashPct = $("splash-pct");

// The log panel is a small console: it shows the last few lines only, so the
// text always stays inside the border and the older lines scroll off.
const LOG_VISIBLE = 5;

let logIndex = 0;
let splashProgress = 0;
let splashStart = Date.now();
const SPLASH_MIN_MS = 7000;
let modulesReady = false;

/** Draw the boot log with one line per step. */
function renderSplashLog() {
  if (!splashLog) return;
  splashLog.innerHTML = "";

  const rows = [];
  for (let i = 0; i < logIndex; i++) {
    const [label, state] = BOOT_LOG[i];
    rows.push(`&gt; ${label} <span class="ok">${state} ✓</span>`);
  }
  if (logIndex < BOOT_LOG.length) {
    rows.push(`&gt; ${BOOT_LOG[logIndex][0]} <span class="cursor">_</span>`);
  }

  // Only the last few lines fit — the older ones scroll off.
  for (const html of rows.slice(-LOG_VISIBLE)) {
    const line = document.createElement("div");
    line.innerHTML = html;
    splashLog.appendChild(line);
  }
}

function tickSplash() {
  if (logIndex < BOOT_LOG.length) logIndex += 1;
  renderSplashLog();
  const target = Math.min(0.95, logIndex / BOOT_LOG.length);
  splashProgress += (target - splashProgress) * 0.35;
  if (splashBarFill) splashBarFill.style.width = `${(splashProgress * 100).toFixed(1)}%`;
  if (splashPct) splashPct.textContent = `${Math.round(splashProgress * 100)}%`;
}

const splashTimer = setInterval(tickSplash, 420);
renderSplashLog();

// The start-up sound.
try {
  API.playSound("loading");
} catch {
  // No audio device — that is fine.
}

function finishSplash() {
  const elapsed = Date.now() - splashStart;
  const remaining = Math.max(0, SPLASH_MIN_MS - elapsed);
  setTimeout(() => {
    clearInterval(splashTimer);
    logIndex = BOOT_LOG.length;
    renderSplashLog();
    splashProgress = 1;
    if (splashBarFill) splashBarFill.style.width = "100%";
    if (splashPct) splashPct.textContent = "100%";
    splash.style.opacity = "0";
    try {
      API.playSound("ready");
    } catch {
      // ignore
    }
    setTimeout(() => {
      splash.remove();
      app.classList.remove("hidden");
      showTab("ai");
      // The window is only shown now, so the splash is really seen first.
      try {
        API.readyToShow();
      } catch {
        // ignore
      }
    }, 400);
  }, remaining);
}

// ------------------------------------------------------------------ tab switching
function showTab(tabId) {
  currentTab = tabId;
  document.querySelectorAll(".tab-btn").forEach((b) => {
    b.classList.toggle("active", b.dataset.tab === tabId);
  });
  document.querySelectorAll(".tab-panel").forEach((p) => {
    // Panels are shown through the "active" class (see .tab-panel.active in
    // the stylesheet); "hidden" is kept in sync so other rules agree.
    const isActive = p.id === `tab-${tabId}`;
    p.classList.toggle("active", isActive);
    p.classList.toggle("hidden", !isActive);
  });
  if (tabId === "ai") {
    refreshModels();
    startMemPolling();
    checkOllamaHealth();
  } else {
    stopMemPolling();
  }
}

document.querySelectorAll(".tab-btn").forEach((b) => {
  b.addEventListener("click", () => showTab(b.dataset.tab));
});

// ------------------------------------------------------------------ settings
//
// The gear in the bottom-left corner of the sidebar opens the settings page.
// Everything the program can be configured with lives there.

/** Open the settings page. */
function showSettings() {
  showTab("settings");
  loadSettingsPage();
}

/** Go back to the chat. */
function hideSettings() {
  showTab("ai");
}

const providerCards = $("provider-cards");
const settingsModelProvider = $("settings-model-provider");
const settingsModelInfo = $("settings-model-info");
const settingsLocalInfo = $("settings-local-info");

/** Build one card per cloud provider: name, tier, key field and buttons. */
function buildProviderCards() {
  if (!providerCards) return;
  providerCards.innerHTML = "";

  for (const provider of cloudProviders) {
    const card = document.createElement("div");
    card.className = "provider-card";
    card.dataset.providerId = provider.id;

    const top = document.createElement("div");
    top.className = "provider-top";

    const name = document.createElement("span");
    name.className = "provider-name";
    name.textContent = provider.name;
    top.appendChild(name);

    const badge = document.createElement("span");
    badge.className = "provider-badge";
    badge.dataset.tier = (provider.tierLabel || "PAID")
      .replace(" + ", "-")
      .replace(" ", "-")
      .toLowerCase();
    badge.textContent = provider.tierLabel || "PAID";
    top.appendChild(badge);

    card.appendChild(top);

    const notes = document.createElement("div");
    notes.className = "provider-notes";
    notes.textContent = provider.notes || "";
    card.appendChild(notes);

    const row = document.createElement("div");
    row.className = "provider-row";

    const key = document.createElement("input");
    key.type = "password";
    key.className = "settings-key-input";
    key.placeholder = "API key — stored in the app's data folder";
    key.dataset.providerId = provider.id;
    row.appendChild(key);

    const save = document.createElement("button");
    save.className = "settings-save-btn";
    save.textContent = "SAVE";
    save.addEventListener("click", async () => {
      await API.cloudSaveKey(provider.id, key.value.trim());
      await loadSettingsPage();
      await refreshCloudModels();
    });
    row.appendChild(save);

    const clear = document.createElement("button");
    clear.className = "settings-clear-btn";
    clear.textContent = "CLEAR";
    clear.addEventListener("click", async () => {
      await API.cloudSaveKey(provider.id, "");
      key.value = "";
      await loadSettingsPage();
      await refreshCloudModels();
    });
    row.appendChild(clear);

    if (provider.signupUrl) {
      const link = document.createElement("button");
      link.className = "settings-link-btn";
      link.textContent = "GET A FREE KEY";
      link.title = provider.signupUrl;
      link.addEventListener("click", async () => {
        await API.openExternal(provider.signupUrl);
      });
      row.appendChild(link);
    }

    card.appendChild(row);

    // The base URL, only for the custom endpoint.
    if (provider.id === "custom") {
      const baseRow = document.createElement("div");
      baseRow.className = "provider-row";
      const baseLabel = document.createElement("span");
      baseLabel.textContent = "Base URL:";
      baseRow.appendChild(baseLabel);
      const base = document.createElement("input");
      base.type = "text";
      base.className = "settings-key-input";
      base.placeholder = "https://your-endpoint/v1";
      base.id = "custom-base-url";
      baseRow.appendChild(base);
      card.appendChild(baseRow);
    }

    const status = document.createElement("div");
    status.className = "provider-status";
    status.dataset.providerId = provider.id;
    card.appendChild(status);

    providerCards.appendChild(card);
  }

  updateProviderStatuses();
}

/** Show which providers have a key stored. */
async function updateProviderStatuses() {
  if (!providerCards) return;
  for (const status of providerCards.querySelectorAll(".provider-status")) {
    const providerId = status.dataset.providerId;
    let has = false;
    try {
      has = await API.cloudHasKey(providerId);
    } catch {
      has = false;
    }
    status.textContent = has
      ? "KEY STORED ●"
      : "NO KEY — the provider cannot be used yet";
    status.dataset.state = has ? "stored" : "none";

    const input = providerCards.querySelector(
      `.settings-key-input[data-provider-id="${providerId}"]`
    );
    if (input && !input.dataset.touched) {
      input.value = has ? "•".repeat(24) : "";
      input.dataset.stored = has ? "1" : "";
    }
  }
}

/** Show the models of the selected provider, free ones first. */
function updateSettingsModelInfo() {
  if (!settingsModelInfo) return;
  const providerId = settingsModelProvider.value;
  const provider = cloudProviders.find((p) => p.id === providerId);
  if (!provider) return;

  const models = catalogueCloudModels.filter((m) => m.providerId === providerId);
  if (!models.length) {
    settingsModelInfo.textContent =
      `${provider.name} — no models found. Check the key and press REFRESH MODELS.`;
    return;
  }

  const free = models.filter((m) => m.free);
  const paid = models.filter((m) => !m.free);
  const lines = [
    `${provider.name} — ${models.length} models (${provider.tierLabel || "PAID"})`,
  ];
  if (free.length) {
    lines.push(
      "● FREE: " + free.slice(0, 10).map((m) => m.id).join(", ") +
        (free.length > 10 ? " …" : "")
    );
  }
  if (paid.length) {
    lines.push(
      "○ PAID: " + paid.slice(0, 10).map((m) => m.id).join(", ") +
        (paid.length > 10 ? " …" : "")
    );
  }
  settingsModelInfo.textContent = lines.join("\n");
}

/** List the Ollama models that are installed on this PC. */
async function refreshLocalModels() {
  if (!settingsLocalInfo) return;
  try {
    const resp = await fetch("http://127.0.0.1:11434/api/tags");
    const data = await resp.json();
    const list = data.models || [];
    if (!list.length) {
      settingsLocalInfo.textContent =
        "No local models found. Start Ollama and pull a model, for example:  ollama pull qwen2.5-coder:7b";
      return;
    }
    const lines = [`${list.length} models installed`];
    for (const m of list.slice(0, 12)) {
      const gb = (m.size || 0) / (1024 * 1024 * 1024);
      lines.push(`${m.name}  (${gb.toFixed(1)} GB)`);
    }
    if (list.length > 12) lines.push(`… and ${list.length - 12} more`);
    settingsLocalInfo.textContent = lines.join("\n");
  } catch {
    settingsLocalInfo.textContent = "Ollama is not running.";
  }
}

/** Load everything the settings page shows. */
async function loadSettingsPage() {
  if (!providerCards) return;
  if (!providerCards.childElementCount) {
    buildProviderCards();
  }
  if (settingsModelProvider && !settingsModelProvider.childElementCount) {
    for (const provider of cloudProviders) {
      const option = document.createElement("option");
      option.value = provider.id;
      option.textContent = provider.name;
      settingsModelProvider.appendChild(option);
    }
  }
  await updateProviderStatuses();
  updateSettingsModelInfo();
  await refreshLocalModels();

  const base = $("custom-base-url");
  if (base) {
    try {
      base.value = (await API.cloudGetBaseUrl()) || "";
    } catch {
      base.value = "";
    }
  }
}

if ($("btn-settings")) {
  $("btn-settings").addEventListener("click", () => showSettings());
}
if ($("btn-settings-back")) {
  $("btn-settings-back").addEventListener("click", () => hideSettings());
}
if (settingsModelProvider) {
  settingsModelProvider.addEventListener("change", updateSettingsModelInfo);
}
if ($("btn-refresh-models")) {
  $("btn-refresh-models").addEventListener("click", async () => {
    await refreshCloudModels();
    updateSettingsModelInfo();
  });
}
if ($("btn-refresh-local")) {
  $("btn-refresh-local").addEventListener("click", () => refreshLocalModels());
}

// ------------------------------------------------------------------ system stats
// ------------------------------------------------------------------ memory polling (AI tab)
function startMemPolling() {
  fetchMem();
  memInterval = setInterval(fetchMem, 2000);
  // Keeps the OLLAMA lamp truthful while OpenCode is the active provider.
  healthInterval = setInterval(checkOllamaHealth, 5000);
}

function stopMemPolling() {
  if (memInterval) {
    clearInterval(memInterval);
    memInterval = null;
  }
  if (healthInterval) {
    clearInterval(healthInterval);
    healthInterval = null;
  }
}

async function fetchMem() {
  // The gauges show the memory used by TheCore and Ollama only — not the
  // whole machine.
  try {
    const m = await API.getAiMemory();
    if (m && m.gpuAvailable) {
      setGauge(
        memVramFill,
        memVramValue,
        m.vramPercent,
        `${m.vramPercent.toFixed(0).padStart(3, " ")}%  ${Math.round(m.totalVramMB).toLocaleString()} MB`,
      );
    } else {
      setGauge(memVramFill, memVramValue, null, "n/a");
    }
    setGauge(
      memRamFill,
      memRamValue,
      m ? m.ramPercent : 0,
      `${((m && m.ramPercent) || 0).toFixed(1).padStart(4, " ")}%  ${((m && m.totalRamGB) || 0).toFixed(2)} GB`,
    );
  } catch {
    // ignore
  }
}

function setGauge(fillEl, valueEl, percent, text) {
  if (!fillEl || !valueEl) return;
  if (percent === null || percent === undefined) {
    fillEl.style.width = "0%";
    fillEl.removeAttribute("data-state");
  } else {
    fillEl.style.width = `${Math.max(0, Math.min(100, percent))}%`;
    fillEl.dataset.state = percent >= 90 ? "crit" : percent >= 70 ? "warn" : "normal";
  }
  valueEl.textContent = text;
}

// ------------------------------------------------------------------ status helpers
/** Drives the header LED lamp (always captioned "OLLAMA"). */
function setStatus(text, state = "online") {
  if (statusText) {
    statusText.textContent = text;
    statusText.setAttribute("state", state);
  }
  if (statusLamp) {
    statusLamp.dataset.state = state;
    statusLamp.title = text;
  }
  if (statusCaption) {
    statusCaption.dataset.state = state;
    statusCaption.title = text;
  }
}

/** Status line inside the OpenCode console panel. */
function setConsoleStatus(text, state = "online") {
  if (!consoleStatus) return;
  consoleStatus.textContent = text;
  consoleStatus.dataset.state = state;
}

const CONSOLE_DEFAULT_HEIGHT = 240;

/** Show/hide the console panel together with its draggable grip. */
function setConsoleVisible(visible) {
  opencodeConsole.classList.toggle("hidden", !visible);
  consoleGrip.classList.toggle("hidden", !visible);
  if (visible) {
    opencodeConsole.style.height = `${CONSOLE_DEFAULT_HEIGHT}px`;
    opencodeConsole.style.flex = "0 0 auto";
  } else {
    opencodeConsole.style.height = "";
    opencodeConsole.style.flex = "";
  }
}

/**
 * The grip sits exactly on the line above the console: grab it and drag
 * upwards to stretch the console, downwards to shrink it.
 */
function initConsoleGrip() {
  if (!consoleGrip || !opencodeConsole) return;
  let dragging = false;
  let startY = 0;
  let startHeight = 0;

  const onMove = (e) => {
    if (!dragging) return;
    const max = Math.max(120, chatSplit.clientHeight - 120);
    const next = Math.min(max, Math.max(120, startHeight + (startY - e.clientY)));
    opencodeConsole.style.height = `${next}px`;
    opencodeConsole.style.flex = "0 0 auto";
  };

  const onUp = () => {
    dragging = false;
    document.body.style.userSelect = "";
  };

  consoleGrip.addEventListener("mousedown", (e) => {
    dragging = true;
    startY = e.clientY;
    startHeight = opencodeConsole.getBoundingClientRect().height;
    document.body.style.userSelect = "none";
    e.preventDefault();
  });

  window.addEventListener("mousemove", onMove);
  window.addEventListener("mouseup", onUp);

  consoleGrip.addEventListener("dblclick", () => {
    opencodeConsole.style.height = `${CONSOLE_DEFAULT_HEIGHT}px`;
  });
}

/** Keeps the OLLAMA lamp truthful while OpenCode is the active provider. */
async function checkOllamaHealth() {
  if (currentProvider !== "opencode") return;
  try {
    const resp = await fetch("http://127.0.0.1:11434/api/tags");
    const data = await resp.json();
    const count = (data.models || []).length;
    setStatus(`OLLAMA: ONLINE (${count} models)`, "online");
  } catch {
    setStatus("OLLAMA: OFFLINE", "offline");
  }
}

// ------------------------------------------------------------------ OpenCode availability
async function checkOpenCode() {
  try {
    opencodeAvailable = await API.isOpenCodeAvailable();
    $("opencode-version").textContent = opencodeAvailable ? "installed" : "not found";
  } catch {
    opencodeAvailable = false;
    $("opencode-version").textContent = "not found";
  }
}

// ------------------------------------------------------------------ models
async function refreshModels() {
  if (currentProvider === "opencode") {
    modelCombo.disabled = true;
    modelCombo.innerHTML = '<option value="opencode">OpenCode</option>';
    modelCombo.value = "opencode";
    loadBtn.textContent = "LOAD OPENCODE";
    loadBtn.removeAttribute("loaded");
    loadBtn.disabled = !opencodeAvailable;
    // The header lamp always reports the OLLAMA backend; OpenCode reports in
    // the console panel itself.
    setConsoleStatus(
      opencodeAvailable ? "OPENCODE: ONLINE" : "OPENCODE: NOT FOUND",
      opencodeAvailable ? "online" : "offline",
    );
    return;
  }

  // The local models.
  try {
    const resp = await fetch("http://127.0.0.1:11434/api/tags");
    const data = await resp.json();
    models = data.models || [];
    catalogueModels = models;
    setStatus("OLLAMA: ONLINE", "online");

    // The button belongs to Ollama again — it still said "LOAD OPENCODE".
    loadBtn.textContent = ollamaModelLoaded ? "UNLOAD" : "LOAD MODEL";
    loadBtn.disabled = false;
    if (ollamaModelLoaded) loadBtn.setAttribute("loaded", "true");
    else loadBtn.removeAttribute("loaded");

    modelCombo.disabled = false;
    if (models.length === 0) {
      setStatus("OLLAMA: NO MODELS", "offline");
    }
  } catch {
    catalogueModels = [];
    setStatus("OLLAMA: OFFLINE", "offline");
    modelCombo.disabled = true;
    modelCombo.innerHTML = "";
    return;
  }

  // The cloud models of every provider that has a key.
  await refreshCloudModels();

  // Keep the pick if it is still there.
  const kind = currentProvider === "cloud" ? "cloud" : currentProvider === "ollama" ? "local" : null;
  applyCatalogue(kind);
  await detectCapabilities();
}

// ------------------------------------------------------------------ capabilities

const capabilityIcons = $("capability-icons");
const attachBtn = $("btn-attach");
const imageStrip = $("image-strip");

let modelSupportsTools = false;
let modelSupportsVision = false;
let modelSupportsThinking = false;
let pendingImages = [];

/** Ask Ollama what the selected model can do. */
async function detectCapabilities() {
  const entry = selectedModelEntry(modelCombo);
  const model = entry && entry.kind === "local" ? entry.modelId : "";
  if (!model) {
    updateCapabilityLabel();
    return;
  }
  let capabilities = [];
  try {
    capabilities = (await API.modelCapabilities(model)) || [];
  } catch {
    capabilities = [];
  }
  modelSupportsTools = capabilities.includes("tools");
  modelSupportsVision = capabilities.includes("vision");
  modelSupportsThinking = capabilities.includes("thinking");
  updateCapabilityLabel();
}

function updateCapabilityLabel() {
  const entries = [
    ["tools", modelSupportsTools],
    ["vision", modelSupportsVision],
    ["reasoning", modelSupportsThinking],
  ].filter(([, active]) => active);

  capabilityIcons.innerHTML = "";
  for (const [kind] of entries) {
    const pill = document.createElement("span");
    pill.className = `capability-pill ${kind}`;
    pill.title = CAPABILITY_LABELS[kind];
    // Icons only — the name stays in the tooltip.
    pill.innerHTML = capabilityIcon(kind);
    capabilityIcons.appendChild(pill);
  }
  capabilityIcons.classList.toggle("hidden", !entries.length);

  if (attachBtn) {
    attachBtn.disabled = !modelSupportsVision;
    attachBtn.title = modelSupportsVision
      ? "Attach an image"
      : "This model has no vision — pick one that has";
  }
}

// ------------------------------------------------------------------ images

if (attachBtn) {
  attachBtn.addEventListener("click", async () => {
    const picked = await API.pickImage();
    if (!picked) return;
    if (picked.error) {
      addMessage("system", picked.error, false);
      return;
    }
    pendingImages.push(picked);
    renderImageStrip();
  });
}

function renderImageStrip() {
  if (!imageStrip) return;
  imageStrip.innerHTML = "";
  imageStrip.classList.toggle("hidden", !pendingImages.length);
  for (const image of pendingImages) {
    const chip = document.createElement("span");
    chip.className = "image-chip";
    chip.textContent = image.name;
    chip.title = image.path;
    imageStrip.appendChild(chip);
  }
}

// ------------------------------------------------------------------ provider dropdown
//
// A native <select> cannot show per-option icons on Windows, so the provider
// picker is a small custom dropdown.

const providerDropdown = $("provider-dropdown");
const providerTrigger = $("provider-trigger");
const providerMenu = $("provider-menu");
const providerLabel = $("provider-label");
const providerIconBox = $("provider-icon");

const PROVIDER_KINDS = { ollama: "local", cloud: "cloud", opencode: "terminal" };

function paintProviderIcons() {
  providerDropdown
    .querySelectorAll("[data-icon]")
    .forEach((el) => {
      el.innerHTML = providerIcon(el.dataset.icon);
    });
  // The four pillars on the start screen.
  document.querySelectorAll(".core-card-icon").forEach((el) => {
    el.innerHTML = coreGlyph(el.dataset.glyph);
  });
}

function selectProvider(providerId, options = {}) {
  currentProvider = providerId;
  providerLabel.textContent =
    providerId === "cloud" ? "Cloud LLM" : providerId === "opencode" ? "OpenCode" : "Local-LLM";
  providerIconBox.innerHTML = providerIcon(PROVIDER_KINDS[providerId] || "local");
  providerDropdown.querySelectorAll(".dropdown-item").forEach((item) => {
    item.classList.toggle("selected", item.dataset.provider === providerId);
  });

  if (currentProvider !== "opencode" && opencodeLoaded) {
    API.stopOpencode();
    opencodeLoaded = false;
    opencodeBusy = false;
    loadBtn.textContent = "LOAD OPENCODE";
    loadBtn.removeAttribute("loaded");
    setConsoleVisible(false);
    setComposerInputVisible(true);
    setConsoleStatus("OPENCODE: ONLINE", "online");
  }

  // The cloud bar moved to the settings page — the provider picker only
  // picks the family now, the model dropdown holds every model.
  setComposerInputVisible(currentProvider !== "opencode");
  updateLoadButtonState();
  if (options.skipRefresh) return;
  const kind = providerId === "cloud" ? "cloud" : providerId === "ollama" ? "local" : null;
  applyCatalogue(kind);
  refreshModels().then(() => jumpToFamily(providerId));
}

/** Jump to the first model of a family (local or cloud). */
function jumpToFamily(providerId) {
  const options = Array.from(modelCombo.querySelectorAll("option"));
  const want = providerId === "cloud" ? "cloud" : "local";
  const match = options.find((o) => o.dataset.kind === want);
  if (match) {
    modelCombo.value = match.value;
    modelCombo.dispatchEvent(new Event("change"));
  }
}

providerTrigger.addEventListener("click", (e) => {
  e.stopPropagation();
  providerMenu.classList.toggle("hidden");
});

providerDropdown.querySelectorAll(".dropdown-item").forEach((item) => {
  item.addEventListener("click", () => {
    providerMenu.classList.add("hidden");
    selectProvider(item.dataset.provider);
  });
});

document.addEventListener("click", () => providerMenu.classList.add("hidden"));

// ------------------------------------------------------------------ LOAD / UNLOAD toggle
function showLoadSpinner(show) {
  loadSpinner.classList.toggle("hidden", !show);
  loadElapsed.classList.toggle("hidden", !show);
  if (!show) loadElapsed.textContent = "";
  loadBtn.disabled = show;
  $("btn-stop").hidden = !show;
}

async function loadOllamaModel(modelName) {
  ollamaLoading = true;
  ollamaModelLoaded = false;
  ollamaLoadStart = Date.now();
  showLoadSpinner(true);
  setStatus(`OLLAMA: LOADING ${modelName}… (0.0s)`, "loading");

  const loadTimer = setInterval(() => {
    const elapsed = ((Date.now() - ollamaLoadStart) / 1000).toFixed(1);
    setStatus(`OLLAMA: LOADING ${modelName}… (${elapsed}s)`, "loading");
    // Show the elapsed time next to the spinning dial.
    loadElapsed.textContent = `LOADING ${elapsed}s`;
  }, 500);

  try {
    await fetch("http://127.0.0.1:11434/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: modelName,
        prompt: " ",
        stream: false,
      }),
    });
    ollamaModelLoaded = true;
    ollamaLoadedModel = modelName;
    setStatus(`OLLAMA: ${modelName} (LOADED)`, "online");
    loadBtn.textContent = "UNLOAD";
    loadBtn.setAttribute("loaded", "true");
  } catch (e) {
    setStatus("OLLAMA: LOAD FAILED", "offline");
    ollamaModelLoaded = false;
    ollamaLoadedModel = null;
  } finally {
    ollamaLoading = false;
    clearInterval(loadTimer);
    showLoadSpinner(false);
  }
}

async function unloadOllamaModel() {
  if (ollamaAbortController) ollamaAbortController.abort();

  ollamaModelLoaded = false;
  ollamaLoadedModel = null;
  ollamaLoadStart = null;

  setStatus("OLLAMA: ONLINE (model unloaded)", "online");
  loadBtn.textContent = "LOAD MODEL";
  loadBtn.removeAttribute("loaded");
  loadBtn.disabled = false;
}

loadBtn.addEventListener("click", async () => {
  if (currentProvider === "opencode") {
    if (opencodeLoaded) {
      API.stopOpencode();
      opencodeLoaded = false;
      opencodeBusy = false;
      loadBtn.textContent = "LOAD OPENCODE";
      loadBtn.removeAttribute("loaded");
      setConsoleVisible(false);
      setComposerInputVisible(true);
      setConsoleStatus("OPENCODE: ONLINE", "online");
    } else {
      await startOpencodeConsole();
    }
  } else if (currentProvider === "cloud") {
    // Show refresh button for cloud models
    loadBtn.textContent = "REFRESH MODELS";
    await refreshCloudModels();
  } else if (currentProvider === "local") {
    // Hide the load button for local LLM
    loadBtn.classList.add("hidden");
  } else {
    // Ollama model load/unload
    if (ollamaModelLoaded) {
      await unloadOllamaModel();
    } else {
      const entry = selectedModelEntry(modelCombo);
      const name = entry && entry.kind === "local" ? entry.modelId : "";
      if (!name) return;
      await loadOllamaModel(name);
    }
  }
});

// Update load button visibility and text based on provider selection.
function updateLoadButtonState() {
  if (!loadBtn) return;
  if (currentProvider === "local") {
    loadBtn.textContent = "";
    loadBtn.disabled = true;
    loadBtn.classList.add("hidden");
  } else if (currentProvider === "cloud") {
    loadBtn.textContent = "REFRESH MODELS";
    loadBtn.disabled = false;
    loadBtn.classList.remove("hidden");
  } else if (currentProvider === "opencode") {
    loadBtn.textContent = opencodeLoaded ? "UNLOAD OPENCODE" : "LOAD OPENCODE";
    loadBtn.disabled = !opencodeAvailable;
    loadBtn.classList.remove("hidden");
  }
}

// ------------------------------------------------------------------ OpenCode console
//
// The real `opencode` CLI is an interactive TUI: it queries the terminal's
// capabilities and draws nothing without the answers.  The main process runs
// it on a ConPTY pseudo console (node-pty) and streams the raw output here;
// xterm.js renders that stream exactly like a real terminal would.

let term = null;
let fitAddon = null;

function ensureTerminal() {
  if (term) return term;

  const el = $("console-terminal");
  if (!el || typeof Terminal === "undefined") return null;

  term = new Terminal({
    fontFamily: '"Cascadia Mono", "Consolas", monospace',
    fontSize: 13,
    cursorBlink: true,
    cursorStyle: "block",
    allowProposedApi: true,
    scrollback: 5000,
    theme: {
      background: "#0d100e",
      foreground: "#e0e0e0",
      cursor: "#4ade80",
      cursorAccent: "#0d100e",
      green: "#4ade80",
      brightGreen: "#7cff7c",
      yellow: "#f2c94c",
      brightYellow: "#fff58a",
      red: "#e5484d",
      brightRed: "#ff6b6b",
      blue: "#3ddc84",
      brightBlue: "#7fe4ff",
      magenta: "#c77dff",
      cyan: "#00d7c3",
      white: "#d4d4d4",
      brightWhite: "#ffffff",
    },
  });

  term.open(el);
  // Handy for debugging from the devtools console.
  window.thecoreTerminal = term;

  if (typeof FitAddon !== "undefined") {
    fitAddon = new FitAddon.FitAddon();
    term.loadAddon(fitAddon);
  }

  // Keystrokes go straight to the pseudo console.
  term.onData((data) => {
    if (opencodeLoaded) API.writeOpencode(data);
  });

  // Resize the child process when the panel changes size.
  if (typeof ResizeObserver !== "undefined") {
    new ResizeObserver(() => fitTerminal()).observe(el);
  }

  return term;
}

function fitTerminal() {
  if (!term) return;
  try {
    if (fitAddon) fitAddon.fit();
    else term.fit();
    API.resizeOpencode(term.cols, term.rows);
  } catch {
    // The terminal may not be laid out yet.
  }
}

function resetTerminal() {
  if (!term) return;
  term.reset();
  term.clear();
}

// Subscribe once — re-subscribing on every LOAD would leak listeners.
API.onOpenCodeOutput((data) => {
  ensureTerminal();
  if (term) term.write(data);
});
API.onOpenCodeStatus((status) => {
  setConsoleStatus(status, "online");
});
API.onOpenCodeDone((code) => {
  opencodeLoaded = false;
  opencodeBusy = false;
  if (code !== 0) {
    setConsoleStatus(`OPENCODE: EXITED (${code})`, "offline");
  }
});

async function startOpencodeConsole() {
  if (!opencodeAvailable) {
    setConsoleStatus("OPENCODE: NOT FOUND", "offline");
    return;
  }

  const cwd = currentProjectId ? await promptProjectPath() : ".";

  // Show whether the console runs with administrator rights.
  try {
    const admin = await API.isAdmin();
    const badge = $("admin-badge");
    if (badge) {
      badge.textContent = admin ? "ADMIN" : "NOT ADMIN";
      badge.dataset.admin = admin ? "true" : "false";
    }
    const adminBtn = $("btn-run-admin");
    if (adminBtn) adminBtn.classList.toggle("hidden", admin);
  } catch {
    // The badge is informational only.
  }

  const t = ensureTerminal();
  if (!t) {
    setConsoleStatus("OPENCODE: TERMINAL UNAVAILABLE", "offline");
    return;
  }
  resetTerminal();
  fitTerminal();

  opencodeLoaded = true;
  opencodeBusy = false;
  loadBtn.textContent = "UNLOAD OPENCODE";
  loadBtn.setAttribute("loaded", "true");
  setConsoleVisible(true);
  setComposerInputVisible(false);
  setConsoleStatus("OPENCODE: STARTING…", "loading");

  API.startOpencode(cwd, t.cols, t.rows);
  t.focus();
}

function promptProjectPath() {
  return ".";
}

// ------------------------------------------------------------------ Ollama chat
modelCombo.addEventListener("change", async () => {
  const entry = selectedModelEntry(modelCombo);
  if (!entry) return;

  if (entry.kind === "cloud") {
    // The provider picker follows the model that was picked.
    cloudProviderId = entry.providerId;
    currentProvider = "cloud";
    providerLabel.textContent = "Cloud LLM";
    providerIconBox.innerHTML = providerIcon("cloud");
    providerDropdown.querySelectorAll(".dropdown-item").forEach((item) => {
      item.classList.toggle("selected", item.dataset.provider === "cloud");
    });
    setStatus(`CLOUD: ${entry.providerName.toUpperCase()}: ${entry.modelId}`, "online");
    // The cloud providers do not report their capabilities.
    modelSupportsTools = false;
    modelSupportsVision = false;
    modelSupportsThinking = false;
    updateCapabilityLabel();
    return;
  }

  currentProvider = "ollama";
  providerLabel.textContent = "Local-LLM";
  providerIconBox.innerHTML = providerIcon("local");
  providerDropdown.querySelectorAll(".dropdown-item").forEach((item) => {
    item.classList.toggle("selected", item.dataset.provider === "ollama");
  });
  setStatus(`OLLAMA: ${entry.modelId}`, "online");
  // The capabilities belong to the model, so they must be re-read.
  await detectCapabilities();
});

/** Show or hide the input box, keeping the provider picker in view. */
function setComposerInputVisible(visible) {
  const box = document.querySelector(".composer-box");
  if (box) box.classList.toggle("hidden", !visible);
}

function sendCurrent() {
  const entry = selectedModelEntry(modelCombo);
  if (entry && entry.kind === "cloud") {
    sendCloudMessage();
  } else {
    sendOllamaMessage();
  }
}

// Enter sends, Shift+Enter makes a new line.
chatInput.addEventListener("keydown", (e) => {
  if (e.key !== "Enter") return;
  if (e.shiftKey) return;
  e.preventDefault();
  if (!chatInput.value.trim()) return;
  sendCurrent();
});

// The action chips pre-fill the input.
document.querySelectorAll(".composer-chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    chatInput.value = "Work through this in several steps and keep me posted: ";
    chatInput.focus();
  });
});

// The dictation and read-aloud buttons.
$("btn-dictate").addEventListener("click", async () => {
  const ok = await API.startDictation();
  setStatus(ok ? "DICTATING…" : "DICTATION NOT AVAILABLE", ok ? "loading" : "offline");
});
$("btn-speak").addEventListener("click", async () => {
  const messages = Array.from(document.querySelectorAll(".message-bubble.assistant"));
  const last = messages[messages.length - 1];
  const text = last ? last.dataset.content || "" : "";
  if (!text.trim()) {
    setStatus("NOTHING TO READ OUT", "offline");
    return;
  }
  const ok = await API.speak(text);
  setStatus(ok ? "READING OUT LOUD" : "SPEECH NOT AVAILABLE", ok ? "online" : "offline");
});

async function sendOllamaMessage() {
  const text = chatInput.value.trim();
  if (!text || ollamaAbortController) return;

  const entry = selectedModelEntry(modelCombo);
  const model = entry && entry.kind === "local" ? entry.modelId : "";
  if (!model) {
    setStatus("OLLAMA: NO MODEL SELECTED", "offline");
    return;
  }

  if (!currentConversationId) {
    // Make sure there is a conversation to attach the messages to.
    if (Sidebar.currentProjectId == null) {
      setStatus("SELECT A PROJECT FIRST", "offline");
      return;
    }
    await Sidebar.createConversation();
    currentConversationId = Sidebar.currentConversationId;
    if (!currentConversationId) {
      setStatus("COULD NOT CREATE A CONVERSATION", "offline");
      return;
    }
  }

  // A brand new conversation takes its name from the first question.
  // The count is taken *before* the message is stored.
  const isFirstQuestion =
    currentConversationId != null &&
    (await API.countMessages(currentConversationId)) === 0;

  // Images attached to this message (vision models only).
  const images = pendingImages.map((image) => image.data);
  pendingImages = [];
  renderImageStrip();

  addMessage("user", text, false);
  chatInput.value = "";
  $("btn-stop").hidden = true;

  const status = createStatusIndicator(model);
  const bubble = addMessage("assistant", "", true);
  ollamaAbortController = new AbortController();

  try {
    const messages = getMessageHistory();
    if (images.length) {
      const last = messages[messages.length - 1];
      if (last && last.role === "user") last.images = images;
    }
    messages.push({ role: "user", content: text });

    // Tools: only for models that advertise the capability.
    const root = await projectRoot();
    let toolDefs = null;
    if (root && modelSupportsTools) {
      toolDefs = await API.toolDefinitions(root);
      messages.unshift({
        role: "system",
        content:
          "You are a coding assistant working inside the project folder. " +
          "You can read, create and edit files and run commands with the tools " +
          "you are given. Use them whenever the task needs it — do not describe " +
          "what you would do, do it. Call several tools at once when they " +
          "belong together. After the tool results come back, continue with " +
          "the task.",
      });
    }

    let accumulated = "";
    const conversation = [...messages];

    for (let round = 0; round <= 8; round++) {
      const isLastRound = round >= 8;
      const resp = await fetch("http://127.0.0.1:11434/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model: model,
          messages: conversation,
          stream: true,
          think: modelSupportsThinking ? true : undefined,
          tools: isLastRound ? undefined : toolDefs || undefined,
        }),
        signal: ollamaAbortController.signal,
      });

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let roundText = "";
      let toolCalls = [];
      let recoveredFromText = false;

      if (isFirstQuestion && round === 0) {
        nameConversation(text);
      }

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        for (const line of chunk.split("\n")) {
          if (!line.trim()) continue;
          try {
            const parsed = JSON.parse(line);
            const thinking = parsed.message?.thinking || "";
            if (thinking) status.addReasoning(thinking);
            const content = parsed.message?.content || "";
            if (content) {
              roundText += content;
              accumulated += content;
              status.addContent(content);
              bubble.segmentView.update(accumulated);
              bubble.dataset.content = accumulated;
              stickToBottom();
            }
            if (parsed.message?.tool_calls?.length) {
              toolCalls.push(...parsed.message.tool_calls);
            }
            if (parsed.done) {
              status.setStats(parsed.eval_count, parsed.eval_duration);
              status.finish(parsed.total_duration, parsed.load_duration);
            }
          } catch {
            // ignore partial JSON
          }
        }
      }

      // Some models print the tool call as plain JSON.
      if (!toolCalls.length && roundText) {
        const recovered = parseToolCalls(roundText);
        if (recovered.length) {
          toolCalls = recovered;
          recoveredFromText = true;
        }
      }

      if (!toolCalls.length || !root) break;

      // Take the printed JSON out of the answer.
      if (recoveredFromText) {
        const cleaned = stripToolCallsFromContent(roundText);
        accumulated = accumulated.slice(0, accumulated.length - roundText.length) + cleaned;
        bubble.segmentView.update(accumulated);
        bubble.dataset.content = accumulated;
      }

      conversation.push({ role: "assistant", content: "", tool_calls: toolCalls });
      for (const call of toolCalls) {
        const fn = call.function || {};
        const name = fn.name;
        const args = fn.arguments || {};
        const result = await API.toolExecute(root, name, args);
        addToolLine(`⚙ ${result.display || name}`);
        conversation.push({ role: "tool", content: result.content, tool_name: name });
      }
    }

    bubble.querySelector(".bubble").classList.remove("temporary");
    addMessageToHistory("assistant", accumulated);
  } catch (e) {
    if (e.name === "AbortError") {
      status.stop();
      return;
    }
    status.fail(e.message);
    bubble.dataset.content = `[ERROR] ${e.message}`;
    bubble.segmentView.update(bubble.dataset.content);
    bubble.querySelector(".bubble").classList.remove("temporary");
  } finally {
    ollamaAbortController = null;
  $("btn-stop").hidden = false;
  }
}

/** Show a tool call as its own line in the chat. */
function addToolLine(text) {
  const line = document.createElement("div");
  line.className = "tool-line";
  line.textContent = text;
  messageContainer.appendChild(line);
  stickToBottom();
}

/** The folder the model may work in: the workspace of the current project. */
async function projectRoot() {
  try {
    const projectId = Sidebar.currentProjectId;
    if (projectId == null) return null;
    const workspaces = (await API.listWorkspaces()) || [];
    const projects = (await API.listProjects(projectId)) || [];
    const project = projects.find((p) => p.id === projectId);
    if (!project) return null;
    const workspace = workspaces.find((w) => w.id === project.workspace_id);
    return workspace && workspace.path ? workspace.path : null;
  } catch {
    return null;
  }
}

// ------------------------------------------------------------------ status indicator
/** In-chat bubble that shows @connecting / @reasoning / @generating. */
function createStatusIndicator(model) {
  const root = document.createElement("div");
  root.className = "status-card";

  const head = document.createElement("div");
  head.className = "status-head";

  const spinner = document.createElement("span");
  spinner.className = "status-spinner";
  spinner.textContent = "◐";

  const title = document.createElement("span");
  title.className = "status-title";
  title.textContent = model ? `@connecting to ${model}` : "@connecting";

  const stats = document.createElement("span");
  stats.className = "status-stats";

  head.appendChild(spinner);
  head.appendChild(title);
  head.appendChild(stats);

  const reason = document.createElement("div");
  reason.className = "status-reason";
  reason.hidden = true;

  root.appendChild(head);
  root.appendChild(reason);
  document.getElementById("message-container").appendChild(root);

  const state = {
    root,
    spinner,
    title,
    stats,
    reason,
    start: Date.now(),
    tokens: 0,
    chars: 0,
    tps: null,
    phase: "connecting",
    reasoning: "",
    spinTimer: null,
  };

  state.spinTimer = setInterval(() => {
    const frames = ["◐", "◓", "◑", "◒"];
    spinner.textContent = frames[Math.floor(Date.now() / 120) % 4];
    render();
  }, 120);

  function render() {
    const elapsed = ((state.end || Date.now()) - state.start) / 1000;
    const parts = [];
    if (state.totalDuration) parts.push(`total ${(state.totalDuration / 1e9).toFixed(2)}s`);
    if (state.loadDuration) parts.push(`load ${(state.loadDuration / 1e9).toFixed(2)}s`);
    parts.push(`${elapsed.toFixed(1)}s`);
    if (state.tokens) parts.push(`${state.tokens} tok`);
    if (state.tps) parts.push(`${state.tps.toFixed(1)} tok/s`);
    stats.textContent = parts.join("  ·  ");
  }

  const api = {
    addReasoning(text) {
      state.reasoning += text;
      reason.textContent = state.reasoning;
      reason.hidden = false;
      if (state.phase === "connecting") api.setPhase("thinking");
      render();
    },
    addContent(text) {
      state.chars += text.length;
      state.tokens = Math.max(state.tokens, Math.round(state.chars / 4));
      if (state.phase === "connecting" || state.phase === "thinking") {
        api.setPhase("generating");
      }
      render();
    },
    setPhase(phase) {
      state.phase = phase;
      root.dataset.state = phase;
      title.textContent =
        phase === "connecting"
          ? model
            ? `@connecting to ${model}`
            : "@connecting"
          : phase === "thinking"
          ? "@reasoning"
          : phase === "generating"
          ? "@generating"
          : phase === "done"
          ? "@done"
          : "@stopped";
    },
    setStats(evalCount, evalDuration) {
      if (evalCount) state.tokens = evalCount;
      if (evalCount && evalDuration) state.tps = evalCount / (evalDuration / 1e9);
      render();
    },
    finish(totalDuration, loadDuration) {
      state.end = Date.now();
      state.totalDuration = totalDuration || 0;
      state.loadDuration = loadDuration || 0;
      api.setPhase("done");
      spinner.textContent = "✔";
      clearInterval(state.spinTimer);
      render();
    },
    fail(reason) {
      state.end = Date.now();
      root.dataset.state = "error";
      title.textContent = `@error — ${reason}`;
      spinner.textContent = "✕";
      stats.textContent = "";
      clearInterval(state.spinTimer);
    },
    stop() {
      state.end = Date.now();
      api.setPhase("stopped");
      spinner.textContent = "■";
      clearInterval(state.spinTimer);
      render();
    },
  };

  return api;
}

btnStop.addEventListener("click", () => {
  if (ollamaAbortController) ollamaAbortController.abort();
  $("btn-stop").hidden = true;
});

// How many lines a folded answer still shows.
const COLLAPSED_LINES = 6;

// ------------------------------------------------------------------ messages
function getMessageHistory() {
  const history = [];
  document.querySelectorAll("#message-container .message-bubble").forEach((el) => {
    const role = el.classList.contains("user") ? "user" : "assistant";
    // The rendered bubble contains code-block chrome, so the raw text is kept
    // separately on the element.
    const content = el.dataset.content ?? el.querySelector(".bubble").textContent;
    history.push({ role, content });
  });
  return history;
}

/** Split a message into text and fenced-code segments. */
function splitSegments(content) {
  const segments = [];
  const textBuf = [];
  const codeBuf = [];
  let lang = "";
  let inCode = false;

  const flushText = () => {
    if (textBuf.length) {
      segments.push({ kind: "text", lang: "", text: textBuf.join("\n") });
      textBuf.length = 0;
    }
  };

  for (const line of content.split("\n")) {
    const trimmed = line.trim();
    if (trimmed.startsWith("```")) {
      if (inCode) {
        segments.push({ kind: "code", lang, text: codeBuf.join("\n") });
        codeBuf.length = 0;
        lang = "";
        inCode = false;
      } else {
        flushText();
        inCode = true;
        lang = trimmed.slice(3).trim();
      }
      continue;
    }
    (inCode ? codeBuf : textBuf).push(line);
  }
  if (inCode) {
    // Still streaming / unterminated block.
    segments.push({ kind: "code", lang, text: codeBuf.join("\n") });
  }
  flushText();
  return segments;
}

/** Renders a message into a bubble, with collapsible code sections. */
function createSegmentView(bubble) {
  let structure = null;
  let nodes = [];

  function buildCodeBlock(segment) {
    const block = document.createElement("div");
    block.className = "code-block";

    const head = document.createElement("div");
    head.className = "code-block-head";

    const toggle = document.createElement("button");
    toggle.className = "code-toggle";
    toggle.type = "button";

    const copy = document.createElement("button");
    copy.className = "code-copy";
    copy.type = "button";
    copy.textContent = "COPY";

    const body = document.createElement("pre");
    body.className = "code-body";
    body.hidden = true;

    let expanded = false;
    const label = () => {
      const lines = body.textContent ? body.textContent.split("\n").length : 0;
      const name = segment.lang ? segment.lang.toUpperCase() : "CODE";
      toggle.textContent = `${expanded ? "▾" : "▸"}  ${name}  ·  ${lines} line${lines === 1 ? "" : "s"}`;
    };

    toggle.addEventListener("click", () => {
      expanded = !expanded;
      body.hidden = !expanded;
      label();
    });
    copy.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(body.textContent);
        copy.textContent = "COPIED";
        setTimeout(() => {
          copy.textContent = "COPY";
        }, 1200);
      } catch {
        // clipboard unavailable — ignore
      }
    });

    head.appendChild(toggle);
    head.appendChild(copy);
    block.appendChild(head);
    block.appendChild(body);
    label();
    return { block, body, label };
  }

  return {
    update(content) {
      const segments = splitSegments(content || "");
      const nextStructure = segments.map((s) => `${s.kind}:${s.lang}`).join("|");

      if (nextStructure !== structure || nodes.length !== segments.length) {
        bubble.innerHTML = "";
        nodes = [];
        for (const segment of segments) {
          if (segment.kind === "code") {
            const node = buildCodeBlock(segment);
            node.body.textContent = segment.text;
            node.label();
            bubble.appendChild(node.block);
            nodes.push(node);
          } else {
            const node = document.createElement("div");
            node.className = "bubble-text";
            node.textContent = segment.text;
            bubble.appendChild(node);
            nodes.push(node);
          }
        }
        structure = nextStructure;
      } else {
        segments.forEach((segment, i) => {
          const node = nodes[i];
          if (!node) return;
          if (segment.kind === "code") {
            if (node.body.textContent !== segment.text) {
              node.body.textContent = segment.text;
              node.label();
            }
          } else {
            node.textContent = segment.text;
          }
        });
      }
    },
  };
}

function addMessage(role, content, temporary = false) {
  const div = document.createElement("div");
  div.className = `message-bubble ${role}`;
  div.dataset.content = content || "";
  const bubble = document.createElement("div");
  bubble.className = `bubble ${role} ${temporary ? "temporary" : ""}`;
  const roleLabel = document.createElement("div");
  roleLabel.className = "role-label";
  roleLabel.textContent = role === "user" ? "YOU" : "ASSISTANT";
  div.appendChild(roleLabel);
  div.appendChild(bubble);
  messageContainer.appendChild(div);
  const view = createSegmentView(bubble);
  view.update(content || "");
  div.segmentView = view;
  stickToBottom();

  // A long answer is folded so the chat stays readable; clicking it shows the
  // whole text.
  if (!temporary && role === "assistant") {
    const lines = (content || "").split("\n");
    if (lines.length > COLLAPSED_LINES) {
      const more = document.createElement("button");
      more.className = "more-button";
      more.textContent = `⋯ ${lines.length - COLLAPSED_LINES} more lines  ·  show all`;
      more.addEventListener("click", () => {
        div.classList.add("expanded");
        more.remove();
        view.update(content || "");
      });
      div.insertBefore(more, bubble);
      div.classList.add("folded");
    }
  }

  // Persist the turn (temporary bubbles are only placeholders).
  if (!temporary && role !== "system") {
    addMessageToHistory(role, content || "");
  }
  return div;
}

// ------------------------------------------------------------------ sidebar
//
// The sidebar itself lives in sidebar.js (workspaces → projects →
// conversations, with delete buttons).  Here we only react to its events.

const Sidebar = window.TheCoreSidebar;

Sidebar.on("conversationSelected", (conversationId) => {
  openConversation(conversationId);
});

Sidebar.on("projectSelected", (projectId) => {
  currentProjectId = projectId;
  updateScope();
});

/** Show which workspace and project the turn belongs to. */
async function updateScope() {
  const combo = $("scope-combo");
  if (!combo) return;
  try {
    if (currentProjectId == null) {
      combo.innerHTML = "<option>This PC</option>";
      return;
    }
    const workspaces = (await API.listWorkspaces()) || [];
    const projects = (await API.listProjects(currentProjectId)) || [];
    const project = projects.find((p) => p.id === currentProjectId);
    const workspace = workspaces.find(
      (w) => w.id === (project ? project.workspace_id : -1)
    );
    const label =
      workspace && project
        ? `${workspace.name} ▸ ${project.name}`
        : project
        ? project.name
        : "This PC";
    combo.innerHTML = `<option>${label}</option>`;
  } catch {
    combo.innerHTML = "<option>This PC</option>";
  }
}

Sidebar.on("projectDeleted", (projectId) => {
  if (currentProjectId === projectId) {
    currentProjectId = null;
    currentConversationId = null;
    clearMessages();
  }
});

Sidebar.on("conversationDeleted", (conversationId) => {
  if (currentConversationId === conversationId) {
    currentConversationId = null;
    clearMessages();
  }
});

/** Load a conversation from the database and show its messages. */
async function openConversation(conversationId) {
  currentConversationId = conversationId;
  clearMessages();
  const messages = (await API.listMessages(conversationId)) || [];
  messages.forEach((m) => addMessage(m.role, m.content, false));
}

/** Remember the conversation that is currently open. */
function addMessageToHistory(role, content) {
  if (currentConversationId == null) return;
  API.addMessage(currentConversationId, role, content).catch((e) =>
    console.error("could not persist message", e)
  );
  API.touchConversation(currentConversationId).catch(() => {});
}

/**
 * Give a new conversation its automatic name.
 *
 * "what is the color of a house mouse" becomes "Mouse" — the subject of the
 * question, not a generic word like "New Conversation".
 */
async function nameConversation(question) {
  if (currentConversationId == null) return;
  const title = titleFromQuestion(question);
  if (!title) return;
  try {
    await API.renameConversation(currentConversationId, title);
  } catch {
    return;
  }
  Sidebar.renameConversation(currentConversationId, title);
}

function clearMessages() {
  messageContainer.innerHTML = "";
}

// ------------------------------------------------------------------ menu actions

API.onMenuNewChat(() => {
  Sidebar.createConversation();
});
API.onMenuNewWorkspace(() => {
  const name = prompt("Workspace name:");
  if (!name) return;
  const wsPath = prompt(
    "Folder for this workspace:",
    "C:\\Users\\Lemo\\Documents\\TheCore"
  );
  if (!wsPath) return;
  API.createWorkspace(name.trim(), wsPath.trim()).then(() => Sidebar.refresh());
});
API.onMenuNewProject(() => {
  const name = prompt("Project name:");
  if (!name) return;
  const workspaceId = Sidebar.currentWorkspaceId;
  if (workspaceId == null) {
    setStatus("CREATE A WORKSPACE FIRST", "offline");
    return;
  }
  API.createProject(workspaceId, name.trim(), "").then(() => Sidebar.refresh());
});
API.onMenuToggleSidebar(() => {
  const sidebar = $("ai-sidebar");
  const expand = $("btn-expand");
  if (sidebar.classList.contains("collapsed")) {
    sidebar.classList.remove("collapsed");
    expand.hidden = true;
  } else {
    sidebar.classList.add("collapsed");
    expand.hidden = false;
  }
});
API.onMenuReload(() => {
  Sidebar.refresh();
  refreshModels();
});
API.onMenuSettings(() => {
  showSettings();
});
API.onMenuAbout(() => {
  alert(
    "CORE\n\nAn AI-powered development environment for Windows.\n" +
      "Code Orchestration & Real-time Engineering."
  );
});

// ------------------------------------------------------------------ cloud provider

let cloudProviders = [];
let cloudProviderId = "";
let cloudModels = [];
// The catalogue: the local models plus every configured cloud model.
let catalogueModels = [];
let catalogueCloudModels = [];

async function initCloud() {
  try {
    cloudProviders = (await API.cloudProviders()) || [];
  } catch {
    cloudProviders = [];
  }
}

/** The provider with this id. */
function currentCloudProvider() {
  return cloudProviders.find((p) => p.id === cloudProviderId) || null;
}

/**
 * Rebuild the model dropdown with the whole catalogue.
 *
 * The local models come first, then the models of every cloud provider that
 * has a key — each labelled with its provider and `● FREE` / `○ PAID`.
 */
function applyCatalogue(kind) {
  const rows = buildCatalogue(catalogueModels, catalogueCloudModels, kind);
  fillModelCombo(modelCombo, rows);
}

/** Ask every configured cloud provider for its models. */
async function refreshCloudModels() {
  try {
    catalogueCloudModels = (await API.cloudCatalogue()) || [];
  } catch {
    catalogueCloudModels = [];
  }
  cloudModels = catalogueCloudModels;
  const kind = currentProvider === "cloud" ? "cloud" : currentProvider === "ollama" ? "local" : null;
  applyCatalogue(kind);
  if (!catalogueCloudModels.length) {
    setStatus("CLOUD: NO MODELS — ADD A KEY IN THE SETTINGS", "offline");
    return;
  }
  const free = catalogueCloudModels.filter((m) => m.free).length;
  setStatus(`CLOUD: ${catalogueCloudModels.length} MODELS (${free} FREE)`, "online");
}

// Subscribe once — re-subscribing on every LOAD would leak listeners.
let cloudReply = "";
let cloudBubble = null;
let cloudStatus = null;
API.onCloudChunk((text) => {
  cloudReply += text;
  if (cloudBubble) {
    cloudBubble.segmentView.update(cloudReply);
    cloudBubble.dataset.content = cloudReply;
    stickToBottom();
  }
});
API.onCloudDone(() => {
  if (cloudStatus) {
    cloudStatus.finish();
    cloudStatus = null;
  }
  if (cloudBubble) {
    cloudBubble.classList.remove("temporary");
  }
  if (cloudReply) {
    addMessageToHistory("assistant", cloudReply);
  }
  cloudReply = "";
  cloudBubble = null;
  $("btn-stop").hidden = false;
});
API.onCloudError((text) => {
  addMessage("system", `CLOUD ERROR: ${text}`, false);
  cloudReply = "";
  cloudBubble = null;
  cloudStatus = null;
  $("btn-stop").hidden = false;
});

/** Send the current chat to the cloud provider of the picked model. */
async function sendCloudMessage() {
  const text = chatInput.value.trim();
  if (!text) return;

  const entry = selectedModelEntry(modelCombo);
  if (!entry || entry.kind !== "cloud") {
    setStatus("CLOUD: NO CLOUD MODEL SELECTED", "offline");
    return;
  }
  const providerId = entry.providerId;
  const model = entry.modelId;

  // A brand new conversation takes its name from the first question.
  const isFirstQuestion =
    currentConversationId != null &&
    (await API.countMessages(currentConversationId)) === 0;

  addMessage("user", text, false);
  chatInput.value = "";
  $("btn-stop").hidden = true;

  cloudStatus = createStatusIndicator(entry.providerName || "Cloud");
  cloudBubble = addMessage("assistant", "", true);
  cloudReply = "";

  if (isFirstQuestion) {
    nameConversation(text);
  }

  const messages = getMessageHistory();
  messages.push({ role: "user", content: text });
  API.cloudChat(providerId, model, messages);
}

// ------------------------------------------------------------------ microphone

const micBtn = $("btn-mic");

/** Refresh the mic button from the real state of the capture endpoints. */
async function refreshMicButton() {
  if (!micBtn) return;
  try {
    const state = await API.micStatus();
    if (state && state.ok) {
      micBtn.textContent = state.muted ? "UNMUTE MICS" : "MUTE MICS";
      micBtn.classList.toggle("muted", Boolean(state.muted));
      micBtn.title = state.message || "";
    } else {
      micBtn.textContent = "NO MICS";
      micBtn.classList.remove("muted");
    }
  } catch {
    micBtn.textContent = "NO MICS";
  }
}

if (micBtn) {
  micBtn.addEventListener("click", async () => {
    micBtn.disabled = true;
    try {
      const result = await API.micToggle();
      if (result && result.message) {
        setConsoleStatus(`OPENCODE: ${result.message}`, result.ok ? "online" : "offline");
      }
    } catch {
      // ignore
    }
    micBtn.disabled = false;
    await refreshMicButton();
  });
  refreshMicButton();
}

// ------------------------------------------------------------------ settings
$("btn-run-admin").addEventListener("click", async () => {
  const btn = $("btn-run-admin");
  btn.disabled = true;
  btn.textContent = "REQUESTING…";
  try {
    const started = await API.relaunchAsAdmin();
    if (!started) {
      btn.disabled = false;
      btn.textContent = "RUN AS ADMIN";
      setConsoleStatus(
        "OPENCODE: UAC DECLINED — RUN AS ADMIN MANUALLY",
        "offline"
      );
    }
  } catch {
    btn.disabled = false;
    btn.textContent = "RUN AS ADMIN";
  }
});

$("setting-text-size").addEventListener("change", (e) => {
  document.documentElement.style.setProperty("--size", e.target.value + "px");
});

$("btn-quit").addEventListener("click", () => {
  API.quitApp();
});

// ------------------------------------------------------------------ init
async function init() {
  initConsoleGrip();
  setupAutoScroll();
  paintProviderIcons();
  Sidebar.init();
  await checkOpenCode();
  await initCloud();
  // The settings page needs the provider list, so its cards are built now.
  buildProviderCards();
  await refreshModels();
  selectProvider("ollama", { skipRefresh: true });
  updateLoadButtonState();
  jumpToFamily("ollama");
  finishSplash();
}

init();
